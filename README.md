# Copyleft v3.0.0
---
## 项目背景

本项目是基于开源项目 **semi-utils** 迁移而来的图片处理工具。v2.x 是 PyQt5 图形界面版；
**从 v3.0.0 起，发布产物改为 Rust 重写的引擎与界面**，Python 版停止打包发布。


原项目信息：
- 项目名称：Semi-Utils
- 作者：leslievan
- 开源协议：Apache 2.0 License
- 项目介绍：https://www.bilibili.com/video/BV11A411U7Kn
- 项目地址：https://github.com/leslievan/semi-utils
- 项目介绍（博客）：https://lsvm.xyz/2023/02/semi-utils-intro/
---
## 主要变更

### 1. 用户界面迁移
- **从命令行迁移到图形界面**：将原有的命令行交互模式完全替换为PyQt5图形用户界面
- **单界面设计**：左侧参数设置，右侧文件选择、处理控制与统计（v2.2 起合并原有三个标签页）
- **实时配置预览**：所有设置更改实时生效，无需手动保存

### 2. 功能增强
- **多线程处理**：图片处理在后台线程进行，界面保持响应
- **进度显示**：实时显示处理进度和状态信息
- **错误处理**：完善的错误提示和日志记录机制
- **文件选择**：图形化的目录选择对话框

### 3. 代码重构
- **模块化结构**：将核心功能模块迁移到`core/entity`和`core/enums`目录
- **配置管理**：统一的配置管理系统
- **处理器链**：灵活的图片处理器链设计
---
## 系统要求

- **操作系统**：Windows 10/11 x64（Linux/macOS 能编译，暂不发布产物）
- **构建**：Rust stable + 平台的 C 链接器（Windows 上是 VS 2022 Build Tools 的 MSVC）。
  `eframe` 钉在 0.35，因为 0.36.2 起要求 rustc 1.95。
- **运行**：无运行时依赖，单文件 exe，不附带 DLL。
---
## 安装说明

本仓库 `main` 是 Rust 实现线。从源码构建见下一节「用 Rust 从源码构建」；
普通使用直接去 Releases 下载 zip。

### （可选）安装 exiftool
Rust 侧读取是双通道：探测到 exiftool 就优先用它（能读到 MakerNotes 里的镜头型号、ISO），
没有则回退内置的 `kamadak-exif`——相机型号、拍摄参数、日期这些照常显示。
查找顺序是 `PATH`，然后是可执行文件所在目录及当前目录下的 `exiftool.exe`、`exiftool/exiftool.exe`。
部分单反（如 Nikon D810）把 ISO 和镜头信息放在 Makernotes，若要完整读取，从
[exiftool 官网](https://exiftool.org/)下载后把 `exiftool(-k).exe` 改名成 `exiftool.exe`
放到 exe 同目录即可。启动时询问并自动下载的逻辑排在计划 C。

### Python 版（遗留线）
PyQt5 的实现整体挪到了 **`legacy-python`** 分支，那边保留可运行的 Python 版
（含 EXIF tag 与等效焦距两处修复）和原来的 PyInstaller 发布流程。要跑 Python 版：

```bash
git checkout legacy-python
pip install -r requirements.txt
python main.py
```

## 下载 exe 版本
在 [Releases](https://github.com/Piggywu981/Copyleft/releases) 页面下载 `Copyleft-<版本>-windows-x64.zip`，解压后双击 `Copyleft.exe` 即可运行，无需安装 Python 或 Rust 运行时（单文件，不附带 DLL）。

**v3.0.0 的功能范围（请先读这条再下载）**：本版发布的是 Rust 重写的**第一阶段**——EXIF 双通道读取、16 个文字项、文字栅格化与度量对齐都已经完成并通过与 Python 版的逐行对拍；但布局处理器（水印/白边等）与图形界面尚未移植，所以这个 exe 打开是一个不含处理功能的窗口。需要完整水印功能请继续使用 **v2.6.0**。

## 自动发布
推送 `v*` 格式的 tag 即可自动构建并发布 Release（见 `.github/workflows/release.yml`）：

```bash
git tag v3.0.0
git push origin v3.0.0
```

GitHub Actions 会在 windows-latest 上用 `cargo build --release -p copyleft-gui` 打包，
构建前强制 `cargo fmt --check`、`cargo clippy -- -D warnings` 和 `cargo test`，任一不过就不出产物。
也可以在仓库的 Actions 页面手动触发（workflow_dispatch）做测试构建（不发布）。

## 用 Rust 从源码构建
```bash
cd rust
cargo build --release -p copyleft-gui   # 产物在 rust/target/release/copyleft-gui.exe
cargo test                              # 需要本地有 input/ 样张时才跑全量对拍测试
cargo run -p copyleft-cli -- meta ../input/_DSC7969.JPG
```
工程决策、体积基线、字体度量选型与对拍结果都记在 `rust/NOTES.md`；
设计与分阶段计划见 `docs/superpowers/specs/` 和 `docs/superpowers/plans/`。
---
## 使用说明

程序为单界面设计：左侧为设置面板，右侧为处理面板。

### 布局设置
- **布局类型**：选择图片处理布局（水印、正方形、背景模糊等）
- **Logo启用**：控制是否在图片上添加Logo

### 文字位置设置
- **四个角落文字**：分别设置左上、右上、左下、右下角的文字内容
- 支持的文字类型：相机型号、镜头信息、拍摄参数、日期时间、自定义文字等
- **自定义文字**：当下方某处文字选择"自定义"时，显示在此输入框中填写的内容

### 高级设置
- **阴影效果**：为图片添加阴影效果
- **白边效果**：为图片添加白色边框
- **按比例填充**：保持原始图片比例进行填充
- **等效焦距**：使用等效焦距信息
- **图片质量**：设置输出图片的质量（1-100）

### 文件选择
- **输入目录**：选择包含待处理图片的目录
- **输出目录**：选择处理后的图片保存目录

### 处理控制
- **开始处理**：启动图片处理流程
- **停止**：停止处理（已在处理中的图片会处理完）
- **进度显示**：实时显示处理进度

### 处理统计
- 实时显示排队数、正在处理数、已处理数和每秒处理数
---
## 功能特性

### 支持的布局类型
1. **水印布局**：带Logo的水印布局
2. **正方形布局**：正方形裁剪布局
3. **简单布局**：基本处理布局
4. **背景模糊**：背景模糊效果
5. **纯白边框**：纯白色边框布局

### 文字位置选项
- 相机型号
- 相机品牌
- 镜头信息
- 拍摄参数
- 日期时间
- 自定义文字
- 地理位置信息
- 文件名
- 无文字

### 处理效果
- **阴影效果**：为图片添加逼真的阴影
- **白边效果**：添加白色边框增强视觉效果
- **比例保持**：保持原始图片比例
- **高质量输出**：可调节的输出质量
---
## 注意事项

### 1. 输入图片要求
- 支持常见的图片格式（JPG、PNG等）
- 建议使用高质量原始图片
- 处理前请备份重要图片

### 2. 输出目录
- 输出目录会自动创建
- 处理后的图片会保持原文件名
- 建议使用空目录作为输出目录

### 3. 性能考虑
- 大量图片处理可能需要较长时间
- 建议分批处理大量图片
- 处理过程中不要关闭程序

### 4. 错误处理
- 处理失败的文件会在日志中显示错误信息
- 单个文件处理失败不会影响其他文件
- 建议检查错误日志进行问题排查
---
## 已知问题和解决方案

### 1. Qt相关错误
**问题**：`ImportError: DLL load failed`
**解决方案**：安装Microsoft Visual C++ Redistributable

### 2. 字体显示问题
**问题**：界面字体过小
**解决方案**：程序已优化字体大小，如仍有问题可手动调整配置文件中的`font_size`和`bold_font_size`值

### 3. UI界面简化
**问题**：多标签页操作复杂
**解决方案**：v2.2版本已合并为一个界面，左侧设置，右侧处理，操作更直观

### 4. 日志显示问题
**问题**：日志区域占用空间，信息不直观
**解决方案**：v2.2版本已删除日志显示，改为错误弹窗提示，界面更简洁

---
## 技术架构

### crate 划分
- **`copyleft-core`**：引擎库，零 GUI 依赖。`config`（config.yaml 读写）、`exif`（双通道）、
  `meta`（EXIF → 16 个文字项）、`text`（文字栅格化）、`imageops` 与 `layout`（计划 B）
- **`copyleft-cli`**：`meta` / `text` 两个观测命令，也是与 Python 版逐行对拍的入口
- **`copyleft-gui`**：eframe/egui 外壳（计划 C；当前是能编译运行的空窗口壳）

### EXIF 双通道
优先调用 exiftool（`-j` 结构化输出，能读 MakerNotes 里的镜头与 ISO），失败或缺失时回退
`kamadak-exif`。两条通道都归一化到同一个 `ExifFacts`，字段存的是「显示就绪」的字符串而不是
数值——因为两条通道给同一条信息的形态不同（exiftool 打 `145 mm`、内置解析格式化成 `145.0 mm`），
而对拍要求两边逐字一致。

### 文字渲染
`rustybuzz` shaping + `skrifa` 取轮廓 + `tiny-skia` 填充，走的是能处理 CFF（`.otf`，本项目
的中文字体就是 `OTTO`）轮廓的路径。位图尺寸按 Pillow `getbbox` 的语义算：宽 = 推进量，
高 = max(ascender, 墨迹下沿)，基线在 `y = ascender`；ascender/descender 的取整规则以 Pillow
`getmetrics()` 实测值（255/82、276/89、223/59、242/64）为验收线，结论是 ceil。

### 处理器链与并发（计划 B、C）
责任链装配规则与 5 线程批处理在计划 B/C 落地。设计上把配置在「开始处理」时冻结成不可变
`RenderPlan`，worker 只读它——Python 版靠人肉纪律避免工作线程跨线程写配置，Rust 版让它在类型层面不成立。
---
## 开发说明

### 项目结构
```
Copyleft/
├── rust/
│   ├── Cargo.toml                # workspace
│   ├── NOTES.md                  # 体积基线、字体选型、与计划的偏差、对拍结果
│   ├── crates/
│   │   ├── copyleft-core/        # 引擎库（config / exif / meta / text / imageops / layout）
│   │   ├── copyleft-cli/         # meta、text 子命令
│   │   └── copyleft-gui/         # eframe 外壳
│   ├── fixtures/make.sh          # 从 input/ 派生测试样张
│   └── tests/                    # parity.sh + exif_parity.py 对拍
├── fonts/                        # 水印字体（含 CFF 的 .otf 中文字体）
├── logos/                        # 相机厂商 Logo
├── assets/                       # 界面图片（鸣谢页）
├── config.yaml                   # 主配置（Python 与 Rust 共用同一份 schema）
└── docs/superpowers/             # 设计规格与分阶段实现计划
```
Python 实现不在 `main`，在 **`legacy-python`** 分支。

### 常用命令
```bash
cd rust
cargo test                                     # 单测与集成测试
cargo clippy --all-targets -- -D warnings      # CI 的门禁之一
cargo run -p copyleft-cli -- meta ../input/_DSC7969.JPG
bash rust/tests/parity.sh                      # 与 Python 版逐行对拍
```

### 对拍闸门怎么跑
`parity.sh` 需要 Python 实现作为基准，而 `main` 上已经没有它。开一份 `legacy-python`
的 worktree 指过去即可（已实测 5 张样张 × 2 种焦距模式全部逐行一致）：

```bash
git worktree add ../legacy-python legacy-python
PY_ROOT=../legacy-python bash rust/tests/parity.sh          # exiftool 通道
bash rust/tests/parity.sh                                    # 没有 exiftool 时两边同走内置解析
git worktree remove ../legacy-python
```
脚本会把 exiftool 二进制所在目录塞进 Python 那次调用的 `PATH`——否则 Rust 走 exiftool、
Python 走内置解析，比的是两条不同通道，DIFF 会是假警报。

### 扩展开发
- 加布局：在 `copyleft-core/src/layout/` 实现 `Processor`，并在 `keys::LayoutId` 注册——
  id 字符串必须与 `config.yaml` 里 `layout.type` 的取值一致
- 加文字项：加 `TextKey` 变体、`as_str()`（要与 Python 侧 `constant.py` 的 `*_VALUE` 逐字一致）、
  `display_name()`、`ImageMeta::text()` 分支，并补对拍断言
- 改界面：`copyleft-gui`（计划 C）
---
## 许可证

本项目基于Apache 2.0 License开源协议发布。
---
## 联系方式

### 原项目作者
- **leslievan**
- **GitHub**：@[leslievan](https://github.com/leslievan)
- **Bilibili**：@[吨吨吨的半夏](https://space.bilibili.com/13400294)

### 本项目作者
- **PiggyWu981**
- **GitHub**：@[PiggyWu981](https://github.com/PiggyWu981)
- **Bilibili**：@[PiggyWu981](https://space.bilibili.com/355054416)
---
## 支持与打赏

如果这个项目对你有帮助，欢迎通过给我们买杯咖啡支持我们的工作！

![作者打赏二维码](https://github.com/Piggywu981/Copyleft/blob/main/assets/IMG_7190.JPG)

***以及原作者：***
![原作者打赏二维码](https://github.com/Piggywu981/Copyleft/blob/main/assets/wechat.jpg)

### 其他支持方式
- ⭐ Star 这个项目
- 📝 提交 Issue 或 Pull Request
- 📢 分享给更多有需要的人

感谢您的支持！
---
## 更新日志

### v3.0.0 更新日志
- **发布产物切换到 Rust**：`rust/` 下新增 copyleft-core / copyleft-cli / copyleft-gui 三个 crate，Release 不再用 PyInstaller 打包 Python。空窗口 exe 实测 7.7 MB，对比 v2.6.0 的 123,427,746 字节。
- **已完成的第一阶段（引擎地基）**：config.yaml 零改动兼容读写；EXIF 双通道（exiftool 子进程 + kamadak-exif，含缺失时的回退）；16 个文字项；文字栅格化（rustybuzz + skrifa + tiny-skia，支持本项目使用的 CFF/`.otf` 中文字体）。以上在 5 张样张、两条通道、共 20 组比对中与 Python 版逐行一致。
- 修复：未安装 exiftool 时 ISO 永远显示 `--`。内置解析通道把 tag 写成了十进制 `8827`，正确是 `34855`（0x8827）；LensMake 同理从 `42032` 纠正为 `42035`。
- 修复：**「使用等效焦距」此前完全无效**——参数串在对象构造时就被缓存，而界面是在构造之后才置标志位。现在两边都改成实时计算。⚠️ 这会让输出文字与 v2.6.0 不同（例如 `50mm` 变成等效的 `75mm`），如果你依赖旧输出请注意。
- 已知范围限制：布局处理器（水印、白边、阴影、背景模糊等）与图形界面尚未移植，因此本版 exe 不含图片处理功能，需要完整功能请用 v2.6.0。

### v2.6.0 更新日志
- EXIF 读取双通道：优先 exiftool（可读取 Makernotes 中的 ISO、镜头信息），缺失或失败时自动回退 Pillow 解析，不再强依赖 exiftool
- 启动时检测 exiftool，缺失时询问并自动下载安装
- 拍摄方向自动摆正（EXIF Orientation），竖拍照片输出不再横竖颠倒
- 拍摄时间缺失时回退为文件修改时间
- 修复浏览按钮因缺少配置方法而崩溃的问题；修复空 Logo id 误匹配所有厂商的问题
- 新增停止处理按钮；单张图片失败不再中断整体流程，错误统一弹窗汇总
- 支持打包为单文件 exe，新增 GitHub Actions 自动发布：推送 v* 标签即自动构建并发布 Release

### v2.5 更新日志
- 优化界面布局和用户体验，改进设置项的组织结构
- 增强配置管理功能，支持更多自定义选项
- 修复已知bug，提升程序稳定性和性能
- 改进错误处理机制，提供更详细的错误信息

### v2.4 更新日志
- 添加并行处理功能：支持同时处理最多5张图片，大大提高了程序运行效率
- 优化资源利用率：使用线程池管理工作线程，充分利用系统资源
- 改进错误处理机制：单个图片处理失败不会影响整体处理流程

### v2.3 更新日志
- 添加进度显示功能，包括进度条和详细统计信息
- 在处理界面右下角新增处理统计区域
- 显示内容包括：排队数、正在处理数、已处理数和每秒处理数

### v2.2 更新日志
- 简化UI界面，合并三个标签页为一个
- 删除日志显示，改为错误弹窗提示
- 优化界面布局，左侧设置，右侧处理
- 提升用户体验和操作效率

### v2.1 
- 修复布局切换和文字位置设置的bug
- 优化字体大小显示效果
- 改进配置管理系统
- 增强错误处理和稳定性

### v2.0 
- 完成PyQt5 GUI迁移
- 实现图形化用户界面
- 添加多线程处理支持
- 完善错误处理机制

### v1.x (原命令行版本)
- 命令行交互模式
- 基本图片处理功能
- 配置管理系统
