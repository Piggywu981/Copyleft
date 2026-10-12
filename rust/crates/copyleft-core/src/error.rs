use std::path::Path;

use crate::keys::LayoutId;

#[derive(Debug, thiserror::Error)]
pub enum CoreError {
    #[error("打开图片失败 {path}: {source}")]
    ImageOpen {
        path: String,
        #[source]
        source: image::ImageError,
    },

    #[error("EXIF 读取失败 {path}: {reason}")]
    Exif { path: String, reason: String },

    #[error("调用 exiftool 失败 {bin}: {reason}")]
    ExiftoolRun { bin: String, reason: String },

    #[error("字体读取失败 {path}: {reason}")]
    Font { path: String, reason: String },

    #[error("布局 {0} 要到计划 B 才可用")]
    LayoutNotAvailable(LayoutId),

    #[error(transparent)]
    Io(#[from] std::io::Error),

    #[error("{0}")]
    Other(String),
}

pub type Result<T> = std::result::Result<T, CoreError>;

impl CoreError {
    /// EXIF 相关错误都得带上人可读的路径，集中一个入口免得每处手写 display()。
    pub fn exif(path: &Path, reason: impl std::fmt::Display) -> Self {
        Self::Exif {
            path: path.display().to_string(),
            reason: reason.to_string(),
        }
    }
}
