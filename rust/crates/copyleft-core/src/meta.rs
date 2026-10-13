//! `ImageContainer` 的对应物：把 EXIF 与图像尺寸整理成 16 个文字项。
use std::path::{Path, PathBuf};

use chrono::{DateTime, Local, NaiveDateTime};

use crate::error::{CoreError, Result};
use crate::exif::{self, facts::ExifFacts};
use crate::keys::TextKey;

pub const NO_TEXT: &str = "无";

#[derive(Debug, Clone)]
pub struct ImageMeta {
    pub path: PathBuf,
    pub exif: ExifFacts,
    /// 未摆正的宽高，`padding_to_original_ratio` 与 `TotalPixel` 用它。
    pub original_width: u32,
    pub original_height: u32,
    /// 按 Orientation 交换后的宽高，即像素摆正后的尺寸。
    pub width: u32,
    pub height: u32,
    pub orientation: u16,
    pub use_equivalent_focal_length: bool,
    /// 挂钟时间：EXIF 声明的是拍摄地的本地时间，不做时区换算。
    date: NaiveDateTime,
}

impl ImageMeta {
    /// 用本机探测到的 exiftool（若有）读取。
    pub fn load(path: &Path, use_equivalent_focal_length: bool) -> Result<Self> {
        use crate::exif::{tool, ExiftoolBinary};
        Self::load_with(
            path,
            use_equivalent_focal_length,
            &ExiftoolBinary(tool::locate()),
        )
    }

    /// 只读 EXIF 与图像头尺寸，不解码像素（像素由布局层自己 open）。
    /// 通道做成注入点：不然测试就只能依赖本机装没装 exiftool。
    pub fn load_with(
        path: &Path,
        use_equivalent_focal_length: bool,
        tool: &dyn crate::exif::ExifTool,
    ) -> Result<Self> {
        let exif = exif::read_with(path, tool)?;
        let (w, h) = image::image_dimensions(path).map_err(|e| CoreError::ImageOpen {
            path: path.display().to_string(),
            source: e,
        })?;
        let orientation = exif.orientation.unwrap_or(1);
        let (dw, dh) = rotated_dims(w, h, orientation);
        let date = exif
            .date_time_original
            .as_deref()
            .and_then(parse_photo_date)
            // 无 EXIF 时间时用文件修改时间，避免显示成处理时刻
            .or_else(|| file_date(path))
            .unwrap_or_else(|| Local::now().naive_local());
        Ok(Self {
            path: path.to_path_buf(),
            exif,
            original_width: w,
            original_height: h,
            width: dw,
            height: dh,
            orientation,
            use_equivalent_focal_length,
            date,
        })
    }

    /// `image_container.get_attribute_str()`：Custom 取 element.value，其余查表。
    pub fn text(&self, key: TextKey, custom: Option<&str>) -> String {
        match key {
            TextKey::Model => self.exif.model.clone(),
            TextKey::Make => self.exif.make.clone(),
            TextKey::LensModel => self.exif.lens_model.clone(),
            TextKey::Param => self.param_str(),
            TextKey::Datetime => self.format("%Y-%m-%d %H:%M"),
            TextKey::Date => self.format("%Y-%m-%d"),
            TextKey::Custom => custom
                .map(str::to_owned)
                .unwrap_or_else(|| NO_TEXT.to_owned()),
            TextKey::None => String::new(),
            TextKey::TotalPixel => megapixel(self.original_width, self.original_height),
            TextKey::Filename => self.file_stem(),
            TextKey::LensMakeLensModel => join_space(&self.exif.lens_make, &self.exif.lens_model),
            TextKey::CameraModelLensModel => join_space(&self.exif.model, &self.exif.lens_model),
            TextKey::CameraMakeCameraModel => join_space(&self.exif.make, &self.exif.model),
            TextKey::DateFilename => join_space(&self.format("%Y-%m-%d"), &self.file_stem()),
            TextKey::DatetimeFilename => {
                join_space(&self.format("%Y-%m-%d %H:%M"), &self.file_stem())
            }
            TextKey::GeoInfo => self.geo(),
        }
    }

    pub fn ratio(&self) -> f64 {
        self.width as f64 / self.height as f64
    }

    pub fn original_ratio(&self) -> f64 {
        self.original_width as f64 / self.original_height as f64
    }

    fn file_stem(&self) -> String {
        self.path
            .file_stem()
            .map(|s| s.to_string_lossy().to_string())
            .unwrap_or_default()
    }

    /// `image_container.get_param_str()`：两个空格分隔，并保留
    /// `--mm` / `f/--` / `ISO--` 这三处既有怪癖（快门缺失时不带 s）。
    fn param_str(&self) -> String {
        let focal = if self.use_equivalent_focal_length
            && self.exif.focal_35_display != crate::exif::facts::DEFAULT_VALUE
        {
            &self.exif.focal_35_display
        } else {
            &self.exif.focal_display
        };
        format!(
            "{}mm  f/{}  {}  ISO{}",
            focal, self.exif.f_number, self.exif.exposure, self.exif.iso
        )
    }

    fn format(&self, spec: &str) -> String {
        self.date.format(spec).to_string()
    }

    /// GPS：exiftool 的 GPSPosition 或标准通道拼好的同形态串；都没有则「无」。
    fn geo(&self) -> String {
        self.exif
            .gps_position
            .as_deref()
            .and_then(geo_from_position)
            .unwrap_or_else(|| NO_TEXT.to_owned())
    }
}

/// `"46 deg 55' 20.88\" N, 7 deg 13' 36.72\" E"` → `"46°55'N 7°13'E"`
/// 对应 `utils.extract_gps_lat_and_long`：度取整、分取整、丢掉秒。
pub fn geo_from_position(pos: &str) -> Option<String> {
    let (lat, lon) = pos.split_once(", ")?;
    Some(format!("{} {}", abbr_dms(lat)?, abbr_dms(lon)?))
}

fn abbr_dms(s: &str) -> Option<String> {
    let mut it = s.split_whitespace();
    let deg = it.next()?;
    let min = it.find(|t| t.ends_with('\''))?.trim_end_matches('\'');
    let hemi = s.split_whitespace().next_back()?;
    if !["N", "S", "E", "W"].contains(&hemi) {
        return None;
    }
    Some(format!("{deg}°{min}'{hemi}"))
}

fn join_space(a: &str, b: &str) -> String {
    format!("{a} {b}")
}

fn megapixel(w: u32, h: u32) -> String {
    format!("{:.2} MP", (w as u64 * h as u64) as f64 / 1_000_000.0)
}

fn rotated_dims(w: u32, h: u32, orientation: u16) -> (u32, u32) {
    match orientation {
        5 | 6 | 7 | 8 => (h, w),
        _ => (w, h),
    }
}

/// 两条通道的日期形态都要吃：exiftool 带 `-d` 时是小数秒加偏移，内置解析是纯时间。
/// `naive_local()` 取的是该偏移下的挂钟时间，等价于 Python 的 `strftime`——不做时区换算。
pub fn parse_photo_date(raw: &str) -> Option<NaiveDateTime> {
    if raw.is_empty() {
        return None;
    }
    if let Ok(d) = DateTime::parse_from_str(raw, "%Y-%m-%d %H:%M:%S%.f%z") {
        return Some(d.naive_local());
    }
    NaiveDateTime::parse_from_str(raw, "%Y-%m-%d %H:%M:%S")
        .or_else(|_| NaiveDateTime::parse_from_str(raw, "%Y-%m-%d %H:%M"))
        .ok()
}

fn file_date(path: &Path) -> Option<NaiveDateTime> {
    let t = std::fs::metadata(path).ok()?.modified().ok()?;
    Some(DateTime::<Local>::from(t).naive_local())
}
