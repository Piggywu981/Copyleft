//! 测试与示例共用的样张定位。编译进 lib 是因为 integration test 拿不到 `#[cfg(test)]` 项。
use std::path::PathBuf;

/// `rust/crates/copyleft-core` → 仓库根。
pub fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../..")
}

/// `rust/fixtures/` 下由 `make.sh` 派生的样张。
pub fn fixture(name: &str) -> PathBuf {
    let p = repo_root().join("rust/fixtures").join(name);
    assert!(
        p.exists(),
        "缺 {}，先跑 bash rust/fixtures/make.sh",
        p.display()
    );
    p
}

/// `input/` 下的真实照片（被 .gitignore 排除，只在本地存在）。
pub fn photo(name: &str) -> PathBuf {
    let p = repo_root().join("input").join(name);
    assert!(p.exists(), "仓库 input/ 下没有 {name}");
    p
}

pub fn font(name: &str) -> PathBuf {
    let p = repo_root().join("fonts").join(name);
    assert!(p.exists(), "仓库 fonts/ 下没有 {name}");
    p
}

/// `input/` 的真实照片和 `rust/fixtures/` 的派生样张都被 .gitignore 排除，
/// CI 的检出里不存在。依赖它们的测试必须先问一句再跳过，否则会 panic。
pub fn samples_available() -> bool {
    repo_root().join("input/_DSC7969.JPG").exists() && fixture_dir_exists()
}

fn fixture_dir_exists() -> bool {
    repo_root().join("rust/fixtures/rotated.jpg").exists()
}

#[macro_export]
macro_rules! require_samples {
    () => {
        if !copyleft_core::test_support::samples_available() {
            eprintln!(
                "跳过：input/ 或 rust/fixtures/ 的样张不在检出里（两者都被 .gitignore 排除）。"
            );
            return;
        }
    };
}
