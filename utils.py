import logging
import platform
import re
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFilter
from PIL import ImageOps

# 透明色；utils 为底层模块，不反向依赖 core 包（避免循环导入）
TRANSPARENT = (0, 0, 0, 0)

logger = logging.getLogger(__name__)

# 优先使用 exiftool（可读取 Makernotes，如 Nikon 单反的 ISO/镜头信息）；
# 未安装时回退到 Pillow 内置 EXIF 读取（基础拍摄信息开箱即用）
_EXIFTOOL_CANDIDATES = [Path('./exiftool.exe'), Path('./exiftool/exiftool.exe')] \
    if platform.system() == 'Windows' else [Path('./exiftool'), Path('./exiftool/exiftool')]
_found = shutil.which('exiftool')
EXIFTOOL_PATH = Path(_found) if _found else next(
    (c for c in _EXIFTOOL_CANDIDATES if c.exists()), None)
EXIFTOOL_AVAILABLE = EXIFTOOL_PATH is not None

EXIFTOOL_DOWNLOAD_PAGE = 'https://exiftool.org/'
# 官网首页解析失败时使用的兜底版本
_EXIFTOOL_FALLBACK_VERSION = '13.59'


def reload_exiftool_path():
    """重新探测 exiftool（自动下载完成后调用）"""
    global EXIFTOOL_PATH, EXIFTOOL_AVAILABLE
    _found = shutil.which('exiftool')
    EXIFTOOL_PATH = Path(_found) if _found else next(
        (c for c in _EXIFTOOL_CANDIDATES if c.exists()), None)
    EXIFTOOL_AVAILABLE = EXIFTOOL_PATH is not None
    return EXIFTOOL_AVAILABLE


def download_exiftool(dest_dir='.') -> Path:
    """
    从 exiftool.org 下载 Windows 版 exiftool 并解压为 dest_dir/exiftool.exe
    :param dest_dir: 目标目录，默认项目根目录
    :return: exe 路径，失败抛异常
    """
    import io
    import urllib.request
    import zipfile

    # 从官网首页解析最新版本号，失败则使用兜底版本
    version = _EXIFTOOL_FALLBACK_VERSION
    try:
        page = urllib.request.urlopen(EXIFTOOL_DOWNLOAD_PAGE, timeout=15).read()
        match = re.search(r'exiftool-(\d+\.\d+)_64\.zip', page.decode('utf-8', errors='ignore'))
        if match:
            version = match.group(1)
    except Exception as e:
        logger.warning(f'解析 exiftool 版本失败，使用兜底版本 {version}：{e}')

    url = f'https://downloads.sourceforge.net/project/exiftool/exiftool-{version}_64.zip'
    logger.info(f'下载 exiftool：{url}')
    data = urllib.request.urlopen(url, timeout=180).read()

    dest_dir = Path(dest_dir)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = zf.namelist()
        # 主程序为 exiftool(-k).exe / exiftool.exe，排除运行时自带的 perl.exe
        main_exe = next((name for name in names
                         if name.lower().endswith('.exe') and 'perl' not in name.lower()), None)
        if main_exe is None:
            raise RuntimeError('压缩包中未找到 exiftool 主程序')
        exe_bytes = zf.read(main_exe)
        # 分体式打包：exiftool_files/ 为 Perl 运行时，必须与主程序同目录；去掉 zip 顶层目录平铺解压
        for name in names:
            if name.endswith('/') or name == main_exe:
                continue
            parts = Path(name).parts
            if len(parts) < 2:
                continue
            target = dest_dir.joinpath(*parts[1:])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(name))

    dest = dest_dir / 'exiftool.exe'
    dest.write_bytes(exe_bytes)
    reload_exiftool_path()
    logger.info(f'exiftool {version} 已就绪：{dest}')
    return dest


def get_file_list(path):
    """
    获取 jpg/png 文件列表
    :param path: 路径
    :return: 文件路径列表
    """
    path = Path(path)
    supported_exts = {'.jpg', '.jpeg', '.png'}
    return sorted(file_path for file_path in path.iterdir()
                  if file_path.is_file() and file_path.suffix.lower() in supported_exts)


def _exiftool_exif(path) -> dict:
    """通过 exiftool 获取 exif 信息"""
    exif_dict = {}
    output_bytes = subprocess.check_output([EXIFTOOL_PATH, '-d', '%Y-%m-%d %H:%M:%S%3f%z', path])
    output = output_bytes.decode('utf-8', errors='ignore')

    for line in output.splitlines():
        # 将每一行按冒号分隔成键值对
        kv_pair = line.split(':')
        if len(kv_pair) < 2:
            continue
        key = kv_pair[0].strip()
        value = ':'.join(kv_pair[1:]).strip()
        # 将键中的空格移除
        key = re.sub(r'\s+', '', key)
        key = re.sub(r'/', '', key)
        # 将键值对添加到字典中
        exif_dict[key] = value
    for key, value in exif_dict.items():
        # 过滤非 ASCII 字符
        value_clean = ''.join(c for c in value if ord(c) < 128)
        # 将处理后的值更新到 exif_dict 中
        exif_dict[key] = value_clean
    return exif_dict


def _tag_str(value) -> str:
    if value is None:
        return ''
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='ignore').replace('\x00', '').strip()
    return str(value).strip()


def _fmt_exposure_time(value) -> str:
    rat = Fraction(int(value.numerator), int(value.denominator))
    if rat >= 1:
        return str(rat.numerator) if rat.denominator == 1 else f'{float(rat):g}'
    return f'1/{round(1 / float(rat))}'


# EXIF Orientation tag 值与原 exiftool 输出的对应关系
_ORIENTATION_NAMES = {1: 'Rotate 0', 3: 'Rotate 180', 6: 'Rotate 90 CW', 8: 'Rotate 270 CW'}


def _pillow_exif(path) -> dict:
    """通过 Pillow 读取 exif 信息，键名与 exiftool 版本保持兼容"""
    exif_dict = {}
    with Image.open(path) as im:
        exif = im.getexif()
        exif_ifd = exif.get_ifd(0x8769)
        gps_ifd = exif.get_ifd(0x8825)

    if _tag_str(exif.get(271)):
        exif_dict['Make'] = _tag_str(exif.get(271))
    if _tag_str(exif.get(272)):
        exif_dict['CameraModelName'] = _tag_str(exif.get(272))
    if _tag_str(exif_ifd.get(42035)):  # 0xA433 LensMake（42032 是 CameraOwnerName）
        exif_dict['LensMake'] = _tag_str(exif_ifd.get(42035))
    if _tag_str(exif_ifd.get(42036)):
        exif_dict['LensModel'] = _tag_str(exif_ifd.get(42036))
    dto = _tag_str(exif_ifd.get(36867))
    if dto:
        # EXIF 原生日期为 "2014:01:01 08:25:54" 冒号格式，dateutil 会丢弃日期部分，
        # 规范化为 "2014-01-01 08:25:54"（与 exiftool -d 的输出格式一致）
        date_part, _, time_part = dto.partition(' ')
        if time_part:
            dto = date_part.replace(':', '-') + ' ' + time_part
        exif_dict['DateTimeOriginal'] = dto

    if exif_ifd.get(37386) is not None:
        exif_dict['FocalLength'] = f'{float(exif_ifd.get(37386)):.1f} mm'
    if exif_ifd.get(41989) is not None:
        exif_dict['FocalLengthIn35mmFormat'] = f'{float(exif_ifd.get(41989)):.1f} mm'
    if exif_ifd.get(33437) is not None:
        exif_dict['FNumber'] = f'{float(exif_ifd.get(33437)):.1f}'
    if exif_ifd.get(33434) is not None:
        exif_dict['ExposureTime'] = _fmt_exposure_time(exif_ifd.get(33434))
    if exif_ifd.get(34855) is not None:  # 0x8827 PhotographicSensitivity，不是十进制 8827
        exif_dict['ISO'] = str(int(exif_ifd.get(34855)))
    if exif.get(274) in _ORIENTATION_NAMES:
        exif_dict['Orientation'] = _ORIENTATION_NAMES[exif.get(274)]

    # GPS：组装成 exiftool 的 GPSPosition 格式 "50 deg 32' 27.72\" N, 13 deg 22' 5.09\" E"
    lat, lat_ref = gps_ifd.get(2), _tag_str(gps_ifd.get(1))
    lon, lon_ref = gps_ifd.get(4), _tag_str(gps_ifd.get(3))

    def _fmt_gps(values, ref):
        deg, minute, sec = (float(v) for v in values)
        return f'{deg:.0f} deg {minute:.0f}\' {sec:.2f}" {ref}'

    try:
        if lat and lon and lat_ref and lon_ref:
            exif_dict['GPSPosition'] = f"{_fmt_gps(lat, lat_ref)}, {_fmt_gps(lon, lon_ref)}"
    except (TypeError, ValueError):
        pass

    return exif_dict


def get_exif(path) -> dict:
    """
    获取exif信息
    :param path: 照片路径
    :return: exif信息
    """
    if EXIFTOOL_AVAILABLE:
        try:
            return _exiftool_exif(path)
        except Exception as e:
            logger.warning(f'exiftool 读取失败，回退到 Pillow：{path} : {e}')
    try:
        return _pillow_exif(path)
    except Exception as e:
        logger.error(f'get_exif error: {path} : {e}')
    return {}


def concatenate_image(images, align='left'):
    """
    将多张图片拼接成一列
    :param images: 图片对象列表
    :param align: 对齐方向，left/center/right
    :return: 拼接后的图片对象
    """
    widths, heights = zip(*(i.size for i in images))

    sum_height = sum(heights)
    max_width = max(widths)

    new_img = Image.new('RGBA', (max_width, sum_height), color=TRANSPARENT)

    x_offset = 0
    y_offset = 0
    if 'left' == align:
        for img in images:
            new_img.paste(img, (0, y_offset))
            y_offset += img.height
    elif 'center' == align:
        for img in images:
            x_offset = int((max_width - img.width) / 2)
            new_img.paste(img, (x_offset, y_offset))
            y_offset += img.height
    elif 'right' == align:
        for img in images:
            x_offset = max_width - img.width  # 右对齐
            new_img.paste(img, (x_offset, y_offset))
            y_offset += img.height
    return new_img


def padding_image(image, padding_size, padding_location='tb', color=TRANSPARENT) -> Image.Image:
    """
    在图片四周填充白色像素
    :param image: 图片对象
    :param padding_size: 填充像素大小
    :param padding_location: 填充位置，top/bottom/left/right
    :return: 填充白色像素后的图片对象
    """
    if image is None:
        return None

    total_width, total_height = image.size
    x_offset, y_offset = 0, 0
    if 't' in padding_location:
        total_height += padding_size
        y_offset += padding_size
    if 'b' in padding_location:
        total_height += padding_size
    if 'l' in padding_location:
        total_width += padding_size
        x_offset += padding_size
    if 'r' in padding_location:
        total_width += padding_size

    padding_img = Image.new('RGBA', (total_width, total_height), color=color)
    padding_img.paste(image, (x_offset, y_offset))
    return padding_img


def square_image(image, auto_close=True) -> Image.Image:
    """
    将图片按照正方形进行填充
    :param auto_close: 是否自动关闭图片对象
    :param image: 图片对象
    :return: 填充后的图片对象
    """
    # 计算图片的宽度和高度
    width, height = image.size
    if width == height:
        return image

    # 计算需要填充的白色区域大小
    delta_w = abs(width - height)
    padding = (delta_w // 2, 0) if width < height else (0, delta_w // 2)

    square_img = ImageOps.expand(image, padding, fill='white')

    if auto_close:
        image.close()

    # 返回正方形图片对象
    return square_img


def resize_image_with_height(image, height, auto_close=True):
    """
    按照高度对图片进行缩放
    :param image: 图片对象
    :param height: 指定高度
    :return: 按照高度缩放后的图片对象
    """
    # 获取原始图片的宽度和高度
    width, old_height = image.size

    # 计算缩放后的宽度
    scale = height / old_height
    new_width = round(width * scale)

    # 进行等比缩放
    resized_image = image.resize((new_width, height), Image.LANCZOS)

    # 关闭图片对象
    if auto_close:
        image.close()

    # 返回缩放后的图片对象
    return resized_image


def resize_image_with_width(image, width, auto_close=True):
    """
    按照宽度对图片进行缩放
    :param image: 图片对象
    :param width: 指定宽度
    :return: 按照宽度缩放后的图片对象
    """
    # 获取原始图片的宽度和高度
    old_width, height = image.size

    # 计算缩放后的宽度
    scale = width / old_width
    new_height = round(height * scale)

    # 进行等比缩放
    resized_image = image.resize((width, new_height), Image.LANCZOS)

    # 关闭图片对象
    if auto_close:
        image.close()

    # 返回缩放后的图片对象
    return resized_image


def append_image_by_side(background, images, side='left', padding=200, is_start=False):
    """
    将图片横向拼接到背景图片中
    :param background: 背景图片对象
    :param images: 图片对象列表
    :param side: 拼接方向，left/right
    :param padding: 图片之间的间距
    :param is_start: 是否在最左侧添加 padding
    :return: 拼接后的图片对象
    """
    if 'right' == side:
        if is_start:
            x_offset = background.width - padding
        else:
            x_offset = background.width
        images.reverse()
        for i in images:
            if i is None:
                continue
            i = resize_image_with_height(i, background.height, auto_close=False)
            x_offset -= i.width
            x_offset -= padding
            background.paste(i, (x_offset, 0))
    else:
        if is_start:
            x_offset = padding
        else:
            x_offset = 0
        for i in images:
            if i is None:
                continue
            i = resize_image_with_height(i, background.height, auto_close=False)
            background.paste(i, (x_offset, 0))
            x_offset += i.width
            x_offset += padding


def text_to_image(content, font, bold_font, is_bold=False, fill='black') -> Image.Image:
    """
    将文字内容转换为图片
    """
    if is_bold:
        font = bold_font
    if content == '':
        content = '   '
    _, _, text_width, text_height = font.getbbox(content)
    image = Image.new('RGBA', (text_width, text_height), color=TRANSPARENT)
    draw = ImageDraw.Draw(image)
    draw.text((0, 0), content, fill=fill, font=font)
    return image


def merge_images(images, axis=0, align=0):
    """
    拼接多张图片
    :param images: 图片对象列表
    :param axis: 0 水平拼接，1 垂直拼接
    :param align: 0 居中对齐，1 底部/右对齐，2 顶部/左对齐
    :return: 拼接后的图片对象
    """
    # 获取每张图像的 size
    widths, heights = zip(*(img.size for img in images))

    # 计算输出图像的尺寸
    if axis == 0:  # 水平拼接
        total_width = sum(widths)
        max_height = max(heights)
    else:  # 垂直拼接
        total_width = max(widths)
        max_height = sum(heights)

    # 创建输出图像
    output_image = Image.new('RGBA', (total_width, max_height), color=TRANSPARENT)

    # 拼接图像
    x_offset, y_offset = 0, 0
    for img in images:
        if axis == 0:  # 水平拼接
            if align == 1:  # 底部对齐
                y_offset = max_height - img.size[1]
            elif align == 2:  # 顶部对齐
                y_offset = 0
            else:  # 居中排列
                y_offset = (max_height - img.size[1]) // 2
            output_image.paste(img, (x_offset, y_offset))
            x_offset += img.size[0]
        else:  # 垂直拼接
            if align == 1:  # 右对齐
                x_offset = total_width - img.size[0]
            elif align == 2:  # 左对齐
                x_offset = 0
            else:  # 居中排列
                x_offset = (total_width - img.size[0]) // 2
            output_image.paste(img, (x_offset, y_offset))
            y_offset += img.size[1]

    return output_image


def calculate_pixel_count(width: int, height: int) -> str:
    # 计算像素总数
    pixel_count = width * height
    # 计算百万像素数
    megapixel_count = pixel_count / 1000000.0
    # 返回结果字符串
    return f"{megapixel_count:.2f} MP"


def extract_attribute(data_dict: dict, *keys, default_value: str = '', prefix='', suffix='') -> str:
    """
    从字典中提取对应键的属性值

    :param data_dict: 包含属性值的字典
    :param keys: 一个或多个键
    :param default_value: 默认值，默认为空字符串
    :return: 对应的属性值或空字符串
    """
    for key in keys:
        if key in data_dict:
            return data_dict[key] + suffix
    return default_value


def extract_gps_lat_and_long(lat: str, long: str):
    # 提取出纬度和经度主要部分
    lat_deg, _, lat_min = re.findall(r"(\d+ deg \d+)", lat)[0].split()
    long_deg, _, long_min = re.findall(r"(\d+ deg \d+)", long)[0].split()

    # 提取出方向（北 / 南 / 东 / 西）
    lat_dir = re.findall(r"([NS])", lat)[0]
    long_dir = re.findall(r"([EW])", long)[0]

    latitude = f"{lat_deg}°{lat_min}'{lat_dir}"
    longitude = f"{long_deg}°{long_min}'{long_dir}"

    return latitude, longitude


def extract_gps_info(gps_info: str):
    lat, long = gps_info.split(", ")
    return extract_gps_lat_and_long(lat, long)


def add_rounded_corners(image, radius):
    """
    为图片添加圆角效果

    :param image: 图片对象
    :param radius: 圆角半径
    :return: 添加圆角后的图片对象
    """
    # 创建一个与原图大小相同的透明背景
    rounded_img = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(rounded_img)

    # 绘制圆角矩形
    draw.rounded_rectangle(
        [(0, 0), image.size],
        radius=radius,
        fill=(255, 255, 255, 255)
    )

    # 如果原图不是RGBA模式，转换为RGBA模式
    if image.mode != "RGBA":
        image = image.convert("RGBA")

    # 将原图与圆角矩形蒙版合并
    rounded_img.paste(image, mask=rounded_img)

    return rounded_img


def add_soft_shadow(image, radius=25, opacity=128):
    """
    为图片四周都添加由内向外逐渐变淡的柔滑黑色阴影效果，以增强层次感

    :param image: 图片对象
    :param radius: 阴影模糊半径，控制阴影的扩散范围和柔和度
    :param opacity: 阴影不透明度 (0-255)
    :return: 添加阴影后的图片对象
    """
    # 创建一个比原图大的透明背景，以容纳四周扩散的阴影
    # 阴影半径的2倍，确保阴影有足够的空间扩散
    shadow_margin = radius * 2
    shadow_width = image.width + shadow_margin * 2
    shadow_height = image.height + shadow_margin * 2
    result = Image.new("RGBA", (shadow_width, shadow_height), (0, 0, 0, 0))

    # 创建阴影层
    shadow_layer = Image.new("RGBA", (shadow_width, shadow_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(shadow_layer)

    # 绘制阴影基础形状（位于中心位置）
    # 不使用偏移，确保阴影均匀分布在四周
    shadow_x = shadow_margin
    shadow_y = shadow_margin
    draw.rectangle(
        [(shadow_x, shadow_y), (shadow_x + image.width, shadow_y + image.height)],
        fill=(0, 0, 0, opacity)
    )

    # 应用高斯模糊使阴影变柔滑并向四周扩散
    # 多次应用模糊可以获得更柔和的效果
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=radius))
    # 再次应用模糊以增强由内向外的渐变效果
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=radius//2))

    # 将阴影层与结果层合并
    result.paste(shadow_layer, (0, 0), shadow_layer)

    # 将原图放置在结果层的中心位置
    result.paste(image, (shadow_margin, shadow_margin), image)

    return result
