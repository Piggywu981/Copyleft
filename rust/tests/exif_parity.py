"""打印 Python 版的 16 个文字项，供与 copyleft-cli meta 逐行 diff。

用法：
  PY_ROOT=/path/to/legacy-python-检出 python rust/tests/exif_parity.py <photo> [--eq]
不带 PY_ROOT 时假定 Python 实现就在本检出里（在 legacy-python 分支上直接跑的情形）。

输出格式与 Rust 侧刻意保持一致：裸值 + tab，不加任何一方的 repr，
否则每一行都会因为引号风格不同而 diff 失败。
"""
import os
import sys
from pathlib import Path

PY_ROOT = os.environ.get("PY_ROOT") or str(Path(__file__).resolve().parents[2])
sys.path.insert(0, PY_ROOT)
os.chdir(PY_ROOT)  # config.yaml / exiftool.exe 都按相对路径找

import utils  # noqa: E402
from core.entity.config import ElementConfig  # noqa: E402
from core.entity.image_container import ImageContainer  # noqa: E402
from init import ITEM_LIST  # noqa: E402

# utils._ORIENTATION_NAMES 的反向表；exiftool 对 1 还会打印 "Horizontal (normal)"
_ORIENT = {
    'Rotate 0': 1,
    'Horizontal (normal)': 1,
    'Rotate 180': 3,
    'Rotate 90 CW': 6,
    'Rotate 270 CW': 8,
}


def main() -> int:
    photo = Path(sys.argv[1])
    eq = '--eq' in sys.argv
    ic = ImageContainer(photo)
    ic.is_use_equivalent_focal_length(eq)
    print(f"source\t{'Exiftool' if utils.EXIFTOOL_AVAILABLE else 'Standard'}")
    orient = _ORIENT.get(ic.exif.get('Orientation', 'Rotate 0'), 1)
    print(f"size\t{ic.img.width}x{ic.img.height}\torientation\t{orient}")
    # get_attribute_str 要的是 ElementConfig，不是裸 dict（它会调 element.get_name()）
    element = ElementConfig({'name': None, 'is_bold': False, 'value': '自定义文字'})
    for item in ITEM_LIST:
        element.element['name'] = item.value
        print(f"{item.value}\t{ic.get_attribute_str(element)}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
