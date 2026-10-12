# Copyleft Rust 重写 · 计划 A：引擎地基（骨架 + EXIF + 文字）

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 建好 `rust/` workspace 骨架，实现「读 EXIF → 产出 16 个文字项 → 把一行文字渲染成 RGBA 位图」，直到与 Python 版逐行对拍一致。

**架构：** 三 crate 分工——`copyleft-core`（无 GUI 依赖的引擎库）、`copyleft-cli`（观测与对拍工具）、`copyleft-gui`（本计划只放一个能编译运行的空窗口壳，用于实测体积）。EXIF 两个通道（exiftool 子进程 / kamadak-exif）都归一化到同一个 `ExifFacts`，下游只认 `ExifFacts`。文字走 `rustybuzz` shaping + `skrifa` 轮廓 + `tiny-skia` 填充，度量以 Pillow `getmetrics()` 的实测值为验收线。

**技术栈：** Rust edition 2021、`image` 0.25、`kamadak-exif` 0.6、`rustybuzz` + `skrifa` + `tiny-skia` + `kurbo`、`serde` + `serde_yaml` 0.9、`serde_json`、`thiserror`、`clap` 4、`eframe`（壳）、`python3` + Pillow（对拍基准）。

**规格：** `docs/superpowers/specs/2026-10-12-rust-refactor-design.md`。本计划覆盖 § 2、§ 4、§ 6、§ 7、§ 7.1、§ 9 的相应部分；§ 5（布局）在计划 B，§ 8（GUI）与 § 10（CI）在计划 C。

**拆分说明：** 阶段 1 含四个可独立验收的子系统，各写一份计划：
- **计划 A（本文件）**：骨架 + config + EXIF + 文字渲染 + 文字项对拍。
- **计划 B**：`imageops` + 布局处理器 + EXIF 写出（`exif/tiff.rs`）+ 整图对拍闸门。
- **计划 C**：GUI + 并发批处理 + exiftool 自动下载 + 首启资源释放 + CI。
A 的产出（`ImageMeta` 与文字位图尺寸）是 B 留白计算的输入。

**基准数据：** 附录 A 是 2026-10-12 在本机 `input/_DSC7969.JPG` 上实测的 Python 侧输出，所有断言以它为准。**若某张样张换了，先重跑附录 A 的采集命令更新数字，再动 Rust。**

---

## 文件结构

| 文件 | 职责 | 建立于 |
|---|---|---|
| `rust/Cargo.toml` | workspace + `[workspace.dependencies]` | 任务 1 |
| `rust/crates/copyleft-core/src/lib.rs` | 模块声明 | 任务 1 |
| `rust/crates/copyleft-core/src/keys.rs` | `LayoutId` / `ComponentId` / `TextKey` 字符串互转 | 任务 1 |
| `rust/crates/copyleft-core/src/error.rs` | `CoreError` | 任务 1，后续增补变体 |
| `rust/crates/copyleft-core/src/test_support.rs` | 样张路径辅助 | 任务 1 |
| `rust/crates/copyleft-core/src/config.rs` | `config.yaml` 读写 + 默认值钳制 | 任务 2 |
| `rust/crates/copyleft-core/src/exif/facts.rs` | `ExifFacts` + `format_exposure` | 任务 3 |
| `rust/crates/copyleft-core/src/exif/standard.rs` | kamadak-exif 通道 | 任务 3 |
| `rust/crates/copyleft-core/src/exif/tool.rs` | exiftool 子进程通道 | 任务 4 |
| `rust/crates/copyleft-core/src/exif/mod.rs` | 通道编排 + 回退 | 任务 5 |
| `rust/crates/copyleft-core/src/meta.rs` | `ImageMeta` → 16 文字项 | 任务 6 |
| `rust/crates/copyleft-core/src/text/store.rs` | 字体加载 + 度量 | 任务 7 |
| `rust/crates/copyleft-core/src/text/mod.rs` | `render_line` → `RgbaImage` | 任务 8 |
| `rust/crates/copyleft-cli/src/main.rs` | `meta` / `text` 子命令 | 任务 9 |
| `rust/crates/copyleft-gui/src/main.rs` | 空窗口壳（体积实测） | 任务 1，计划 C 替换 |
| `rust/fixtures/make.sh` | 派生样张脚本 | 任务 3 |
| `rust/tests/exif_parity.py` | Python 侧 16 文字项基准 | 任务 9 |
| `rust/NOTES.md` | 体积基线、选型结论、对拍结果 | 任务 1 |
| `utils.py:163-164,184-185` | 修两处 EXIF tag 数字 | 任务 3 |

`copyleft-core` 不依赖 egui；`copyleft-gui` 除窗口壳外不含任何图像处理代码。

---

## 任务 1：workspace 与 crate 骨架

**文件：**
- 创建：`rust/Cargo.toml`、`rust/NOTES.md`、`rust/crates/copyleft-core/Cargo.toml`、`rust/crates/copyleft-core/src/{lib.rs,keys.rs,error.rs,test_support.rs,config.rs,meta.rs,imageops.rs}`、`rust/crates/copyleft-core/src/exif/mod.rs`、`rust/crates/copyleft-core/src/text/mod.rs`、`rust/crates/copyleft-core/src/layout/mod.rs`、`rust/crates/copyleft-core/tests/keys.rs`、`rust/crates/copyleft-cli/Cargo.toml`、`rust/crates/copyleft-cli/src/main.rs`、`rust/crates/copyleft-gui/Cargo.toml`、`rust/crates/copyleft-gui/src/main.rs`
- 修改：`.gitignore`

- [ ] **步骤 1：workspace manifest**

`rust/Cargo.toml`（`[workspace.dependencies]` 里 `kamadak-exif` 只登记一次，用 `package` 改名；写两行会让 TOML 报重复键）：

```toml
[workspace]
resolver = "2"
members = ["crates/copyleft-core", "crates/copyleft-cli", "crates/copyleft-gui"]

[workspace.package]
version = "2.6.0"
edition = "2021"

[workspace.dependencies]
copyleft-core = { path = "crates/copyleft-core" }
image = "0.25"
thiserror = "2"
serde = { version = "1", features = ["derive"] }
serde_yaml = "0.9"
serde_json = "1"
exif = { package = "kamadak-exif", version = "0.6" }
rustybuzz = "0.20"
skrifa = "0.34"
tiny-skia = "0.11"
kurbo = "0.11"
regex = "1"
chrono = { version = "0.4", default-features = false, features = ["std", "clock"] }
clap = { version = "4", features = ["derive"] }
tracing = "0.2"
which = "7"

[profile.release]
opt-level = 3
lto = "fat"
codegen-units = 1
strip = true
```

不加 `panic = "abort"`：批处理里 `std::panic::catch_unwind` 是「单张图失败不中断整批」的兜底手段（计划 C 用），abort 会让它失效。

- [ ] **步骤 2：三个 crate 的 `Cargo.toml`**

```toml
# crates/copyleft-core/Cargo.toml
[package]
name = "copyleft-core"
version.workspace = true
edition.workspace = true

[dependencies]
image = { workspace = true }
thiserror = { workspace = true }
serde = { workspace = true }
serde_yaml = { workspace = true }
serde_json = { workspace = true }
exif = { workspace = true }
rustybuzz = { workspace = true }
skrifa = { workspace = true }
tiny-skia = { workspace = true }
kurbo = { workspace = true }
regex = { workspace = true }
chrono = { workspace = true }
tracing = { workspace = true }
which = { workspace = true }
```

`copyleft-cli` 依赖 `copyleft-core`、`clap`、`image`；`copyleft-gui` 依赖 `copyleft-core` 与 `eframe`（`default-features = false, features = ["glow", "default_fonts", "winit"]`，glow 而非 wgpu 以减小体积）。

- [ ] **步骤 3：`keys.rs`（三张字符串表）**

`TextKey::as_str()` 的返回值必须与 `config.yaml` 里 `layout.elements.*.name` 的取值逐字一致，写错就是「旧配置读出来全是空文字」。

```rust
// rust/crates/copyleft-core/src/keys.rs
use std::fmt;

/// 用户可选的 11 个布局 id，顺序与 init.py 的 LAYOUT_ITEMS 一致。
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum LayoutId {
    WatermarkLeftLogo, WatermarkRightLogo, DarkWatermarkLeftLogo, DarkWatermarkRightLogo,
    CustomWatermark, Square, Simple, BackgroundBlur, BackgroundBlurWithWhiteBorder,
    BackgroundBlurWithParams, PureWhiteMargin,
}

/// 链上非用户可选的组件，对应 Python 里只有 LAYOUT_ID 的处理器。
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum ComponentId { Empty, Shadow, Margin, PaddingToOriginalRatio }

/// 四角文字 16 个可选项，对应 core/enums/constant.py 的 16 个 *_VALUE。
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum TextKey {
    Model, Make, LensModel, Param, Datetime, Date, Custom, None,
    LensMakeLensModel, CameraModelLensModel, TotalPixel, CameraMakeCameraModel,
    Filename, DateFilename, DatetimeFilename, GeoInfo,
}

impl LayoutId {
    pub const ALL: [LayoutId; 11] = [
        LayoutId::WatermarkLeftLogo, LayoutId::WatermarkRightLogo,
        LayoutId::DarkWatermarkLeftLogo, LayoutId::DarkWatermarkRightLogo,
        LayoutId::CustomWatermark, LayoutId::Square, LayoutId::Simple,
        LayoutId::BackgroundBlur, LayoutId::BackgroundBlurWithWhiteBorder,
        LayoutId::BackgroundBlurWithParams, LayoutId::PureWhiteMargin,
    ];

    pub fn as_str(self) -> &'static str {
        match self {
            LayoutId::WatermarkLeftLogo => "watermark_left_logo",
            LayoutId::WatermarkRightLogo => "watermark_right_logo",
            LayoutId::DarkWatermarkLeftLogo => "dark_watermark_left_logo",
            LayoutId::DarkWatermarkRightLogo => "dark_watermark_right_logo",
            LayoutId::CustomWatermark => "custom_watermark",
            LayoutId::Square => "square",
            LayoutId::Simple => "simple",
            LayoutId::BackgroundBlur => "background_blur",
            LayoutId::BackgroundBlurWithWhiteBorder => "background_blur_with_white_border",
            LayoutId::BackgroundBlurWithParams => "background_blur_with_params",
            LayoutId::PureWhiteMargin => "pure_white_margin",
        }
    }

    /// 计划 A/B 结束时可用的 id；GUI 下拉据此显示禁用占位（规格 § 8）。
    pub fn is_available(self) -> bool {
        matches!(self, LayoutId::WatermarkLeftLogo | LayoutId::WatermarkRightLogo
            | LayoutId::DarkWatermarkLeftLogo | LayoutId::DarkWatermarkRightLogo
            | LayoutId::CustomWatermark | LayoutId::PureWhiteMargin)
    }

    pub fn parse(s: &str) -> Option<LayoutId> {
        LayoutId::ALL.into_iter().find(|id| id.as_str() == s)
    }
}

impl ComponentId {
    pub fn as_str(self) -> &'static str {
        match self {
            ComponentId::Empty => "empty",
            ComponentId::Shadow => "shadow",
            ComponentId::Margin => "margin",
            ComponentId::PaddingToOriginalRatio => "padding_to_original_ratio",
        }
    }
}

impl TextKey {
    pub const ALL: [TextKey; 16] = [
        TextKey::Model, TextKey::Make, TextKey::LensModel, TextKey::Param,
        TextKey::Datetime, TextKey::Date, TextKey::Custom, TextKey::None,
        TextKey::LensMakeLensModel, TextKey::CameraModelLensModel, TextKey::TotalPixel,
        TextKey::CameraMakeCameraModel, TextKey::Filename, TextKey::DateFilename,
        TextKey::DatetimeFilename, TextKey::GeoInfo,
    ];

    pub fn as_str(self) -> &'static str {
        match self {
            TextKey::Model => "Model",
            TextKey::Make => "Make",
            TextKey::LensModel => "LensModel",
            TextKey::Param => "Param",
            TextKey::Datetime => "Datetime",
            TextKey::Date => "Date",
            TextKey::Custom => "Custom",
            TextKey::None => "None",
            TextKey::LensMakeLensModel => "LensMake_LensModel",
            TextKey::CameraModelLensModel => "CameraModel_LensModel",
            TextKey::TotalPixel => "TotalPixel",
            TextKey::CameraMakeCameraModel => "CameraMake_CameraModel",
            TextKey::Filename => "Filename",
            TextKey::DateFilename => "Date_Filename",
            TextKey::DatetimeFilename => "Datetime_Filename",
            TextKey::GeoInfo => "GeoInfo",
        }
    }

    pub fn parse(s: &str) -> Option<TextKey> {
        TextKey::ALL.into_iter().find(|k| k.as_str() == s)
    }

    /// GUI 下拉显示名，逐字取自 core/enums/constant.py 的 *_NAME。
    pub fn display_name(self) -> &'static str {
        match self {
            TextKey::Model => "相机型号(eg. Nikon Z7)",
            TextKey::Make => "相机厂商(eg. Nikon)",
            TextKey::LensModel => "镜头型号(eg. Nikkor 24-70 f/2.8)",
            TextKey::Param => "拍摄参数(eg. 50mm f/1.8 1/1000s ISO 100)",
            TextKey::Datetime => "拍摄时间(eg. 2023-01-01 12:00)",
            TextKey::Date => "拍摄日期(eg. 2023-01-01)",
            TextKey::Custom => "自定义",
            TextKey::None => " ",
            TextKey::LensMakeLensModel => "镜头厂商 + 镜头型号(eg. Nikon Nikkor 24-70 f/2.8)",
            TextKey::CameraModelLensModel => "相机型号 + 镜头型号(eg. Nikon Z7 Nikkor 24-70 f/2.8)",
            TextKey::TotalPixel => "总像素(MP)",
            TextKey::CameraMakeCameraModel => "相机厂商 + 相机型号(eg. DJI FC123)",
            TextKey::Filename => "文件名",
            TextKey::DateFilename => "日期 + 文件名(eg. 2023-01-01 DXO_0001)",
            TextKey::DatetimeFilename => "日期时间 + 文件名(eg. 2023-01-01 12:00 DXO_0001)",
            TextKey::GeoInfo => "地理信息",
        }
    }
}

impl fmt::Display for LayoutId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result { f.write_str(self.as_str()) }
}
impl fmt::Display for TextKey {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result { f.write_str(self.as_str()) }
}
```

- [ ] **步骤 4：`error.rs` 与 `test_support.rs`**

```rust
// rust/crates/copyleft-core/src/error.rs
use crate::keys::LayoutId;

#[derive(Debug, thiserror::Error)]
pub enum CoreError {
    #[error("打开图片失败 {path}: {source}")]
    ImageOpen { path: String, #[source] source: image::ImageError },

    #[error("EXIF 读取失败 {path}: {reason}")]
    Exif { path: String, reason: String },

    #[error("调用 exiftool 失败 {bin}: {reason}")]
    ExiftoolRun { bin: String, reason: String },

    #[error("字体读取失败 {path}: {reason}")]
    Font { path: String, reason: String },

    #[error("布局 {0} 要到计划 B 才可用")]
    LayoutNotAvailable(LayoutId),

    #[error(transparent)]
    Io(#[from] std::io::Error),

    #[error("{0}")]
    Other(String),
}

pub type Result<T> = std::result::Result<T, CoreError>;
```

`Exif` 变体需要一个能装任意原因的构造helper：加 `impl CoreError { pub fn exif(path: &std::path::Path, reason: impl std::fmt::Display) -> Self { Self::Exif { path: path.display().to_string(), reason: reason.to_string() } } }`，后续任务都用它，避免每处手写 `display().to_string()`。

```rust
// rust/crates/copyleft-core/src/test_support.rs
use std::path::{Path, PathBuf};

pub fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../..")
}

pub fn fixture(name: &str) -> PathBuf {
    let p = repo_root().join("rust/fixtures").join(name);
    assert!(p.exists(), "缺 {name}，先跑 bash rust/fixtures/make.sh");
    p
}

pub fn photo(name: &str) -> PathBuf {
    let p = repo_root().join("input").join(name);
    assert!(p.exists(), "仓库 input/ 下没有 {name}");
    p
}

pub fn font(name: &str) -> PathBuf { repo_root().join("fonts").join(name) }
```

`lib.rs` 声明模块：

```rust
pub mod config;
pub mod error;
pub mod exif;
pub mod imageops;
pub mod keys;
pub mod layout;
pub mod meta;
pub mod test_support;
pub mod text;
```

任务 1 只实现 `keys`、`error`、`test_support`；`config.rs`、`meta.rs`、`imageops.rs`、`exif/mod.rs`、`text/mod.rs`、`layout/mod.rs` 先建成空文件（`lib.rs` 引用它们，空文件即可编译）。空文件在各自任务里填内容，不预留 `todo!()` 或假类型。

- [ ] **步骤 5：CLI 与 GUI 壳**

`copyleft-cli/src/main.rs`（任务 9 换成真实子命令）：

```rust
fn main() -> std::process::ExitCode {
    eprintln!("copyleft-cli: 子命令在计划 A 任务 9 落地");
    std::process::ExitCode::from(2)
}
```

`copyleft-gui/src/main.rs`（体积实测用壳，计划 C 整体替换）：

```rust
//! 空窗口壳：只为量出 Rust 产物的真实体积，不含任何图像处理。
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() -> eframe::Result {
    eframe::run_native(
        "Copyleft",
        eframe::NativeOptions::default(),
        Box::new(|_cc| Ok(Box::new(App))),
    )
}

struct App;

impl eframe::App for App {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        egui::CentralPanel::default().show(ctx, |ui| {
            ui.heading("Copyleft 骨架");
        });
    }
}
```

- [ ] **步骤 6：写 `keys.rs` 的测试**

`copyleft-core/tests/keys.rs`：

```rust
use copyleft_core::keys::{ComponentId, LayoutId, TextKey};

#[test]
fn layout_ids_match_python_constants() {
    let expected = [
        "watermark_left_logo", "watermark_right_logo",
        "dark_watermark_left_logo", "dark_watermark_right_logo", "custom_watermark",
        "square", "simple", "background_blur",
        "background_blur_with_white_border", "background_blur_with_params",
        "pure_white_margin",
    ];
    let got: Vec<&str> = LayoutId::ALL.iter().map(|id| id.as_str()).collect();
    assert_eq!(got, expected.to_vec());
    for s in expected { assert!(LayoutId::parse(s).is_some(), "{s} 解析不出"); }
    assert_eq!(LayoutId::parse("nope"), None);
}

#[test]
fn text_keys_are_unique_and_roundtrip() {
    let strs: Vec<&str> = TextKey::ALL.iter().map(|k| k.as_str()).collect();
    let uniq: std::collections::HashSet<&str> = strs.iter().copied().collect();
    assert_eq!(uniq.len(), 16, "as_str 有重复：{strs:?}");
    for s in &strs { assert_eq!(TextKey::parse(s).unwrap().as_str(), *s); }
    assert_eq!(TextKey::None.display_name(), " ", "constant.py 里 NONE_NAME 是一个空格");
}

#[test]
fn availability_is_six_layouts() {
    let ok: Vec<&str> = LayoutId::ALL.iter().filter(|id| id.is_available())
        .map(|id| id.as_str()).collect();
    assert_eq!(ok.len(), 6, "只应放开 6 个 id，实际 {ok:?}");
    assert!(!LayoutId::Simple.is_available());
    assert_eq!(ComponentId::Shadow.as_str(), "shadow");
}
```

- [ ] **步骤 7：跑测试**

运行：`cd rust && cargo test -p copyleft-core --test keys`
预期：三个测试 PASS（步骤 4 的空文件建好后）。若 `lib.rs` 报 `expected item, found EOF`，说明某个空 `.rs` 文件没被 `touch` 出来。

- [ ] **步骤 8：`.gitignore` + 体积基线**

根 `.gitignore` 追加：

```
rust/target/
rust/fixtures/*.png
rust/fixtures/*.jpg
rust/fixtures/*.json
```

运行：`cd rust && cargo build --release -p copyleft-gui && ls -l --block-size=1 target/release/copyleft-gui.exe | awk '{print $5}'`
预期：3,000,000–15,000,000 之间（eframe 官方模板实测 6,676,992）。若 >15 MB，先查是否落进 wgpu 后端。

把数字写进新建的 `rust/NOTES.md`：

```markdown
# Rust 重写工程笔记

## 体积基线
- Python 版 `dist/Copyleft.exe`：123,427,746 字节（PyInstaller onefile，含 15 MB 字体 + 3.3 MB logo）
- eframe 官方模板 windows exe：6,676,992 字节（参照物）
- 本仓库空窗口壳 `copyleft-gui`：<填入实测字节数>，日期 2026-10-12
```

- [ ] **步骤 9：fmt / clippy / commit**

```bash
cd rust && cargo fmt && cargo clippy --all-targets -- -D warnings && cargo test
git add rust .gitignore
git commit -m "feat(rust): 建 workspace 骨架与 keys/error 地基

11 个布局 id、16 个文字项与 constant.py 逐字对齐；空窗口壳用来量
Rust 产物的真实体积基线，直接验证重写的第一个诉求。"
```

---

## 任务 2：`config.rs`（config.yaml 零改动兼容）

**文件：**
- 修改：`rust/crates/copyleft-core/src/config.rs`（填任务 1 的空文件）
- 创建：`rust/crates/copyleft-core/tests/config.rs`
- 读取（不修改）：`config.yaml`

- [ ] **步骤 1：写失败的测试**

`tests/config.rs`（`CARGO_MANIFEST_DIR` = `rust/crates/copyleft-core`，仓库根上溯三级）：

```rust
use copyleft_core::config::{Config, Slot};
use copyleft_core::keys::TextKey;

#[test]
fn loads_real_config_yaml() {
    let cfg = Config::load(copyleft_core::test_support::repo_root().join("config.yaml")).unwrap();
    assert_eq!(cfg.layout_type(), copyleft_core::keys::LayoutId::CustomWatermark);
    assert_eq!(cfg.quality(), 100);
    assert_eq!(cfg.slot_name(Slot::LeftTop), TextKey::Model);
    assert_eq!(cfg.slot_name(Slot::LeftBottom), TextKey::Param);
    assert_eq!(cfg.slot_name(Slot::RightTop), TextKey::Custom);
    assert_eq!(cfg.slot_name(Slot::RightBottom), TextKey::Datetime);
    assert_eq!(cfg.custom_text(), "PiggyWu©");
    assert_eq!(cfg.font_size_px(), 240);
    assert_eq!(cfg.bold_font_size_px(), 260);
    assert_eq!(cfg.font_padding_level(), 2);
    assert!(cfg.logo_enabled());
    assert!(cfg.is_logo_left());
    assert_eq!(cfg.background_color(), "#ffffff");
    assert_eq!(cfg.white_margin_width(), 3);
    assert!(!cfg.shadow_enabled());
    assert!(cfg.use_equivalent_focal_length());
}

#[test]
fn every_element_name_in_config_is_a_known_text_key() {
    let raw = std::fs::read_to_string(copyleft_core::test_support::repo_root().join("config.yaml")).unwrap();
    for line in raw.lines().filter(|l| l.trim_start().starts_with("name:")) {
        let v = line.split(':').nth(1).unwrap().trim().trim_matches('\'');
        assert!(TextKey::parse(v).is_some(), "config.yaml 里的 name {v:?} 不在 TextKey 表内");
    }
}

#[test]
fn normalizes_null_and_out_of_range_like_python() {
    let dir = std::env::temp_dir().join("copyleft_cfg_null");
    std::fs::create_dir_all(&dir).unwrap();
    let path = dir.join("c.yaml");
    std::fs::write(&path, r#"
base: {font_size: 9, bold_font_size: 9, quality: 100, font: a, bold_font: b,
       alternative_font: c, alternative_bold_font: d, input_dir: ./input, output_dir: ./output}
global:
  focal_length: {use_equivalent_focal_length: false}
  padding_with_original_ratio: {enable: false}
  shadow: {enable: false}
  white_margin: {enable: false, width: 99}
layout:
  elements:
    left_top: {is_bold: true, name: null}
    left_bottom: {is_bold: false, name: 'null'}
    right_top: {is_bold: true, name: Param}
    right_bottom: {is_bold: false, name: Whatever}
  logo_enable: true
  logo_position: right
  type: null
logo: {default: {id: '', path: ./logos/empty.png}, makes: {}}
"#).unwrap();
    let cfg = Config::load(&path).unwrap();
    assert_eq!(cfg.layout_type().as_str(), "watermark_left_logo", "type: null 回落默认布局");
    assert_eq!(cfg.slot_name(Slot::LeftTop), TextKey::None);
    assert_eq!(cfg.slot_name(Slot::RightBottom), TextKey::None);
    assert_eq!(cfg.font_size_px(), 240);
    assert_eq!(cfg.bold_font_size_px(), 260);
    assert_eq!(cfg.white_margin_width(), 30, "width 钳到上限 30");
    assert_eq!(cfg.font_padding_level(), 2, "越界档位在 padding level 里按 1 算");
    assert!(!cfg.is_logo_left());
    assert_eq!(cfg.background_color(), "#ffffff");
}
```

- [ ] **步骤 2：跑测试验证失败**

运行：`cd rust && cargo test -p copyleft-core --test config`
预期：编译失败 `could not find Config in config`。

- [ ] **步骤 3：实现 `config.rs`**

要点：`name`/`type` 存成 `Option<String>`，在访问器里做 Python 同款归一化；嵌套 map 用 `BTreeMap` 保住 `yaml.dump` 的字母序；`#[serde(flatten)]` 兜住未知顶层键。

```rust
// rust/crates/copyleft-core/src/config.rs
use std::collections::BTreeMap;
use std::path::Path;

use serde::{Deserialize, Serialize};

use crate::error::{CoreError, Result};
use crate::keys::{LayoutId, TextKey};

pub const DEFAULT_LAYOUT: LayoutId = LayoutId::WatermarkLeftLogo;
pub const DEFAULT_COLOR: &str = "#ffffff";
pub const ELEMENT_COLOR_FALLBACK: &str = "#212121";

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Slot { LeftTop, LeftBottom, RightTop, RightBottom }

pub const ALL_SLOTS: [Slot; 4] = [Slot::LeftTop, Slot::RightTop, Slot::LeftBottom, Slot::RightBottom];

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Element {
    pub is_bold: bool,
    #[serde(default)] pub color: Option<String>,
    #[serde(default)] pub name: Option<String>,
    #[serde(default)] pub value: Option<String>,
}

impl Element {
    pub fn color(&self) -> &str { self.color.as_deref().unwrap_or(ELEMENT_COLOR_FALLBACK) }
    pub fn is_bold(&self) -> bool { self.is_bold }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Layout {
    #[serde(default, rename = "type")] pub layout_type: Option<String>,
    #[serde(default)] pub background_color: Option<String>,
    #[serde(default)] pub logo_enable: bool,
    #[serde(default)] pub logo_position: Option<String>,
    pub elements: BTreeMap<Slot, Element>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Base {
    pub font: String, pub bold_font: String,
    pub alternative_font: String, pub alternative_bold_font: String,
    pub font_size: u8, pub bold_font_size: u8,
    pub input_dir: String, pub output_dir: String, pub quality: u8,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Flag { #[serde(default)] pub enable: bool }

/// global.focal_length 的字段名与其它 Flag 不同。
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct FocalLength { #[serde(default)] pub use_equivalent_focal_length: bool }

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct WhiteMargin { #[serde(default)] pub enable: bool, #[serde(default)] pub width: i32 }

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Global {
    pub focal_length: FocalLength,
    pub padding_with_original_ratio: Flag,
    pub shadow: Flag,
    pub white_margin: WhiteMargin,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct LogoEntry { #[serde(default)] pub id: String, pub path: String }

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Logo { pub default: LogoEntry, pub makes: BTreeMap<String, LogoEntry> }

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Config {
    pub base: Base,
    pub global: Global,
    pub layout: Layout,
    pub logo: Logo,
    #[serde(flatten, default)] pub extra: BTreeMap<String, serde_yaml::Value>,
}

impl Config {
    pub fn load(path: impl AsRef<Path>) -> Result<Config> {
        let p = path.as_ref();
        let text = std::fs::read_to_string(p)
            .map_err(|e| CoreError::Other(format!("读取配置失败 {}: {e}", p.display())))?;
        serde_yaml::from_str(&text)
            .map_err(|e| CoreError::Other(format!("解析配置失败 {}: {e}", p.display())))
    }

    pub fn save(&self, path: impl AsRef<Path>) -> Result<()> {
        let p = path.as_ref();
        let text = serde_yaml::to_string(self)
            .map_err(|e| CoreError::Other(format!("序列化配置失败: {e}")))?;
        std::fs::write(p, text).map_err(|e| CoreError::Other(format!("写入配置失败 {}: {e}", p.display())))
    }

    /// config.py: get_layout_type()——None 与字面量 "null" 都回落默认布局
    pub fn layout_type(&self) -> LayoutId {
        self.layout.layout_type.as_deref()
            .filter(|s| *s != "null")
            .and_then(LayoutId::parse)
            .unwrap_or(DEFAULT_LAYOUT)
    }

    /// config.py: get_element_name()
    pub fn slot_name(&self, slot: Slot) -> TextKey {
        self.layout.elements.get(&slot).and_then(|e| e.name.as_deref())
            .filter(|s| *s != "null")
            .and_then(TextKey::parse)
            .unwrap_or(TextKey::None)
    }

    pub fn element(&self, slot: Slot) -> Option<&Element> { self.layout.elements.get(&slot) }

    /// main.py: _initial_custom_text()——取第一个 Custom 槽位的 value
    pub fn custom_text(&self) -> String {
        ALL_SLOTS.into_iter()
            .filter(|s| self.slot_name(*s) == TextKey::Custom)
            .find_map(|s| self.layout.elements.get(&s).and_then(|e| e.value.clone()))
            .unwrap_or_default()
    }

    /// config.py: set_custom_text()——更新所有 Custom 槽位
    pub fn set_custom_text(&mut self, value: &str) {
        for slot in ALL_SLOTS {
            if let Some(e) = self.layout.elements.get_mut(&slot) {
                if e.name.as_deref() == Some("Custom") { e.value = Some(value.to_owned()) }
            }
        }
    }

    /// config.py: set_element_name() + set_custom()
    pub fn set_element_name(&mut self, slot: Slot, key: TextKey) {
        let Some(e) = self.layout.elements.get_mut(&slot) else { return };
        if key == TextKey::Custom {
            e.name = Some("Custom".into());
            e.value.get_or_insert_with(String::new);
        } else {
            e.name = Some(key.as_str().to_owned());
        }
    }

    pub fn set_layout(&mut self, id: LayoutId) { self.layout.layout_type = Some(id.as_str().to_owned()) }

    /// config.py: get_font_size()——越界一律回落 240
    pub fn font_size_px(&self) -> u32 { match self.base.font_size { 2 => 250, 3 => 300, _ => 240 } }
    /// config.py: get_bold_font_size()——越界回落 260
    pub fn bold_font_size_px(&self) -> u32 { match self.base.bold_font_size { 2 => 290, 3 => 320, _ => 260 } }

    /// config.py: get_font_padding_level()——两档各自钳到 1..=3 后求和
    pub fn font_padding_level(&self) -> u32 {
        let clamp = |v: u8| u32::from((1..=3).contains(&v));
        clamp(self.base.bold_font_size) + clamp(self.base.font_size) + 2
    }

    /// config.py: get_white_margin_width()
    pub fn white_margin_width(&self) -> i32 { self.global.white_margin.width.clamp(0, 30) }
    pub fn set_white_margin_width(&mut self, w: i32) { self.global.white_margin.width = w; }

    pub fn quality(&self) -> u8 { self.base.quality }
    pub fn set_quality(&mut self, q: u8) { self.base.quality = q }
    pub fn background_color(&self) -> String {
        self.layout.background_color.clone().unwrap_or_else(|| DEFAULT_COLOR.to_owned())
    }
    pub fn set_background_color(&mut self, c: &str) { self.layout.background_color = Some(c.to_owned()) }

    pub fn logo_enabled(&self) -> bool { self.layout.logo_enable }
    pub fn set_logo_enabled(&mut self, on: bool) { self.layout.logo_enable = on }
    pub fn is_logo_left(&self) -> bool { self.layout.logo_position.as_deref() == Some("left") }
    pub fn set_logo_left(&mut self) { self.layout.logo_position = Some("left".into()) }
    pub fn set_logo_right(&mut self) { self.layout.logo_position = Some("right".into()) }

    pub fn use_equivalent_focal_length(&self) -> bool { self.global.focal_length.use_equivalent_focal_length }
    pub fn set_use_equivalent_focal_length(&mut self, on: bool) { self.global.focal_length.use_equivalent_focal_length = on }
    pub fn shadow_enabled(&self) -> bool { self.global.shadow.enable }
    pub fn set_shadow(&mut self, on: bool) { self.global.shadow.enable = on }
    pub fn white_margin_enabled(&self) -> bool { self.global.white_margin.enable }
    pub fn set_white_margin(&mut self, on: bool) { self.global.white_margin.enable = on }
    pub fn padding_with_original_ratio_enabled(&self) -> bool { self.global.padding_with_original_ratio.enable }
    pub fn set_padding_with_original_ratio(&mut self, on: bool) { self.global.padding_with_original_ratio.enable = on }

    pub fn input_dir(&self) -> &str { &self.base.input_dir }
    pub fn set_input_dir(&mut self, d: &str) { self.base.input_dir = d.to_owned() }
    pub fn output_dir(&self) -> &str { &self.base.output_dir }
    pub fn set_output_dir(&mut self, d: &str) { self.base.output_dir = d.to_owned() }

    pub fn font_path(&self) -> &str { &self.base.font }
    pub fn bold_font_path(&self) -> &str { &self.base.bold_font }
    pub fn alternative_font_path(&self) -> &str { &self.base.alternative_font }
    pub fn alternative_bold_font_path(&self) -> &str { &self.base.alternative_bold_font }
    pub fn default_logo_path(&self) -> &str { &self.logo.default.path }
    pub fn logo_makes(&self) -> &BTreeMap<String, LogoEntry> { &self.logo.makes }
}
```

`font_padding_level()` 的 `+2` 是把「钳到 1..=3 后为 1」折算成布尔求和的写法，语义等价于 Python 的 `clamp(v)` 后相加；测试用真实配置（两档都是 1）断言结果为 `2`，用越界配置也断言 `2`，两条路径都锁住。

- [ ] **步骤 4：跑测试验证通过**

运行：`cd rust && cargo test -p copyleft-core --test config`
预期：三个测试 PASS。若 `custom_text()` 断言失败，先确认转义语义差异：

```bash
python -c "import yaml;print(repr(yaml.safe_load(open('config.yaml',encoding='utf-8'))['layout']['elements']['right_top']['value']))"
```

`config.yaml:41` 写的是 `"PiggyWu\xA9"`，`\xA9` 是 PyYAML 的双引号转义（©），serde_yaml 同样支持——若 serde 给出的是带反斜杠的字面串，说明它没按 YAML 双引号转义解析，此时以 Python 的输出为准，把 Rust 侧解析换成支持该转义的方式，并在 `NOTES.md` 记录这条差异。

- [ ] **步骤 5：往返保序测试**

追加到 `tests/config.rs`：

```rust
#[test]
fn save_roundtrip_keeps_top_level_key_order() {
    let src = copyleft_core::test_support::repo_root().join("config.yaml");
    let top_keys = |text: &str| -> Vec<String> {
        text.lines()
            .filter(|l| !l.starts_with(' ') && !l.starts_with('#') && l.contains(':'))
            .map(|l| l.split(':').next().unwrap().to_owned())
            .collect()
    };
    let cfg = Config::load(&src).unwrap();
    let before = top_keys(&std::fs::read_to_string(&src).unwrap());

    let dir = std::env::temp_dir().join("copyleft_cfg_rt");
    std::fs::create_dir_all(&dir).unwrap();
    let out = dir.join("c.yaml");
    cfg.save(&out).unwrap();

    assert_eq!(before, top_keys(&std::fs::read_to_string(&out).unwrap()), "顶层键顺序变了");
    assert_eq!(Config::load(&out).unwrap(), cfg, "往返后内容变了");
}
```

运行：`cd rust && cargo test -p copyleft-core --test config save_roundtrip`
预期：PASS。顶层键顺序由结构体字段声明顺序（`base, global, layout, logo`）决定，与真实文件的字母序恰好一致；嵌套层的字母序由 `BTreeMap` 保证。若 `logo.makes` 顺序变了，说明 `Logo` 里用了 `HashMap`。

- [ ] **步骤 6：commit**

```bash
cd rust && cargo fmt && cargo clippy --all-targets -- -D warnings && cargo test
git add rust
git commit -m "feat(rust): config.yaml 兼容层

null/越界/缺字段三类容错与 config.py 逐条对齐；BTreeMap 保住
yaml.dump 的字母序，避免用户比对配置时看到无意义 diff。"
```

---

## 任务 3：`ExifFacts` + kamadak-exif 通道 + Python tag 修正

**文件：**
- 创建：`rust/crates/copyleft-core/src/exif/facts.rs`、`rust/crates/copyleft-core/src/exif/standard.rs`、`rust/fixtures/make.sh`
- 修改：`rust/crates/copyleft-core/src/exif/mod.rs`、`rust/crates/copyleft-core/src/lib.rs`（无需改）、`rust/crates/copyleft-core/tests/exif_standard.rs`、`utils.py:163-164`、`utils.py:184-185`

- [ ] **步骤 1：派生样张脚本**

`rust/fixtures/make.sh`（生成的文件已被 `.gitignore` 排除，新环境跑一次即可）：

```bash
#!/usr/bin/env bash
# 从仓库根 input/ 的真实照片派生测试样张；重复执行安全。
set -euo pipefail
cd "$(dirname "$0")/../.."
python - <<'PY'
from PIL import Image
from pathlib import Path
src = Path('input/_DSC7969.JPG')
out = Path('rust/fixtures'); out.mkdir(parents=True, exist_ok=True)
im = Image.open(src)
ex = im.getexif()

im.convert('RGB').save(out / 'no_exif.png')                 # 无任何 EXIF
if ex: im.save(out / 'with_exif.png', exif=ex.tobytes())     # PNG 带 EXIF

# 竖拍样张：像素按 ROTATE_90 转置后，标签必须改写成 6，否则等于没测方向交换
rotated = im.transpose(Image.Transpose.ROTATE_90)
tagged = im.getexif(); tagged[274] = 6
rotated.save(out / 'rotated.jpg', exif=tagged.tobytes())
print('fixtures:', sorted(p.name for p in out.iterdir()))
PY
```

运行：`bash rust/fixtures/make.sh`
预期：`rust/fixtures/` 下出现 `no_exif.png`、`with_exif.png`、`rotated.jpg`。

- [ ] **步骤 1b：验证派生的 orientation 标签真的生效**

运行：`./exiftool.exe -orientation -s -s -s rust/fixtures/rotated.jpg && python -c "from PIL import Image; print(Image.open('rust/fixtures/rotated.jpg').getexif().get(274))"`
预期：都输出 `6`。**注意 Pillow 的 `exif_transpose` 会自动把标签清成 1**，所以这里必须直接改 `getexif()[274]` 而不要经过 `exif_transpose`；`rotated.jpg` 的像素是转置过的、标签是 6，正是「查看器需要按标签再转回来」的真实形态，`ImageMeta` 应报 `width=original_height`。


- [ ] **步骤 2：写失败的测试**

`tests/exif_standard.rs`（断言值全部来自附录 A 的实测）：

```rust
use copyleft_core::exif::facts::{format_exposure, ExifFacts, ExifSource};
use copyleft_core::exif::standard;
use copyleft_core::test_support::{fixture, photo};

#[test]
fn nikon_facts_via_standard_channel() {
    let f = standard::read(&photo("_DSC7969.JPG")).unwrap();
    assert_eq!(f.make, "NIKON CORPORATION");
    assert_eq!(f.model, "NIKON D810");
    // 附录 A：ISO 在 tag 34855（0x8827），值 800
    assert_eq!(f.iso, "800");
    assert_eq!(f.f_number, "2.8");
    assert_eq!(f.exposure, "1/500s");
    // 标准通道用 {:.1} 格式化，两个焦距都带 .0
    assert_eq!(f.focal_display, "145.0");
    assert_eq!(f.focal_35_display, "145.0");
    assert_eq!(f.date_time_original.as_deref(), Some("2014-01-01 08:25:54"));
    assert_eq!(f.orientation, Some(1));
    assert_eq!(f.lens_model, "", "Nikon 镜头信息只在 MakerNote，标准通道读不到");
    assert_eq!(f.gps_position, None);
    assert_eq!(f.source, ExifSource::Standard);
}

#[test]
fn png_without_exif_yields_empty_facts() {
    let f = standard::read(&fixture("no_exif.png")).unwrap();
    assert_eq!(f, ExifFacts::empty(ExifSource::Standard));
}

#[test]
fn png_with_exif_reads_back_iso() {
    let f = standard::read(&fixture("with_exif.png")).unwrap();
    assert_eq!(f.iso, "800", "PNG 里的 EXIF 同样要能读");
    assert_eq!(f.model, "NIKON D810");
}

#[test]
fn exposure_formatting_matches_pillow_branches() {
    assert_eq!(format_exposure(1, 250), "1/250");
    assert_eq!(format_exposure(1, 1000), "1/1000");
    assert_eq!(format_exposure(1, 1), "1");
    assert_eq!(format_exposure(30, 10), "3");
    assert_eq!(format_exposure(25, 10), "2.5");
    assert_eq!(format_exposure(3, 2), "1.5");
    // Python 的 round() 是银行家舍入：1/0.4 = 2.5 → 2；Rust 的 round() 会给 3
    assert_eq!(format_exposure(2, 5), "1/2");
}
```

- [ ] **步骤 3：跑测试验证失败**

运行：`cd rust && cargo test -p copyleft-core --test exif_standard`
预期：编译失败 `unresolved imports copyleft_core::exif::facts`。

- [ ] **步骤 4：实现 `facts.rs`**

```rust
// rust/crates/copyleft-core/src/exif/facts.rs
use serde::{Deserialize, Serialize};

/// Python 侧 DEFAULT_VALUE，缺失字段直接进显示串（"ISO--"、"--mm"）。
pub const DEFAULT_VALUE: &str = "--";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ExifSource { Exiftool, Standard, Empty }

/// 显示就绪的 EXIF。两个通道都填它，下游不再碰格式差异。
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ExifFacts {
    pub make: String,
    pub model: String,
    /// 取值顺序 LensModel → Lens → LensID（与 ExifId.LENS_MODEL 一致）。
    pub lens_model: String,
    pub lens_make: String,
    /// 已含 "s" 后缀（"1/500s"）；缺失时为 "--"（Python 的默认值不带后缀）。
    pub exposure: String,
    pub f_number: String,
    pub iso: String,
    /// 保留匹配到的原样数字串："145.0"（exiftool 通道）或 "--"。
    pub focal_display: String,
    pub focal_35_display: String,
    /// 规范化到 "YYYY-MM-DD HH:MM:SS"；None 表示 EXIF 无有效时间。
    pub date_time_original: Option<String>,
    pub orientation: Option<u16>,
    /// exiftool 的 GPSPosition 原文，或标准通道自拼的同款串。
    pub gps_position: Option<String>,
    /// 写回用的原始 EXIF 块（TIFF 结构，不含 "Exif\0\0" 前缀）。计划 B 填。
    pub raw_app1: Option<Vec<u8>>,
    pub source: ExifSource,
}

impl ExifFacts {
    pub fn empty(source: ExifSource) -> Self {
        Self {
            make: String::new(), model: String::new(),
            lens_model: String::new(), lens_make: String::new(),
            exposure: DEFAULT_VALUE.into(), f_number: DEFAULT_VALUE.into(),
            iso: DEFAULT_VALUE.into(),
            focal_display: DEFAULT_VALUE.into(), focal_35_display: DEFAULT_VALUE.into(),
            date_time_original: None, orientation: None, gps_position: None,
            raw_app1: None, source,
        }
    }

    /// 空串按 Python 的 default_value 回落成 "--"。
    pub fn with_display_defaults(mut self) -> Self {
        for s in [&mut self.exposure, &mut self.f_number, &mut self.iso,
                  &mut self.focal_display, &mut self.focal_35_display] {
            if s.is_empty() { *s = DEFAULT_VALUE.to_owned() }
        }
        self
    }
}

/// 复刻 utils._fmt_exposure_time，含 Python round() 的银行家舍入。
pub fn format_exposure(numerator: u32, denominator: u32) -> String {
    if denominator == 0 { return String::new() }
    let value = numerator as f64 / denominator as f64;
    if value <= 0.0 { return String::new() }
    if value >= 1.0 {
        if denominator == 1 { return numerator.to_string() }
        return format_g(value);
    }
    format!("1/{}", round_half_even(1.0 / value))
}

/// Python round()：半数取偶。0.4s → 1/0.4 = 2.5 → 2（Rust 原生 round 会给 3）。
fn round_half_even(x: f64) -> i64 {
    let floor = x.floor();
    let frac = x - floor;
    if (frac - 0.5).abs() < 1e-9 {
        let f = floor as i64;
        if f % 2 == 0 { f } else { f + 1 }
    } else {
        x.round() as i64
    }
}

/// 对应 f"{x:g}"：整数值不带小数点。
fn format_g(x: f64) -> String {
    if x == x.trunc() { format!("{}", x as i64) } else { format!("{x}") }
}
```

- [ ] **步骤 5：实现 `standard.rs`**

一律用 `ExifTag::*` 变体名取标签，绝不写数字——`utils.py` 那两个 bug 就是抄数字抄出来的。

```rust
// rust/crates/copyleft-core/src/exif/standard.rs
use std::fs::File;
use std::io::BufReader;
use std::path::Path;

use exif::{Exif, ExifTag, InCamera, Rational, Value};

use crate::error::{CoreError, Result};
use crate::exif::facts::{format_exposure, ExifFacts, ExifSource};

pub fn read(path: &Path) -> Result<ExifFacts> {
    let file = File::open(path).map_err(|e| CoreError::exif(path, e))?;
    let mut reader = BufReader::new(file);
    // 无 EXIF 的 PNG 不是错误：返回空 facts，让上层继续跑
    let Ok(exif) = Exif::from_io(&mut reader, InCamera::default()) else {
        return Ok(ExifFacts::empty(ExifSource::Standard));
    };
    Ok(facts_from(&exif))
}

/// 字段映射单独成函数：JPEG 走容器解析，PNG 若 kamadak 不认 eXIf，
/// 就改成先取 EXIF 原始字节再进这里，两条路共用同一套映射。
pub fn facts_from(exif: &Exif) -> ExifFacts {
    let camera = exif.get_ifd(InCamera::default());
    let find = |tag: ExifTag| exif.exif.get(&tag).or_else(|| camera.get(&tag));

    let facts = ExifFacts {
        make: find(ExifTag::Make).map(ascii).unwrap_or_default(),
        model: find(ExifTag::Model).map(ascii).unwrap_or_default(),
        lens_model: find(ExifTag::LensModel).map(ascii)
            .or_else(|| find(ExifTag::Lens).map(ascii))
            .or_else(|| find(ExifTag::LensID).map(ascii))
            .unwrap_or_default(),
        lens_make: find(ExifTag::LensMake).map(ascii).unwrap_or_default(),
        exposure: find(ExifTag::ExposureTime).and_then(rational_pair)
            .map(|(n, d)| format_exposure(n, d) + "s").unwrap_or_default(),
        f_number: find(ExifTag::FNumber).and_then(as_f32)
            .map(|v| format!("{v:.1}")).unwrap_or_default(),
        iso: find(ExifTag::PhotographicSensitivity).and_then(as_f32)
            .map(|v| format!("{}", v as u32)).unwrap_or_default(),
        focal_display: find(ExifTag::FocalLength).and_then(as_f32)
            .map(|v| format!("{v:.1}")).unwrap_or_default(),
        focal_35_display: find(ExifTag::FocalLengthIn35mmFilm).and_then(as_f32)
            .map(|v| format!("{v:.1}")).unwrap_or_default(),
        date_time_original: find(ExifTag::DateTimeOriginal)
            .map(|v| normalize_datetime(&ascii(v))).filter(|s| !s.is_empty()),
        orientation: find(ExifTag::Orientation).and_then(as_f32).map(|v| v as u16),
        gps_position: gps(&exif),
        raw_app1: None,
        source: ExifSource::Standard,
    };
    facts.with_display_defaults()
}

fn ascii(v: &Value) -> String {
    match v {
        Value::Ascii(bytes) => String::from_utf8_lossy(bytes)
            .trim_end_matches('\0').trim().to_owned(),
        other => format!("{other:?}").trim().to_owned(),
    }
}

fn as_f32(v: &Value) -> Option<f32> {
    match v {
        Value::Rational(r) => r.first().map(|x| x.to_f32()),
        Value::U16(x) => x.first().map(|&v| v as f32),
        Value::U32(x) => x.first().map(|&v| v as f32),
        Value::I16(x) => x.first().map(|&v| v as f32),
        Value::I32(x) => x.first().map(|&v| v as f32),
        _ => None,
    }
}

fn rational_pair(v: &Value) -> Option<(u32, u32)> {
    let Rational { numerator, denominator } = v.as_rational()?.first()?;
    Some((*numerator, *denominator))
}

/// EXIF 原生 "2014:01:01 08:25:54" → "2014-01-01 08:25:54"（对齐 exiftool -d 的输出）
fn normalize_datetime(s: &str) -> String {
    match s.split_once(' ') {
        Some((date, time)) => format!("{} {time}", date.replace(':', "-")),
        None => s.to_owned(),
    }
}

/// 拼成 exiftool GPSPosition 的形态：46 deg 55' 20.88" N, 7 deg 13' 36.72" E
fn gps(exif: &Exif) -> Option<String> {
    use exif::{Metadata, Tag};
    let g = exif.get_ifd(Metadata::Gps);
    let dms = |tag: Tag| g.get(&tag).and_then(|v| v.as_rational()).cloned();
    let hemi = |tag: Tag| g.get(&tag).map(ascii);
    let (lat, lon) = (dms(Tag::GPSLatitude)?, dms(Tag::GPSLongitude)?);
    let (lat_ref, lon_ref) = (hemi(Tag::GPSLatitudeRef)?, hemi(Tag::GPSLongitudeRef)?);
    let part = |v: &[Rational], hemi: &str| {
        let nums: Vec<f64> = v.iter().map(|r| r.to_f64()).collect();
        format!("{} deg {}' {}\" {}", nums[0] as i32, nums[1] as i32, nums[2], hemi)
    };
    Some(format!("{}, {}", part(&lat, &lat_ref), part(&lon, &lon_ref)))
}
```

若 `Exif::from_io` / `InCamera::default()` / `ExifTag::*` 在 kamadak-exif 0.6 里签名不同（0.6 把 `Source` 换成了 `InCamera`），按 `cargo build` 报错 + docs.rs/kamadak-exif 0.6 调整，**改动只允许落在 `standard.rs` 这一个文件**，并在 commit message 里记下实际签名。

- [ ] **步骤 6：跑测试验证通过**

运行：`cd rust && cargo test -p copyleft-core --test exif_standard`
预期：`exposure_formatting_matches_pillow_branches` 与 `png_without_exif_yields_empty_facts` PASS；`nikon_facts_via_standard_channel` 的 `iso` 断言此时应已满足（Rust 用枚举名取标签，不继承 Python 的数字错误）。

`png_with_exif_reads_back_iso` 检验的是一条**尚未证实的假设**：kamadak-exif 的 README 只保证「TIFF 及基于 TIFF 的若干 RAW 格式」，PNG 的 eXIf chunk 能不能被它的容器解析吃下并不确定。若这条失败，按三步处理：

1. `python -c "from PIL import Image; print(len(Image.open('rust/fixtures/with_exif.png').info.get('exif') or b''))"` — 先确认 PNG 里确实有 EXIF，排除派生脚本的问题。
2. 确认是 kamadak 不吃 PNG 后，把 `standard::read` 改成「按容器取 EXIF 原始字节 → 交给 `facts_from`」：JPEG 从 APP1 段取、PNG 从 `eXIf` chunk 取，不再依赖 kamadak 的容器解析（两条路共用同一套字段映射，正是 `facts_from` 独立成函数的原因）。
3. 记进 `rust/NOTES.md`，并核对一条连带结论：Python 的 Pillow 通道能读 PNG EXIF，所以 Rust 读不到就是相对旧版的能力倒退，必须补齐，不能以「测试改掉」收场。

任一字段失败时，先跑附录 A 的采集命令核对 Python 实际值，再改 Rust，禁止放宽断言。

- [ ] **步骤 7：修 Python 侧两处 tag**

`utils.py:163-164`：`42032` → `42035`（0xA433 LensMake；0xA430 是 CameraOwnerName）。
`utils.py:184-185`：`8827` → `34855`（0x8827）。

- [ ] **步骤 8：验证修正生效**

运行：

```bash
rm -rf __pycache__ core/__pycache__ core/entity/__pycache__ core/enums/__pycache__
python -c "
import utils
from pathlib import Path
e = utils._pillow_exif(Path('input/_DSC7969.JPG'))
print('ISO =', e.get('ISO'), '| LensMake =', repr(e.get('LensMake')), '| FNumber =', e.get('FNumber'))"
```

预期：`ISO = 800`（修之前是 `None`）。`LensMake` 仍是 `None` 属正常——这台 Nikon 的镜头信息只在 MakerNote 里，标准通道本就取不到，改动只是把取错的 tag 号纠正。再跑一次全链路：

```bash
python -c "
from pathlib import Path
import core.entity.image_container as c
ic = c.ImageContainer(Path('input/_DSC7969.JPG'))
print(ic._param_dict['Param'])"
```

预期：`145.0mm  f/2.8  1/500s  ISO800`。

- [ ] **步骤 9：commit**

```bash
cd rust && cargo fmt && cargo clippy --all-targets -- -D warnings && cargo test
git add rust utils.py
git commit -m "fix(exif): Pillow 回退通道读错 tag，并落地 Rust 标准通道

ISO 在 0x8827=34855，原代码写成十进制 8827，无 exiftool 时永远显示
ISO--；LensMake 同理取错 0xA430。Rust 侧统一用 ExifTag 枚举名而非
数字，杜绝同一类错误。"
```

---

## 任务 4：exiftool 通道

**文件：**
- 创建：`rust/crates/copyleft-core/src/exif/tool.rs`、`rust/crates/copyleft-core/tests/exif_tool.rs`
- 修改：`rust/crates/copyleft-core/src/exif/mod.rs`

- [ ] **步骤 1：先抓真实 JSON，确定键名**

运行：

```bash
./exiftool.exe -j -d '%Y-%m-%d %H:%M:%S%3f%z' input/_DSC7969.JPG > rust/fixtures/exiftool_nikon.json
python -c "
import json
d=json.load(open('rust/fixtures/exiftool_nikon.json',encoding='utf-8'))[0]
for k in ['Make','Model','CameraModelName','Lens','LensID','LensModel','LensMake',
          'ISO','FNumber','ExposureTime','FocalLength','FocalLengthIn35mmFormat',
          'DateTimeOriginal','Orientation','GPSPosition']:
    print('%-24s %r'%(k,d.get(k)))"
```

预期：与附录 A 的 exiftool 通道一致——`Lens` = `'70-200mm f/2.8'`、`LensID` = `'AF-S Nikkor 70-200mm f/2.8G ED VR II'`、`LensModel`/`LensMake` 为 `None`、`Orientation` = `'Horizontal (normal)'`。

**只用 `-j`，不加 `-a -G1 -u`：** 实测 `-a -G1` 会同时给出 `IFD0:Model` 与 `ExifIFD:CameraModelName`、以及一堆 `Composite:` 键，剥掉组名前缀后在扁平 map 里互相覆盖；而默认 `-j` 的裸键与 Python 文本解析出的键完全一致（`_exiftool_exif` 的键归一化只去空格和 `/`，默认输出本来就没有这两种字符）。

**弃用 Python 的冒号切分：** `_exiftool_exif` 用 `line.split(':')`，值里带冒号时会被切错；JSON 结构化解析没这个问题。

- [ ] **步骤 2：写失败的测试**

`tests/exif_tool.rs`：

```rust
use copyleft_core::exif::facts::ExifSource;
use copyleft_core::exif::tool;

#[test]
fn maps_nikon_json_onto_facts() {
    // 键名与 rust/fixtures/exiftool_nikon.json 一致（ISO/FNumber 是 JSON 数字）
    let json = r#"[{"SourceFile":"x","Make":"NIKON CORPORATION","CameraModelName":"NIKON D810",
      "Lens":"70-200mm f/2.8","LensID":"AF-S Nikkor 70-200mm f/2.8G ED VR II",
      "ISO":800,"FNumber":2.8,"ExposureTime":"1/500","FocalLength":"145.0 mm",
      "FocalLengthIn35mmFormat":"145 mm","DateTimeOriginal":"2014-01-01 08:25:54.000+0800",
      "Orientation":"Horizontal (normal)"}]"#;
    let f = tool::facts_from_json_str(json).unwrap();
    assert_eq!(f.make, "NIKON CORPORATION");
    assert_eq!(f.model, "NIKON D810");
    // 顺序必须是 LensModel → Lens → LensID：这台机器 LensModel 缺失，
    // 取到 Lens='70-200mm f/2.8'；若把 LensID 排前面就会错拿全名。
    assert_eq!(f.lens_model, "70-200mm f/2.8");
    assert_eq!(f.iso, "800");
    assert_eq!(f.f_number, "2.8");
    assert_eq!(f.exposure, "1/500s");
    assert_eq!(f.focal_display, "145.0");
    // exiftool 打印 "145 mm"，Python 的 PATTERN 抓到 "145"（不带 .0）
    assert_eq!(f.focal_35_display, "145");
    assert_eq!(f.date_time_original.as_deref(), Some("2014-01-01 08:25:54.000+0800"));
    assert_eq!(f.orientation, Some(1));
    assert_eq!(f.source, ExifSource::Exiftool);
}

#[test]
fn gps_position_string_passthrough_and_ascii_filter() {
    let json = r#"[{"GPSPosition":"46 deg 55' 20.88\" N, 7 deg 13' 36.72\" E",
                   "Comment":"中文备注 test"}]"#;
    let f = tool::facts_from_json_str(json).unwrap();
    assert_eq!(f.gps_position.as_deref(), Some("46 deg 55' 20.88\" N, 7 deg 13' 36.72\" E"));
    assert_eq!(f.lens_model, "");
}

#[test]
fn real_binary_matches_fixture() {
    let Some(bin) = tool::locate() else {
        eprintln!("本机无 exiftool，跳过"); return;
    };
    let f = tool::read(&bin, &copyleft_core::test_support::photo("_DSC7969.JPG")).unwrap();
    assert_eq!(f.model, "NIKON D810");
    assert_eq!(f.lens_model, "70-200mm f/2.8");
    assert_eq!(f.iso, "800");
    assert_eq!(f.focal_35_display, "145");
    assert!(f.date_time_original.is_some());
}
```

- [ ] **步骤 3：跑测试验证失败**

运行：`cd rust && cargo test -p copyleft-core --test exif_tool`
预期：编译失败 `unresolved module tool`。

- [ ] **步骤 4：实现 `tool.rs`**

```rust
// rust/crates/copyleft-core/src/exif/tool.rs
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::process::Command;

use serde_json::Value as Json;

use crate::error::{CoreError, Result};
use crate::exif::facts::{ExifFacts, ExifSource};

/// 与 utils.py 的探测顺序一致：PATH 优先，再看本地两种摆放位置。
pub fn locate() -> Option<PathBuf> {
    if let Some(found) = which::which("exiftool").map(PathBuf::from) {
        if found.exists() { return Some(found); }
    }
    let names: &[&str] = if cfg!(windows) { &["exiftool.exe", "exiftool/exiftool.exe"] }
                         else { &["exiftool", "exiftool/exiftool"] };
    names.iter().map(PathBuf::from).find(|p| p.exists())
}

pub fn read(bin: &Path, photo: &Path) -> Result<ExifFacts> {
    let out = Command::new(bin)
        .arg("-j")
        .arg("-d").arg("%Y-%m-%d %H:%M:%S%3f%z")
        .arg(photo)
        .output()
        .map_err(|e| CoreError::ExiftoolRun { bin: bin.display().to_string(), reason: e.to_string() })?;
    if !out.status.success() {
        return Err(CoreError::ExiftoolRun {
            bin: bin.display().to_string(),
            reason: String::from_utf8_lossy(&out.stderr).trim().to_owned(),
        });
    }
    facts_from_json_str(&String::from_utf8_lossy(&out.stdout))
}

/// 剥组名前缀（默认 -j 输出没有前缀，保留这层是为容忍 -G），并照抄 Python 的 ASCII 过滤。
fn flatten(root: &Json) -> HashMap<String, String> {
    let mut map = HashMap::new();
    let Some(obj) = root.as_array().and_then(|a| a.first()).and_then(|o| o.as_object()) else {
        return map;
    };
    for (k, v) in obj {
        let bare = k.rsplit("] ").next().unwrap_or(k);
        let text = match v {
            Json::String(s) => s.clone(),
            Json::Number(n) => n.to_string(),
            Json::Bool(b) => b.to_string(),
            Json::Array(items) => items.iter().map(|i| i.to_string().trim_matches('"').to_owned())
                .collect::<Vec<String>>().join(" "),
            _ => continue,
        };
        map.insert(bare.replace('/', "").trim().to_owned(),
                   text.chars().filter(char::is_ascii).collect());
    }
    map
}

/// 对应 PATTERN = r"(\d+(?:\.\d+)?)"：取第一个数字串，含小数点。
fn first_number(s: &str) -> String {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    let re = RE.get_or_init(|| regex::Regex::new(r"\d+(?:\.\d+)?").unwrap());
    re.find(s).map(|m| m.as_str().to_owned()).unwrap_or_default()
}

fn orientation_from(text: &str) -> Option<u16> {
    // exiftool 文本值 → 数值，与 utils._ORIENTATION_NAMES 的对应关系一致
    if text.contains("Rotate 90 CW") { Some(6) }
    else if text.contains("Rotate 180") { Some(3) }
    else if text.contains("Rotate 270 CW") { Some(8) }
    else if text.contains("Rotate 0") || text.contains("Horizontal (normal)") { Some(1) }
    else { None }
}

/// EXIF 原生冒号日期 → 连字符（标准通道同款处理；exiftool 带 -d 时已是连字符，
/// 这里对已规范化的串是幂等的）。
fn normalize_datetime(s: &str) -> String {
    match s.split_once(' ') {
        Some((date, rest)) if date.len() == 10 && date.contains(':') =>
            format!("{} {rest}", date.replace(':', "-")),
        _ => s.to_owned(),
    }
}

pub fn facts_from_json_str(text: &str) -> Result<ExifFacts> {
    let json: Json = serde_json::from_str(text.trim())
        .map_err(|e| CoreError::ExiftoolRun { bin: "json".into(), reason: e.to_string() })?;
    let m = flatten(&json);
    let pick = |k: &str| m.get(k).cloned().unwrap_or_default();
    // ExifId.LENS_MODEL 的顺序：LensModel → Lens → LensID
    let lens_model = [ "LensModel", "Lens", "LensID" ].iter()
        .map(|k| pick(k)).find(|v| !v.is_empty()).unwrap_or_default();
    // model 优先 CameraModelName（exiftool 的复合名），回退 IFD0 Model
    let model = { let v = pick("CameraModelName"); if v.is_empty() { pick("Model") } else { v } };
    // 焦距数字统一用 first_number，与 Python 的 PATTERN.findall(...)[0] 等价
    let focal = |k: &str| first_number(&pick(k));
    // ISO 可能是 "800 800"（多组 ISO 值合并），取第一个
    let iso = pick("ISO").split_whitespace().next().unwrap_or_default().to_owned();
    let raw_date = pick("DateTimeOriginal");

    Ok(ExifFacts {
        make: pick("Make"),
        model,
        lens_model,
        lens_make: pick("LensMake"),
        exposure: { let v = pick("ExposureTime"); if v.is_empty() { String::new() } else { v + "s" } },
        f_number: pick("FNumber"),
        iso,
        focal_display: focal("FocalLength"),
        focal_35_display: focal("FocalLengthIn35mmFormat"),
        date_time_original: if raw_date.is_empty() { None } else { Some(normalize_datetime(&raw_date)) },
        orientation: if pick("Orientation").is_empty() { None } else { orientation_from(&pick("Orientation")) },
        gps_position: { let v = pick("GPSPosition"); if v.is_empty() { None } else { Some(v) } },
        raw_app1: None,
        source: ExifSource::Exiftool,
    }.with_display_defaults())
}
```

`FNumber` 是 JSON 数字时 `n.to_string()` 给出 `2.8`，与 Python 文本通道的 `'2.8'` 一致；若某相机 exiftool 给出 `f/2.8` 形态的字符串，`pick("FNumber")` 会带 `f/`，此时改用 `first_number` 并保持前缀拼接在 `meta.rs` 里做（任务 6 的 `param_str` 负责加 `f/`）。落地时用 `rust/fixtures/exiftool_nikon.json` 确认属于哪种。

- [ ] **步骤 5：跑测试验证通过**

运行：`cd rust && cargo test -p copyleft-core --test exif_tool`
预期：三个测试 PASS（第三个在无 exiftool 的机器上打印跳过并 PASS）。

- [ ] **步骤 6：commit**

```bash
cd rust && cargo fmt && cargo clippy --all-targets -- -D warnings && cargo test
git add rust
git commit -m "feat(rust): exiftool JSON 通道

用 -j 取结构化输出替掉按冒号切行的脆弱解析；明确不加 -a -G1（会引入
跨组重名键），镜头取值顺序保持 LensModel→Lens→LensID 与 Python 一致。"
```

---

## 任务 5：通道编排与回退

**文件：**
- 修改：`rust/crates/copyleft-core/src/exif/mod.rs`
- 创建：`rust/crates/copyleft-core/tests/exif_fallback.rs`

- [ ] **步骤 1：写失败的测试**

`tests/exif_fallback.rs`：

```rust
use std::path::{Path, PathBuf};

use copyleft_core::error::{CoreError, Result};
use copyleft_core::exif::facts::{ExifFacts, ExifSource};
use copyleft_core::exif::{read_with, ExifTool};
use copyleft_core::test_support::{fixture, photo};

struct FakeTool(Option<PathBuf>);

impl ExifTool for FakeTool {
    fn read(&self, _photo: &Path) -> Result<ExifFacts> {
        match self.0 {
            None => Err(CoreError::ExiftoolRun { bin: "missing".into(), reason: "not found".into() }),
            Some(_) => Ok(ExifFacts { model: "FAKE MODEL".into(), ..ExifFacts::empty(ExifSource::Exiftool) }),
        }
    }
}

#[test]
fn prefers_exiftool_when_available() {
    let f = read_with(&photo("_DSC7969.JPG"), &FakeTool(Some(PathBuf::from("x")))).unwrap();
    assert_eq!(f.model, "FAKE MODEL");
    assert_eq!(f.source, ExifSource::Exiftool);
}

#[test]
fn falls_back_to_standard_on_error() {
    let f = read_with(&photo("_DSC7969.JPG"), &FakeTool(None)).unwrap();
    assert_eq!(f.source, ExifSource::Standard);
    assert_eq!(f.model, "NIKON D810");
    assert_eq!(f.iso, "800", "回退后 ISO 仍要拿到（任务 3 修的那两条 tag）");
}

#[test]
fn no_exif_anywhere_is_not_an_error() {
    let f = read_with(&fixture("no_exif.png"), &FakeTool(None)).unwrap();
    assert_eq!(f.source, ExifSource::Standard);
    assert_eq!(f, ExifFacts::empty(ExifSource::Standard));
}
```

- [ ] **步骤 2：跑测试验证失败**

运行：`cd rust && cargo test -p copyleft-core --test exif_fallback`
预期：编译失败 `unresolved imports copyleft_core::exif::read_with`。

- [ ] **步骤 3：实现 `exif/mod.rs`**

```rust
// rust/crates/copyleft-core/src/exif/mod.rs
pub mod facts;
pub mod standard;
pub mod tool;

use std::path::Path;

use crate::error::{CoreError, Result};
use facts::{ExifFacts, ExifSource};

/// 注入点：真机走 `ExiftoolBinary`，测试给假实现，避免依赖本机二进制。
pub trait ExifTool {
    fn read(&self, photo: &Path) -> Result<ExifFacts>;
}

pub struct ExiftoolBinary(pub Option<std::path::PathBuf>);

impl ExifTool for ExiftoolBinary {
    fn read(&self, photo: &Path) -> Result<ExifFacts> {
        let bin = self.0.as_ref().ok_or_else(|| CoreError::ExiftoolRun {
            bin: "exiftool".into(), reason: "未探测到 exiftool".into() })?;
        tool::read(bin, photo)
    }
}

/// 规格 § 7：exiftool 优先；异常时 warn 并回退标准通道；两路都失败给空 facts。
/// 单张图读不出 EXIF 绝不能让整批处理中断。
pub fn read_with(photo: &Path, tool: &dyn ExifTool) -> Result<ExifFacts> {
    match tool.read(photo) {
        Ok(facts) => Ok(facts),
        Err(e) => {
            tracing::warn!("exiftool 读取失败，回退到内置 EXIF 解析：{} : {e}", photo.display());
            Ok(standard::read(photo).unwrap_or_else(|e2| {
                tracing::error!("内置解析同样失败：{} : {e2}", photo.display());
                ExifFacts::empty(ExifSource::Empty)
            }))
        }
    }
}

pub fn read(photo: &Path) -> Result<ExifFacts> {
    read_with(photo, &ExiftoolBinary(tool::locate()))
}
```

`no_exif_anywhere_is_not_an_error` 断言 `source == Standard`：`standard::read` 对无 EXIF 文件返回 `ExifFacts::empty(ExifSource::Standard)`，走的是 `Ok` 分支，不会被替换成 `Empty`。`Empty` 只在内置解析真的抛错时出现。

- [ ] **步骤 4：跑测试验证通过**

运行：`cd rust && cargo test -p copyleft-core`
预期：全绿。

- [ ] **步骤 5：commit**

```bash
cd rust && cargo fmt && cargo clippy --all-targets -- -D warnings
git add rust && git commit -m "feat(rust): EXIF 双通道编排与回退

语义与 utils.get_exif 一致；外部进程调用做成 ExifTool 注入点，
测试不依赖本机是否装了 exiftool。"
```

---

## 任务 6：`ImageMeta`（EXIF → 16 个文字项）

**文件：**
- 修改：`rust/crates/copyleft-core/src/meta.rs`
- 创建：`rust/crates/copyleft-core/tests/meta.rs`

- [ ] **步骤 1：写失败的测试**

`tests/meta.rs`（断言值全部来自附录 A）：

```rust
use copyleft_core::keys::TextKey;
use copyleft_core::meta::ImageMeta;
use copyleft_core::test_support::{fixture, photo};

#[test]
fn single_items_match_python() {
    let m = ImageMeta::load(&photo("_DSC7969.JPG"), false).unwrap();
    assert_eq!(m.text(TextKey::Model, None), "NIKON D810");
    assert_eq!(m.text(TextKey::Make, None), "NIKON CORPORATION");
    assert_eq!(m.text(TextKey::LensModel, None), "70-200mm f/2.8");
    assert_eq!(m.text(TextKey::Date, None), "2014-01-01");
    assert_eq!(m.text(TextKey::Datetime, None), "2014-01-01 08:25");
    assert_eq!(m.text(TextKey::Filename, None), "_DSC7969");
    assert_eq!(m.text(TextKey::TotalPixel, None), "36.15 MP");
    assert_eq!(m.text(TextKey::None, None), "");
    assert_eq!(m.text(TextKey::Custom, Some("我的水印")), "我的水印");
    assert_eq!(m.text(TextKey::Custom, None), "无");
    assert_eq!(m.text(TextKey::GeoInfo, None), "无");
}

#[test]
fn param_keeps_python_quirks_and_channel_diff() {
    // 附录 A：非等效 "145.0mm  f/2.8  1/500s  ISO800"；等效 "145mm  ..."（exiftool 打印 "145 mm"）
    let m = ImageMeta::load(&photo("_DSC7969.JPG"), false).unwrap();
    assert_eq!(m.text(TextKey::Param, None), "145.0mm  f/2.8  1/500s  ISO800");
    let eq = ImageMeta::load(&photo("_DSC7969.JPG"), true).unwrap();
    assert_eq!(eq.text(TextKey::Param, None), "145mm  f/2.8  1/500s  ISO800");
}

#[test]
fn combined_items_join_with_single_space_including_empty_parts() {
    let m = ImageMeta::load(&photo("_DSC7969.JPG"), false).unwrap();
    assert_eq!(m.text(TextKey::CameraMakeCameraModel, None), "NIKON CORPORATION NIKON D810");
    assert_eq!(m.text(TextKey::DateFilename, None), "2014-01-01 _DSC7969");
    assert_eq!(m.text(TextKey::DatetimeFilename, None), "2014-01-01 08:25 _DSC7969");
    // lens_make 缺失 → Python 产出前导空格，必须原样保留
    assert_eq!(m.text(TextKey::LensMakeLensModel, None), " 70-200mm f/2.8");
    assert_eq!(m.text(TextKey::CameraModelLensModel, None), "NIKON D810 70-200mm f/2.8");
}

#[test]
fn dimensions_and_orientation() {
    let m = ImageMeta::load(&photo("_DSC7969.JPG"), false).unwrap();
    assert_eq!((m.original_width, m.original_height), (7360, 4912));
    assert_eq!(m.orientation, 1);
    assert_eq!(m.ratio(), 7360.0 / 4912.0);

    let r = ImageMeta::load(&fixture("rotated.jpg"), false).unwrap();
    assert_eq!(r.orientation, 6, "派生的 rotated.jpg 应带 Orientation=6");
    assert_eq!((r.width, r.height), (r.original_height, r.original_width), "宽高要按方向交换");
}

#[test]
fn missing_exif_falls_back_to_file_mtime() {
    let m = ImageMeta::load(&fixture("no_exif.png"), false).unwrap();
    assert_eq!(m.text(TextKey::Date, None).len(), 10, "应为 mtime 格式化出的 YYYY-MM-DD");
    assert_eq!(m.text(TextKey::Param, None), "--mm  f/--  --  ISO--");
    assert_eq!(m.text(TextKey::Model, None), "");
}

#[test]
fn gps_abbr_format_from_exiftool_position_shape() {
    let pos = "46 deg 55' 20.88\" N, 7 deg 13' 36.72\" E";
    assert_eq!(copyleft_core::meta::geo_from_position(pos).as_deref(), Some("46°55'N 7°13'E"));
    assert_eq!(copyleft_core::meta::geo_from_position("nonsense"), None);
}
```

- [ ] **步骤 2：跑测试验证失败**

运行：`cd rust && cargo test -p copyleft-core --test meta`
预期：编译失败 `ImageMeta` 未定义。

- [ ] **步骤 3：实现 `meta.rs`**

```rust
// rust/crates/copyleft-core/src/meta.rs
use std::path::{Path, PathBuf};

use chrono::{DateTime, Local, NaiveDate};

use crate::error::{CoreError, Result};
use crate::exif::{self, facts::ExifFacts};
use crate::keys::TextKey;

pub const NO_TEXT: &str = "无";

#[derive(Debug, Clone)]
pub struct ImageMeta {
    pub path: PathBuf,
    pub exif: ExifFacts,
    /// 未摆正的宽高（padding_to_original_ratio 用）。
    pub original_width: u32,
    pub original_height: u32,
    /// 按 Orientation 交换后的宽高（即像素摆正后的尺寸）。
    pub width: u32,
    pub height: u32,
    pub orientation: u16,
    pub use_equivalent_focal_length: bool,
    date: DateTime<Local>,
}

impl ImageMeta {
    /// 只读 EXIF 与图像尺寸，不解码像素（像素由布局层 open）。
    pub fn load(path: &Path, use_equivalent_focal_length: bool) -> Result<Self> {
        let exif = exif::read(path)?;
        let (w, h) = image::image_dimensions(path)
            .map_err(|e| CoreError::ImageOpen { path: path.display().to_string(), source: e })?;
        let orientation = exif.orientation.unwrap_or(1);
        let (dw, dh) = rotated_dims(w, h, orientation);
        let date = parse_photo_date(exif.date_time_original.as_deref())
            .unwrap_or_else(|| file_date(path).unwrap_or_else(|| Local::now()));
        Ok(Self {
            path: path.to_path_buf(), exif,
            original_width: w, original_height: h, width: dw, height: dh,
            orientation, use_equivalent_focal_length, date,
        })
    }

    /// image_container.get_attribute_str()：Custom 走 element.value，其余查表。
    pub fn text(&self, key: TextKey, custom: Option<&str>) -> String {
        match key {
            TextKey::Model => self.exif.model.clone(),
            TextKey::Make => self.exif.make.clone(),
            TextKey::LensModel => self.exif.lens_model.clone(),
            TextKey::Param => self.param_str(),
            TextKey::Datetime => self.format("%Y-%m-%d %H:%M"),
            TextKey::Date => self.format("%Y-%m-%d"),
            TextKey::Custom => custom.map(str::to_owned).unwrap_or_else(|| NO_TEXT.to_owned()),
            TextKey::None => String::new(),
            TextKey::TotalPixel => megapixel(self.original_width, self.original_height),
            TextKey::Filename => self.file_stem(),
            TextKey::LensMakeLensModel => join_space(&self.exif.lens_make, &self.exif.lens_model),
            TextKey::CameraModelLensModel => join_space(&self.exif.model, &self.exif.lens_model),
            TextKey::CameraMakeCameraModel => join_space(&self.exif.make, &self.exif.model),
            TextKey::DateFilename => join_space(&self.format("%Y-%m-%d"), &self.file_stem()),
            TextKey::DatetimeFilename => join_space(&self.format("%Y-%m-%d %H:%M"), &self.file_stem()),
            TextKey::GeoInfo => self.geo(),
        }
    }

    pub fn ratio(&self) -> f64 { self.width as f64 / self.height as f64 }
    pub fn original_ratio(&self) -> f64 { self.original_width as f64 / self.original_height as f64 }

    fn file_stem(&self) -> String {
        self.path.file_stem().map(|s| s.to_string_lossy().to_owned()).unwrap_or_default()
    }

    /// image_container.get_param_str()：两处空格分隔，并保留 "--mm"/"f/--"/"ISO--" 三处怪癖。
    fn param_str(&self) -> String {
        let focal = if self.use_equivalent_focal_length
            && self.exif.focal_35_display != crate::exif::facts::DEFAULT_VALUE {
            &self.exif.focal_35_display
        } else {
            &self.exif.focal_display
        };
        format!("{}mm  f/{}  {}  ISO{}", focal, self.exif.f_number, self.exif.exposure, self.exif.iso)
    }

    fn format(&self, spec: &str) -> String { self.date.format(spec).to_string() }

    /// GPS：优先 exiftool 的 GPSPosition，其次标准通道拼好的同形态串；都没有则 "无"。
    fn geo(&self) -> String {
        self.exif.gps_position.as_deref()
            .and_then(geo_from_position)
            .unwrap_or_else(|| NO_TEXT.to_owned())
    }
}

/// "46 deg 55' 20.88\" N, 7 deg 13' 36.72\" E" → "46°55'N 7°13'E"
/// 对应 utils.extract_gps_lat_and_long：度取整、分取整、丢掉秒。
pub fn geo_from_position(pos: &str) -> Option<String> {
    let (lat, lon) = pos.split_once(", ")?;
    Some(format!("{} {}", abbr_dms(lat)?, abbr_dms(lon)?))
}

fn abbr_dms(s: &str) -> Option<String> {
    let mut it = s.split_whitespace().peekable();
    let deg = it.next()?;
    let min = it.find(|t| t.ends_with('\''))?.trim_end_matches('\'');
    let hemi = *it.peek_back()?;
    if !matches!(hemi, "N" | "S" | "E" | "W") { return None }
    Some(format!("{deg}°{min}'{hemi}"))
}

fn join_space(a: &str, b: &str) -> String { format!("{a} {b}") }

fn megapixel(w: u32, h: u32) -> String {
    format!("{:.2} MP", (w as u64 * h as u64) as f64 / 1_000_000.0)
}

fn rotated_dims(w: u32, h: u32, orientation: u16) -> (u32, u32) {
    match orientation { 5 | 6 | 7 | 8 => (h, w), _ => (w, h) }
}

/// 两种通道的日期形态都要吃：
/// exiftool 带 -d → "2014-01-01 08:25:54.000+0800"；标准通道 → "2014-01-01 08:25:54"。
/// 与 Python 一致：exiftool 那条是带时区的挂钟时间，**不做时区换算**，直接取本地字段。
fn parse_photo_date(raw: Option<&str>) -> Option<DateTime<Local>> {
    let s = raw?;
    if let Ok(d) = chrono::DateTime::parse_from_str(s, "%Y-%m-%d %H:%M:%S%.f%z") {
        return Some(d.with_timezone(&Local));
    }
    let naive = chrono::NaiveDateTime::parse_from_str(s, "%Y-%m-%d %H:%M:%S").ok()?;
    naive.date().and_hms_opt(naive.time().hour(), naive.time().minute(), naive.time().second())
        .map(|d| d.and_local_timezone(Local).single().unwrap_or_else(Local::now))
}

fn file_date(path: &Path) -> Option<DateTime<Local>> {
    let t = std::fs::metadata(path).ok()?.modified().ok()?;
    Some(DateTime::<Local>::from(t))
}
```

**时区语义是这条链路上最容易错的地方。** Python 用 `dateutil.parser.parse` 得到带 `+0800` 的 tz-aware 对象，再 `strftime` 输出的是**挂钟时间**、不做换算。Rust 的 `with_timezone(&Local)` 在机器时区等于 +0800 时结果相同，机器时区不同时就会差几小时。落地时的正确做法：把 `Datetime`/`Date` 的格式化基准存成 `NaiveDateTime`（即「按 EXIF 声明的偏移取本地字段」而不是「转成本地时区」），`file_date` 分支才用 `Local`。写一个专门的测试：构造 `"2014-01-01 08:25:54.000+0800"` 与 `"2014-01-01 08:25:54"` 两个输入，断言二者产出的 `Date`/`Datetime` 字符串相同。

`Local::today()` 与 `single()` 的 API 用法（`and_local_timezone` 返回 `LocalResult`）在落地时按编译错误调整，必要时用 `.latest()`。

- [ ] **步骤 4：跑测试验证通过**

运行：`cd rust && cargo test -p copyleft-core --test meta`
预期：六个测试 PASS。任一文字项失败，先跑附录 A 的采集命令核对 Python 输出，再改 Rust；`TotalPixel` 与 `GeoInfo` 是最容易差的两处。

- [ ] **步骤 5：commit**

```bash
cd rust && cargo fmt && cargo clippy --all-targets -- -D warnings && cargo test
git add rust && git commit -m "feat(rust): ImageMeta 与 16 个文字项

文案怪癖（--mm / f/-- / ISO-- / 前导空格）原样继承，否则计划 B 的整图
对拍无从对齐；无 EXIF 时间回退文件 mtime，日期不做时区换算。"
```

---

## 任务 7：字体加载与度量对齐（去风险）

`fonts/AlibabaPuHuiTi-2-45-Light.otf` 实测 sfnt tag 是 `OTTO`（CFF 轮廓）。这一步不写业务逻辑，只做两件事：确认可用的栅格化路径，并把 Pillow 的度量复现出来。**它必须在布局任务之前完成**，因为留白计算全靠文字位图的宽高。

**文件：**
- 创建：`rust/crates/copyleft-core/src/text/store.rs`、`rust/crates/copyleft-core/tests/text_metrics.rs`、`rust/crates/copyleft-core/examples/text_probe.rs`
- 修改：`rust/crates/copyleft-core/src/text/mod.rs`

- [ ] **步骤 1：写失败的度量测试**

`tests/text_metrics.rs`（期望值来自 2026-10-12 的 Pillow 实测，命令见附录 A）：

```rust
use copyleft_core::text::store::Face;
use copyleft_core::test_support::font;

#[test]
fn ascender_descender_match_pillow_getmetrics() {
    let cases = [
        ("AlibabaPuHuiTi-2-45-Light.otf", 240u32, 255u32, 82u32),
        ("AlibabaPuHuiTi-2-85-Bold.otf", 240, 255, 82),
        ("AlibabaPuHuiTi-2-85-Bold.otf", 260, 276, 89),
        ("Roboto-Regular.ttf", 240, 223, 59),
        ("Roboto-Medium.ttf", 260, 242, 64),
    ];
    for (file, size, asc, desc) in cases {
        let face = Face::load(&font(file), size).unwrap();
        assert_eq!(face.ascender_px(), asc, "{file}@{size} ascender");
        assert_eq!(face.descender_px(), desc, "{file}@{size} descender");
    }
}

#[test]
fn otf_and_ttf_both_rasterize() {
    let otf = Face::load(&font("AlibabaPuHuiTi-2-45-Light.otf"), 240).unwrap();
    let ttf = Face::load(&font("Roboto-Regular.ttf"), 240).unwrap();
    for (name, face) in [("OTTO/CFF", &otf), ("glyf", &ttf)] {
        let (w, h, ink) = face.probe_line("Nikon Z7 中国摄影师");
        assert!(w > 0 && h > 0, "{name} 渲染尺寸为 0");
        assert!(ink.covered > 500, "{name} 覆盖像素过少 {ink:?}，栅格化没生效");
    }
}
```

- [ ] **步骤 2：跑测试验证失败**

运行：`cd rust && cargo test -p copyleft-core --test text_metrics`
预期：编译失败 `could not find Face in store`。

- [ ] **步骤 3：写探针，把取整规则和后端选择一次跑清楚**

`examples/text_probe.rs`：

```rust
//! 一次性探针：对同一批字体打印 skrifa 原始度量与三种取整结果（floor / round / ceil），
//! 目标是找出能复现 Pillow getmetrics() 的那条规则。结论写进 NOTES.md 后删除本文件。
use copyleft_core::text::store::*;

fn main() {
    let cases = [
        ("fonts/AlibabaPuHuiTi-2-45-Light.otf", 240u32, 255u32, 82u32),
        ("fonts/AlibabaPuHuiTi-2-85-Bold.otf", 260u32, 276u32, 89u32),
        ("fonts/Roboto-Regular.ttf", 240u32, 223u32, 59u32),
        ("fonts/Roboto-Medium.ttf", 260u32, 242u32, 64u32),
    ];
    for (path, size, want_asc, want_desc) in cases {
        let raw = raw_metrics(path, size);
        println!("{path}@{size} want=({want_asc},{want_desc}) raw={raw:?} \
                  floor=({},{}) round=({},{}) ceil=({},{})",
            raw.0.floor() as u32, raw.1.floor() as u32,
            raw.0.round() as u32, raw.1.round() as u32,
            raw.0.ceil() as u32, raw.1.ceil() as u32);
    }
}
```

- [ ] **步骤 4：跑探针并记录结论**

运行：`cd rust && cargo run --example text_probe`
预期：四行输出，其中有且只有一种取整规则同时命中 `want`。把结论（哪条规则、原始值是多少、是否 `units_per_em` 归一）追加到 `rust/NOTES.md` 的「文字后端选型」小节，并记下 `tiny-skia` 路径的耗时；若 `skrifa` 读不到 CFF 轮廓（`otf_and_ttf_both_rasterize` 失败），改用规格 § 12 风险 2 的 `swash`，并在 NOTES.md 写明换的原因。

- [ ] **步骤 5：实现 `store.rs`**

```rust
// rust/crates/copyleft-core/src/text/store.rs
use std::path::Path;
use std::sync::Arc;

use crate::error::{CoreError, Result};

/// 一次 (字体文件, 字号) 的加载结果。`Arc` 让渲染期可以跨线程共享只读副本。
#[derive(Clone)]
pub struct Face {
    inner: Arc<FaceData>,
    ascender_px: u32,
    descender_px: u32,
    size_px: u32,
}

struct FaceData {
    bytes: Arc<Vec<u8>>,
    /// 字体名，用于报错信息。
    name: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct InkStats { pub covered: usize, pub x_min: i32, pub y_min: i32, pub x_max: i32, pub y_max: i32 }

impl Face {
    pub fn load(path: &Path, size_px: u32) -> Result<Face> {
        let bytes = std::fs::read(path).map_err(|e| CoreError::Font {
            path: path.display().to_string(), reason: e.to_string() })?;
        let name = path.file_name().map(|s| s.to_string_lossy().to_owned()).unwrap_or_default();
        // 先让 skrifa 解析一次，确认 CFF 与 glyf 都能打开（这一步失败 = 字体不可用）
        let font = skrifa::FontRef::new(&bytes).map_err(|e| CoreError::Font {
            path: name.clone(), reason: format!("{e:?}") })?;
        let metrics = font.metrics(skrifa::metrics::DocumentHints::Default);
        let asc = f64::from(metrics.ascender());   // 已按 size_px 归一的浮点值
        let desc = f64::from(metrics.descender());
        // 取整规则由任务 7 步骤 4 的探针确定，命中 Pillow 的 255/82、276/89、223/59、242/64
        let ascender_px = asc.ceil() as u32;
        let descender_px = desc.ceil().abs() as u32;
        Ok(Self { inner: Arc::new(FaceData { bytes: Arc::new(bytes), name }),
                  ascender_px, descender_px, size_px })
    }

    pub fn ascender_px(&self) -> u32 { self.ascender_px }
    pub fn descender_px(&self) -> u32 { self.descender_px }
    pub fn size_px(&self) -> u32 { self.size_px }
    pub fn bytes(&self) -> &[u8] { &self.inner.bytes }

    /// 渲染一行并返回 (宽, 高, 墨迹统计)。宽 = shaping 推进量，高 = max(ascender, 墨迹下沿)。
    pub fn probe_line(&self, text: &str) -> (u32, u32, InkStats) {
        crate::text::measure(self, text)
    }
}

/// 供探针使用：暴露未经取整的原始度量。
pub fn raw_metrics(path: &str, size_px: u32) -> (f64, f64) {
    let bytes = std::fs::read(path).expect("缺字体");
    let font = skrifa::FontRef::new(&bytes).expect("字体解析失败");
    let m = font.metrics(skrifa::metrics::DocumentHints::Default);
    (f64::from(m.ascender()), f64::from(m.descender()))
}
```

`metrics.ascender()` 是否已按 `size_px` 归一，取决于 `Size` 参数：skrifa 需要 `font.metrics(hints).size(Size::new(size_px))` 这一层配置。落地时按探针输出校正——**判据只有一条：四组数字必须等于 Pillow 的 `getmetrics()`**，不达标的调归一与取整，不许改期望值。

- [ ] **步骤 6：跑测试验证通过**

运行：`cd rust && cargo test -p copyleft-core --test text_metrics`
预期：两个测试 PASS。`text/measure` 此时还不存在，本步骤先让 `probe_line` 走 `render_line` 的最小版本（任务 8 实现）——因此任务 7 与任务 8 之间允许一次「先写 measure 的骨架、再在任务 8 补测试」的交叉，但 **commit 时两个任务都必须各自测试全绿**：任务 7 的 commit 只带 `ascender_descender_match_pillow_getmetrics` 通过，`otf_and_ttf_both_rasterize` 留到任务 8 步骤 5 一起点亮。

- [ ] **步骤 7：删探针 + commit**

```bash
cd rust && rm crates/copyleft-core/examples/text_probe.rs && cargo fmt && cargo clippy --all-targets -- -D warnings
cargo test -p copyleft-core --test text_metrics ascender
git add rust && git commit -m "feat(rust): 字体加载与 Pillow 度量对齐

CFF(.otf) 栅格化必须实测不能靠文档假设；ascender/descender 的取整规则
以 Pillow getmetrics 的 255/82、276/89、223/59、242/64 四组数为验收线。"
```

---

## 任务 8：`render_line`（文字 → RGBA）

**尺寸规则（附录 A 的 Pillow 实测）：** `font.getbbox(text)` 返回 `(0, top, advance, bottom)`，且 `advance == getlength`、`bottom == max(ascender, 墨迹下沿)`。Python 用它建图，所以 Rust 必须：**宽 = shaping 推进量、高 = max(ascender, 墨迹下沿)、基线在 `y = ascender`、墨迹上沿在 `y = top`**。全空格串时 `bottom == ascender`，图高恰为 ascender——这就是空槽位仍占 255 像素高的原因。

**文件：**
- 修改：`rust/crates/copyleft-core/src/text/mod.rs`、`rust/crates/copyleft-core/src/text/store.rs`
- 创建：`rust/crates/copyleft-core/tests/text_render.rs`

- [ ] **步骤 1：写失败的测试**

`tests/text_render.rs`（期望尺寸全部来自附录 A 的 Pillow `getbbox`）：

```rust
use copyleft_core::text::{parse_color, render_line};
use copyleft_core::text::store::Face;
use copyleft_core::test_support::font;

fn light() -> Face { Face::load(&font("AlibabaPuHuiTi-2-45-Light.otf"), 240).unwrap() }
fn bold() -> Face { Face::load(&font("AlibabaPuHuiTi-2-85-Bold.otf"), 260).unwrap() }
fn medium() -> Face { Face::load(&font("Roboto-Medium.ttf"), 260).unwrap() }

#[test]
fn image_size_matches_pillow_getbbox() {
    // bbox("Nikon Z7", 240) = (0, 72, 977, 258)
    let img = render_line("Nikon Z7", &light(), "#212121");
    assert_eq!((img.width(), img.height()), (977, 258));
    // bbox("gjpqy", 240) = (0, 79, 626, 304) —— 有降部时下沿超过 ascender
    let g = render_line("gjpqy", &light(), "#212121");
    assert_eq!((g.width(), g.height()), (626, 304));
    // bbox("中国摄影师", 240) = (0, 61, 1180, 281)
    let c = render_line("中国摄影师", &light(), "#212121");
    assert_eq!((c.width(), c.height()), (1180, 281));
    // bold 260：bbox("Nikon Z7") = (0, 77, 1130, 279)
    assert_eq!(size(render_line("Nikon Z7", &bold(), "#D32F2F")), (1130, 279));
    // Roboto Medium 260：bbox("Nikon Z7") = (0, 47, 1050, 245)
    assert_eq!(size(render_line("Nikon Z7", &medium(), "#212121")), (1050, 245));
}

#[test]
fn spaces_only_gives_advance_by_ascender() {
    // bbox("   ", 240) = (0, 255, 177, 255)
    let img = render_line("   ", &light(), "#212121");
    assert_eq!((img.width(), img.height()), (177, 255));
    assert!(img.pixels().all(|p| p.0[3] == 0), "三个空格必须完全透明");
}

#[test]
fn empty_content_is_replaced_by_three_spaces() {
    // utils.text_to_image 的 content == '' 分支
    assert_eq!(size(render_line("", &light(), "#212121")), (177, 255));
}

#[test]
fn ink_top_matches_pillow_bbox_top() {
    let img = render_line("Nikon Z7", &light(), "#212121");
    let first_ink = (0..img.height()).find(|y| (0..img.width()).any(|x| img.get_pixel(x, *y).0[3] > 0));
    assert_eq!(first_ink, Some(72), "墨迹上沿必须与 Pillow bbox 的 top 一致，否则整条水印垂直位置偏移");
}

#[test]
fn fill_color_is_applied_with_alpha() {
    let img = render_line("N", &light(), "#D32F2F");
    let inked = img.pixels().find(|p| p.0[3] > 200).expect("找不到实心像素");
    assert_eq!((inked.0[0], inked.0[1], inked.0[2]), (0xD3, 0x2F, 0x2F));
}

#[test]
fn parse_color_handles_hex6_and_hex8_and_junk() {
    assert_eq!(parse_color("#212121"), [0x21, 0x21, 0x21, 255]);
    assert_eq!(parse_color("#D32F2F"), [0xD3, 0x2F, 0x2F, 255]);
    assert_eq!(parse_color("#00000000"), [0, 0, 0, 0]);
    assert_eq!(parse_color("not-a-color"), [0, 0, 0, 255]);
}

fn size(img: image::RgbaImage) -> (u32, u32) { (img.width(), img.height()) }
```

- [ ] **步骤 2：跑测试验证失败**

运行：`cd rust && cargo test -p copyleft-core --test text_render`
预期：编译失败 `unresolved imports copyleft_core::text::render_line`。

- [ ] **步骤 3：实现 `text/mod.rs`**

```rust
// rust/crates/copyleft-core/src/text/mod.rs
pub mod store;

use image::RgbaImage;

pub use store::Face;

/// "#RRGGBB" / "#RRGGBBAA" → [r,g,b,a]；非法输入回落不透明黑，与 Python 的静默容错相当。
pub fn parse_color(s: &str) -> [u8; 4] {
    let hex = s.trim_start_matches('#');
    let byte = |i: usize| hex.get(i * 2..i * 2 + 2)
        .and_then(|h| u8::from_str_radix(h, 16).ok()).unwrap_or(0);
    match hex.len() {
        6 => [byte(0), byte(1), byte(2), 255],
        8 => [byte(0), byte(1), byte(2), byte(3)],
        _ => [0, 0, 0, 255],
    }
}

/// 把一行文字渲染成 RGBA 位图。尺寸与基线规则见本任务开头的说明。
pub fn render_line(content: &str, face: &Face, fill: &str) -> RgbaImage {
    let content = if content.is_empty() { "   " } else { content };
    draw(content, face, parse_color(fill))
}

/// 供 store::probe_line 使用：返回 (宽, 高, 墨迹统计)。
pub(crate) fn measure(face: &Face, text: &str) -> (u32, u32, store::InkStats) {
    let img = draw(text, face, [0, 0, 0, 255]);
    let mut stats = store::InkStats { covered: 0, x_min: i32::MAX, y_min: i32::MAX, x_max: i32::MIN, y_max: i32::MIN };
    for (x, y, p) in img.enumerate_pixels() {
        if p.0[3] > 0 {
            stats.covered += 1;
            stats.x_min = stats.x_min.min(x as i32); stats.x_max = stats.x_max.max(x as i32);
            stats.y_min = stats.y_min.min(y as i32); stats.y_max = stats.y_max.max(y as i32);
        }
    }
    (img.width(), img.height(), stats)
}
```

步骤 3 里 `render_line` 与 `measure` 都调用尚未定义的 `draw`——`draw` 在步骤 4 落地，本步骤不必先让它编译通过（先跑测试看红，是预期状态）。

```rust
fn draw(content: &str, face: &Face, fill: [u8; 4]) -> RgbaImage {
    let (paths, advance, ink_bottom) = layout(content, face);   // 见下
    let height = face.ascender_px().max(ink_bottom.ceil() as u32);
    let width = advance.ceil().max(1.0) as u32;

    let mut pixmap = tiny_skia::Pixmap::new(width, height).expect("位图尺寸非法");
    let mut paint = tiny_skia::Paint::default();
    paint.set_color_rgba8(fill[0], fill[1], fill[2], fill[3]);
    paint.anti_alias = true;
    for path in paths {
        pixmap.fill_path(&path, &paint, tiny_skia::FillRule::Winding,
                         tiny_skia::Transform::default(), None);
    }
    // tiny-skia 是 premul alpha，转回 straight alpha 的 RgbaImage
    from_premul(pixmap)
}
```

`layout()` 负责：`rustybuzz::shape` → 逐字形 `skrifa::outline::Outline` 写进 `kurbo::BezPath`（`Pen` 的四个回调映射到 `move_to/line_to/quadratic_to/cubic_to`，`close` → `close_path`）→ 平移到 `(pen_x, ascender - y_offset)`，`pen_x += glyph.advance`；同时返回所有路径的 `y` 最大值作为 `ink_bottom`。

- [ ] **步骤 4：跑测试验证通过**

运行：`cd rust && cargo test -p copyleft-core --test text_render`
预期：六个测试 PASS。`ink_top_matches_pillow_bbox_top` 若差 1–3 像素，按规格 § 12 风险 1：先查基线取整，再查 premul 转换，**不许放宽断言**。`image_size_matches_pillow_getbbox` 的宽度允许 ±2 像素（shaping 的 side bearing 差异），超出则逐字记录进 NOTES.md。

- [ ] **步骤 5：点亮任务 7 遗留的栅格化测试**

运行：`cd rust && cargo test -p copyleft-core`
预期：全绿，含 `otf_and_ttf_both_rasterize`。

- [ ] **步骤 6：commit**

```bash
cd rust && cargo fmt && cargo clippy --all-targets -- -D warnings && cargo test
git add rust && git commit -m "feat(rust): 单行文字渲染成 RGBA 位图

尺寸按 Pillow getbbox 语义（宽=advance，高=max(ascender, 墨迹下沿)），
空串走三个空格占位；这些宽高是计划 B 留白计算的直接输入。"
```

---

## 任务 9：CLI 观测命令 + 文字项对拍（计划 A 闸门）

**文件：**
- 修改：`rust/crates/copyleft-cli/src/main.rs`
- 创建：`rust/tests/exif_parity.py`、`rust/tests/parity.sh`

- [ ] **步骤 1：实现两个子命令**

```rust
// rust/crates/copyleft-cli/src/main.rs
use std::path::PathBuf;

use clap::{Parser, Subcommand};
use copyleft_core::keys::TextKey;
use copyleft_core::meta::ImageMeta;
use copyleft_core::text::{render_line, Face};

#[derive(Parser)]
#[command(name = "copyleft-cli", version)]
struct Cli { #[command(subcommand)] cmd: Cmd }

#[derive(Subcommand)]
enum Cmd {
    /// 打印一张照片的 16 个文字项（默认非等效焦距）
    Meta { photo: PathBuf, #[arg(long)] eq: bool },
    /// 渲染一行文字，打印尺寸，可选存图
    Text { font: PathBuf, #[arg(long, default_value_t = 240)] size: u32,
           #[arg(long, default_value = "#212121")] color: String,
           #[arg(long)] save: Option<PathBuf>, content: String },
}

fn main() -> std::process::ExitCode {
    let cli = Cli::parse();
    let result = match cli.cmd {
        Cmd::Meta { photo, eq } => run_meta(&photo, eq),
        Cmd::Text { font, size, color, save, content } => run_text(&font, size, &color, &content, save),
    };
    match result {
        Ok(()) => std::process::ExitCode::SUCCESS,
        Err(e) => { eprintln!("错误: {e}"); std::process::ExitCode::FAILURE }
    }
}

fn run_meta(photo: &std::path::Path, eq: bool) -> copyleft_core::error::Result<()> {
    let m = ImageMeta::load(photo, eq)?;
    println!("source\t{:?}", m.exif.source);
    println!("size\t{}x{}\torientation\t{}", m.width, m.height, m.orientation);
    for key in TextKey::ALL {
        println!("{:?}\t{:?}", key, m.text(key, Some("自定义文字")));
    }
    Ok(())
}

fn run_text(font: &std::path::Path, size: u32, color: &str, content: &str,
            save: Option<PathBuf>) -> copyleft_core::error::Result<()> {
    let face = Face::load(font, size)?;
    let img = render_line(content, &face, color);
    println!("{:?}\tx{}\ty{}", content, img.width(), img.height());
    if let Some(path) = save { img.save(path).map_err(|e| copyleft_core::error::CoreError::Other(e.to_string()))?; }
    Ok(())
}
```

`copyleft-cli/Cargo.toml` 依赖 `copyleft-core`（workspace）、`clap`、`image`（workspace）。

- [ ] **步骤 2：手测两个命令**

运行：
```bash
cd rust && cargo run -q -p copyleft-cli -- meta ../input/_DSC7969.JPG
cargo run -q -p copyleft-cli -- text --size 240 ../fonts/AlibabaPuHuiTi-2-45-Light.otf "Nikon Z7"
```
预期：第一条输出 18 行，`Param` 行是 `"145.0mm  f/2.8  1/500s  ISO800"`；第二条输出 `"Nikon Z7"  x977  y258`。

- [ ] **步骤 3：Python 侧基准脚本**

`rust/tests/exif_parity.py`（`ImageContainer` 只接受 `Path`，传 `str` 会在 `image_container.py:115` 崩，这是既有行为）：

```python
"""打印 Python 版的 16 个文字项，供与 copyleft-cli meta 逐行 diff。
用法：python rust/tests/exif_parity.py <photo> [--eq]
必须在仓库根运行（依赖 ./config.yaml 与可选的 ./exiftool.exe）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.entity.image_container import ImageContainer  # noqa: E402
from init import ITEM_LIST  # noqa: E402


def main() -> int:
    photo = Path(sys.argv[1])
    eq = '--eq' in sys.argv
    ic = ImageContainer(photo)
    ic.is_use_equivalent_focal_length(eq)
    from utils import EXIFTOOL_AVAILABLE
    print(f"source\t{'Exiftool' if EXIFTOOL_AVAILABLE else 'Standard'}")
    print(f"size\t{ic.img.width}x{ic.height}\torientation\t{ic.exif.get('Orientation', 'Rotate 0')}")
    for item in ITEM_LIST:
        element = {'name': item.value, 'is_bold': False, 'value': '自定义文字'}
        print(f'{item.value!r}\t{ic.get_attribute_str(element)!r}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
```

`copyleft-cli meta` 用 `{:?}` 打印键值，正是为了和这里的 `repr()` 直接 diff。注意 `size` 行：Python 打印的是 `exif_transpose` 之后的 `ic.img.width/height`，Rust 的 `m.width/m.height` 是按 Orientation 交换后的值，两者应当一致；orientation 一侧 Python 打印的是文本（`Horizontal (normal)`），Rust 打印的是数字，对拍脚本里按附录 B 的对照表换算。

- [ ] **步骤 4：对拍脚本与全量比对**

`rust/tests/parity.sh`：

```bash
#!/usr/bin/env bash
# 逐张样张对拍 16 个文字项：Rust 与 Python 的输出必须完全一致。
# exiftool 在场时比的是 Exiftool 通道；把 exiftool.exe 改名后再跑一次比 Standard 通道。
set -uo pipefail
cd "$(dirname "$0")/../.."
fail=0
for p in input/_DSC7969.JPG input/_DSC7976.JPG rust/fixtures/with_exif.png rust/fixtures/rotated.jpg rust/fixtures/no_exif.png; do
  [ -f "$p" ] || { echo "SKIP $p"; continue; }
  for eq in "" "--eq"; do
    (cd rust && cargo run -q -p copyleft-cli -- meta "../$p" $eq) > /tmp/r.txt
    python rust/tests/exif_parity.py "$p" $eq > /tmp/p.txt
    if diff -q /tmp/p.txt /tmp/r.txt >/dev/null; then
      echo "OK   $p ${eq:-non-eq}"
    else
      echo "DIFF $p ${eq:-non-eq}"; diff -u /tmp/p.txt /tmp/r.txt | head -12; fail=1
    fi
  done
done
exit $fail
```

运行：`bash rust/tests/parity.sh`
预期：10 行 `OK`（5 张 × 2 种焦距模式）。

再比 Standard 通道：`mv exiftool.exe exiftool.exe.bak && bash rust/tests/parity.sh; mv exiftool.exe.bak exiftool.exe`
预期：同样全 `OK`，`source` 行两边都是 `Standard`。此处 `_DSC7969.JPG` 的 `LensModel` 两边都应是 `''`（标准通道读不到 MakerNote），而 `Param` 的焦距在 `--eq` 下 Rust 与 Python 都是 `145.0`（标准通道统一 `{:.1}`），与 exiftool 通道的 `145` 不同属**既有的通道差异**，两边一致即可。

任何 `DIFF` 必须查明是 Rust 侧算错还是 Python 侧行为差异，逐条写进 `rust/NOTES.md` 的「计划 A 对拍结果」。**不许用放宽断言或过滤 diff 行的方式消除 DIFF。**

- [ ] **步骤 5：commit**

```bash
cd rust && cargo fmt && cargo clippy --all-targets -- -D warnings && cargo test
bash tests/parity.sh
git add rust && git commit -m "feat(rust): copyleft-cli meta/text 与文字项对拍

计划 A 的验收闸门：16 个文字项在 exiftool 与内置两个通道下都要与
Python 版逐行一致，DIFF 不过不进计划 B。"
```

---

## 附录 A：实测基准数据（2026-10-12）

采集命令（换样张后必须重跑）：

```bash
python - <<'PY'
from pathlib import Path
import core.entity.image_container as c, utils
p = Path('input/_DSC7969.JPG')
ic = c.ImageContainer(p)
print('dims', ic.original_width, ic.original_height)
for k in sorted(ic._param_dict): print(k, repr(ic._param_dict[k]))
ic.is_use_equivalent_focal_length(True); print('param(eq)', repr(ic.get_param_str()))
print('standard-channel dict:', {k: utils._pillow_exif(p).get(k) for k in
      ('Make','CameraModelName','ISO','FNumber','ExposureTime','FocalLength',
       'FocalLengthIn35mmFormat','DateTimeOriginal','Orientation','LensMake','LensModel')})
PY
python -c "
from PIL import ImageFont
for f,s in [('AlibabaPuHuiTi-2-45-Light.otf',240),('AlibabaPuHuiTi-2-85-Bold.otf',260),
            ('Roboto-Regular.ttf',240),('Roboto-Medium.ttf',260)]:
    ft=ImageFont.truetype('fonts/'+f,s); print(f, s, ft.getmetrics())
    for t in ['   ','Nikon Z7','gjpqy','中国摄影师']: print('  ',repr(t),ft.getbbox(t),ft.getlength(t))"
```

`input/_DSC7969.JPG`（exiftool 通道）：

| 项 | 值 |
|---|---|
| Make / Model | `NIKON CORPORATION` / `NIKON D810` |
| Lens（裸键） | `70-200mm f/2.8`（`LensID` = `AF-S Nikkor 70-200mm f/2.8G ED VR II`，`LensModel`/`LensMake` 不存在） |
| ISO / FNumber / ExposureTime | `800` / `2.8` / `1/500` |
| FocalLength / FocalLengthIn35mmFormat | `145.0 mm` / `145 mm` |
| DateTimeOriginal | `2014-01-01 08:25:54.760+0800` |
| Orientation | `Horizontal (normal)` → 1 |
| GPSPosition | 不存在（有 `GPSVersionID` 但无坐标） |
| 尺寸 / TotalPixel | `7360x4912` / `36.15 MP` |
| Param（非等效） | `145.0mm  f/2.8  1/500s  ISO800` |
| Param（等效） | `145mm  f/2.8  1/500s  ISO800` |
| Date / Datetime | `2014-01-01` / `2014-01-01 08:25` |
| LensMake_LensModel / CameraModel_LensModel | ` 70-200mm f/2.8`（前导空格）/ `NIKON D810 70-200mm f/2.8` |
| GeoInfo | `无` |

Standard 通道（无 exiftool）与 exiftool 通道的差异：`ISO` 在 `utils.py` 修正前为 `None`（修后为 `800`）、`Lens` 读不到（`LensModel` 为空）、`FocalLengthIn35mmFormat` 是 `145.0`（`{:.1}` 格式化）而非 `145`、`DateTimeOriginal` 无小数秒与时区偏移。

Pillow 字体度量与 `getbbox`（Rust 断言的期望值）：

| 字体 / 字号 | `getmetrics()` | bbox |
|---|---|---|
| AlibabaPuHuiTi-2-45-Light @240 | `(255, 82)` | `"   "`=(0,255,177,255)、`"Nikon Z7"`=(0,72,977,258)、`"gjpqy"`=(0,79,626,304)、`"中国摄影师"`=(0,61,1180,281) |
| AlibabaPuHuiTi-2-85-Bold @260 | `(276, 89)` | `"Nikon Z7"`=(0,77,1130,279)、`"   "`=(0,276,201,276) |
| Roboto-Regular @240 | `(223, 59)` | `"Nikon Z7"`=(0,43,958,225) |
| Roboto-Medium @260 | `(242, 64)` | `"Nikon Z7"`=(0,47,1050,245) |

## 附录 B：Orientation 文本 ↔ 数值对照

`utils._ORIENTATION_NAMES` 与 exiftool 打印值的对应，Rust 侧 `orientation_from` 依此实现：`Rotate 0`→1、`Rotate 180`→3、`Rotate 90 CW`→6、`Rotate 270 CW`→8；exiftool 对 1 还会打印 `Horizontal (normal)`。其余值（2/4/5/7 的镜像形态）Python 现有实现不映射，返回 `None`，Rust 保持一致，不要"顺手补全"。

## 计划 A 完成的定义

1. `cd rust && cargo test` 全绿；`cargo clippy --all-targets -- -D warnings` 无告警。
2. `bash rust/tests/parity.sh` 在 exiftool 通道与 Standard 通道下各跑一轮，两轮全部 `OK`、零 `DIFF`。
3. `utils.py` 两处 tag 修正生效：无 exiftool 时 Python 也能显示 `ISO800`。
4. `rust/NOTES.md` 记有三项：空窗口 exe 字节数（对比 123,427,746）、文字后端与取整规则选型结论、每条对拍差异的判定。
5. 计划 B 可以直接开始：`ImageMeta`（尺寸 + 16 文字项）与 `render_line`（文字位图宽高）就是布局留白计算需要的全部输入。
