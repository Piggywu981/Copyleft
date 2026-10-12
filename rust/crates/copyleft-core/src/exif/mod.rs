//! EXIF 读取：内置通道（`standard`）与 exiftool 子进程通道（`tool`）的编排。
pub mod facts;
pub mod standard;
pub mod tool;

use std::path::{Path, PathBuf};

use crate::error::{CoreError, Result};
use facts::{ExifFacts, ExifSource};

/// 注入点：真机走 `ExiftoolBinary`，测试给假实现，避免依赖本机装没装 exiftool。
pub trait ExifTool {
    fn read(&self, photo: &Path) -> Result<ExifFacts>;
}

pub struct ExiftoolBinary(pub Option<PathBuf>);

impl ExifTool for ExiftoolBinary {
    fn read(&self, photo: &Path) -> Result<ExifFacts> {
        let bin = self.0.as_ref().ok_or_else(|| CoreError::ExiftoolRun {
            bin: "exiftool".into(),
            reason: "未探测到 exiftool".into(),
        })?;
        tool::read(bin, photo)
    }
}

/// 规格 § 7：exiftool 优先；异常时记 warning 回退内置解析；两路都失败给空 facts。
/// 单张照片读不出 EXIF 绝不能中断整批处理。
pub fn read_with(photo: &Path, tool: &dyn ExifTool) -> Result<ExifFacts> {
    match tool.read(photo) {
        Ok(facts) => Ok(facts),
        Err(e) => {
            tracing::warn!(
                "exiftool 读取失败，回退到内置 EXIF 解析：{} : {e}",
                photo.display()
            );
            Ok(standard::read(photo).unwrap_or_else(|e2| {
                tracing::error!("内置解析同样失败：{} : {e2}", photo.display());
                ExifFacts::empty(ExifSource::Empty)
            }))
        }
    }
}

/// 用本机探测到的 exiftool（若有）读取。
pub fn read(photo: &Path) -> Result<ExifFacts> {
    read_with(photo, &ExiftoolBinary(tool::locate()))
}
