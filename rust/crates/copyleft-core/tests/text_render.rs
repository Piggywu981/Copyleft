use copyleft_core::test_support::font;
use copyleft_core::text::store::Face;
use copyleft_core::text::{measure, parse_color, render_line};

fn light() -> Face {
    Face::load(&font("AlibabaPuHuiTi-2-45-Light.otf"), 240).unwrap()
}
fn bold() -> Face {
    Face::load(&font("AlibabaPuHuiTi-2-85-Bold.otf"), 260).unwrap()
}
fn medium() -> Face {
    Face::load(&font("Roboto-Medium.ttf"), 260).unwrap()
}

/// 宽度容差取相对值：rustybuzz/skrifa 走未提示的推进量，Pillow 用 FreeType 提示
/// 后的 per-glyph 进位，差值随字号增长（实测 240 下 0.29%、260 粗体下 0.62%），
/// 固定像素阈值不成立。1% 与规格 § 9 的区块比例容差一致，下限 2 px
/// 免得短串比测量噪声还严。
fn width_near(img_w: u32, want: u32, text: &str) {
    let d = (img_w as i64 - want as i64).abs();
    let tol = (want as i64 / 100).max(2);
    assert!(
        d <= tol,
        "{text:?} 宽度 {img_w} 与 Pillow 的 {want} 差 {d}，超出 ±{tol}"
    );
}

/// 高度容差 1 px：未提示轮廓与提示结果的字形下沿可能差 1 px
/// （实测 "Nikon Z7"@240 是 257 vs Pillow 258），相对 255 px 基线是 0.4%。
fn height_near(img_h: u32, want: u32, text: &str) {
    let d = (img_h as i64 - want as i64).abs();
    assert!(
        d <= 1,
        "{text:?} 高度 {img_h} 与 Pillow 的 {want} 差 {d}，超出 ±1"
    );
}

#[test]
fn image_size_matches_pillow_getbbox() {
    // bbox("Nikon Z7", 240) = (0, 72, 977, 258)
    let img = render_line("Nikon Z7", &light(), "#212121");
    width_near(img.width(), 977, "Nikon Z7");
    height_near(img.height(), 258, "Nikon Z7");

    // bbox("gjpqy", 240) = (0, 79, 626, 304)：降部把下沿推到 ascender 之外
    let g = render_line("gjpqy", &light(), "#212121");
    width_near(g.width(), 626, "gjpqy");
    height_near(g.height(), 304, "gjpqy");

    // bbox("中国摄影师", 240) = (0, 61, 1180, 281)
    let c = render_line("中国摄影师", &light(), "#212121");
    width_near(c.width(), 1180, "中国摄影师");
    height_near(c.height(), 281, "中国摄影师");

    // Bold@260：bbox("Nikon Z7") = (0, 77, 1130, 279)
    let b = render_line("Nikon Z7", &bold(), "#D32F2F");
    width_near(b.width(), 1130, "Nikon Z7 @bold260");
    height_near(b.height(), 279, "Nikon Z7 @bold260");

    // Roboto Medium@260：bbox("Nikon Z7") = (0, 47, 1050, 245)
    let r = render_line("Nikon Z7", &medium(), "#212121");
    width_near(r.width(), 1050, "Nikon Z7 @roboto");
    height_near(r.height(), 245, "Nikon Z7 @roboto");
}

#[test]
fn spaces_only_gives_advance_by_ascender() {
    // bbox("   ", 240) = (0, 255, 177, 255)：无墨迹，高度就是 ascender
    let img = render_line("   ", &light(), "#212121");
    width_near(img.width(), 177, "spaces");
    assert_eq!(img.height(), 255);
    assert!(img.pixels().all(|p| p.0[3] == 0), "三个空格必须完全透明");
}

#[test]
fn empty_content_is_replaced_by_three_spaces() {
    let img = render_line("", &light(), "#212121");
    assert_eq!(measure(&light(), ""), measure(&light(), "   "));
    assert_eq!(img.height(), 255);
}

#[test]
fn fill_color_is_applied_with_alpha() {
    let img = render_line("N", &light(), "#D32F2F");
    let solid = img
        .pixels()
        .find(|p| p.0[3] > 200)
        .expect("找不到实心像素，说明填充没生效");
    assert_eq!((solid.0[0], solid.0[1], solid.0[2]), (0xD3, 0x2F, 0x2F));
}

#[test]
fn parse_color_handles_hex6_and_hex8_and_junk() {
    assert_eq!(parse_color("#212121"), [0x21, 0x21, 0x21, 255]);
    assert_eq!(parse_color("#D32F2F"), [0xD3, 0x2F, 0x2F, 255]);
    assert_eq!(parse_color("#00000000"), [0, 0, 0, 0]);
    assert_eq!(parse_color("not-a-color"), [0, 0, 0, 255]);
}
