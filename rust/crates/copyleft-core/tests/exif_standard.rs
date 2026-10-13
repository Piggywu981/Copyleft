use copyleft_core::exif::facts::{format_exposure, ExifFacts, ExifSource};
use copyleft_core::exif::standard;
use copyleft_core::test_support::{fixture, photo};

#[test]
fn nikon_facts_via_standard_channel() {
    copyleft_core::require_samples!();
    let f = standard::read(&photo("_DSC7969.JPG")).unwrap();
    assert_eq!(f.make, "NIKON CORPORATION");
    assert_eq!(f.model, "NIKON D810");
    // 实测：ISO 在 tag 34855（0x8827），值 800
    assert_eq!(f.iso, "800");
    assert_eq!(f.f_number, "2.8");
    assert_eq!(f.exposure, "1/500s");
    // 标准通道统一用 {:.1} 格式化，两个焦距都带 .0
    assert_eq!(f.focal_display, "145.0");
    assert_eq!(f.focal_35_display, "145.0");
    assert_eq!(f.date_time_original.as_deref(), Some("2014-01-01 08:25:54"));
    assert_eq!(f.orientation, Some(1));
    assert_eq!(
        f.lens_model, "",
        "Nikon 镜头信息只在 MakerNote，标准通道读不到"
    );
    assert_eq!(f.gps_position, None);
    assert_eq!(f.source, ExifSource::Standard);
}

#[test]
fn png_without_exif_yields_empty_facts() {
    copyleft_core::require_samples!();
    let f = standard::read(&fixture("no_exif.png")).unwrap();
    assert_eq!(f, ExifFacts::empty(ExifSource::Standard));
}

#[test]
fn png_with_exif_reads_back_iso() {
    copyleft_core::require_samples!();
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
    // Python 的 round() 是银行家舍入：1/0.4 = 2.5 → 2；Rust 原生 round() 会给 3
    assert_eq!(format_exposure(2, 5), "1/2");
}

#[test]
fn rotated_fixture_carries_orientation_six() {
    copyleft_core::require_samples!();
    let f = standard::read(&fixture("rotated.jpg")).unwrap();
    assert_eq!(f.orientation, Some(6), "派生样张必须真的带上 6");
}
