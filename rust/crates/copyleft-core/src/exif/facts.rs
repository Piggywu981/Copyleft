//! 两个 EXIF 通道共用的归一化结果。
use serde::{Deserialize, Serialize};

/// Python 侧 `DEFAULT_VALUE`，缺失字段直接进显示串（`ISO--`、`--mm`）。
pub const DEFAULT_VALUE: &str = "--";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ExifSource {
    Exiftool,
    Standard,
    Empty,
}

impl ExifSource {
    /// 对拍输出用的稳定名字，与 Python 侧 exif_parity.py 的写法一致。
    pub fn name(self) -> &'static str {
        match self {
            ExifSource::Exiftool => "Exiftool",
            ExifSource::Standard => "Standard",
            ExifSource::Empty => "Empty",
        }
    }
}

/// 显示就绪的 EXIF：两个通道都填它，下游不再处理格式差异。
///
/// 字段存的是**最终显示串**而不是数值，因为两条通道给的同一条信息形态不同
/// （exiftool 打 `145 mm`、内置解析格式化 `145.0 mm`），存数值再渲染会抹平这个差异，
/// 而对拍要求两边逐字一致。
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ExifFacts {
    pub make: String,
    pub model: String,
    /// 取值顺序 LensModel → Lens → LensID，与 `ExifId.LENS_MODEL` 一致。
    pub lens_model: String,
    pub lens_make: String,
    /// 已含 `s` 后缀（`1/500s`）；缺失时是 `--`（Python 的默认值不带后缀）。
    pub exposure: String,
    pub f_number: String,
    pub iso: String,
    /// 原样保留匹配到的数字串：`145.0`，缺失时 `--`。
    pub focal_display: String,
    pub focal_35_display: String,
    /// 规范化到 `YYYY-MM-DD HH:MM:SS`；`None` 表示 EXIF 里没有有效时间。
    pub date_time_original: Option<String>,
    pub orientation: Option<u16>,
    /// exiftool 的 `GPSPosition` 原文，或标准通道拼出的同形态串。
    pub gps_position: Option<String>,
    /// 写回用的原始 EXIF（TIFF 结构，不含 `Exif\0\0` 前缀）。计划 B 填充。
    pub raw_app1: Option<Vec<u8>>,
    pub source: ExifSource,
}

impl ExifFacts {
    pub fn empty(source: ExifSource) -> Self {
        Self {
            make: String::new(),
            model: String::new(),
            lens_model: String::new(),
            lens_make: String::new(),
            exposure: DEFAULT_VALUE.into(),
            f_number: DEFAULT_VALUE.into(),
            iso: DEFAULT_VALUE.into(),
            focal_display: DEFAULT_VALUE.into(),
            focal_35_display: DEFAULT_VALUE.into(),
            date_time_original: None,
            orientation: None,
            gps_position: None,
            raw_app1: None,
            source,
        }
    }

    /// 空串按 Python 的 `default_value` 回落成 `--`。相机名等字段不受影响
    /// （Python 那侧它们缺失时就是空串）。
    pub fn with_display_defaults(mut self) -> Self {
        for s in [
            &mut self.exposure,
            &mut self.f_number,
            &mut self.iso,
            &mut self.focal_display,
            &mut self.focal_35_display,
        ] {
            if s.is_empty() {
                *s = DEFAULT_VALUE.to_owned();
            }
        }
        self
    }
}

/// 复刻 `utils._fmt_exposure_time`：≥1 秒直接给秒数，<1 秒给 `1/N`。
pub fn format_exposure(numerator: u32, denominator: u32) -> String {
    if denominator == 0 || numerator == 0 {
        return String::new();
    }
    let value = numerator as f64 / denominator as f64;
    if value <= 0.0 {
        return String::new();
    }
    if value >= 1.0 {
        if denominator == 1 {
            return numerator.to_string();
        }
        return format_g(value);
    }
    format!("1/{}", round_half_even(1.0 / value))
}

/// Python 的 `round()` 是银行家舍入（半数取偶），Rust 的 `f64::round` 是半数远离零。
/// 0.4 秒这条路径会撞上：`1/0.4 = 2.5`，Python 给 2、Rust 原生给 3。
fn round_half_even(x: f64) -> i64 {
    let floor = x.floor();
    let frac = x - floor;
    if (frac - 0.5).abs() < 1e-9 {
        let f = floor as i64;
        if f % 2 == 0 {
            f
        } else {
            f + 1
        }
    } else {
        x.round() as i64
    }
}

/// 对应 `f"{x:g}"`：整数值不带小数点。
fn format_g(x: f64) -> String {
    if x == x.trunc() {
        format!("{}", x as i64)
    } else {
        format!("{x}")
    }
}
