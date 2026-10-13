//! 单行文字渲染成 RGBA 位图。
//!
//! 尺寸规则由 Pillow 的 `font.getbbox()` 反推（实测见计划附录 A）：
//! 宽 = shaping 的推进量，高 = max(ascender, 墨迹下沿)，基线在 `y = ascender`。
//! 空串按 `utils.text_to_image` 替换成三个空格。
pub mod store;

use image::RgbaImage;
use skrifa::outline::{DrawSettings, OutlinePen};
use skrifa::prelude::*;

pub use store::Face;

/// "#RRGGBB" / "#RRGGBBAA" → [r,g,b,a]；非法输入回落不透明黑。
pub fn parse_color(s: &str) -> [u8; 4] {
    let hex = s.trim_start_matches('#');
    let byte = |i: usize| {
        hex.get(i * 2..i * 2 + 2)
            .and_then(|h| u8::from_str_radix(h, 16).ok())
            .unwrap_or(0)
    };
    match hex.len() {
        6 => [byte(0), byte(1), byte(2), 255],
        8 => [byte(0), byte(1), byte(2), byte(3)],
        _ => [0, 0, 0, 255],
    }
}

/// 渲染一行文字。粗体由调用方选字体决定（与 Python 传两套字体的做法一致）。
pub fn render_line(content: &str, face: &Face, fill: &str) -> RgbaImage {
    let content = if content.is_empty() { "   " } else { content };
    draw(content, face, parse_color(fill))
}

/// 供测试与布局层使用：只关心尺寸时不必转换整张位图。
pub fn measure(face: &Face, text: &str) -> (u32, u32) {
    let img = render_line(text, face, "#000000");
    (img.width(), img.height())
}

/// 把 skrifa 的轮廓命令直接攒成 tiny-skia 路径：y 轴翻折并平移到笔位。
struct Translator {
    build: tiny_skia::PathBuilder,
    pen_x: f32,
    baseline_y: f32,
    /// 墨迹下沿（图像坐标，y 向下）
    max_y: f32,
    drew_any: bool,
}

impl Translator {
    fn new(pen_x: f32, baseline_y: f32) -> Self {
        Self {
            build: tiny_skia::PathBuilder::new(),
            pen_x,
            baseline_y,
            max_y: f32::MIN,
            drew_any: false,
        }
    }

    /// 记录一个点，返回图像坐标。控制点也算进包围盒：宁可把下沿估大，
    /// 也不要裁掉实际笔画。
    fn track(&mut self, x: f32, y: f32) -> (f32, f32) {
        let gx = self.pen_x + x;
        let gy = self.baseline_y - y; // skrifa 的 y 向上，图像 y 向下
        self.max_y = self.max_y.max(gy);
        self.drew_any = true;
        (gx, gy)
    }

    fn finish(self) -> Option<tiny_skia::Path> {
        if self.drew_any {
            self.build.finish()
        } else {
            None
        }
    }
}

impl OutlinePen for Translator {
    fn move_to(&mut self, x: f32, y: f32) {
        let (x, y) = self.track(x, y);
        self.build.move_to(x, y);
    }
    fn line_to(&mut self, x: f32, y: f32) {
        let (x, y) = self.track(x, y);
        self.build.line_to(x, y);
    }
    fn quad_to(&mut self, cx: f32, cy: f32, x: f32, y: f32) {
        let (cx, cy) = self.track(cx, cy);
        let (x, y) = self.track(x, y);
        self.build.quad_to(cx, cy, x, y);
    }
    fn curve_to(&mut self, c0x: f32, c0y: f32, c1x: f32, c1y: f32, x: f32, y: f32) {
        let (c0x, c0y) = self.track(c0x, c0y);
        let (c1x, c1y) = self.track(c1x, c1y);
        let (x, y) = self.track(x, y);
        self.build.cubic_to(c0x, c0y, c1x, c1y, x, y);
    }
    fn close(&mut self) {
        self.build.close();
    }
}

/// shaping → 逐字形取轮廓 → (路径, 总推进量, 墨迹下沿)
fn layout(content: &str, face: &Face) -> (Vec<tiny_skia::Path>, f32, Option<f32>) {
    let Some(rb_face) = rustybuzz::Face::from_slice(face.bytes(), 0) else {
        return (Vec::new(), 1.0, None);
    };
    let mut buf = rustybuzz::UnicodeBuffer::new();
    buf.push_str(content);
    let shaped = rustybuzz::shape(&rb_face, &[], buf);
    let infos = shaped.glyph_infos();
    let positions = shaped.glyph_positions();

    // rustybuzz 的位置是字体单位（探针实测 AlibabaPuHuiTi 的 upm=1000），要按字号缩放。
    let scale = face.size_px() as f32 / face.units_per_em as f32;
    // 基线用未取整的 ascent：Pillow 的 bbox 也是从浮点基线推出来的，
    // 先 ceil 再相加会整体偏 1 px。
    let baseline = face.ascent_units;
    let mut paths = Vec::with_capacity(infos.len());
    let mut pen_x = 0.0f32;
    let mut ink_bottom: Option<f32> = None;

    let Ok(font) = face.font() else {
        return (paths, pen_x.max(1.0), ink_bottom);
    };
    let outlines = font.outline_glyphs();
    let size = Size::new(face.size_px() as f32);

    for (info, pos) in infos.iter().zip(positions.iter()) {
        let x = pen_x + pos.x_offset as f32 * scale;
        let y_off = pos.y_offset as f32 * scale;
        if let Some(glyph) = outlines.get(GlyphId::new(info.glyph_id)) {
            let mut t = Translator::new(x, baseline + y_off);
            // DrawSettings 不是 Copy，每个字形造一次，成本就是一次 size 换算。
            let settings = DrawSettings::unhinted(size, LocationRef::default());
            if glyph.draw(settings, &mut t).is_ok() {
                let bottom = t.max_y;
                if let Some(path) = t.finish() {
                    ink_bottom = Some(ink_bottom.unwrap_or(bottom).max(bottom));
                    paths.push(path);
                }
            }
        }
        pen_x += pos.x_advance as f32 * scale;
    }
    (paths, pen_x, ink_bottom)
}

fn draw(content: &str, face: &Face, fill: [u8; 4]) -> RgbaImage {
    let (paths, advance, ink_bottom) = layout(content, face);
    let asc = face.ascender_px() as f32;
    // 无墨迹（三个空格那种）时高度就是 ascender，与 Pillow 的 bbox 一致
    let height = ink_bottom.map_or(asc, |b| asc.max(b)).ceil().max(1.0) as u32;
    let width = advance.ceil().max(1.0) as u32;

    let Some(mut pixmap) = tiny_skia::Pixmap::new(width, height) else {
        return RgbaImage::from_pixel(1, 1, image::Rgba([0, 0, 0, 0]));
    };
    let mut paint = tiny_skia::Paint::default();
    paint.set_color_rgba8(fill[0], fill[1], fill[2], fill[3]);
    paint.anti_alias = true;
    for path in &paths {
        pixmap.fill_path(
            path,
            &paint,
            tiny_skia::FillRule::Winding,
            tiny_skia::Transform::identity(),
            None,
        );
    }
    from_premul(&pixmap)
}

/// tiny-skia 存 premultiplied alpha，而布局层的合成语义是 straight alpha
/// （Python 那边的 RGBA 图直接被 paste / alpha_composite 使用），所以还原回去。
fn from_premul(px: &tiny_skia::Pixmap) -> RgbaImage {
    let (w, h) = (px.width(), px.height());
    let mut out = RgbaImage::from_pixel(w, h, image::Rgba([0, 0, 0, 0]));
    for (i, chunk) in px.data().chunks_exact(4).enumerate() {
        let a = chunk[3];
        let rgba = if a == 0 {
            [0, 0, 0, 0]
        } else {
            [
                (chunk[0] as u32 * 255 / a as u32) as u8,
                (chunk[1] as u32 * 255 / a as u32) as u8,
                (chunk[2] as u32 * 255 / a as u32) as u8,
                a,
            ]
        };
        out.put_pixel(i as u32 % w, i as u32 / w, image::Rgba(rgba));
    }
    debug_assert_eq!(w as usize * h as usize * 4, px.data().len());
    out
}
