import string

from PIL import Image
from PIL import ImageFilter
from PIL import ImageOps

from .config import Config
from .image_container import ImageContainer
from ..enums.constant import GRAY
from ..enums.constant import TRANSPARENT
from utils import append_image_by_side
from utils import concatenate_image
from utils import merge_images
from utils import padding_image
from utils import resize_image_with_height
from utils import resize_image_with_width
from utils import square_image
from utils import text_to_image
from utils import add_rounded_corners
from utils import add_soft_shadow

printable = set(string.printable)

NORMAL_HEIGHT = 1000
SMALL_HORIZONTAL_GAP = Image.new('RGBA', (50, 20), color=TRANSPARENT)
MIDDLE_HORIZONTAL_GAP = Image.new('RGBA', (100, 20), color=TRANSPARENT)
LARGE_HORIZONTAL_GAP = Image.new('RGBA', (200, 20), color=TRANSPARENT)
SMALL_VERTICAL_GAP = Image.new('RGBA', (20, 50), color=TRANSPARENT)
MIDDLE_VERTICAL_GAP = Image.new('RGBA', (20, 100), color=TRANSPARENT)
LARGE_VERTICAL_GAP = Image.new('RGBA', (20, 200), color=TRANSPARENT)
LINE_GRAY = Image.new('RGBA', (20, 1000), color=GRAY)
LINE_TRANSPARENT = Image.new('RGBA', (20, 1000), color=TRANSPARENT)


class ProcessorComponent:
    """
    图片处理器组件
    """
    LAYOUT_ID = None
    LAYOUT_NAME = None

    def __init__(self, config: Config):
        self.config = config

    def process(self, container: ImageContainer) -> None:
        """
        处理图片容器中的 watermark_img，将处理后的图片放回容器中
        """
        raise NotImplementedError

    def add(self, component):
        raise NotImplementedError


class ProcessorChain(ProcessorComponent):
    def __init__(self):
        super().__init__(None)
        self.components = []

    def add(self, component) -> None:
        self.components.append(component)

    def process(self, container: ImageContainer) -> None:
        for component in self.components:
            component.process(container)


class EmptyProcessor(ProcessorComponent):
    LAYOUT_ID = 'empty'

    def process(self, container: ImageContainer) -> None:
        pass


class ShadowProcessor(ProcessorComponent):
    LAYOUT_ID = 'shadow'

    def process(self, container: ImageContainer) -> None:
        # 加载图像
        image = container.get_watermark_img()

        max_pixel = max(image.width, image.height)
        # 计算阴影边框大小
        radius = int(max_pixel / 512)

        # 创建阴影效果
        shadow = Image.new('RGB', image.size, color='#6B696A')
        shadow = ImageOps.expand(shadow, border=(radius * 2, radius * 2, radius * 2, radius * 2), fill=(255, 255, 255))
        # 模糊阴影
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=radius))

        # 将原始图像放置在阴影图像上方
        shadow.paste(image, (radius, radius))
        container.update_watermark_img(shadow)


class SquareProcessor(ProcessorComponent):
    LAYOUT_ID = 'square'
    LAYOUT_NAME = '1:1填充'

    def process(self, container: ImageContainer) -> None:
        image = container.get_watermark_img()
        container.update_watermark_img(square_image(image, auto_close=False))


class WatermarkProcessor(ProcessorComponent):
    LAYOUT_ID = 'watermark'

    def __init__(self, config: Config):
        super().__init__(config)
        # 默认值
        self.logo_position = 'left'
        self.logo_enable = True
        self.bg_color = '#ffffff'
        self.line_color = GRAY
        self.font_color_lt = '#212121'
        self.bold_font_lt = True
        self.font_color_lb = '#424242'
        self.bold_font_lb = False
        self.font_color_rt = '#212121'
        self.bold_font_rt = True
        self.font_color_rb = '#424242'
        self.bold_font_rb = False

    def is_logo_left(self):
        return self.logo_position == 'left'

    def process(self, container: ImageContainer) -> None:
        """
        生成一个默认布局的水印图片
        :param container: 图片对象
        :return: 添加水印后的图片对象
        """
        config = self.config
        config.bg_color = self.bg_color

        # 下方水印的占比
        ratio = (.04 if container.get_ratio() >= 1 else .09) + 0.02 * config.get_font_padding_level()
        # 水印中上下边缘空白部分的占比
        padding_ratio = (.52 if container.get_ratio() >= 1 else .7) - 0.04 * config.get_font_padding_level()

        # 创建一个空白的水印图片
        watermark = Image.new('RGBA', (int(NORMAL_HEIGHT / ratio), NORMAL_HEIGHT), color=self.bg_color)

        with Image.new('RGBA', (10, 100), color=self.bg_color) as empty_padding:
            # 填充左边的文字内容
            left_top = text_to_image(container.get_attribute_str(config.get_left_top()),
                                     config.get_font(),
                                     config.get_bold_font(),
                                     is_bold=self.bold_font_lt,
                                     fill=self.font_color_lt)
            left_bottom = text_to_image(container.get_attribute_str(config.get_left_bottom()),
                                        config.get_font(),
                                        config.get_bold_font(),
                                        is_bold=self.bold_font_lb,
                                        fill=self.font_color_lb)
            left = concatenate_image([left_top, empty_padding, left_bottom])
            # 填充右边的文字内容
            right_top = text_to_image(container.get_attribute_str(config.get_right_top()),
                                      config.get_font(),
                                      config.get_bold_font(),
                                      is_bold=self.bold_font_rt,
                                      fill=self.font_color_rt)
            right_bottom = text_to_image(container.get_attribute_str(config.get_right_bottom()),
                                         config.get_font(),
                                         config.get_bold_font(),
                                         is_bold=self.bold_font_rb,
                                         fill=self.font_color_rb)
            right = concatenate_image([right_top, empty_padding, right_bottom])

        # 将左右两边的文字内容等比例缩放到相同的高度
        max_height = max(left.height, right.height)
        left = padding_image(left, int(max_height * padding_ratio), 'tb')
        right = padding_image(right, int(max_height * padding_ratio), 't')
        right = padding_image(right, left.height - right.height, 'b')

        logo = config.load_logo(container.make)
        if self.logo_enable:
            if self.is_logo_left():
                # 如果 logo 在左边
                line = LINE_TRANSPARENT.copy()
                logo = padding_image(logo, int(padding_ratio * logo.height))
                append_image_by_side(watermark, [line, logo, left], is_start=logo is None)
                append_image_by_side(watermark, [right], side='right')
            else:
                # 如果 logo 在右边
                if logo is not None:
                    # 如果 logo 不为空，等比例缩小 logo
                    logo = padding_image(logo, int(padding_ratio * logo.height))
                    # 插入一根线条用于分割 logo 和文字
                    line = padding_image(LINE_GRAY, int(padding_ratio * LINE_GRAY.height * .8))
                else:
                    line = LINE_TRANSPARENT.copy()
                append_image_by_side(watermark, [left], is_start=True)
                append_image_by_side(watermark, [logo, line, right], side='right')
                line.close()
        else:
            append_image_by_side(watermark, [left], is_start=True)
            append_image_by_side(watermark, [right], side='right')
        left.close()
        right.close()

        # 缩放水印的大小
        watermark = resize_image_with_width(watermark, container.get_width())
        # 将水印图片放置在原始图片的下方
        bg = ImageOps.expand(container.get_watermark_img().convert('RGBA'),
                             border=(0, 0, 0, watermark.height),
                             fill=self.bg_color)
        fg = ImageOps.expand(watermark, border=(0, container.get_height(), 0, 0), fill=TRANSPARENT)
        result = Image.alpha_composite(bg, fg)
        watermark.close()
        # 更新图片对象
        result = ImageOps.exif_transpose(result).convert('RGB')
        container.update_watermark_img(result)


class WatermarkRightLogoProcessor(WatermarkProcessor):
    LAYOUT_ID = 'watermark_right_logo'
    LAYOUT_NAME = 'normal(Logo 居右)'

    def __init__(self, config: Config):
        super().__init__(config)
        self.logo_position = 'right'


class WatermarkLeftLogoProcessor(WatermarkProcessor):
    LAYOUT_ID = 'watermark_left_logo'
    LAYOUT_NAME = 'normal'

    def __init__(self, config: Config):
        super().__init__(config)
        self.logo_position = 'left'


class DarkWatermarkRightLogoProcessor(WatermarkRightLogoProcessor):
    LAYOUT_ID = 'dark_watermark_right_logo'
    LAYOUT_NAME = 'normal(黑红配色，Logo 居右)'

    def __init__(self, config: Config):
        super().__init__(config)
        self.bg_color = '#212121'
        self.line_color = GRAY
        self.font_color_lt = '#D32F2F'
        self.bold_font_lt = True
        self.font_color_lb = '#d4d1cc'
        self.bold_font_lb = False
        self.font_color_rt = '#D32F2F'
        self.bold_font_rt = True
        self.font_color_rb = '#d4d1cc'
        self.bold_font_rb = False


class DarkWatermarkLeftLogoProcessor(WatermarkLeftLogoProcessor):
    LAYOUT_ID = 'dark_watermark_left_logo'
    LAYOUT_NAME = 'normal(黑红配色)'

    def __init__(self, config: Config):
        super().__init__(config)
        self.bg_color = '#212121'
        self.line_color = GRAY
        self.font_color_lt = '#D32F2F'
        self.bold_font_lt = True
        self.font_color_lb = '#d4d1cc'
        self.bold_font_lb = False
        self.font_color_rt = '#D32F2F'
        self.bold_font_rt = True
        self.font_color_rb = '#d4d1cc'
        self.bold_font_rb = False


class CustomWatermarkProcessor(WatermarkProcessor):
    LAYOUT_ID = 'custom_watermark'
    LAYOUT_NAME = 'normal(自定义配置)'

    def __init__(self, config: Config):
        super().__init__(config)
        # 读取配置文件
        self.logo_position = self.config.is_logo_left()
        self.logo_enable = self.config.has_logo_enabled()
        self.bg_color = self.config.get_background_color()
        self.font_color_lt = self.config.get_left_top().get_color()
        self.bold_font_lt = self.config.get_left_top().is_bold()
        self.font_color_lb = self.config.get_left_bottom().get_color()
        self.bold_font_lb = self.config.get_left_bottom().is_bold()
        self.font_color_rt = self.config.get_right_top().get_color()
        self.bold_font_rt = self.config.get_right_top().is_bold()
        self.font_color_rb = self.config.get_right_bottom().get_color()
        self.bold_font_rb = self.config.get_right_bottom().is_bold()


class MarginProcessor(ProcessorComponent):
    LAYOUT_ID = 'margin'

    def process(self, container: ImageContainer) -> None:
        config = self.config
        padding_size = int(config.get_white_margin_width() * min(container.get_width(), container.get_height()) / 100)
        padding_img = padding_image(container.get_watermark_img(), padding_size, 'tlr', color=config.bg_color)
        container.update_watermark_img(padding_img)


class SimpleProcessor(ProcessorComponent):
    LAYOUT_ID = 'simple'
    LAYOUT_NAME = '简洁'

    def process(self, container: ImageContainer) -> None:
        ratio = .16 if container.get_ratio() >= 1 else .1
        padding_ratio = .5 if container.get_ratio() >= 1 else .5

        first_text = text_to_image('Shot on',
                                   self.config.get_alternative_font(),
                                   self.config.get_alternative_bold_font(),
                                   is_bold=False,
                                   fill='#212121')
        model = text_to_image(container.get_model().replace(r'/', ' ').replace(r'_', ' '),
                              self.config.get_alternative_font(),
                              self.config.get_alternative_bold_font(),
                              is_bold=True,
                              fill='#D32F2F')
        make = text_to_image(container.get_make().split(' ')[0],
                             self.config.get_alternative_font(),
                             self.config.get_alternative_bold_font(),
                             is_bold=True,
                             fill='#212121')
        first_line = merge_images([first_text, MIDDLE_HORIZONTAL_GAP, model, MIDDLE_HORIZONTAL_GAP, make], 0, 1)
        second_line_text = container.get_param_str()
        second_line = text_to_image(second_line_text,
                                    self.config.get_alternative_font(),
                                    self.config.get_alternative_bold_font(),
                                    is_bold=False,
                                    fill='#9E9E9E')
        image = merge_images([first_line, MIDDLE_VERTICAL_GAP, second_line], 1, 0)
        height = container.get_height() * ratio * padding_ratio
        image = resize_image_with_height(image, int(height))
        horizontal_padding = int((container.get_width() - image.width) / 2)
        vertical_padding = int((container.get_height() * ratio - image.height) / 2)

        watermark = ImageOps.expand(image, (horizontal_padding, vertical_padding), fill=TRANSPARENT)
        bg = Image.new('RGBA', watermark.size, color='white')
        bg = Image.alpha_composite(bg, watermark)

        watermark_img = merge_images([container.get_watermark_img(), bg], 1, 1)
        container.update_watermark_img(watermark_img)


class PaddingToOriginalRatioProcessor(ProcessorComponent):
    LAYOUT_ID = 'padding_to_original_ratio'

    def process(self, container: ImageContainer) -> None:
        original_ratio = container.get_original_ratio()
        ratio = container.get_ratio()
        if original_ratio > ratio:
            # 如果原始比例大于当前比例，说明宽度大于高度，需要填充高度
            padding_size = int(container.get_width() / original_ratio - container.get_height())
            padding_img = ImageOps.expand(container.get_watermark_img(), (0, padding_size), fill='white')
        else:
            # 如果原始比例小于当前比例，说明高度大于宽度，需要填充宽度
            padding_size = int(container.get_height() * original_ratio - container.get_width())
            padding_img = ImageOps.expand(container.get_watermark_img(), (padding_size, 0), fill='white')
        container.update_watermark_img(padding_img)


PADDING_PERCENT_IN_BACKGROUND = 0.18
GAUSSIAN_KERNEL_RADIUS = 75


class BackgroundBlurProcessor(ProcessorComponent):
    LAYOUT_ID = 'background_blur'
    LAYOUT_NAME = '背景模糊'

    def process(self, container: ImageContainer) -> None:
        background = container.get_watermark_img()
        background = background.filter(ImageFilter.GaussianBlur(radius=GAUSSIAN_KERNEL_RADIUS))
        fg = Image.new('RGB', background.size, color=(255, 255, 255))
        background = Image.blend(background, fg, 0.1)
        background = background.resize((int(container.get_width() * (1 + PADDING_PERCENT_IN_BACKGROUND)),
                                        int(container.get_height() * (1 + PADDING_PERCENT_IN_BACKGROUND))))
        background.paste(container.get_watermark_img(),
                         (int(container.get_width() * PADDING_PERCENT_IN_BACKGROUND / 2),
                          int(container.get_height() * PADDING_PERCENT_IN_BACKGROUND / 2)))
        container.update_watermark_img(background)


class BackgroundBlurWithWhiteBorderProcessor(ProcessorComponent):
    LAYOUT_ID = 'background_blur_with_white_border'
    LAYOUT_NAME = '背景模糊+白框'

    def process(self, container: ImageContainer) -> None:
        padding_size = int(
            self.config.get_white_margin_width() * min(container.get_width(), container.get_height()) / 256)
        padding_img = padding_image(container.get_watermark_img(), padding_size, 'tblr', color='white')

        background = container.get_img()
        background = background.filter(ImageFilter.GaussianBlur(radius=GAUSSIAN_KERNEL_RADIUS))
        background = background.resize((int(padding_img.width * (1 + PADDING_PERCENT_IN_BACKGROUND)),
                                        int(padding_img.height * (1 + PADDING_PERCENT_IN_BACKGROUND))))
        fg = Image.new('RGB', background.size, color=(255, 255, 255))
        background = Image.blend(background, fg, 0.1)
        background.paste(padding_img, (int(padding_img.width * PADDING_PERCENT_IN_BACKGROUND / 2),
                                       int(padding_img.height * PADDING_PERCENT_IN_BACKGROUND / 2)))
        container.update_watermark_img(background)


class PureWhiteMarginProcessor(ProcessorComponent):
    LAYOUT_ID = 'pure_white_margin'
    LAYOUT_NAME = '白色边框'

    def process(self, container: ImageContainer) -> None:
        config = self.config
        padding_size = int(config.get_white_margin_width() * min(container.get_width(), container.get_height()) / 100)
        padding_img = padding_image(container.get_watermark_img(), padding_size, 'tlrb', color=config.bg_color)
        container.update_watermark_img(padding_img)


class BackgroundBlurWithParamsProcessor(ProcessorComponent):
    LAYOUT_ID = 'background_blur_with_params'
    LAYOUT_NAME = '背景模糊+参数'

    def process(self, container: ImageContainer) -> None:
        # 计算参数区域高度（约为原图高度的8%）
        params_area_height = int(container.get_height() * 0.08)
        
        # 计算总尺寸和留白
        final_width = int(container.get_width() * (1 + PADDING_PERCENT_IN_BACKGROUND))
        final_height = int(container.get_height() * (1 + PADDING_PERCENT_IN_BACKGROUND)) + params_area_height
        total_padding_height = int(container.get_height() * PADDING_PERCENT_IN_BACKGROUND)
        top_padding = total_padding_height // 10  # 上留白约为总留白的1/4
        bottom_padding = total_padding_height - top_padding
        
        # 创建一体化背景模糊图像（包含整个区域）
        # 先创建一个放大的原图作为基础
        enlarged_img = container.get_watermark_img().resize((final_width, final_height), Image.LANCZOS)
        
        # 对整个区域应用模糊效果
        background = enlarged_img.filter(ImageFilter.GaussianBlur(radius=GAUSSIAN_KERNEL_RADIUS))
        fg = Image.new('RGB', background.size, color=(255, 255, 255))
        background = Image.blend(background, fg, 0.1)
        
        # 获取相机名称和参数文本
        model_text = container.get_model()
        param_text = container.get_param_str()
        
        # 创建文本图像（相机名称和参数文本）
        # 相机名称使用粗体，灰白色
        model_image = text_to_image(model_text,
                                    self.config.get_font(),
                                    self.config.get_bold_font(),
                                    is_bold=True,
                                    fill='#F5F5F5')  # 接近纯白的灰白色
        
        # 参数文本使用常规字重，灰白色
        param_image = text_to_image(param_text,
                                    self.config.get_font(),
                                    self.config.get_bold_font(),
                                    is_bold=False,
                                    fill='#F5F5F5')  # 接近纯白的灰白色
        
        # 计算最大允许的文本宽度（原图宽度的3/4）
        max_text_width = int(container.get_width() * 0.75)
        
        # 计算文本区域总高度（相机名称+参数+间距）
        total_text_height = model_image.height + param_image.height + 10
        
        # 计算统一的缩放因子，考虑参数区域高度和最大宽度限制
        if total_text_height > 0:
            # 基于参数区域高度的缩放因子
            height_scale = params_area_height / total_text_height
            
            # 基于最大宽度的缩放因子
            max_text_image_width = max(model_image.width, param_image.width)
            width_scale = max_text_width / max_text_image_width if max_text_image_width > 0 else 1.0
            
            # 取较小的缩放因子以确保同时满足高度和宽度限制
            scale_factor = min(height_scale, width_scale)
            
            # 使用统一的缩放因子对两个文本图像进行缩放
            if model_image.height > 0:
                model_image = model_image.resize((int(model_image.width * scale_factor), 
                                                  int(model_image.height * scale_factor)), 
                                                 Image.LANCZOS)
            
            if param_image.height > 0:
                param_image = param_image.resize((int(param_image.width * scale_factor), 
                                                  int(param_image.height * scale_factor)), 
                                                 Image.LANCZOS)
        
        # 计算文本位置（垂直和水平居中）
        total_text_height = model_image.height + param_image.height + 10  # 10像素间距
        # 在参数区域中垂直居中
        start_y = final_height - params_area_height + (params_area_height - total_text_height) // 2 - top_padding
        
        # 放置相机名称（水平居中）
        model_x = (final_width - model_image.width) // 2
        model_y = start_y
        background.paste(model_image, (model_x, model_y), model_image)
        
        # 放置参数文本（水平居中，在相机名称下方）
        param_x = (final_width - param_image.width) // 2
        param_y = start_y - model_image.height + 10
        background.paste(param_image, (param_x, param_y), param_image)
        
        # 放置原图（在背景模糊图像上方，上移）
        original_img = container.get_watermark_img()
        
        # 为原图添加圆角效果，圆角半径设置为原图宽度的1%
        rounded_radius = int(container.get_width() * 0.01)
        rounded_img = add_rounded_corners(original_img, rounded_radius)
        
        # 为圆角后的原图添加柔滑的黑色阴影效果
        # 阴影参数：模糊半径为50，不透明度为128
        shadow_img = add_soft_shadow(rounded_img, radius=50, opacity=256)
        
        # 计算添加阴影后的原图位置
        # 阴影边缘留出足够空间，确保阴影效果完整显示
        shadow_margin = 50 * 2  # 阴影半径的2倍
        original_x = int(container.get_width() * PADDING_PERCENT_IN_BACKGROUND / 2) - shadow_margin
        original_y = int(container.get_height() * PADDING_PERCENT_IN_BACKGROUND / 2) - top_padding - shadow_margin
        
        # 将带阴影的图片粘贴到背景上
        background.paste(shadow_img, (original_x, original_y), shadow_img)
        
        # 清理资源
        model_image.close()
        param_image.close()
        original_img.close()
        rounded_img.close()
        shadow_img.close()
        enlarged_img.close()
        fg.close()
        
        container.update_watermark_img(background)
