//! 与 Python 侧 `core/enums/constant.py` 一一对应的 id 与文字项字符串表。
use std::fmt;

/// 用户可选的 11 个布局 id，顺序与 `init.py` 的 `LAYOUT_ITEMS` 一致。
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum LayoutId {
    WatermarkLeftLogo,
    WatermarkRightLogo,
    DarkWatermarkLeftLogo,
    DarkWatermarkRightLogo,
    CustomWatermark,
    Square,
    Simple,
    BackgroundBlur,
    BackgroundBlurWithWhiteBorder,
    BackgroundBlurWithParams,
    PureWhiteMargin,
}

/// 处理器链上非用户可选的组件，对应 Python 里只有 `LAYOUT_ID` 的处理器。
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum ComponentId {
    Empty,
    Shadow,
    Margin,
    PaddingToOriginalRatio,
}

/// 四个角落文字的 16 个可选项，对应 `constant.py` 的 16 个 `*_VALUE`。
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum TextKey {
    Model,
    Make,
    LensModel,
    Param,
    Datetime,
    Date,
    Custom,
    None,
    LensMakeLensModel,
    CameraModelLensModel,
    TotalPixel,
    CameraMakeCameraModel,
    Filename,
    DateFilename,
    DatetimeFilename,
    GeoInfo,
}

impl LayoutId {
    pub const ALL: [LayoutId; 11] = [
        LayoutId::WatermarkLeftLogo,
        LayoutId::WatermarkRightLogo,
        LayoutId::DarkWatermarkLeftLogo,
        LayoutId::DarkWatermarkRightLogo,
        LayoutId::CustomWatermark,
        LayoutId::Square,
        LayoutId::Simple,
        LayoutId::BackgroundBlur,
        LayoutId::BackgroundBlurWithWhiteBorder,
        LayoutId::BackgroundBlurWithParams,
        LayoutId::PureWhiteMargin,
    ];

    pub fn as_str(self) -> &'static str {
        match self {
            LayoutId::WatermarkLeftLogo => "watermark_left_logo",
            LayoutId::WatermarkRightLogo => "watermark_right_logo",
            LayoutId::DarkWatermarkLeftLogo => "dark_watermark_left_logo",
            LayoutId::DarkWatermarkRightLogo => "dark_watermark_right_logo",
            LayoutId::CustomWatermark => "custom_watermark",
            LayoutId::Square => "square",
            LayoutId::Simple => "simple",
            LayoutId::BackgroundBlur => "background_blur",
            LayoutId::BackgroundBlurWithWhiteBorder => "background_blur_with_white_border",
            LayoutId::BackgroundBlurWithParams => "background_blur_with_params",
            LayoutId::PureWhiteMargin => "pure_white_margin",
        }
    }

    /// 阶段 1（计划 A+B）结束时可用的 id；GUI 下拉据此显示禁用占位。
    pub fn is_available(self) -> bool {
        matches!(
            self,
            LayoutId::WatermarkLeftLogo
                | LayoutId::WatermarkRightLogo
                | LayoutId::DarkWatermarkLeftLogo
                | LayoutId::DarkWatermarkRightLogo
                | LayoutId::CustomWatermark
                | LayoutId::PureWhiteMargin
        )
    }

    pub fn parse(s: &str) -> Option<LayoutId> {
        LayoutId::ALL.into_iter().find(|id| id.as_str() == s)
    }
}

impl ComponentId {
    pub fn as_str(self) -> &'static str {
        match self {
            ComponentId::Empty => "empty",
            ComponentId::Shadow => "shadow",
            ComponentId::Margin => "margin",
            ComponentId::PaddingToOriginalRatio => "padding_to_original_ratio",
        }
    }
}

impl TextKey {
    pub const ALL: [TextKey; 16] = [
        TextKey::Model,
        TextKey::Make,
        TextKey::LensModel,
        TextKey::Param,
        TextKey::Datetime,
        TextKey::Date,
        TextKey::Custom,
        TextKey::None,
        TextKey::LensMakeLensModel,
        TextKey::CameraModelLensModel,
        TextKey::TotalPixel,
        TextKey::CameraMakeCameraModel,
        TextKey::Filename,
        TextKey::DateFilename,
        TextKey::DatetimeFilename,
        TextKey::GeoInfo,
    ];

    /// 返回值必须与 `config.yaml` 里 `layout.elements.*.name` 的取值逐字一致。
    pub fn as_str(self) -> &'static str {
        match self {
            TextKey::Model => "Model",
            TextKey::Make => "Make",
            TextKey::LensModel => "LensModel",
            TextKey::Param => "Param",
            TextKey::Datetime => "Datetime",
            TextKey::Date => "Date",
            TextKey::Custom => "Custom",
            TextKey::None => "None",
            TextKey::LensMakeLensModel => "LensMake_LensModel",
            TextKey::CameraModelLensModel => "CameraModel_LensModel",
            TextKey::TotalPixel => "TotalPixel",
            TextKey::CameraMakeCameraModel => "CameraMake_CameraModel",
            TextKey::Filename => "Filename",
            TextKey::DateFilename => "Date_Filename",
            TextKey::DatetimeFilename => "Datetime_Filename",
            TextKey::GeoInfo => "GeoInfo",
        }
    }

    pub fn parse(s: &str) -> Option<TextKey> {
        TextKey::ALL.into_iter().find(|k| k.as_str() == s)
    }

    /// GUI 下拉显示名，逐字取自 `constant.py` 的 `*_NAME`。
    pub fn display_name(self) -> &'static str {
        match self {
            TextKey::Model => "相机型号(eg. Nikon Z7)",
            TextKey::Make => "相机厂商(eg. Nikon)",
            TextKey::LensModel => "镜头型号(eg. Nikkor 24-70 f/2.8)",
            TextKey::Param => "拍摄参数(eg. 50mm f/1.8 1/1000s ISO 100)",
            TextKey::Datetime => "拍摄时间(eg. 2023-01-01 12:00)",
            TextKey::Date => "拍摄日期(eg. 2023-01-01)",
            TextKey::Custom => "自定义",
            TextKey::None => " ",
            TextKey::LensMakeLensModel => "镜头厂商 + 镜头型号(eg. Nikon Nikkor 24-70 f/2.8)",
            TextKey::CameraModelLensModel => "相机型号 + 镜头型号(eg. Nikon Z7 Nikkor 24-70 f/2.8)",
            TextKey::TotalPixel => "总像素(MP)",
            TextKey::CameraMakeCameraModel => "相机厂商 + 相机型号(eg. DJI FC123)",
            TextKey::Filename => "文件名",
            TextKey::DateFilename => "日期 + 文件名(eg. 2023-01-01 DXO_0001)",
            TextKey::DatetimeFilename => "日期时间 + 文件名(eg. 2023-01-01 12:00 DXO_0001)",
            TextKey::GeoInfo => "地理信息",
        }
    }
}

impl fmt::Display for LayoutId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

impl fmt::Display for TextKey {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}
