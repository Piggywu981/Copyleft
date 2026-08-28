import logging
import os
import re
from datetime import datetime
from enum import Enum
from pathlib import Path

from PIL import Image
from PIL import ImageOps
from dateutil import parser

from .config import ElementConfig
from ..enums.constant import *
from utils import calculate_pixel_count
from utils import extract_attribute
from utils import extract_gps_info
from utils import extract_gps_lat_and_long
from utils import get_exif

logger = logging.getLogger(__name__)


class ExifId(Enum):
    CAMERA_MODEL = 'CameraModelName'
    CAMERA_MAKE = 'Make'
    LENS_MODEL = ['LensModel', 'Lens', 'LensID']
    LENS_MAKE = 'LensMake'
    DATETIME = 'DateTimeOriginal'
    FOCAL_LENGTH = 'FocalLength'
    FOCAL_LENGTH_IN_35MM_FILM = 'FocalLengthIn35mmFormat'
    F_NUMBER = 'FNumber'
    ISO = 'ISO'
    EXPOSURE_TIME = 'ExposureTime'
    SHUTTER_SPEED_VALUE = 'ShutterSpeedValue'
    ORIENTATION = 'Orientation'


PATTERN = re.compile(r"(\d+(?:\.\d+)?)")  # 匹配数字（含小数）


def get_datetime(exif):
    """解析拍摄时间，无有效 EXIF 时间时返回 None"""
    raw = extract_attribute(exif, ExifId.DATETIME.value)
    if not raw:
        return None
    try:
        return parser.parse(raw)
    except (ValueError, TypeError):
        logger.info(f'Error: 时间格式错误：{raw}')
        return None


def get_focal_length(exif):
    focal_length = DEFAULT_VALUE
    focal_length_in_35mm_film = DEFAULT_VALUE

    try:
        focal_matches = PATTERN.findall(extract_attribute(exif, ExifId.FOCAL_LENGTH.value))
        if focal_matches:
            focal_length = focal_matches[0]
        focal_35mm_matches = PATTERN.findall(extract_attribute(exif, ExifId.FOCAL_LENGTH_IN_35MM_FILM.value))
        if focal_35mm_matches:
            focal_length_in_35mm_film = focal_35mm_matches[0]
    except Exception as e:
        logger.info(f'焦距解析错误：{extract_attribute(exif, ExifId.FOCAL_LENGTH.value)} : {e}')

    return focal_length, focal_length_in_35mm_film


class ImageContainer(object):
    def __init__(self, path: Path):
        self.path: Path = path
        self.target_path: Path | None = None
        self.img: Image.Image = Image.open(path)
        self.exif: dict = get_exif(path)
        # 图像信息
        self.original_width = self.img.width
        self.original_height = self.img.height

        self._param_dict = dict()

        self.model: str = extract_attribute(self.exif, ExifId.CAMERA_MODEL.value)
        self.make: str = extract_attribute(self.exif, ExifId.CAMERA_MAKE.value)
        self.lens_model: str = extract_attribute(self.exif, *ExifId.LENS_MODEL.value)
        self.lens_make: str = extract_attribute(self.exif, ExifId.LENS_MAKE.value)
        self.date: datetime = get_datetime(self.exif)
        if self.date is None:
            # 无 EXIF 时间时使用文件修改时间，避免误显示为处理时刻
            self.date = datetime.fromtimestamp(Path(self.path).stat().st_mtime)
        self.focal_length, self.focal_length_in_35mm_film = get_focal_length(self.exif)
        self.f_number: str = extract_attribute(self.exif, ExifId.F_NUMBER.value, default_value=DEFAULT_VALUE)
        self.exposure_time: str = extract_attribute(self.exif, ExifId.EXPOSURE_TIME.value, default_value=DEFAULT_VALUE,
                                                    suffix='s')
        self.iso: str = extract_attribute(self.exif, ExifId.ISO.value, default_value=DEFAULT_VALUE)

        # 是否使用等效焦距
        self.use_equivalent_focal_length: bool = False

        # 依据 EXIF 方向标签摆正像素（exif_transpose 同时会移除方向标签，防止查看器二次旋转）
        self.img = ImageOps.exif_transpose(self.img)

        # 水印设置
        self.custom = '无'
        self.logo = None

        # 水印图片
        self.watermark_img = None

        self._param_dict[MODEL_VALUE] = self.model
        self._param_dict[PARAM_VALUE] = self.get_param_str()
        self._param_dict[MAKE_VALUE] = self.make
        self._param_dict[DATETIME_VALUE] = self._parse_datetime()
        self._param_dict[DATE_VALUE] = self._parse_date()
        self._param_dict[LENS_VALUE] = self.lens_model
        filename_without_ext = os.path.splitext(self.path.name)[0]
        self._param_dict[FILENAME_VALUE] = filename_without_ext
        self._param_dict[TOTAL_PIXEL_VALUE] = calculate_pixel_count(self.original_width, self.original_height)

        # GPS 信息
        if 'GPSPosition' in self.exif:
            self._param_dict[GEO_INFO_VALUE] = str.join(' ', extract_gps_info(self.exif.get('GPSPosition')))
        elif 'GPSLatitude' in self.exif and 'GPSLongitude' in self.exif:
            self._param_dict[GEO_INFO_VALUE] = str.join(' ', extract_gps_lat_and_long((self.exif.get('GPSLatitude'),
                                                                                       self.exif.get('GPSLongitude'))))
        else:
            self._param_dict[GEO_INFO_VALUE] = '无'

        self._param_dict[CAMERA_MAKE_CAMERA_MODEL_VALUE] = ' '.join(
            [self._param_dict[MAKE_VALUE], self._param_dict[MODEL_VALUE]])
        self._param_dict[LENS_MAKE_LENS_MODEL_VALUE] = ' '.join(
            [self.lens_make, self._param_dict[LENS_VALUE]])
        self._param_dict[CAMERA_MODEL_LENS_MODEL_VALUE] = ' '.join(
            [self._param_dict[MODEL_VALUE], self._param_dict[LENS_VALUE]])
        self._param_dict[DATE_FILENAME_VALUE] = ' '.join(
            [self._param_dict[DATE_VALUE], self._param_dict[FILENAME_VALUE]])
        self._param_dict[DATETIME_FILENAME_VALUE] = ' '.join(
            [self._param_dict[DATETIME_VALUE], self._param_dict[FILENAME_VALUE]])

    def get_height(self):
        return self.get_watermark_img().height

    def get_width(self):
        return self.get_watermark_img().width

    def get_model(self):
        return self.model

    def get_make(self):
        return self.make

    def get_ratio(self):
        return self.img.width / self.img.height

    def get_img(self):
        return self.img

    def _parse_datetime(self) -> str:
        """
        解析日期，转换为指定的格式
        :return: 指定格式的日期字符串，转换失败返回原始的时间字符串
        """
        return datetime.strftime(self.date, '%Y-%m-%d %H:%M')

    def _parse_date(self) -> str:
        """
        解析日期，转换为指定的格式
        :return: 指定格式的日期字符串，转换失败返回原始的时间字符串
        """
        return datetime.strftime(self.date, '%Y-%m-%d')

    def get_attribute_str(self, element: ElementConfig) -> str:
        """
        通过 element 获取属性值
        :param element: element 对象有 name 和 value 两个字段，通过 name 和 value 获取属性值
        :return: 属性值字符串
        """
        if element is None:
            return ''
        name = element.get_name()
        if name in self._param_dict:
            return self._param_dict[name]
        if name == CUSTOM_VALUE:
            self.custom = element.get_value()
            return self.custom
        return ''

    def get_param_str(self) -> str:
        """
        组合拍摄参数，输出一个字符串
        :return: 拍摄参数字符串
        """
        focal_length = self.focal_length_in_35mm_film if self.use_equivalent_focal_length and self.focal_length_in_35mm_film != "--" else self.focal_length
        return '  '.join([str(focal_length) + 'mm', 'f/' + self.f_number, self.exposure_time,
                          'ISO' + str(self.iso)])

    def get_original_height(self):
        return self.original_height

    def get_original_width(self):
        return self.original_width

    def get_original_ratio(self):
        return self.original_width / self.original_height

    def set_logo(self, logo) -> None:
        self.logo = logo

    def is_use_equivalent_focal_length(self, flag: bool) -> None:
        self.use_equivalent_focal_length = flag

    def get_watermark_img(self) -> Image.Image:
        if self.watermark_img is None:
            self.watermark_img = self.img.copy()
        return self.watermark_img

    def update_watermark_img(self, watermark_img) -> None:
        if self.watermark_img == watermark_img:
            return
        original_watermark_img = self.watermark_img
        self.watermark_img = watermark_img
        if original_watermark_img is not None:
            original_watermark_img.close()

    def close(self):
        self.img.close()
        if self.watermark_img is not None:
            self.watermark_img.close()

    def save(self, target_path, quality=100):
        if self.watermark_img.mode != 'RGB':
            self.watermark_img = self.watermark_img.convert('RGB')

        # 方向已烘焙进像素，输出前移除 Orientation 标签，避免查看器二次旋转
        exif_bytes = None
        if 'exif' in self.img.info:
            exif_obj = self.img.getexif()
            exif_obj.pop(0x0112, None)
            exif_bytes = exif_obj.tobytes()

        if exif_bytes:
            self.watermark_img.save(target_path, quality=quality, encoding='utf-8', exif=exif_bytes)
        else:
            self.watermark_img.save(target_path, quality=quality, encoding='utf-8')
