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

## 文字后端选型

（计划 A 任务 7 落地时填写：取整规则、CFF 栅格化实测结果、耗时）

## 计划 A 对拍结果

（计划 A 任务 9 落地时填写：每条 DIFF 的判定）
