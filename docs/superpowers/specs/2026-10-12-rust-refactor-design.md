# Copyleft Rust 重写 — 设计规格（阶段 1）

日期：2026-10-12
范围：把 `core/` + `utils.py` + `main.py` 的图片水印引擎与 GUI 用 Rust 重写，落在同仓库 `rust/` 下与 Python 版并行。
阶段 2（未在本规格内）：`square`、`simple`、背景模糊三兄弟布局。

## 1. 目标与验收口径

主目标是产物体积与启动速度：当前 `dist/Copyleft.exe` 为 123,427,746 字节（约 118 MB），PyInstaller onefile 把 CPython、Qt、qfluentwidgets、15 MB 字体和 3.3 MB logo 全部塞进单个 exe。Rust 侧参照 eframe 官方模板的 Windows 产物（6,676,992 字节单文件、无附带 DLL），叠加内嵌的 14.3 MB 字体与 3.3 MB logo，目标量级是单 exe 约 25 MB、zip 约 22 MB，冷启动不再解释 Python 运行时。

次目标：

- Windows 优先，但代码不写死 Windows 专有假设（路径一律 `std::path::Path`，平台差异集中在 exiftool 探测与自动下载两处，用 `cfg!(windows)` 收口）。
- 图片输出与 Python 版**视觉近似**：输出宽高必须完全相等，各区块高度比例误差 < 1%，文字内容与排版位置一致；允许抗锯齿、模糊核与字距的细微像素差异。不追求逐像素 diff 为 0——`image` crate 的高斯核是真高斯核，Pillow 的 `GaussianBlur` 用 box 近似，两者不可能完全一致。
- `config.yaml` 与旧版完全兼容：同一份配置文件两个程序都能读写。

非目标：不做像素级一致、不支持 macOS/Linux 产物发布、不改水印文案规则、不新增布局类型、不重构 Python 侧代码。

阶段 1 用一个实现计划覆盖，内部按 `core 骨架 → exif 双通道 → 文字渲染 → watermark 布局 → CLI 对拍 → GUI → CI` 的顺序推进，前一步的产物是后一步的验收输入；其中「CLI 对拍」是继续做 GUI 的闸门，对拍不过不进入下一步。

## 2. 已核实的技术约束

- `fonts/AlibabaPuHuiTi-2-45-Light.otf` 与 `-85-Bold.otf` 的 sfnt tag 是 `OTTO`（CFF 轮廓），Roboto 四个是 `glyf`。文字栅格化必须走支持 CFF 的栈：`rustybuzz`（shaping）+ `skrifa`（度量/轮廓）+ `swash`（覆盖栅格）。
- egui 0.34 起字体后端从 `ab_glyph` 换成 `skrifa` + `vello_cpu`，`.otf` 可直接作为 UI 字体加载，不需要为界面另备 TTF。
- `kamadak-exif`（crates.io 名 `kamadak-exif`，不是 `exif`）只解析标准 IFD，**不解码 MakerNotes**（上游 issue #26 仍未完成）。Nikon 等机型存放在 MakerNotes 里的 ISO 与镜头信息拿不到，因此 exiftool 通道必须保留，回退链语义照搬现状。
- `image` 0.25 支持写入 JPEG/PNG 的 EXIF（`ImageEncoder::set_exif_metadata`），但只是原样塞入字节，不能编辑字段；EXIF Orientation 需显式调用 `Decoder::orientation()` + `DynamicImage::apply_orientation()`，不会自动摆正。
- `Lanczos3` 是 `image` 提供的最高档缩放核，对应现在的 `Image.LANCZOS`。

## 3. 架构

`rust/` 是独立 cargo workspace，与 Python 代码互不引用。

```
rust/
├── Cargo.toml                  workspace 声明
├── crates/
│   ├── copyleft-core/          引擎库，零 GUI 依赖
│   │   ├── config.rs           config.yaml 读写
│   │   ├── exif/mod.rs         双通道编排与回退
│   │   ├── exif/tool.rs        exiftool 子进程调用 + 输出解析
│   │   ├── exif/download.rs    exiftool 自动下载与解压
│   │   ├── exif/standard.rs    kamadak-exif 通道
│   │   ├── exif/facts.rs       ExifFacts 统一结构
│   │   ├── exif/tiff.rs        原始 EXIF 块里删 Orientation 条目
│   │   ├── meta.rs             ExifFacts → 16 个文字项
│   │   ├── text/mod.rs         文本 → RGBA 位图
│   │   ├── text/store.rs       字体加载缓存
│   │   ├── imageops.rs         8 个图像工具函数
│   │   ├── layout/mod.rs       Processor trait + ProcessorChain
│   │   ├── layout/watermark.rs watermark 家族（5 个 id）
│   │   ├── layout/border.rs    margin / pure_white_margin
│   │   ├── pipeline.rs         链装配 + 批处理 + 事件
│   │   ├── assets.rs           内嵌资源首启释放
│   │   ├── error.rs            CoreError
│   │   └── logging.rs          三份日志文件
│   ├── copyleft-cli/           批处理 CLI（对拍与无 GUI 用法）
│   └── copyleft-gui/           eframe/egui 外壳
└── fixtures/                   测试样张
```

crate 边界：`copyleft-core` 不依赖 egui，可被 CLI 和 GUI 同时使用，是「引擎」的唯一实现处；`copyleft-gui` 只做控件、状态与事件消费，一行图像处理代码都没有；`copyleft-cli` 只做参数解析和调用。

三个设计取舍：

1. **渲染期只读。** 现状 `main.py:153` 注释「在启动工作线程前统一设置，避免工作线程跨线程写配置」说明共享可变 `Config` 是靠纪律避开的。Rust 里点「开始处理」时把配置冻结成不可变 `RenderPlan`（含 `FontStore`、logo 表），worker 只持有 `&RenderPlan`。跨线程写配置这类 bug 在类型层面消失。
2. **一个 watermark 实现覆盖 5 个 id。** `watermark_left_logo` / `watermark_right_logo` / `dark_watermark_left_logo` / `dark_watermark_right_logo` / `custom_watermark` 的 `process()` 完全同源，四个 `Watermark*LogoProcessor` 子类只改 `logo_position`，两个 `DarkWatermark*` 只再改 10 个配色与粗体字段。Rust 用 `WatermarkLayout { logo_side, palette, source }` 参数化，`source` 区分「固定预设」与「读 config」。
3. **`ExifFacts` 取代「把 float 格式化成字符串再正则抓回来」。** Python 链路是 `_pillow_exif` 先 `f'{float(v):.1f} mm'`，`image_container.get_focal_length` 再用 `PATTERN` 把数字找回来。Rust 里 exiftool 通道解析文本时一次抽取数值，kamadak 通道直接用类型化值，两个通道都填同一个 `ExifFacts`，下游只认 `ExifFacts`。

## 4. 数据模型

### 4.1 Config（保持 schema 不变）

`config.yaml` 用 `serde` + `serde_yaml` 0.9 映射成结构体，嵌套 map 用 `BTreeMap`，使 `save()` 输出的键序与现在 `yaml.dump`（默认按字母序）一致，用户比对配置文件时不产生噪声 diff。

```rust
struct Config { base: Base, global: Global, layout: Layout, logo: Logo }
struct Base { alternative_bold_font, alternative_font, bold_font, bold_font_size: u8,
              font, font_size: u8, input_dir, output_dir, quality: u8 }
struct Global { focal_length: { use_equivalent_focal_length }, padding_with_original_ratio: { enable },
                shadow: { enable }, white_margin: { enable, width } }
struct Layout { background_color, elements: BTreeMap<Slot, Element>, logo_enable,
                logo_position: String, type_: String }   // serde rename = "type"
struct Element { color, is_bold, name: String, value: Option<String> }
struct Logo { default: LogoEntry, makes: BTreeMap<String, LogoEntry> }
```

缺失字段的容错行为照搬 `config.py`：`background_color` 缺省 `#ffffff`；`type` 为 `null` 或字符串 `"null"` 时取 `watermark_left_logo`；`name` 为 `null`/`"null"`/缺失时取 `None`；`white_margin.width` 钳制在 0..=30；`font_size` 档位表 1→240、2→250、3→300（越界取 240），`bold_font_size` 1→260、2→290、3→320（越界取 260）；`get_font_padding_level()` = 钳制后的两档之和。`get_or_default` 与 `set_custom_text`（写所有 `name == Custom` 的槽位）语义保留。

### 4.2 TextKey（16 个文字项）

`enum TextKey` 的 `as_str()` 必须与 `config.yaml` 里 `element.name` 的取值逐字一致，否则旧配置读出来全是空文字。

| TextKey | as_str() | 内容 |
|---|---|---|
| Model | `Model` | 相机型号（EXIF `CameraModelName`） |
| Make | `Make` | 相机厂商（`Make`） |
| LensModel | `LensModel` | 镜头型号（`LensModel`/`Lens`/`LensID` 依次取） |
| Param | `Param` | 拍摄参数串 |
| Datetime | `Datetime` | `%Y-%m-%d %H:%M` |
| Date | `Date` | `%Y-%m-%d` |
| Custom | `Custom` | 取 `element.value` |
| None | `None` | 空文字 |
| LensMake_LensModel | 同名 | `lens_make + " " + lens_model` |
| CameraModel_LensModel | 同名 | `model + " " + lens_model` |
| TotalPixel | `TotalPixel` | `{MP:.2} MP` |
| CameraMake_CameraModel | 同名 | `make + " " + model` |
| Filename | `Filename` | 去扩展名的文件名 |
| Date_Filename | 同名 | `date + " " + filename` |
| Datetime_Filename | 同名 | `datetime + " " + filename` |
| GeoInfo | `GeoInfo` | `50°32'N 13°22'E` 形式，无 GPS 时 `无` |

GUI 下拉里的中文显示名沿用 `constant.py` 的 `*_NAME` 字面量（含括号里的示例），顺序也与 `ITEM_LIST` 一致，避免用户升级后看不懂选项。

`ImageMeta::text(&TextKey, custom: Option<&str>) -> String` 取代 Python 的 `_param_dict` 查表。查不到且非 `Custom` 时返回空串，与 `get_attribute_str` 一致。

### 4.3 文案一致性（含既有怪癖）

`Param` 串为 `[focal, "f/"+f_number, exposure, "ISO"+iso]` 以两个空格连接。各字段的缺失行为不一致，必须逐个对齐：

- 焦距默认值是 `--` 且**总是**拼 `mm`，缺失时输出 `--mm`。
- 光圈缺失时输出 `f/--`。
- 快门由 `extract_attribute(..., suffix='s')` 得到：有值时带 `s` 后缀，走默认分支时返回的是不带后缀的 `--`。
- ISO 缺失时输出 `ISO--`。
- `model`/`make`/`lens_model`/`lens_make` 缺失时是空串，于是 `LensMake_LensModel` 会输出前导空格。

等效焦距开关打开且 35mm 值存在（≠ `--`）时用 35mm 值。**阶段 1 原样保留这些输出**，包括 `ISO--`、`--mm` 与前导空格——修它们会让对拍永远对不上，且属于文案改版，不在重写范围内。

## 5. 布局处理器

```rust
trait Processor {
    fn id(&self) -> LayoutId;
    fn process(&self, canvas: &mut Canvas, meta: &ImageMeta, plan: &RenderPlan) -> Result<()>;
}
struct ProcessorChain { items: Vec<&'static dyn Processor> }   // 预设实例 + CustomWatermark
```

链装配规则逐条复刻 `main.py:149-166`：

1. 按 `layout.type` 从注册表取主处理器。Python 的兜底是退回 `simple`，而 `simple` 属阶段 2，所以阶段 1 定义为：**未实现的 id 一律不静默兜底**——`copyleft-cli` 返回 `CoreError::LayoutNotImplemented(LayoutId)` 并以非零码退出；GUI 见 § 8 的启动期处理规则。
2. `shadow.enable` 且 layout ≠ `square` → 前置 `ShadowProcessor`。
3. 主处理器。
4. `white_margin.enable` 且 layout 字符串**包含** `watermark` → 追加 `MarginProcessor`（`dark_watermark_*`、`custom_watermark` 都命中，与现状一致）。
5. `padding_with_original_ratio.enable` 且 layout ≠ `square` → 追加 `PaddingToOriginalRatioProcessor`。

`bg_color` 取自主处理器（Python 是 `config.bg_color = layout_processor.bg_color`），Rust 里放进 `RenderPlan`，`MarginProcessor` 只读它。

阶段 1 实现的布局：`watermark_left_logo`、`watermark_right_logo`、`dark_watermark_left_logo`、`dark_watermark_right_logo`、`custom_watermark`、`pure_white_margin`，加 `shadow`、`margin`、`padding_to_original_ratio` 三个修饰符。`CustomWatermarkProcessor` 每次渲染前从 `RenderPlan` 读 4 个槽位的颜色与粗体（对应 Python `_refresh()`，保证改设置实时生效）。

`imageops.rs` 与 Python 的对应（全部以 `RgbaImage` 为单元，无手动释放）：

| Rust | 对应 Python | 要点 |
|---|---|---|
| `concatenate(imgs, Align)` | `concatenate_image` | 垂直堆叠，横向 left/center/right，间距图为 RGBA |
| `merge(imgs, Axis, Align)` | `merge_images` | axis 0 水平/1 垂直，align 0 居中/1 底部或右/2 顶部或左 |
| `append_by_side(bg, imgs, Side, pad=200, is_start)` | `append_image_by_side` | 按高度缩放到 bg 高，right 侧需反序遍历 |
| `pad(img, size, Slots, color)` | `padding_image` | t/b/l/r 任意组合 |
| `square(img)` | `square_image` | 阶段 2 |
| `resize_h(img, h)` / `resize_w(img, w)` | `resize_image_with_*` | Lanczos3，`round` 取整 |
| `rounded_corners(img, r)` | `add_rounded_corners` | 圆角矩形作 mask |
| `soft_shadow(img, radius, opacity)` | `add_soft_shadow` | 两次 blur（`radius` 与 `radius/2`），`shadow_margin = radius*2` |
| `blur(img, sigma)` | `ImageFilter.GaussianBlur` | `image::imageops::blur` |

watermark 主处理器的关键常量：`NORMAL_HEIGHT = 1000`；下方水印占比 `if ratio >= 1 { 0.04 } else { 0.09 } + 0.02 * font_padding_level`；上下空白占比 `(if ratio >= 1 { 0.52 } else { 0.7 }) - 0.04 * font_padding_level`；透明与灰色分隔线 `20x1000`、`#CBCBC9`；水平间距图 `50/100/200 x 20`，垂直 `20 x 50/100/200`。

## 6. 文字子系统

`text::render(line, face, size, bold, color) -> RgbaImage`：

1. `rustybuzz` 对单行文本 shaping（LTR，无换行；自定义文字可能含中日韩，需 CJK fallback 表）。
2. `skrifa` 取字形轮廓与度量，`swash` 生成覆盖位图（CFF 与 glyf 同一条路径）。
3. 输出尺寸取 **ink bbox**（字形实际覆盖范围），对齐 Pillow `font.getbbox(content)` 的语义——布局里大量 `text_image.width/height` 参与留白计算，用 advance 而非 ink 会让水印条宽度系统性偏大。
4. 空串按现状替换成三个空格再渲染。
5. 颜色以 `fill` 乘进覆盖 alpha 后合成到 RGBA 缓冲。

`FontStore` 在 `RenderPlan` 构建时按 (路径, 字号) 一次性加载 4 组字体（`font`/`bold_font`/`alternative_font`/`alternative_bold_font`），Python 每次 `ImageFont.truetype` 重复解析 7 MB OTF，这里是硬编码 4 次。字体文件从内嵌资源或已释放目录读取，两者对上层透明。

## 7. EXIF 读取与写出

读取（`exif/mod.rs`）保持现状的通道顺序：探测到 exiftool → 用 exiftool；其输出异常 → 记 warning 并回退 kamadak；都没有时返回空 `ExifFacts`，程序继续跑（只缺相机信息，不报错）。

exiftool 探测沿用 `_EXIFTOOL_CANDIDATES` 语义：先看 `PATH`，再看 `./exiftool.exe`、`./exiftool/exiftool.exe`（非 Windows 为 `./exiftool`、`./exiftool/exiftool`）。调用形态与现状一致：`exiftool -d '%Y-%m-%d %H:%M:%S%3f%z' <path>`，解析「键: 值」行、键去空格与斜杠、值裁非 ASCII。自动下载保留：从 `https://exiftool.org/` 首页正则取 `exiftool-(\d+\.\d+)_64.zip`，失败用兜底版本 `13.59`，从 sourceforge 下载，解压时把主程序（排除名字含 `perl` 的 exe）落成 `exiftool.exe`、其余按去掉顶层目录后的路径平铺到 `exiftool_files/`。GUI 启动后延迟约 800ms 检查，缺失时弹询问框；非 Windows 只探测不下载。

写出：`apply_orientation()` 已把方向烘焙进像素，保存前必须去掉 Orientation 标签，否则查看器二次旋转（现状 `image_container.save` 的做法）。`exif/tiff.rs` 在原始 APP1 载荷上原地操作：解析 TIFF 头取字节序 → IFD0 条目数与目录 → 找 tag `0x0112` → 把该条目之后整体上移一条、条目数减一 → 修正「下一个 IFD 偏移」及受影响子 IFD 的指针。MakerNote（tag `0x927c`）字节整体不动，因此 Nikon 信息不丢。JPEG 用 `JpegEncoder::set_exif_metadata`，PNG 同样写 eXIf。拿 `input/_DSC7969.JPG` 做单测：打完补丁后 exiftool 仍读回完整 EXIF 且无 Orientation。

## 8. GUI 与并发

`egui` 两页：「图片处理」「鸣谢与支持」。第一页左侧三张卡片（布局设置：布局下拉 + 启用 Logo；文字位置设置：四角下拉 + 自定义文字输入；高级设置：阴影/白边/按比例填充/等效焦距/质量 1–100），右侧三张卡片（文件选择：输入/输出目录 + 浏览按钮；处理控制：进度条 + 开始/停止；处理统计：排队数/正在处理数/已处理数/每秒处理数）。窗口 1000x700，亮色主题，卡片圆角与间距自绘以近似 Fluent。目录浏览用 `rfd`。控件改动只更新内存 `Config`；点开始处理与关窗时 `save()`。底部版本号用 `env!("CARGO_PKG_VERSION")` 渲染，替掉现在写死的 `Copyleft v2.5`（README 已到 2.6.0，属于随包必改项）。

未实现布局的启动期规则：用户可能带着 Python 版写下的 `config.yaml` 过来，里面 `layout.type` 可能已经是 `square`/`simple`/`background_blur_*`。这时下拉框显示为「1:1填充（阶段 2 提供，当前不可用）」这样的占位项并保持原值**不写回**（不擅自改用户配置），「开始处理」按钮置灰并在旁边给出原因，用户改选任一已实现布局后恢复可用。阶段 1 未实现的 id：`square`、`simple`、`background_blur`、`background_blur_with_white_border`、`background_blur_with_params`。

输入扫描与输出命名与现状一致：只收 `.jpg`/`.jpeg`/`.png`（扩展名大小写不敏感），按路径字典序排序；输出沿用源文件名与扩展名落到输出目录（目录不存在则创建），编码器按扩展名选。

并发：`pipeline::run_batch(plan, files, workers, stop: Arc<AtomicBool>, tx)`，`workers = min(5, files.len())`，与现状 `setMaxThreadCount(5)` 一致。事件 `enum Event { Started(usize), Finished(usize), Failed(usize, String), Stats { queued, processing, processed, rate }, Done(bool) }` 经 `crossbeam-channel` 发出，GUI 每帧 drain 后更新进度条与统计，worker 侧持有 `egui::Context` 调 `request_repaint()` 唤醒。

统计口径照现状：`queued` 从总数递减（每次派发一个文件）、`processing` 开始 +1 / 结束 -1、`rate = processed / elapsed`、进度 `int((processed + failed) / total * 100)`。停止 = 置 `AtomicBool`，已取到的文件跑完、不再取新的，结束时提示「处理已停止」。单文件失败不中断整体，错误累积后在结束弹窗里展示前 3 条 + 总数，完整信息进 `logs/error.log`。

日志：`logs/` 目录自动创建，`all.log` 收 DEBUG 及以上、`info.log` 收 INFO 及以上、`error.log` 收 ERROR 及以上，格式含时间、target、级别、消息。

首启资源释放（`assets.rs`）：exe 同目录缺 `config.yaml`/`fonts`/`logos`/`assets` 时从内嵌字节写出，与 `_setup_frozen_env()` 行为一致；工作目录切到 exe 所在目录，保证相对路径配置可用。

## 9. 测试与验收

- 单元测试：`config` 读写往返保持键序与默认值钳制；`TextKey::as_str()` 与 `config.yaml` 里出现的每个 `name` 值一致；`format_exposure`（≥1 输出整数或小数，<1 输出 `1/N`）；MP 格式化；`exif::tiff` 删 Orientation 后 EXIF 合法；`imageops` 各函数的输出尺寸。
- 集成测试：`fixtures/` 下 5 张样张（Nikon JPG 含 MakerNotes、无 EXIF 的 PNG、竖拍带 Orientation、含 GPS 的 JPG、含自定义中文文字的 JPG）各跑 6 个阶段 1 布局，断言不 panic、输出尺寸等于预期表、水印条高度占比落在容差内。
- 对拍：`copyleft-cli render -c config.yaml -i <dir> -o <out> -j 4` 与 Python 处理同一目录，逐图检查——输出宽高必须完全相等；文字条基线位置以「该位图左上角相对整图宽/高的归一化坐标」衡量，误差 < 1%；水印条高度占比同理。误差来源仅限抗锯齿与字宽，出现结构性偏移（Logo 换边、条带错位）算失败。最后人工并排看样张。
- GUI 手工验证：`cargo run -p copyleft-gui` 走完「选目录 → 改四角文字 → 切布局 → 开始 → 看进度 → 停止 → 关窗存配置」，并验证首启释放资源与 exiftool 缺失时的下载询问。**我会实际跑起来截图确认，不凭代码推断界面正确。**

## 10. 交付与 CI

`rust/.gitignore` 加 `target/`。新增 `.github/workflows/release-rust.yml`：`push tags v*` + `workflow_dispatch`，`windows-latest`，`x86_64-pc-windows-msvc`，`cargo build --release -p copyleft-gui`，产物打包 `Copyleft-<tag>-windows-x64-rust.zip`（单 exe，资源内嵌）。现有 `release.yml` 不改，两条流水线并存；Release 正文沿用从 README 抓 `### <tag> 更新日志` 的做法。

## 11. 依赖清单

`image` 0.25、`kamadak-exif` 0.6、`rustybuzz`、`skrifa`、`swash`、`serde` + `serde_yaml` 0.9、`crossbeam-channel`、`egui`/`eframe`（glow 后端，减小体积）、`rfd`、`thiserror`、`tracing` + `tracing-subscriber` + `tracing-appender`、`ureq` + `zip`（exiftool 自动下载）、`chrono`（日期格式化与解析）、`regex`（exiftool 输出与版本号解析）。

## 12. 已知风险

1. 文字 ink bbox 与 Pillow `getbbox` 不完全一致，会让水印条宽度出现偏差，极端情况下超出 § 9 定的 1% 容差。缓解：先按 swash 覆盖范围取 bbox，对拍超容差再补 Pillow 同源的侧 bearings（left/right bearing）修正。
2. `swash` 的 CPU 覆盖栅格（`scale::Mask`）若对 CFF 的 hinting 处理不理想，回退到 `tiny-skia` 填充 `skrifa` 轮廓路径。
3. 手写 TIFF 条目删除有踩边界情况的风险（子 IFD 偏移、大端序）。缓解：只做「删一条 + 前移 + 修偏移」的最小改动，配 `fixtures` 上 exiftool 回读断言。
4. 阶段 1 未实现的 5 个布局 id 会出现在用户带过来的 `config.yaml` 里。行为已在 § 5（CLI 显式报错）与 § 8（GUI 占位不可选、不写回）定义，不留未定义路径。
5. `serde_yaml` 0.9 已被作者归档、不再更新。功能上够用，但如果后续要写注释或控键序就得换分叉（`serde_yml`/`serde_norway`）。缓解：YAML 读写集中在 `config.rs` 一个模块，替换面可控。
