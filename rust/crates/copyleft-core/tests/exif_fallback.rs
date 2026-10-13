use std::path::{Path, PathBuf};

use copyleft_core::error::{CoreError, Result};
use copyleft_core::exif::facts::{ExifFacts, ExifSource};
use copyleft_core::exif::{read_with, ExifTool};
use copyleft_core::test_support::{fixture, photo};

struct FakeTool(Option<PathBuf>);

impl ExifTool for FakeTool {
    fn read(&self, _photo: &Path) -> Result<ExifFacts> {
        match self.0 {
            None => Err(CoreError::ExiftoolRun {
                bin: "missing".into(),
                reason: "not found".into(),
            }),
            Some(_) => Ok(ExifFacts {
                model: "FAKE MODEL".into(),
                ..ExifFacts::empty(ExifSource::Exiftool)
            }),
        }
    }
}

#[test]
fn prefers_exiftool_when_available() {
    copyleft_core::require_samples!();
    let f = read_with(&photo("_DSC7969.JPG"), &FakeTool(Some(PathBuf::from("x")))).unwrap();
    assert_eq!(f.model, "FAKE MODEL");
    assert_eq!(f.source, ExifSource::Exiftool);
}

#[test]
fn falls_back_to_standard_on_error() {
    copyleft_core::require_samples!();
    let f = read_with(&photo("_DSC7969.JPG"), &FakeTool(None)).unwrap();
    assert_eq!(f.source, ExifSource::Standard);
    assert_eq!(f.model, "NIKON D810");
    // 回退后 ISO 仍要拿到，靠的是任务 3 修好的那条 tag
    assert_eq!(f.iso, "800");
}

#[test]
fn no_exif_anywhere_is_not_an_error() {
    copyleft_core::require_samples!();
    let f = read_with(&fixture("no_exif.png"), &FakeTool(None)).unwrap();
    assert_eq!(f.source, ExifSource::Standard);
    assert_eq!(f, ExifFacts::empty(ExifSource::Standard));
}

#[test]
fn real_orchestration_agrees_with_python_ground_truth() {
    copyleft_core::require_samples!();
    use copyleft_core::exif::{tool, ExiftoolBinary};
    // 仓库根才有 exiftool.exe，而集成测试的 CWD 是 crate 目录，
    // 所以显式按仓库根探测，走的仍是 locate_from 的真实实现。
    let base = copyleft_core::test_support::repo_root();
    let Some(bin) = tool::locate_from(&[base]) else {
        eprintln!("仓库根没有 exiftool.exe，跳过");
        return;
    };
    let f = read_with(&photo("_DSC7969.JPG"), &ExiftoolBinary(Some(bin))).unwrap();
    assert_eq!(f.source, ExifSource::Exiftool);
    assert_eq!(f.model, "NIKON D810");
    assert_eq!(f.lens_model, "70-200mm f/2.8");
    assert_eq!(f.focal_35_display, "145");
}

#[test]
fn locate_probes_cwd_and_exe_dir() {
    use copyleft_core::exif::tool;
    let found = tool::locate();
    if found.is_none() {
        eprintln!("本机既没在 PATH 也没在 CWD/exe 目录放了 exiftool，属正常配置");
    }
    // 空基准目录列表只可能命中 PATH，不应 panic
    let _ = tool::locate_from(&[]);
}
