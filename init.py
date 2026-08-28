import logging
from dataclasses import dataclass
from pathlib import Path

from core.entity.config import Config
from core.entity.image_processor import (BackgroundBlurProcessor,
                                         BackgroundBlurWithParamsProcessor,
                                         BackgroundBlurWithWhiteBorderProcessor,
                                         CustomWatermarkProcessor,
                                         DarkWatermarkLeftLogoProcessor,
                                         DarkWatermarkRightLogoProcessor,
                                         MarginProcessor,
                                         PaddingToOriginalRatioProcessor,
                                         ProcessorComponent,
                                         PureWhiteMarginProcessor,
                                         ShadowProcessor,
                                         SimpleProcessor,
                                         SquareProcessor,
                                         WatermarkLeftLogoProcessor,
                                         WatermarkRightLogoProcessor)
from core.enums.constant import (CAMERA_MAKE_CAMERA_MODEL_NAME, CAMERA_MAKE_CAMERA_MODEL_VALUE,
                                 CAMERA_MODEL_LENS_MODEL_NAME, CAMERA_MODEL_LENS_MODEL_VALUE,
                                 CUSTOM_NAME, CUSTOM_VALUE, DATE_FILENAME_NAME, DATE_FILENAME_VALUE,
                                 DATE_NAME, DATE_VALUE, DATETIME_FILENAME_NAME, DATETIME_FILENAME_VALUE,
                                 DATETIME_NAME, DATETIME_VALUE, FILENAME_NAME, FILENAME_VALUE,
                                 GEO_INFO, GEO_INFO_VALUE, LENS_MAKE_LENS_MODEL_NAME,
                                 LENS_MAKE_LENS_MODEL_VALUE, LENS_NAME, LENS_VALUE, MAKE_NAME,
                                 MAKE_VALUE, MODEL_NAME, MODEL_VALUE, NONE_NAME, NONE_VALUE,
                                 PARAM_NAME, PARAM_VALUE, TOTAL_PIXEL_NAME, TOTAL_PIXEL_VALUE)

# 如果 logs 不存在，创建 logs
Path('./logs').mkdir(parents=True, exist_ok=True)

# 格式化日志输出
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# 添加一个 FileHandler 处理器，将 INFO 级别日志写入 ./logs/info.log 文件中
info_handler = logging.FileHandler('./logs/info.log', mode='a', encoding='utf-8')
info_handler.setLevel(logging.INFO)
info_handler.setFormatter(formatter)

# 添加一个 FileHandler 处理器，将 ERROR 级别日志写入 ./logs/error.log 文件中
error_handler = logging.FileHandler('./logs/error.log', mode='a', encoding='utf-8')
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(formatter)

# 添加一个 FileHandler 处理器，将 DEBUG 级别日志写入 ./logs/all.log 文件中
debug_handler = logging.FileHandler('./logs/all.log', mode='a', encoding='utf-8')
debug_handler.setLevel(logging.DEBUG)
debug_handler.setFormatter(formatter)

# 设置日志输出的格式和级别，并将日志输出到指定文件中
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[debug_handler, info_handler, error_handler])


@dataclass
class ElementItem(object):
    name: str
    value: str


@dataclass
class LayoutItem(object):
    name: str
    value: str
    processor: ProcessorComponent

    @staticmethod
    def from_processor(processor: ProcessorComponent):
        return LayoutItem(processor.LAYOUT_NAME, processor.LAYOUT_ID, processor)


# 读取配置
config = Config('config.yaml')

WATERMARK_LEFT_LOGO_PROCESSOR = WatermarkLeftLogoProcessor(config)
WATERMARK_RIGHT_LOGO_PROCESSOR = WatermarkRightLogoProcessor(config)
MARGIN_PROCESSOR = MarginProcessor(config)
SHADOW_PROCESSOR = ShadowProcessor(config)
SQUARE_PROCESSOR = SquareProcessor(config)
SIMPLE_PROCESSOR = SimpleProcessor(config)
PADDING_TO_ORIGINAL_RATIO_PROCESSOR = PaddingToOriginalRatioProcessor(config)
BACKGROUND_BLUR_PROCESSOR = BackgroundBlurProcessor(config)
BACKGROUND_BLUR_WITH_WHITE_BORDER_PROCESSOR = BackgroundBlurWithWhiteBorderProcessor(config)
BACKGROUND_BLUR_WITH_PARAMS_PROCESSOR = BackgroundBlurWithParamsProcessor(config)
PURE_WHITE_MARGIN_PROCESSOR = PureWhiteMarginProcessor(config)

# 所有可选布局，GUI 布局下拉框和处理器链构建均基于此列表
LAYOUT_ITEMS = [
    LayoutItem.from_processor(WATERMARK_LEFT_LOGO_PROCESSOR),
    LayoutItem.from_processor(WATERMARK_RIGHT_LOGO_PROCESSOR),
    LayoutItem.from_processor(DarkWatermarkLeftLogoProcessor(config)),
    LayoutItem.from_processor(DarkWatermarkRightLogoProcessor(config)),
    LayoutItem.from_processor(CustomWatermarkProcessor(config)),
    LayoutItem.from_processor(SQUARE_PROCESSOR),
    LayoutItem.from_processor(SIMPLE_PROCESSOR),
    LayoutItem.from_processor(BACKGROUND_BLUR_PROCESSOR),
    LayoutItem.from_processor(BACKGROUND_BLUR_WITH_WHITE_BORDER_PROCESSOR),
    LayoutItem.from_processor(BACKGROUND_BLUR_WITH_PARAMS_PROCESSOR),
    LayoutItem.from_processor(PURE_WHITE_MARGIN_PROCESSOR),
]
layout_items_dict = {item.value: item for item in LAYOUT_ITEMS}

# 四个角落文字位置可以使用的文字选项
ITEM_LIST = [
    ElementItem(MODEL_NAME, MODEL_VALUE),
    ElementItem(MAKE_NAME, MAKE_VALUE),
    ElementItem(LENS_NAME, LENS_VALUE),
    ElementItem(PARAM_NAME, PARAM_VALUE),
    ElementItem(DATETIME_NAME, DATETIME_VALUE),
    ElementItem(DATE_NAME, DATE_VALUE),
    ElementItem(CUSTOM_NAME, CUSTOM_VALUE),
    ElementItem(NONE_NAME, NONE_VALUE),
    ElementItem(LENS_MAKE_LENS_MODEL_NAME, LENS_MAKE_LENS_MODEL_VALUE),
    ElementItem(CAMERA_MODEL_LENS_MODEL_NAME, CAMERA_MODEL_LENS_MODEL_VALUE),
    ElementItem(TOTAL_PIXEL_NAME, TOTAL_PIXEL_VALUE),
    ElementItem(CAMERA_MAKE_CAMERA_MODEL_NAME, CAMERA_MAKE_CAMERA_MODEL_VALUE),
    ElementItem(FILENAME_NAME, FILENAME_VALUE),
    ElementItem(DATE_FILENAME_NAME, DATE_FILENAME_VALUE),
    ElementItem(DATETIME_FILENAME_NAME, DATETIME_FILENAME_VALUE),
    ElementItem(GEO_INFO, GEO_INFO_VALUE),
]
