# Rust 重写工程笔记

## 体积基线（2026-10-12，本机 `x86_64-pc-windows-msvc`，rustc 1.94.0）

| 产物 | 字节 | 说明 |
|---|---|---|
| Python 版 `dist/Copyleft.exe` | 123,427,746 | PyInstaller onefile，内含 CPython + Qt + qfluentwidgets + 15 MB 字体 + 3.3 MB logo |
| eframe 官方模板 windows exe | 6,676,992 | 参照物，单文件无附带 DLL |
| `copyleft-gui` 空窗口壳（eframe 默认 features） | 13,933,568 | 依赖树里有 `egui-wgpu` + `wgpu` + `naga` |
| `copyleft-gui` 空窗口壳（`default-features = false, features = ["glow","default_fonts"]`） | **7,681,024** | 砍掉 wgpu 后 −6.25 MB；`cargo tree` 里 wgpu/naga 计数为 0 |

结论：GUI 后端必须显式关默认 features。最终 exe 还要内嵌 14.3 MB 字体 + 3.3 MB logo（`include_bytes!` + 首启释放，保持现有 UX），预期落在 25 MB 量级，相对 118 MB 是 4.7 倍缩减。

**空窗口壳只验证了「能编译、体积量级」，没有验证界面渲染**——窗口实际显示效果到计划 C 做出真界面时截图确认。

## 依赖版本约束

- `eframe` 钉 0.35：0.36.2 起 MSRV 要求 rustc 1.95，本机 stable 是 1.94。升 eframe 需要先升工具链（会影响其它项目，未擅自 `rustup update`）。
- `tracing` 是 0.1.x（计划里写的 0.2 不存在）。
- egui 0.34 起字体栅格化后端已从 `ab_glyph` 换成 `skrifa`，所以 0.35 加载 `OTTO`/CFF 的 `.otf` 不受影响。

## 与计划的偏差（执行时按实测调整）

1. `tracing` 是 0.1.x，计划里写的 `tracing = "0.2"` 在 crates.io 上不存在。
2. `eframe` 从计划的 0.36 降到 0.35（0.36.2 要 rustc 1.95），且必须
   `default-features = false, features = ["glow","default_fonts"]`，否则带进 wgpu+naga 白多 6.25 MB。
   另外 0.33 起 `App::update` 改名 `App::ui`，CentralPanel 由框架建。
3. 任务 2 的 `font_padding_level` 计划里写成布尔计数再加 2，两档都为 1 时会算出 4；
   实现改成「越界取 1 否则取原值」再相加，计划文档已同步。
4. kamadak-exif 0.6.1 的实际 API 与计划示例差别很大：没有 `ExifTag`/`InCamera`，
   是 `Tag`/`In`/`Reader`；`In` 只有 PRIMARY/THUMBNAIL，嵌套 IFD 要扫 `fields()`；
   `Rational` 字段名是 `num`/`denom`；没有 `Lens` 常量（Python 那条 `Lens` 查找在标准通道里
   本来也命中不了），所以标准通道只读 `LensModel`，不做增强。
   计划里标记为未证实的假设「kamadak 能不能读 PNG 的 eXIf」实测**可以**，PNG 在它的 README 支持列表里。
5. 任务 4-5 执行时发现两个真问题并已在代码里修掉：
   - `locate()` 原来只按 CWD 找 `./exiftool.exe`，集成测试因此静默退化到内置通道。
     现在除 CWD 外还探 exe 所在目录（Python 靠入口 `os.chdir` 兜，Rust 不隐式改 CWD）。
   - `ImageMeta::load` 原来写死通道，测试无法指定；改成 `load_with(path, eq, &dyn ExifTool)`，
     `load` 只是它的便捷封装。

## 文字后端选型（任务 7-8，探针实测）

**结论：`rustybuzz` 0.20.1 shaping + `skrifa` 0.34 取轮廓 + `tiny-skia` 0.11 直接填充。**
`swash` 备选没启用；`kurbo` 原计划要用作中间路径格式，实测 tiny-skia 的 `PathBuilder`
可以直接接收 skrifa 的 `OutlinePen` 回调，于是整个依赖去掉了。

探针实测数据（`fonts/AlibabaPuHuiTi-2-45-Light.otf`，CFF/OTTO）：轮廓能正常绘制，
"Nikon Z7" 8 个字形产出 75 条路径命令，所以规格 § 12 风险 2（CFF 栅格化失败）没发生。

### 度量取整规则 = ceil

`skrifa::metrics::Metrics::new(font, Size::new(px), location)` 返回的 `ascent`/`descent`
已按字号缩放。Pillow `getmetrics()` 对比：

| 字体 @ 字号 | skrifa raw | 期望(asc,desc) | ceil | round | floor |
|---|---|---|---|---|---|
| PuHuiTi Light @240 | 254.4, -81.6 | (255, 82) | **(255, 82)** | (254, 82) | (254, 81) |
| PuHuiTi Bold @260 | 275.6, -88.4 | (276, 89) | **(276, 89)** | (276, 88) | (275, 88) |
| Roboto Regular @240 | 222.66, -58.59 | (223, 59) | **(223, 59)** | (223, 59) | (222, 58) |
| Roboto Medium @260 | 241.21, -63.48 | (242, 64) | **(242, 64)** | (241, 63) | (241, 63) |

ceil 命中全部 8 个数字，round 只中 5 个、floor 只中 2 个。图内基线用**未取整**的
`ascent`（254.4），只在最后算高度时 ceil——先把基线取整再叠墨迹会整体偏 1 px。

### 与 Pillow 的两个既有差异（规格 § 12 风险 1 的量化）

| 串 | Rust 宽 | Pillow 宽 | 差 |
|---|---|---|---|
| `"Nikon Z7"` Light@240 | 974 | 977 | −0.31% |
| `"Nikon Z7"` Bold@260 | 1123 | 1130 | −0.62% |

原因是 rustybuzz/skrifa 用未提示的推进量，Pillow 用 FreeType 提示后的 per-glyph 进位，
差值随字号增长，所以固定像素阈值不成立，测试改成 **1% 相对容差**（与规格 § 9 的区块
比例容差对齐）。高度方向实测差 1 px（257 vs 258，0.4%），容差定 ±1。
如果计划 B 的整图目视对拍出现可察觉的错位，再考虑 `DrawSettings::hinted`。

## 计划 A 对拍结果（任务 9，2026-10-13）

`bash rust/tests/parity.sh`：5 张样张 × 2 种焦距模式 = 10 组，每组 18 行逐行比对。

| 通道 | 结果 |
|---|---|
| exiftool（`meta --exiftool ../exiftool.exe`） | 10/10 OK |
| Standard（临时把 `exiftool.exe` 移出仓库根后重跑） | 10/10 OK |

过程中查出的三件事，记在这里免得后来人再踩：

1. **行尾差异会伪装成内容差异。** Python 在 Windows 上 `print()` 写 `\r\n`，Rust `println!` 写 `\n`，
   第一版比对每一行都 DIFF。必须 `diff --strip-trailing-cr`。
2. **通道要对齐。** CLI 从 `rust/` 下跑时 `locate()` 找不到仓库根的 `exiftool.exe`，会静默走
   Standard，而 Python 看的是自己的 `EXIFTOOL_AVAILABLE`，两边比的是不同通道。
   解决：`copyleft-cli meta --exiftool <path>` 显式指定，脚本负责传。
3. **「使用等效焦距」在旧版里是死配置。** `image_container.py` 在构造时就把 Param 缓存进
   `_param_dict`，而 `main.py:101` 是构造之后才调 `is_use_equivalent_focal_length()`，
   勾选框从来没效果（实测置标志后仍是 `145.0mm  f/2.8  1/500s  ISO800`）。
   Rust 按语义实时计算，于是 4 组 `--eq` 比对 DIFF。
   **经伙伴决定：两边都修，让勾选生效**——Python 侧 `get_attribute_str` 里 Param 走实时计算。
   影响：新版输出在等效焦距开启时与旧版 Release 不同（多数机型 50mm 会变成 75mm 这类实际差异），
   发布说明要写明；规格 § 1「不改水印文案规则」这条非目标为此开了例外。
