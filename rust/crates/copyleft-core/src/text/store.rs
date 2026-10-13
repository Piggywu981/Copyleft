//! 字体加载与度量。度量必须复现 Pillow 的 `getmetrics()`，
//! 因为布局里所有垂直留白都按文字的 ascender 算。
use std::path::Path;
use std::sync::Arc;

use skrifa::metrics::Metrics;
use skrifa::prelude::*;
use skrifa::FontRef;

use crate::error::{CoreError, Result};

#[derive(Clone)]
pub struct Face {
    bytes: Arc<Vec<u8>>,
    size_px: u32,
    ascender_px: u32,
    descender_px: u32,
    /// 探针数据，供 measure/render 换算用。
    pub ascent_units: f32,
    pub descent_units: f32,
    /// rustybuzz 的位置值是字体单位，渲染时要按 `size_px / units_per_em` 换算。
    pub units_per_em: u16,
}

impl Face {
    pub fn load(path: &Path, size_px: u32) -> Result<Face> {
        let bytes = std::fs::read(path).map_err(|e| CoreError::Font {
            path: path.display().to_string(),
            reason: e.to_string(),
        })?;
        let name = path
            .file_name()
            .map(|s| s.to_string_lossy().to_string())
            .unwrap_or_default();
        let font = FontRef::new(&bytes).map_err(|e| CoreError::Font {
            path: name,
            reason: format!("{e:?}"),
        })?;
        // Metrics::new 已经按 size_px 缩放，单位是像素
        let m = Metrics::new(&font, Size::new(size_px as f32), LocationRef::default());
        // 探针实测：Pillow/FreeType 的 getmetrics 是**向上取整**（ceil）。
        // Light@240 raw 254.4→255、Bold@260 275.6→276、Roboto-Medium@260 241.21→242，
        // round 只能命中 8 个数字里的 5 个，floor 更差。
        Ok(Face {
            bytes: Arc::new(bytes),
            size_px,
            ascender_px: m.ascent.ceil().max(0.0) as u32,
            descender_px: m.descent.abs().ceil() as u32,
            ascent_units: m.ascent,
            descent_units: m.descent,
            units_per_em: m.units_per_em,
        })
    }

    pub fn ascender_px(&self) -> u32 {
        self.ascender_px
    }

    pub fn descender_px(&self) -> u32 {
        self.descender_px
    }

    pub fn size_px(&self) -> u32 {
        self.size_px
    }

    pub fn bytes(&self) -> &[u8] {
        &self.bytes
    }

    /// 供渲染层取轮廓；`FontRef` 只是表目录视图，构造很便宜。
    pub fn font(&self) -> Result<FontRef<'_>> {
        FontRef::new(&self.bytes).map_err(|e| CoreError::Font {
            path: String::from("(内存中的字体)"),
            reason: format!("{e:?}"),
        })
    }
}

/// 字体字节有 7 MB，派生 Debug 会把整个文件打出来，所以手写只露关键项。
impl std::fmt::Debug for Face {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Face")
            .field("size_px", &self.size_px)
            .field("ascender_px", &self.ascender_px)
            .field("descender_px", &self.descender_px)
            .field("units_per_em", &self.units_per_em)
            .field("bytes_len", &self.bytes.len())
            .finish()
    }
}
