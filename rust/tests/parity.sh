#!/usr/bin/env bash
# 逐张样张对拍 16 个文字项：Rust 与 Python 的输出必须逐行一致。
#
# exiftool 在场时比的是 Exiftool 通道；把仓库根的 exiftool.exe 临时改名后
# 再跑一轮，比的是 Standard 通道。两种都要零 DIFF 才算过计划 A 的闸门。
#
# 注意：本脚本只做文本比对，不比像素。像素级对拍在计划 B。
set -uo pipefail
cd "$(dirname "$0")/../.."

photos=(
  input/_DSC7969.JPG
  input/_DSC7976.JPG
  rust/fixtures/with_exif.png
  rust/fixtures/rotated.jpg
  rust/fixtures/no_exif.png
)

fail=0
# 通道对齐：CLI 的 CWD 在 rust/ 下，默认探测找不到仓库根的 exiftool.exe，
# 所以显式把路径传进去，保证 Rust 与 Python 走同一条通道。
EXIFT=""
if [ -f ./exiftool.exe ]; then EXIFT="--exiftool ../exiftool.exe"; fi
# 先编一次：编译错误只报一遍，而不是每张样张重复一遍
(cd rust && cargo build -q -p copyleft-cli) || { echo "copyleft-cli 编译失败"; exit 1; }
for p in "${photos[@]}"; do
  if [ ! -f "$p" ]; then
    echo "SKIP $p（不存在，先跑 bash rust/fixtures/make.sh）"
    continue
  fi
  for eq in "" "--eq"; do
    tag="${eq:-non-eq}"
    (cd rust && cargo run -q -p copyleft-cli -- meta "../$p" $eq $EXIFT) > "/tmp/r_${tag}.txt" 2>/tmp/r_err.txt
    if [ ! -s "/tmp/r_${tag}.txt" ]; then
      echo "FAIL $p $tag — Rust 端没输出：$(head -2 /tmp/r_err.txt)"
      fail=1
      continue
    fi
    python rust/tests/exif_parity.py "$p" $eq > "/tmp/p_${tag}.txt" 2>/tmp/p_err.txt
    if [ ! -s "/tmp/p_${tag}.txt" ]; then
      echo "FAIL $p $tag — Python 端没输出：$(head -2 /tmp/p_err.txt)"
      fail=1
      continue
    fi
    # 第一行的 source 表示两边各走了哪条通道，不一致就是编排漂移了
    rsrc=$(head -1 "/tmp/r_${tag}.txt"); psrc=$(head -1 "/tmp/p_${tag}.txt")
    # --strip-trailing-cr：Python 在 Windows 上 print() 会写 \r\n，Rust 的
    # println! 只写 \n，不忽略行尾的话每一行都会被判成不同。
    if diff -q --strip-trailing-cr "/tmp/p_${tag}.txt" "/tmp/r_${tag}.txt" > /dev/null; then
      echo "OK   $p $tag [$psrc]"
    else
      echo "DIFF $p $tag [py:$psrc rs:$rsrc]"
      diff -u --strip-trailing-cr "/tmp/p_${tag}.txt" "/tmp/r_${tag}.txt" | sed -n '1,20p'
      fail=1
    fi
  done
done
exit $fail
