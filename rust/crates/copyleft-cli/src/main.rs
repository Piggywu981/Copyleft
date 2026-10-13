//! 观测与对拍用 CLI。`meta` 打印一张照片的 16 个文字项，`text` 渲染一行文字。
use std::path::PathBuf;

use clap::{Parser, Subcommand};
use copyleft_core::keys::TextKey;
use copyleft_core::meta::ImageMeta;
use copyleft_core::text::{render_line, Face};

#[derive(Parser)]
#[command(name = "copyleft-cli", version)]
struct Cli {
    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    /// 打印一张照片的 16 个文字项（与 rust/tests/exif_parity.py 逐行 diff）
    Meta {
        photo: PathBuf,
        /// 用等效焦距（对应 config.global.focal_length）
        #[arg(long)]
        eq: bool,
        /// 显式指定 exiftool；对拍脚本用它保证两边走同一条通道
        /// （不指定则按 CWD/exe 目录探测，从 rust/ 下跑就找不到）
        #[arg(long)]
        exiftool: Option<PathBuf>,
    },
    /// 渲染一行文字，打印尺寸，可选存图
    Text {
        font: PathBuf,
        #[arg(long, default_value_t = 240)]
        size: u32,
        #[arg(long, default_value = "#212121")]
        color: String,
        #[arg(long)]
        save: Option<PathBuf>,
        content: String,
    },
}

fn main() -> std::process::ExitCode {
    let cli = Cli::parse();
    let result = match &cli.cmd {
        Cmd::Meta {
            photo,
            eq,
            exiftool,
        } => run_meta(photo, *eq, exiftool.as_deref()),
        Cmd::Text {
            font,
            size,
            color,
            save,
            content,
        } => run_text(font, *size, color, content, save.clone()),
    };
    match result {
        Ok(()) => std::process::ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("错误: {e}");
            std::process::ExitCode::FAILURE
        }
    }
}

/// 输出格式刻意用「裸值 + tab」，不用任何一方的 repr：Python 的 repr 是单引号、
/// Rust 的 Debug 是双引号，直接 diff 会在每一行都不同。
fn run_meta(
    photo: &std::path::Path,
    eq: bool,
    exiftool: Option<&std::path::Path>,
) -> copyleft_core::error::Result<()> {
    use copyleft_core::exif::{tool, ExiftoolBinary};
    let bin = match exiftool {
        Some(p) => Some(p.to_path_buf()),
        None => tool::locate(),
    };
    let m = ImageMeta::load_with(photo, eq, &ExiftoolBinary(bin))?;
    println!("source\t{}", m.exif.source.name());
    println!(
        "size\t{}x{}\torientation\t{}",
        m.width, m.height, m.orientation
    );
    for key in TextKey::ALL {
        println!("{}\t{}", key.as_str(), m.text(key, Some("自定义文字")));
    }
    Ok(())
}

fn run_text(
    font: &std::path::Path,
    size: u32,
    color: &str,
    content: &str,
    save: Option<PathBuf>,
) -> copyleft_core::error::Result<()> {
    let face = Face::load(font, size)?;
    let img = render_line(content, &face, color);
    println!("{}\t{}x{}", content, img.width(), img.height());
    if let Some(path) = save {
        img.save(&path)
            .map_err(|e| copyleft_core::error::CoreError::ImageOpen {
                path: path.display().to_string(),
                source: e,
            })?;
    }
    Ok(())
}
