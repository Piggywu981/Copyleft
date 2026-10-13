#!/usr/bin/env bash
# 逐张样张对拍 16 个文字项：Rust 与 Python 的输出必须逐行一致。
#
# Python 实现现在在 legacy-python 分支上，所以基准树用 PY_ROOT 指定：
#   PY_ROOT=/path/to/legacy-python bash rust/tests/parity.sh
# 在 legacy-python 检出里直接跑也行（那边 core/ 就在当前目录）。
#
# exiftool 在场时比的是 Exiftool 通道；把 exiftool.exe 临时移出基准树再跑一轮，
# 比的是 Standard 通道。两种都要零 DIFF 才算过计划 A 的闸门。
#
# 注意：本脚本只做文本比对，不比像素。像素级对拍在计划 B。
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"

if [ -n "${PY_ROOT:-}" ]; then
  :
elif [ -f "$ROOT/core/entity/image_container.py" ]; then
  PY_ROOT="$ROOT"
else
  echo "找不到 Python 基准树（需要 core/entity/image_container.py）。"
  echo "main 分支上已经没有 Python 实现，请指一份 legacy-python 的检出："
  echo "  git worktree add ../legacy-python legacy-python"
  echo "  PY_ROOT=../legacy-python bash rust/tests/parity.sh"
  echo "Rust 引擎自身的行为由 cargo test 覆盖（断言取的正是 Python 实测值）。"
  exit 0
fi

if [ ! -f "$PY_ROOT/core/entity/image_container.py" ]; then
  echo "PY_ROOT=$PY_ROOT 里没有 Python 实现，检查路径"
  exit 1
fi

photos=(
  "$ROOT/input/_DSC7969.JPG"
  "$ROOT/input/_DSC7976.JPG"
  "$ROOT/rust/fixtures/with_exif.png"
  "$ROOT/rust/fixtures/rotated.jpg"
  "$ROOT/rust/fixtures/no_exif.png"
)

fail=0
# 通道对齐：CLI 从 rust/ 下跑时默认探测找不到仓库根的 exiftool.exe，会静默走
# Standard，而 Python 看的是自己的 EXIFTOOL_AVAILABLE。显式把两边钉到同一个二进制。
EXIFT=""
BIN="$ROOT/exiftool.exe"
[ -f "$BIN" ] || BIN="$PY_ROOT/exiftool.exe"
if [ -f "$BIN" ]; then
  EXIFT="--exiftool $BIN"
  BIN_DIR="$(cd "$(dirname "$BIN")" && pwd)"
fi

(cd "$ROOT/rust" && cargo build -q -p copyleft-cli) || { echo "copyleft-cli 编译失败"; exit 1; }

for p in "${photos[@]}"; do
  if [ ! -f "$p" ]; then
    echo "SKIP $p（不存在，先跑 bash rust/fixtures/make.sh）"
    continue
  fi
  for eq in "" "--eq"; do
    tag="${eq:-non-eq}"
    (cd "$ROOT/rust" && cargo run -q -p copyleft-cli -- meta "$p" $eq $EXIFT) > "/tmp/r_${tag}.txt" 2>/tmp/r_err.txt
    if [ ! -s "/tmp/r_${tag}.txt" ]; then
      echo "FAIL $p $tag — Rust 端没输出：$(head -2 /tmp/r_err.txt)"
      fail=1
      continue
    fi
    # Python 侧靠 PATH 或当前目录找 exiftool，基准树里没有那个 gitignored
    # 的二进制，所以把它所在目录塞进 PATH，保证两边同一条通道。
    PATH="${BIN_DIR:-$PATH}:$PATH" PY_ROOT="$PY_ROOT" python "$HERE/exif_parity.py" "$p" $eq > "/tmp/p_${tag}.txt" 2>/tmp/p_err.txt
    if [ ! -s "/tmp/p_${tag}.txt" ]; then
      echo "FAIL $p $tag — Python 端没输出：$(head -2 /tmp/p_err.txt)"
      fail=1
      continue
    fi
    psrc=$(head -1 "/tmp/p_${tag}.txt"); rsrc=$(head -1 "/tmp/r_${tag}.txt")
    # --strip-trailing-cr：Python 在 Windows 上 print() 写 \r\n，Rust 的
    # println! 只写 \n，不忽略行尾的话每一行都会被判成不同。
    if diff -q --strip-trailing-cr "/tmp/p_${tag}.txt" "/tmp/r_${tag}.txt" > /dev/null; then
      echo "OK   $(basename "$p") $tag [$psrc]"
    else
      echo "DIFF $(basename "$p") $tag [py:$psrc rs:$rsrc]"
      diff -u --strip-trailing-cr "/tmp/p_${tag}.txt" "/tmp/r_${tag}.txt" | sed -n '1,20p'
      fail=1
    fi
  done
done
exit $fail
