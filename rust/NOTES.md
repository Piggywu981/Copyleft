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

## 文字后端选型

（计划 A 任务 7 落地时填写：取整规则、CFF 栅格化实测结果、耗时）

## 计划 A 对拍结果

（计划 A 任务 9 落地时填写：每条 DIFF 的判定）
