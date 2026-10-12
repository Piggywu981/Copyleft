use copyleft_core::config::{Config, Slot};
use copyleft_core::keys::{LayoutId, TextKey};
use copyleft_core::test_support::repo_root;

#[test]
fn loads_real_config_yaml() {
    let cfg = Config::load(repo_root().join("config.yaml")).unwrap();
    assert_eq!(cfg.layout_type(), LayoutId::CustomWatermark);
    assert_eq!(cfg.quality(), 100);
    assert_eq!(cfg.slot_name(Slot::LeftTop), TextKey::Model);
    assert_eq!(cfg.slot_name(Slot::LeftBottom), TextKey::Param);
    assert_eq!(cfg.slot_name(Slot::RightTop), TextKey::Custom);
    assert_eq!(cfg.slot_name(Slot::RightBottom), TextKey::Datetime);
    assert_eq!(cfg.custom_text(), "PiggyWu©");
    assert_eq!(cfg.font_size_px(), 240);
    assert_eq!(cfg.bold_font_size_px(), 260);
    assert_eq!(cfg.font_padding_level(), 2);
    assert!(cfg.logo_enabled());
    assert!(cfg.is_logo_left());
    assert_eq!(cfg.background_color(), "#ffffff");
    assert_eq!(cfg.white_margin_width(), 3);
    assert!(!cfg.shadow_enabled());
    assert!(cfg.use_equivalent_focal_length());
}

#[test]
fn every_element_name_in_config_is_a_known_text_key() {
    let raw = std::fs::read_to_string(repo_root().join("config.yaml")).unwrap();
    for line in raw.lines().filter(|l| l.trim_start().starts_with("name:")) {
        let v = line.split(':').nth(1).unwrap().trim().trim_matches('\'');
        assert!(
            TextKey::parse(v).is_some(),
            "config.yaml 里的 name {v:?} 不在 TextKey 表内"
        );
    }
}

#[test]
fn normalizes_null_and_out_of_range_like_python() {
    let dir = std::env::temp_dir().join("copyleft_cfg_null");
    std::fs::create_dir_all(&dir).unwrap();
    let path = dir.join("c.yaml");
    std::fs::write(
        &path,
        r#"
base: {font_size: 9, bold_font_size: 9, quality: 100, font: a, bold_font: b,
       alternative_font: c, alternative_bold_font: d, input_dir: ./input, output_dir: ./output}
global:
  focal_length: {use_equivalent_focal_length: false}
  padding_with_original_ratio: {enable: false}
  shadow: {enable: false}
  white_margin: {enable: false, width: 99}
layout:
  elements:
    left_top: {is_bold: true, name: null}
    left_bottom: {is_bold: false, name: 'null'}
    right_top: {is_bold: true, name: Param}
    right_bottom: {is_bold: false, name: Whatever}
  logo_enable: true
  logo_position: right
  type: null
logo: {default: {id: '', path: ./logos/empty.png}, makes: {}}
"#,
    )
    .unwrap();
    let cfg = Config::load(&path).unwrap();
    assert_eq!(
        cfg.layout_type().as_str(),
        "watermark_left_logo",
        "type: null 回落默认布局"
    );
    assert_eq!(cfg.slot_name(Slot::LeftTop), TextKey::None);
    assert_eq!(cfg.slot_name(Slot::LeftBottom), TextKey::None);
    assert_eq!(cfg.slot_name(Slot::RightTop), TextKey::Param);
    assert_eq!(cfg.slot_name(Slot::RightBottom), TextKey::None);
    assert_eq!(cfg.font_size_px(), 240);
    assert_eq!(cfg.bold_font_size_px(), 260);
    assert_eq!(cfg.white_margin_width(), 30, "width 钳到上限 30");
    assert_eq!(
        cfg.font_padding_level(),
        2,
        "越界档位在 padding level 里按 1 算"
    );
    assert!(!cfg.is_logo_left());
    assert_eq!(cfg.background_color(), "#ffffff");
}

#[test]
fn save_roundtrip_keeps_top_level_key_order() {
    let src = repo_root().join("config.yaml");
    let top_keys = |text: &str| -> Vec<String> {
        text.lines()
            .filter(|l| !l.starts_with(' ') && !l.starts_with('#') && l.contains(':'))
            .map(|l| l.split(':').next().unwrap().to_owned())
            .collect()
    };
    let cfg = Config::load(&src).unwrap();
    let before = top_keys(&std::fs::read_to_string(&src).unwrap());

    let dir = std::env::temp_dir().join("copyleft_cfg_rt");
    std::fs::create_dir_all(&dir).unwrap();
    let out = dir.join("c.yaml");
    cfg.save(&out).unwrap();

    assert_eq!(
        before,
        top_keys(&std::fs::read_to_string(&out).unwrap()),
        "顶层键顺序变了"
    );
    assert_eq!(Config::load(&out).unwrap(), cfg, "往返后内容变了");
}

#[test]
fn setters_mutate_in_memory_only_until_saved() {
    let src = repo_root().join("config.yaml");
    let before = std::fs::read_to_string(&src).unwrap();
    let mut cfg = Config::load(&src).unwrap();

    cfg.set_custom_text("Photo by PiggyWu");
    for slot in [
        Slot::LeftTop,
        Slot::RightTop,
        Slot::LeftBottom,
        Slot::RightBottom,
    ] {
        if cfg.slot_name(slot) == TextKey::Custom {
            assert_eq!(
                cfg.element(slot).unwrap().value.as_deref(),
                Some("Photo by PiggyWu")
            );
        }
    }
    cfg.set_element_name(Slot::LeftBottom, TextKey::Custom);
    assert_eq!(cfg.slot_name(Slot::LeftBottom), TextKey::Custom);
    assert_eq!(
        cfg.element(Slot::LeftBottom).unwrap().value.as_deref(),
        Some(""),
        "set_custom 会把缺 value 的槽位补上空串，与 Python 一致"
    );
    cfg.set_quality(88);
    assert_eq!(cfg.quality(), 88);

    assert_eq!(
        std::fs::read_to_string(&src).unwrap(),
        before,
        "改内存不能顺手写文件，保存只在点开始处理/关窗时发生"
    );
}
