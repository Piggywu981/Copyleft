//! 内置 EXIF 通道（kamadak-exif 0.6）。
//!
//! 注意 `In` 在这版只有 PRIMARY/THUMBNAIL 两个常量，ExifIFD/GPS IFD 里的字段
//! 要靠 tag 在全部字段里找，所以这里用 `get_field(PRIMARY)` 优先、再退回全量查找。
use std::fs::File;
use std::io::BufReader;
use std::path::Path;

use exif::{Exif, Field, In, Reader, Tag, Value};

use crate::error::{CoreError, Result};
use crate::exif::facts::{format_exposure, ExifFacts, ExifSource};

pub fn read(path: &Path) -> Result<ExifFacts> {
    let file = File::open(path).map_err(|e| CoreError::exif(path, e))?;
    let mut reader = BufReader::new(file);
    // 读不出 EXIF 不是错误：给空 facts，让上层继续处理这张图。
    let Ok(exif) = Reader::new().read_from_container(&mut reader) else {
        return Ok(ExifFacts::empty(ExifSource::Standard));
    };
    Ok(facts_from(&exif))
}

/// 字段映射独立成函数：容器解析与 raw TIFF 块两条来源都能复用。
pub fn facts_from(exif: &Exif) -> ExifFacts {
    // 0.6 的 In 只有 PRIMARY/THUMBNAIL，ExifIFD 与 GPS IFD 的字段得扫全部字段找。
    let find = |tag| match exif.get_field(tag, In::PRIMARY) {
        Some(f) => Some(f),
        None => exif.fields().find(|f| f.tag == tag),
    };

    // Python 的 Pillow 通道只往字典里塞 `LensModel` 一个键，所以 `Lens`/`LensID`
    // 那两条备用查找在这条通道里永远命中不了；这里刻意不做增强，保持两边一致，
    // 镜头全名要靠 exiftool 通道拿。
    let lens_model = find(Tag::LensModel).map(ascii).unwrap_or_default();

    let facts = ExifFacts {
        make: find(Tag::Make).map(ascii).unwrap_or_default(),
        model: find(Tag::Model).map(ascii).unwrap_or_default(),
        lens_model,
        lens_make: find(Tag::LensMake).map(ascii).unwrap_or_default(),
        exposure: find(Tag::ExposureTime)
            .and_then(rational_pair)
            .map(|(n, d)| format_exposure(n, d) + "s")
            .unwrap_or_default(),
        f_number: find(Tag::FNumber)
            .and_then(first_f64)
            .map(|v| format!("{v:.1}"))
            .unwrap_or_default(),
        iso: find(Tag::PhotographicSensitivity)
            .and_then(|f| f.value.get_uint(0))
            .map(|v| v.to_string())
            .unwrap_or_default(),
        focal_display: find(Tag::FocalLength)
            .and_then(first_f64)
            .map(|v| format!("{v:.1}"))
            .unwrap_or_default(),
        focal_35_display: find(Tag::FocalLengthIn35mmFilm)
            .and_then(first_f64)
            .map(|v| format!("{v:.1}"))
            .unwrap_or_default(),
        date_time_original: find(Tag::DateTimeOriginal)
            .map(ascii)
            .filter(|s| !s.is_empty())
            .map(|s| normalize_datetime(&s)),
        orientation: find(Tag::Orientation)
            .and_then(|f| f.value.get_uint(0))
            .map(|v| v as u16),
        gps_position: gps(exif),
        raw_app1: None,
        source: ExifSource::Standard,
    };
    facts.with_display_defaults()
}

fn ascii(field: &Field) -> String {
    match &field.value {
        Value::Ascii(parts) => parts
            .first()
            .map(|b| {
                String::from_utf8_lossy(b)
                    .trim_end_matches('\0')
                    .trim()
                    .to_owned()
            })
            .unwrap_or_default(),
        // ascii() 只服务于 Make/Model/Lens*/GPSRef 这类字符串标签；
        // 数值型标签走 first_f64 / get_uint，落到这里说明用法错了，给空串而不是编造格式。
        _ => String::new(),
    }
}

fn first_f64(field: &Field) -> Option<f64> {
    match &field.value {
        Value::Rational(v) => v.first().map(|r| r.to_f64()),
        Value::SRational(v) => v.first().map(|r| r.to_f64()),
        _ => field.value.get_uint(0).map(|v| v as f64),
    }
}

fn rational_pair(field: &Field) -> Option<(u32, u32)> {
    let Value::Rational(v) = &field.value else {
        return None;
    };
    let r = v.first()?;
    Some((r.num, r.denom))
}

/// EXIF 原生 `2014:01:01 08:25:54` → `2014-01-01 08:25:54`，对齐 exiftool `-d` 的输出形态。
fn normalize_datetime(s: &str) -> String {
    match s.split_once(' ') {
        Some((date, time)) => format!("{} {time}", date.replace(':', "-")),
        None => s.to_owned(),
    }
}

/// 拼成 exiftool `GPSPosition` 的同形态：`46 deg 55' 20.88" N, 7 deg 13' 36.72" E`
fn gps(exif: &Exif) -> Option<String> {
    let find = |tag| exif.fields().find(|f| f.tag == tag);
    let lat = find(Tag::GPSLatitude).and_then(rational_triple)?;
    let lon = find(Tag::GPSLongitude).and_then(rational_triple)?;
    let lat_ref = find(Tag::GPSLatitudeRef).map(ascii).unwrap_or_default();
    let lon_ref = find(Tag::GPSLongitudeRef).map(ascii).unwrap_or_default();
    if lat_ref.is_empty() || lon_ref.is_empty() {
        return None;
    }
    Some(format!(
        "{}, {}",
        format_position(&lat, &lat_ref),
        format_position(&lon, &lon_ref)
    ))
}

fn rational_triple(field: &Field) -> Option<[f64; 3]> {
    let Value::Rational(v) = &field.value else {
        return None;
    };
    if v.len() < 3 {
        return None;
    }
    Some([v[0].to_f64(), v[1].to_f64(), v[2].to_f64()])
}

/// 度取整、分取整、秒保留两位，与 exiftool 的打印一致。
fn format_position(parts: &[f64; 3], hemi: &str) -> String {
    format!(
        "{} deg {}' {:.2}\" {}",
        parts[0] as i32, parts[1] as i32, parts[2], hemi
    )
}
