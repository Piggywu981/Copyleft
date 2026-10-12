use copyleft_core::exif::facts::ExifSource;
use copyleft_core::exif::tool;
use copyleft_core::test_support::photo;

#[test]
fn maps_nikon_json_onto_facts() {
    // 真实 -j 输出里是 Model 而非 CameraModelName（纯文本输出相反），两种都要能吃下。
    // ISO/FNumber 是 JSON 数字，不是字符串。
    let json = r#"[{"SourceFile":"x","Make":"NIKON CORPORATION","Model":"NIKON D810",
      "Lens":"70-200mm f/2.8","LensID":"AF-S Nikkor 70-200mm f/2.8G ED VR II",
      "ISO":800,"FNumber":2.8,"ExposureTime":"1/500","FocalLength":"145.0 mm",
      "FocalLengthIn35mmFormat":"145 mm","DateTimeOriginal":"2014-01-01 08:25:54.000+0800",
      "Orientation":"Horizontal (normal)"}]"#;
    let f = tool::facts_from_json_str(json).unwrap();
    assert_eq!(f.make, "NIKON CORPORATION");
    assert_eq!(f.model, "NIKON D810");
    // 顺序必须 LensModel → Lens → LensID：这台机器 LensModel 缺失，取到 Lens。
    // 把 LensID 排前面会错拿成长名 "AF-S Nikkor 70-200mm f/2.8G ED VR II"。
    assert_eq!(f.lens_model, "70-200mm f/2.8");
    assert_eq!(f.iso, "800");
    assert_eq!(f.f_number, "2.8");
    assert_eq!(f.exposure, "1/500s");
    assert_eq!(f.focal_display, "145.0");
    // exiftool 打 "145 mm"，Python 的正则抓到 "145"（不带 .0）
    assert_eq!(f.focal_35_display, "145");
    assert_eq!(
        f.date_time_original.as_deref(),
        Some("2014-01-01 08:25:54.000+0800")
    );
    assert_eq!(f.orientation, Some(1));
    assert_eq!(f.lens_make, "");
    assert_eq!(f.source, ExifSource::Exiftool);
}

#[test]
fn prefers_camera_model_name_when_present() {
    let json = r#"[{"Model":"D810","CameraModelName":"NIKON D810"}]"#;
    let f = tool::facts_from_json_str(json).unwrap();
    assert_eq!(
        f.model, "NIKON D810",
        "与 Python 一致：CameraModelName 优先"
    );
}

#[test]
fn gps_position_passes_through_and_non_ascii_is_dropped() {
    let json = r#"[{"GPSPosition":"46 deg 55' 20.88\" N, 7 deg 13' 36.72\" E",
                   "Model":"中文型号 Nikon"}]"#;
    let f = tool::facts_from_json_str(json).unwrap();
    assert_eq!(
        f.gps_position.as_deref(),
        Some("46 deg 55' 20.88\" N, 7 deg 13' 36.72\" E")
    );
    // Python 的 _exiftool_exif 会滤掉非 ASCII 字符，这里保持同样行为
    assert_eq!(f.model, " Nikon");
}

#[test]
fn orientation_text_maps_to_numbers_like_pillow_names() {
    for (text, want) in [
        ("Horizontal (normal)", 1u16),
        ("Rotate 180", 3),
        ("Rotate 90 CW", 6),
        ("Rotate 270 CW", 8),
    ] {
        let json = format!(r#"[{{"Orientation":"{text}"}}]"#);
        let f = tool::facts_from_json_str(&json).unwrap();
        assert_eq!(f.orientation, Some(want), "{text} 映射错");
    }
    // 镜像形态 Python 现有实现不映射，这里也不该猜
    let json = r#"[{"Orientation":"Mirror horizontal"}]"#;
    assert_eq!(tool::facts_from_json_str(json).unwrap().orientation, None);
}

#[test]
fn real_binary_matches_python_ground_truth() {
    let Some(bin) = tool::locate() else {
        eprintln!("本机无 exiftool，跳过");
        return;
    };
    let f = tool::read(&bin, &photo("_DSC7969.JPG")).unwrap();
    assert_eq!(f.model, "NIKON D810");
    assert_eq!(f.lens_model, "70-200mm f/2.8");
    assert_eq!(f.iso, "800");
    assert_eq!(f.f_number, "2.8");
    assert_eq!(f.exposure, "1/500s");
    assert_eq!(f.focal_display, "145.0");
    assert_eq!(f.focal_35_display, "145");
    assert_eq!(f.orientation, Some(1));
}
