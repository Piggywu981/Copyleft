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
