//! `config.yaml` 的读写层。schema 与 Python 版完全兼容，容错行为逐条对齐 `config.py`。
use std::collections::BTreeMap;
use std::path::Path;

use serde::{Deserialize, Serialize};

use crate::error::{CoreError, Result};
use crate::keys::{LayoutId, TextKey};

pub const DEFAULT_LAYOUT: LayoutId = LayoutId::WatermarkLeftLogo;
pub const DEFAULT_COLOR: &str = "#ffffff";
pub const ELEMENT_COLOR_FALLBACK: &str = "#212121";

/// 四个角落槽位。`BTreeMap` 的键序即保存后的字母序，与 `yaml.dump` 一致。
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Slot {
    LeftTop,
    LeftBottom,
    RightTop,
    RightBottom,
}

pub const ALL_SLOTS: [Slot; 4] = [
    Slot::LeftTop,
    Slot::RightTop,
    Slot::LeftBottom,
    Slot::RightBottom,
];

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Element {
    pub is_bold: bool,
    #[serde(default)]
    pub color: Option<String>,
    #[serde(default)]
    pub name: Option<String>,
    #[serde(default)]
    pub value: Option<String>,
}

impl Element {
    /// `config.py` 里 color 缺失回落 `#212121`。
    pub fn color(&self) -> &str {
        self.color.as_deref().unwrap_or(ELEMENT_COLOR_FALLBACK)
    }

    pub fn is_bold(&self) -> bool {
        self.is_bold
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Layout {
    #[serde(default, rename = "type")]
    pub layout_type: Option<String>,
    #[serde(default)]
    pub background_color: Option<String>,
    #[serde(default)]
    pub logo_enable: bool,
    #[serde(default)]
    pub logo_position: Option<String>,
    pub elements: BTreeMap<Slot, Element>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Base {
    pub font: String,
    pub bold_font: String,
    pub alternative_font: String,
    pub alternative_bold_font: String,
    pub font_size: u8,
    pub bold_font_size: u8,
    pub input_dir: String,
    pub output_dir: String,
    pub quality: u8,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Flag {
    #[serde(default)]
    pub enable: bool,
}

/// `global.focal_length` 的字段名与其它 Flag 不同。
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct FocalLength {
    #[serde(default)]
    pub use_equivalent_focal_length: bool,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct WhiteMargin {
    #[serde(default)]
    pub enable: bool,
    #[serde(default)]
    pub width: i32,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Global {
    pub focal_length: FocalLength,
    pub padding_with_original_ratio: Flag,
    pub shadow: Flag,
    pub white_margin: WhiteMargin,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct LogoEntry {
    #[serde(default)]
    pub id: String,
    pub path: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Logo {
    pub default: LogoEntry,
    pub makes: BTreeMap<String, LogoEntry>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Config {
    pub base: Base,
    pub global: Global,
    pub layout: Layout,
    pub logo: Logo,
    /// 兜住未知顶层键，避免重写配置时把用户的额外字段吞掉。
    #[serde(flatten, default)]
    pub extra: BTreeMap<String, serde_yaml::Value>,
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
        std::fs::write(p, text)
            .map_err(|e| CoreError::Other(format!("写入配置失败 {}: {e}", p.display())))
    }

    /// `config.py: get_layout_type()`——`None` 与字面量 `"null"` 都回落默认布局。
    pub fn layout_type(&self) -> LayoutId {
        self.layout
            .layout_type
            .as_deref()
            .filter(|s| *s != "null")
            .and_then(LayoutId::parse)
            .unwrap_or(DEFAULT_LAYOUT)
    }

    /// `config.py: get_element_name()`
    pub fn slot_name(&self, slot: Slot) -> TextKey {
        self.layout
            .elements
            .get(&slot)
            .and_then(|e| e.name.as_deref())
            .filter(|s| *s != "null")
            .and_then(TextKey::parse)
            .unwrap_or(TextKey::None)
    }

    pub fn element(&self, slot: Slot) -> Option<&Element> {
        self.layout.elements.get(&slot)
    }

    /// `main.py: _initial_custom_text()`——取第一个 Custom 槽位的 value。
    pub fn custom_text(&self) -> String {
        ALL_SLOTS
            .into_iter()
            .filter(|s| self.slot_name(*s) == TextKey::Custom)
            .find_map(|s| self.layout.elements.get(&s).and_then(|e| e.value.clone()))
            .unwrap_or_default()
    }

    /// `config.py: set_custom_text()`——更新所有 Name 为 Custom 的槽位。
    pub fn set_custom_text(&mut self, value: &str) {
        for slot in ALL_SLOTS {
            if let Some(e) = self.layout.elements.get_mut(&slot) {
                if e.name.as_deref() == Some("Custom") {
                    e.value = Some(value.to_owned());
                }
            }
        }
    }

    /// `config.py: set_element_name()` + `set_custom()`
    pub fn set_element_name(&mut self, slot: Slot, key: TextKey) {
        let Some(e) = self.layout.elements.get_mut(&slot) else {
            return;
        };
        if key == TextKey::Custom {
            e.name = Some("Custom".into());
            e.value.get_or_insert_with(String::new);
        } else {
            e.name = Some(key.as_str().to_owned());
        }
    }

    pub fn set_layout(&mut self, id: LayoutId) {
        self.layout.layout_type = Some(id.as_str().to_owned());
    }

    /// `config.py: get_font_size()`——越界一律回落 240。
    pub fn font_size_px(&self) -> u32 {
        match self.base.font_size {
            2 => 250,
            3 => 300,
            _ => 240,
        }
    }

    /// `config.py: get_bold_font_size()`——越界回落 260。
    pub fn bold_font_size_px(&self) -> u32 {
        match self.base.bold_font_size {
            2 => 290,
            3 => 320,
            _ => 260,
        }
    }

    /// `config.py: get_font_padding_level()`——两档各自钳到 1..=3 后求和。
    pub fn font_padding_level(&self) -> u32 {
        let clamped = |v: u8| if (1..=3).contains(&v) { v as u32 } else { 1 };
        clamped(self.base.bold_font_size) + clamped(self.base.font_size)
    }

    /// `config.py: get_white_margin_width()`
    pub fn white_margin_width(&self) -> i32 {
        self.global.white_margin.width.clamp(0, 30)
    }

    pub fn set_white_margin_width(&mut self, w: i32) {
        self.global.white_margin.width = w;
    }

    pub fn quality(&self) -> u8 {
        self.base.quality
    }

    pub fn set_quality(&mut self, q: u8) {
        self.base.quality = q;
    }

    pub fn background_color(&self) -> String {
        self.layout
            .background_color
            .clone()
            .unwrap_or_else(|| DEFAULT_COLOR.to_owned())
    }

    pub fn set_background_color(&mut self, c: &str) {
        self.layout.background_color = Some(c.to_owned());
    }

    pub fn logo_enabled(&self) -> bool {
        self.layout.logo_enable
    }

    pub fn set_logo_enabled(&mut self, on: bool) {
        self.layout.logo_enable = on;
    }

    pub fn is_logo_left(&self) -> bool {
        self.layout.logo_position.as_deref() == Some("left")
    }

    pub fn set_logo_left(&mut self) {
        self.layout.logo_position = Some("left".into());
    }

    pub fn set_logo_right(&mut self) {
        self.layout.logo_position = Some("right".into());
    }

    pub fn use_equivalent_focal_length(&self) -> bool {
        self.global.focal_length.use_equivalent_focal_length
    }

    pub fn set_use_equivalent_focal_length(&mut self, on: bool) {
        self.global.focal_length.use_equivalent_focal_length = on;
    }

    pub fn shadow_enabled(&self) -> bool {
        self.global.shadow.enable
    }

    pub fn set_shadow(&mut self, on: bool) {
        self.global.shadow.enable = on;
    }

    pub fn white_margin_enabled(&self) -> bool {
        self.global.white_margin.enable
    }

    pub fn set_white_margin(&mut self, on: bool) {
        self.global.white_margin.enable = on;
    }

    pub fn padding_with_original_ratio_enabled(&self) -> bool {
        self.global.padding_with_original_ratio.enable
    }

    pub fn set_padding_with_original_ratio(&mut self, on: bool) {
        self.global.padding_with_original_ratio.enable = on;
    }

    pub fn input_dir(&self) -> String {
        self.base.input_dir.clone()
    }

    pub fn set_input_dir(&mut self, d: &str) {
        self.base.input_dir = d.to_owned();
    }

    pub fn output_dir(&self) -> String {
        self.base.output_dir.clone()
    }

    pub fn set_output_dir(&mut self, d: &str) {
        self.base.output_dir = d.to_owned();
    }

    pub fn font_path(&self) -> &str {
        &self.base.font
    }

    pub fn bold_font_path(&self) -> &str {
        &self.base.bold_font
    }

    pub fn alternative_font_path(&self) -> &str {
        &self.base.alternative_font
    }

    pub fn alternative_bold_font_path(&self) -> &str {
        &self.base.alternative_bold_font
    }

    pub fn default_logo_path(&self) -> &str {
        &self.logo.default.path
    }

    pub fn logo_makes(&self) -> &BTreeMap<String, LogoEntry> {
        &self.logo.makes
    }
}
