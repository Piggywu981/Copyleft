#!/usr/bin/env bash
# 从仓库根 input/ 的真实照片派生测试样张；产物被 .gitignore 排除，重复执行安全。
set -euo pipefail
cd "$(dirname "$0")/../.."
python - <<'PY'
from PIL import Image
from pathlib import Path

src = Path('input/_DSC7969.JPG')
out = Path('rust/fixtures')
out.mkdir(parents=True, exist_ok=True)
im = Image.open(src)
ex = im.getexif()

im.convert('RGB').save(out / 'no_exif.png')          # 无任何 EXIF
if ex:
    im.save(out / 'with_exif.png', exif=ex.tobytes())  # PNG 带 EXIF

# 竖拍样张：像素转置后必须把 Orientation 写成 6，否则等于没测方向交换。
# 注意不能用 exif_transpose（它会把标签清成 1）。
rotated = im.transpose(Image.Transpose.ROTATE_90)
tagged = im.getexif()
tagged[274] = 6
rotated.save(out / 'rotated.jpg', exif=tagged.tobytes())

print('fixtures:', sorted(p.name for p in out.iterdir()))
print('rotated 尺寸:', rotated.width, rotated.height, 'Orientation:', Image.open(out / 'rotated.jpg').getexif().get(274))
PY
