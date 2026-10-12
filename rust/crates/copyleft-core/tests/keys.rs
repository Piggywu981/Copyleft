use copyleft_core::keys::{ComponentId, LayoutId, TextKey};

#[test]
fn layout_ids_match_python_constants() {
    let expected = [
        "watermark_left_logo",
        "watermark_right_logo",
        "dark_watermark_left_logo",
        "dark_watermark_right_logo",
        "custom_watermark",
        "square",
        "simple",
        "background_blur",
        "background_blur_with_white_border",
        "background_blur_with_params",
        "pure_white_margin",
    ];
    let got: Vec<&str> = LayoutId::ALL.iter().map(|id| id.as_str()).collect();
    assert_eq!(got, expected.to_vec());
    for s in expected {
        assert!(LayoutId::parse(s).is_some(), "{s} 解析不出");
    }
    assert_eq!(LayoutId::parse("nope"), None);
}

#[test]
fn text_keys_are_unique_and_roundtrip() {
    let strs: Vec<&str> = TextKey::ALL.iter().map(|k| k.as_str()).collect();
    let uniq: std::collections::HashSet<&str> = strs.iter().copied().collect();
    assert_eq!(uniq.len(), 16, "as_str 有重复：{strs:?}");
    for s in &strs {
        assert_eq!(TextKey::parse(s).unwrap().as_str(), *s);
    }
    assert_eq!(
        TextKey::None.display_name(),
        " ",
        "constant.py 里 NONE_NAME 是一个空格"
    );
}

#[test]
fn availability_is_six_layouts() {
    let ok: Vec<&str> = LayoutId::ALL
        .iter()
        .filter(|id| id.is_available())
        .map(|id| id.as_str())
        .collect();
    assert_eq!(ok.len(), 6, "只应放开 6 个 id，实际 {ok:?}");
    assert!(!LayoutId::Simple.is_available());
    assert_eq!(ComponentId::Shadow.as_str(), "shadow");
}
