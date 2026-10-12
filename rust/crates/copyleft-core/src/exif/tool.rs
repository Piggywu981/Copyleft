//! exiftool 子进程通道。
//!
//! 只加 `-j`，不加 `-a -G1 -u`：实测 `-a -G1` 会同时给出 `IFD0:Model` 与
//! `ExifIFD:CameraModelName` 以及一堆 `Composite:` 键，剥掉组名前缀后在扁平
//! map 里互相覆盖；而默认 `-j` 的裸键与 Python 文本解析出来的键一致。
//!
//! 另外 `-j` 与纯文本输出的键名有一处不同：JSON 里是 `Model`，文本里是
//! `CameraModelName`。两个都查，顺序保持 Python 的「CameraModelName 优先」。
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::process::Command;

use serde_json::Value as Json;

use crate::error::{CoreError, Result};
use crate::exif::facts::{ExifFacts, ExifSource};

/// 默认搜索基准：当前工作目录 + 可执行文件所在目录。
/// Python 只按 CWD 找，靠入口 `os.chdir(exe目录)` 兜住；Rust 不隐式改 CWD，
/// 所以两个都要探，否则从别的目录启动就找不到随包的 exiftool。
pub fn locate() -> Option<PathBuf> {
    let mut bases: Vec<PathBuf> = vec![PathBuf::from(".")];
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            bases.push(dir.to_path_buf());
        }
    }
    locate_from(&bases)
}

/// 在给定基准目录里找 exiftool；`PATH` 优先，与 `utils.py` 的顺序一致。
pub fn locate_from(bases: &[PathBuf]) -> Option<PathBuf> {
    if let Ok(found) = which::which("exiftool") {
        if found.exists() {
            return Some(found);
        }
    }
    let names: &[&str] = if cfg!(windows) {
        &["exiftool.exe", "exiftool/exiftool.exe"]
    } else {
        &["exiftool", "exiftool/exiftool"]
    };
    bases
        .iter()
        .flat_map(|base| names.iter().map(move |n| base.join(n)))
        .find(|p| p.exists())
}

pub fn read(bin: &Path, photo: &Path) -> Result<ExifFacts> {
    let out = Command::new(bin)
        .arg("-j")
        .arg("-d")
        .arg("%Y-%m-%d %H:%M:%S%3f%z")
        .arg(photo)
        .output()
        .map_err(|e| CoreError::ExiftoolRun {
            bin: bin.display().to_string(),
            reason: e.to_string(),
        })?;
    if !out.status.success() {
        return Err(CoreError::ExiftoolRun {
            bin: bin.display().to_string(),
            reason: String::from_utf8_lossy(&out.stderr).trim().to_owned(),
        });
    }
    facts_from_json_str(&String::from_utf8_lossy(&out.stdout))
}

/// 剥掉可能的组名前缀，并按 Python 的做法把值里的非 ASCII 字符滤掉。
fn flatten(root: &Json) -> HashMap<String, String> {
    let mut map = HashMap::new();
    let Some(obj) = root
        .as_array()
        .and_then(|a| a.first())
        .and_then(|o| o.as_object())
    else {
        return map;
    };
    for (k, v) in obj {
        let bare = k.rsplit("] ").next().unwrap_or(k);
        let text = match v {
            Json::String(s) => s.clone(),
            Json::Number(n) => n.to_string(),
            Json::Bool(b) => b.to_string(),
            Json::Array(items) => items
                .iter()
                .map(|i| i.to_string().trim_matches('"').to_owned())
                .collect::<Vec<String>>()
                .join(" "),
            _ => continue,
        };
        let key = bare.replace('/', "").trim().to_owned();
        map.insert(key, text.chars().filter(|c| c.is_ascii()).collect());
    }
    map
}

/// 对应 `PATTERN = r"(\d+(?:\.\d+)?)"` 取第一个匹配：`"145.0 mm"` → `"145.0"`。
fn first_number(s: &str) -> String {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    let re = RE.get_or_init(|| regex::Regex::new(r"\d+(?:\.\d+)?").expect("正则不合法"));
    re.find(s)
        .map(|m| m.as_str().to_owned())
        .unwrap_or_default()
}

/// exiftool 的方向文本 → 数值，对应 `utils._ORIENTATION_NAMES`。
/// 镜像形态（2/4/5/7）Python 现有实现不映射，这里也保持不映射。
fn orientation_from(text: &str) -> Option<u16> {
    if text.contains("Rotate 90 CW") {
        Some(6)
    } else if text.contains("Rotate 180") {
        Some(3)
    } else if text.contains("Rotate 270 CW") {
        Some(8)
    } else if text.contains("Rotate 0") || text.contains("Horizontal (normal)") {
        Some(1)
    } else {
        None
    }
}

pub fn facts_from_json_str(text: &str) -> Result<ExifFacts> {
    let json: Json = serde_json::from_str(text.trim()).map_err(|e| CoreError::ExiftoolRun {
        bin: "json".into(),
        reason: e.to_string(),
    })?;
    let m = flatten(&json);
    let pick = |k: &str| m.get(k).cloned().unwrap_or_default();
    let pick_num = |k: &str| first_number(&pick(k));

    // ExifId.LENS_MODEL 的顺序：LensModel → Lens → LensID
    let lens_model = ["LensModel", "Lens", "LensID"]
        .iter()
        .map(|k| pick(k))
        .find(|v| !v.is_empty())
        .unwrap_or_default();
    let model = {
        let v = pick("CameraModelName");
        if v.is_empty() {
            pick("Model")
        } else {
            v
        }
    };
    let raw_date = pick("DateTimeOriginal");
    let exposure = {
        let v = pick("ExposureTime");
        if v.is_empty() {
            String::new()
        } else {
            v + "s"
        }
    };

    Ok(ExifFacts {
        make: pick("Make"),
        model,
        lens_model,
        lens_make: pick("LensMake"),
        exposure,
        f_number: pick("FNumber"),
        // exiftool 可能把几个 ISO 相关值并成一个串（"800 800"），取第一个
        iso: pick("ISO")
            .split_whitespace()
            .next()
            .unwrap_or("")
            .to_owned(),
        focal_display: pick_num("FocalLength"),
        focal_35_display: pick_num("FocalLengthIn35mmFormat"),
        date_time_original: if raw_date.is_empty() {
            None
        } else {
            Some(raw_date)
        },
        orientation: if pick("Orientation").is_empty() {
            None
        } else {
            orientation_from(&pick("Orientation"))
        },
        gps_position: {
            let v = pick("GPSPosition");
            if v.is_empty() {
                None
            } else {
                Some(v)
            }
        },
        raw_app1: None,
        source: ExifSource::Exiftool,
    }
    .with_display_defaults())
}
