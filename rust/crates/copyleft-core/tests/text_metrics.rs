use copyleft_core::test_support::font;
use copyleft_core::text::store::Face;

/// 期望值来自 Pillow 的 `ImageFont.truetype(path, size).getmetrics()`，
/// 2026-10-12 实测；这是渲染期所有垂直留白计算的基准。
#[test]
fn ascender_descender_match_pillow_getmetrics() {
    let cases = [
        ("AlibabaPuHuiTi-2-45-Light.otf", 240u32, 255u32, 82u32),
        ("AlibabaPuHuiTi-2-85-Bold.otf", 260u32, 276u32, 89u32),
        ("Roboto-Regular.ttf", 240u32, 223u32, 59u32),
        ("Roboto-Medium.ttf", 260u32, 242u32, 64u32),
    ];
    for (file, size, asc, desc) in cases {
        let face = Face::load(&font(file), size).unwrap();
        assert_eq!(face.ascender_px(), asc, "{file}@{size} ascender");
        assert_eq!(face.descender_px(), desc, "{file}@{size} descender");
    }
}

#[test]
fn loading_a_missing_font_is_an_error_not_a_panic() {
    // 不走 test_support::font()，那个助手会先断言文件存在
    let missing = copyleft_core::test_support::repo_root().join("fonts/不存在的字体.ttf");
    let err = Face::load(&missing, 240).unwrap_err();
    assert!(
        err.to_string().contains("字体读取失败"),
        "错误信息应带上下文，实际：{err}"
    );
}
