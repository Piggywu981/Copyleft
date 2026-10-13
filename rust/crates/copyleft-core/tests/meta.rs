use copyleft_core::exif::{tool, ExiftoolBinary};
use copyleft_core::keys::TextKey;
use copyleft_core::meta::{geo_from_position, parse_photo_date, ImageMeta};
use copyleft_core::test_support::{fixture, photo, repo_root};

/// 仓库根放了 exiftool.exe，但集成测试的 CWD 在 crate 目录，所以显式按仓库根探测。
fn exiftool_channel() -> Option<ExiftoolBinary> {
    tool::locate_from(&[repo_root()]).map(|p| ExiftoolBinary(Some(p)))
}

fn standard_channel() -> ExiftoolBinary {
    // 探测结果为 None 时，read_with 会走内置解析
    ExiftoolBinary(None)
}

fn meta_with(tool: &dyn copyleft_core::exif::ExifTool, eq: bool, p: &std::path::Path) -> ImageMeta {
    ImageMeta::load_with(p, eq, tool).unwrap()
}

#[test]
fn exiftool_channel_matches_python() {
    copyleft_core::require_samples!();
    let Some(tool) = exiftool_channel() else {
        eprintln!("仓库根没有 exiftool.exe，跳过");
        return;
    };
    let m = meta_with(&tool, false, &photo("_DSC7969.JPG"));
    assert_eq!(
        m.exif.source,
        copyleft_core::exif::facts::ExifSource::Exiftool
    );
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
    assert_eq!(
        m.text(TextKey::Param, None),
        "145.0mm  f/2.8  1/500s  ISO800"
    );

    // 等效焦距时换成 35mm 值，exiftool 打的是 "145 mm" → "145"（没有 .0）
    let eq = meta_with(&tool, true, &photo("_DSC7969.JPG"));
    assert_eq!(
        eq.text(TextKey::Param, None),
        "145mm  f/2.8  1/500s  ISO800"
    );

    assert_eq!(
        m.text(TextKey::CameraMakeCameraModel, None),
        "NIKON CORPORATION NIKON D810"
    );
    assert_eq!(m.text(TextKey::DateFilename, None), "2014-01-01 _DSC7969");
    assert_eq!(
        m.text(TextKey::DatetimeFilename, None),
        "2014-01-01 08:25 _DSC7969"
    );
    // lens_make 缺失 → Python 产出前导空格，原样保留
    assert_eq!(m.text(TextKey::LensMakeLensModel, None), " 70-200mm f/2.8");
    assert_eq!(
        m.text(TextKey::CameraModelLensModel, None),
        "NIKON D810 70-200mm f/2.8"
    );
}

#[test]
fn standard_channel_matches_python_fallback_and_differs_documentably() {
    copyleft_core::require_samples!();
    let tool = standard_channel();
    let m = meta_with(&tool, false, &photo("_DSC7969.JPG"));
    assert_eq!(
        m.exif.source,
        copyleft_core::exif::facts::ExifSource::Standard
    );
    assert_eq!(m.text(TextKey::Model, None), "NIKON D810");
    assert_eq!(m.text(TextKey::Date, None), "2014-01-01");
    assert_eq!(m.text(TextKey::TotalPixel, None), "36.15 MP");
    assert_eq!(
        m.text(TextKey::Param, None),
        "145.0mm  f/2.8  1/500s  ISO800"
    );
    // 与 exiftool 通道的两处既有差异：标准通道读不到 MakerNote 里的镜头，
    // 且 35mm 焦距按 {:.1} 格式化所以带 .0。Python 也一样，不是 Rust 的偏差。
    assert_eq!(m.text(TextKey::LensModel, None), "");
    let eq = meta_with(&tool, true, &photo("_DSC7969.JPG"));
    assert_eq!(
        eq.text(TextKey::Param, None),
        "145.0mm  f/2.8  1/500s  ISO800"
    );
}

#[test]
fn dimensions_and_orientation() {
    copyleft_core::require_samples!();
    let m = ImageMeta::load(&photo("_DSC7969.JPG"), false).unwrap();
    assert_eq!((m.original_width, m.original_height), (7360, 4912));
    assert_eq!(m.orientation, 1);
    assert_eq!((m.width, m.height), (7360, 4912));
    assert_eq!(m.ratio(), 7360.0 / 4912.0);

    // 派生样张：像素已是 4912x7360，标签写 6，摆正后应换回 7360x4912
    let r = ImageMeta::load(&fixture("rotated.jpg"), false).unwrap();
    assert_eq!(r.orientation, 6);
    assert_eq!((r.original_width, r.original_height), (4912, 7360));
    assert_eq!((r.width, r.height), (r.original_height, r.original_width));
}

#[test]
fn missing_exif_falls_back_to_file_mtime() {
    copyleft_core::require_samples!();
    let m = ImageMeta::load(&fixture("no_exif.png"), false).unwrap();
    let date = m.text(TextKey::Date, None);
    assert_eq!(
        date.len(),
        10,
        "应为 mtime 格式化的 YYYY-MM-DD，实际 {date:?}"
    );
    assert!(date.starts_with("20"), "mtime 日期不合理：{date:?}");
    assert_eq!(m.text(TextKey::Param, None), "--mm  f/--  --  ISO--");
    assert_eq!(m.text(TextKey::Model, None), "");
}

#[test]
fn exif_time_is_wall_clock_not_tz_converted() {
    // Python 用 dateutil 解析出带 +0800 的对象再 strftime，输出挂钟时间、不做换算。
    // 换成别的机器时区也不该差几个小时，所以这条必须钉住。
    let with_tz = parse_photo_date("2014-01-01 08:25:54.000+0800").unwrap();
    let naive = parse_photo_date("2014-01-01 08:25:54").unwrap();
    assert_eq!(
        with_tz.format("%Y-%m-%d %H:%M").to_string(),
        naive.format("%Y-%m-%d %H:%M").to_string()
    );
    assert_eq!(parse_photo_date("garbage"), None);
    assert_eq!(parse_photo_date(""), None);
}

#[test]
fn gps_abbr_format_from_exiftool_position_shape() {
    let pos = "46 deg 55' 20.88\" N, 7 deg 13' 36.72\" E";
    assert_eq!(geo_from_position(pos).as_deref(), Some("46°55'N 7°13'E"));
    assert_eq!(geo_from_position("nonsense"), None);
    assert_eq!(geo_from_position("46 deg 55' 20.88\" N"), None);
}
