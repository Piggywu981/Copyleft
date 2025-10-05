"""
Semi-Utils - PyQt5 GUI版本主程序入口点
基于semi-utils开源项目迁移而来
整合了主窗口界面功能，使用PyQt-Fluent-Widgets美化界面
"""
import os
import sys
import logging
import traceback
import time
import queue
from pathlib import Path

from PyQt5.QtCore import QThread, QThreadPool, QRunnable, QObject, pyqtSignal, pyqtSlot, Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (QApplication, QVBoxLayout, QHBoxLayout, 
                             QWidget, QGroupBox, QFormLayout, QTextEdit,
                             QMessageBox, QFileDialog, QLabel, QSpacerItem, QSizePolicy)

# 导入PyQt-Fluent-Widgets组件
from qfluentwidgets import (FluentWindow, setTheme, Theme, setThemeColor,
                           PrimaryPushButton, LineEdit, ComboBox, CheckBox, 
                           SpinBox, ProgressBar, TitleLabel, BodyLabel,
                           MessageBox, FluentIcon)

from core.entity.config import Config
from core.entity.image_processor import ProcessorChain
from core.enums.constant import *
from init import (WATERMARK_PROCESSOR, WATERMARK_LEFT_LOGO_PROCESSOR,
                   WATERMARK_RIGHT_LOGO_PROCESSOR, MARGIN_PROCESSOR, SHADOW_PROCESSOR,
                   SQUARE_PROCESSOR, SIMPLE_PROCESSOR, PADDING_TO_ORIGINAL_RATIO_PROCESSOR,
                   config, layout_items_dict)
from utils import get_file_list


class ImageWorker(QRunnable):
    """图片处理工作线程"""
    def __init__(self, config, source_path, output_dir, processor_chain):
        super().__init__()
        self.config = config
        self.source_path = source_path
        self.output_dir = output_dir
        self.processor_chain = processor_chain
        # 创建信号对象并设置线程亲和性
        self.signals = WorkerSignals()
        # 确保信号对象在主线程中创建和管理
        self.signals.moveToThread(QApplication.instance().thread())
        # 设置AutoDelete为False，确保信号发送完成后再删除
        self.setAutoDelete(False)
    
    @pyqtSlot()
    def run(self):
        """处理单个图片"""
        try:
            from core.entity.image_container import ImageContainer
            from utils import ENCODING
            
            # 发送开始信号
            self.signals.started.emit(self.source_path)
            
            # 创建并处理图片容器
            container = ImageContainer(self.source_path)
            container.is_use_equivalent_focal_length(self.config.use_equivalent_focal_length())
            
            # 应用处理器链
            self.processor_chain.process(container)
            
            # 保存处理后的图片
            target_path = Path(self.output_dir).joinpath(self.source_path.name)
            container.save(target_path, quality=self.config.get_quality())
            container.close()
            
            # 发送完成信号
            self.signals.finished.emit(self.source_path)
        except Exception as e:
            error_msg = f"处理文件 {self.source_path.name} 时出错: {str(e)}"
            self.signals.error.emit(error_msg)


class WorkerSignals(QObject):
    """工作线程信号类"""
    started = pyqtSignal(object)  # 开始处理信号，传递文件路径
    finished = pyqtSignal(object)  # 完成处理信号，传递文件路径
    error = pyqtSignal(str)  # 错误信号，传递错误信息
    
    def __init__(self, parent=None):
        super().__init__(parent)


class ProcessingThread(QThread):
    """图片处理线程"""
    progress_updated = pyqtSignal(int)
    processing_finished = pyqtSignal()
    error_occurred = pyqtSignal(str)
    stats_updated = pyqtSignal(int, int, int, float)  # 排队数, 正在处理数, 已处理数, 每秒处理数
    
    def __init__(self, config, input_dir, output_dir):
        super().__init__()
        self.config = config
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.processor_chain = ProcessorChain()
        self.stop_event = False
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(5)  # 设置最大线程数为5
        self.file_queue = queue.Queue()
    
    def run(self):
        """运行处理线程
        
        使用线程池并行处理图片，并更新进度和统计信息。
        """
        try:
            from utils import get_file_list
            
            file_list = get_file_list(self.input_dir)
            total_files = len(file_list)
            
            if total_files == 0:
                self.processing_finished.emit()
                return
            
            # 构建处理器链
            layout_type = self.config.get_layout_type()
            if self.config.has_shadow_enabled() and layout_type and 'square' != layout_type:
                self.processor_chain.add(SHADOW_PROCESSOR)
            
            if layout_type and layout_type in layout_items_dict:
                self.processor_chain.add(layout_items_dict.get(layout_type).processor)
            else:
                self.processor_chain.add(SIMPLE_PROCESSOR)
            
            if self.config.has_white_margin_enabled() and layout_type and 'watermark' in layout_type:
                self.processor_chain.add(MARGIN_PROCESSOR)
            
            if self.config.has_padding_with_original_ratio_enabled() and layout_type and 'square' != layout_type:
                self.processor_chain.add(PADDING_TO_ORIGINAL_RATIO_PROCESSOR)
            
            # 初始化统计信息和变量
            self.queued = total_files
            self.processing = 0
            self.processed = 0
            self.failed = 0
            self.active_workers = {}  # 跟踪活跃的工作线程
            self.start_time = time.time()
            
            # 将所有文件放入队列
            for file_path in file_list:
                self.file_queue.put(file_path)
            
            # 连接信号槽
            self.thread_pool.waitForDone()  # 确保线程池为空
            
            # 启动初始工作线程
            for _ in range(min(5, self.queued)):
                if not self.file_queue.empty():
                    self._start_next_worker()
            
            # 定期更新统计信息
            while self.processing > 0 or not self.file_queue.empty():
                if self.stop_event:
                    break
                
                # 更新统计信息
                elapsed_time = time.time() - self.start_time
                rate = self.processed / elapsed_time if elapsed_time > 0 else 0
                self.stats_updated.emit(self.queued, self.processing, self.processed, rate)
                
                # 更新进度条
                progress = int(((self.processed + self.failed) / total_files) * 100)
                self.progress_updated.emit(progress)
                
                # 短暂休眠避免CPU占用过高
                time.sleep(0.1)
            
            # 等待所有线程完成
            self.thread_pool.waitForDone()
            
            # 发送最终进度和统计信息
            self.progress_updated.emit(100 if self.processed + self.failed == total_files else 0)
            elapsed_time = time.time() - self.start_time
            rate = self.processed / elapsed_time if elapsed_time > 0 else 0
            self.stats_updated.emit(0, 0, self.processed, rate)
            
            # 处理完成
            if not self.stop_event:
                self.processing_finished.emit()
            
        except Exception as e:
            error_msg = f"处理过程中出错: {str(e)}"
            # 在ProcessingThread中获取logger
            import logging
            logger = logging.getLogger(__name__)
            logger.error(error_msg, exc_info=True)
            self.error_occurred.emit(error_msg)
            
    def _start_next_worker(self):
        """启动下一个工作线程"""
        if self.file_queue.empty() or self.stop_event:
            return
        
        file_path = self.file_queue.get()
        self.queued -= 1
        
        # 创建工作线程
        worker = ImageWorker(self.config, file_path, self.output_dir, self.processor_chain)
        worker.signals.started.connect(self._on_worker_started)
        worker.signals.finished.connect(self._on_worker_finished)
        worker.signals.error.connect(self._on_worker_error)
        
        # 将工作线程添加到活动列表
        self.active_workers[file_path] = worker
        
        # 启动工作线程
        self.thread_pool.start(worker)
        
    def _on_worker_started(self, file_path):
        """工作线程开始处理信号槽"""
        self.processing += 1
        
    def _on_worker_finished(self, file_path):
        """工作线程完成处理信号槽"""
        self.processing -= 1
        self.processed += 1
        
        # 从活动列表中移除并清理工作线程对象
        if file_path in self.active_workers:
            worker = self.active_workers[file_path]
            # 断开所有信号连接
            worker.signals.started.disconnect(self._on_worker_started)
            worker.signals.finished.disconnect(self._on_worker_finished)
            worker.signals.error.disconnect(self._on_worker_error)
            del self.active_workers[file_path]
        
        # 启动下一个工作线程
        self._start_next_worker()
        
    def _on_worker_error(self, error_msg):
        """工作线程错误信号槽"""
        self.processing -= 1
        self.failed += 1
        
        # 向主线程发送错误信息
        self.error_occurred.emit(error_msg)
        
        # 启动下一个工作线程
        self._start_next_worker()
        
    def _cleanup_workers(self):
        """清理所有工作线程"""
        # 断开所有信号连接
        for file_path, worker in list(self.active_workers.items()):
            try:
                worker.signals.started.disconnect(self._on_worker_started)
                worker.signals.finished.disconnect(self._on_worker_finished)
                worker.signals.error.disconnect(self._on_worker_error)
            except:
                pass
        # 清空活动工作线程列表
        self.active_workers.clear()
    
    def stop(self):
        """停止处理线程"""
        self.stop_event = True
        # 清理所有工作线程
        self._cleanup_workers()


class MainWindow(FluentWindow):
    """主窗口类 - 使用Fluent Design风格"""
    
    def __init__(self):
        super().__init__()
        self.config = config
        self.processing_thread = None
        self.init_ui()
        
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("Copyleft - 图片处理工具")
        self.resize(1000, 700)
        
        # 使用系统主题颜色 - 不设置固定颜色值，让应用程序自动使用系统主题色
        
        # 创建单一界面（合并所有功能）
        self.main_interface = self.create_main_interface()
        
        # 添加界面到导航
        self.addSubInterface(self.main_interface, FluentIcon.HOME, "图片处理")
        
        # 创建鸣谢与打赏标签页并添加到导航
        self.thanks_interface = self.create_thanks_interface()
        self.addSubInterface(self.thanks_interface, FluentIcon.HEART, "鸣谢与支持")
        
        # 设置初始界面
        self.stackedWidget.setCurrentWidget(self.main_interface)
        self.navigationInterface.setCurrentItem(self.main_interface.objectName())
        
    def create_thanks_interface(self):
        """创建鸣谢与打赏标签页"""
        interface = QWidget()
        interface.setObjectName("thanksInterface")
        main_layout = QVBoxLayout(interface)
        
        # 标题
        title_label = TitleLabel("鸣谢与支持")
        main_layout.addWidget(title_label)
        
        # 鸣谢内容
        thanks_text = """
感谢您使用 Copyleft (Semi-Utils) 图片处理工具！

本工具由开源社区开发，完全免费使用。

如果您觉得本工具对您有所帮助，欢迎通过以下方式支持我们的开发工作：

- 分享本工具给更多有需要的朋友
- 在 GitHub 上给本项目和原项目点个 Star
- 给我们买个咖啡☕

您的支持是我们持续改进的动力！
        """
        
        # 创建文本标签
        thanks_label = BodyLabel(thanks_text)
        thanks_label.setWordWrap(True)
        thanks_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(thanks_label)
        
        # 创建水平布局来容纳两张打赏图片
        images_layout = QHBoxLayout()
        
        # 左侧：原作者打赏图片
        try:
            original_image_path = "d:/Github/Copyleft/core/enums/WeChat.JPG"
            original_pixmap = QPixmap(original_image_path)
            if not original_pixmap.isNull():
                # 缩放图片保持比例
                scaled_original_pixmap = original_pixmap.scaledToWidth(300, Qt.SmoothTransformation)
                original_image_label = QLabel()
                original_image_label.setPixmap(scaled_original_pixmap)
                original_image_label.setAlignment(Qt.AlignCenter)
                
                # 创建左侧图片的垂直布局
                left_layout = QVBoxLayout()
                left_layout.addWidget(original_image_label)
                
                # 添加左侧图片说明
                original_note = BodyLabel("原作者")
                original_note.setAlignment(Qt.AlignCenter)
                left_layout.addWidget(original_note)
                
                images_layout.addLayout(left_layout)
            else:
                original_error_label = BodyLabel("无法加载原作者打赏图片")
                original_error_label.setAlignment(Qt.AlignCenter)
                images_layout.addWidget(original_error_label, 1)
        except Exception as e:
            original_error_label = BodyLabel(f"加载原作者图片时出错: {str(e)}")
            original_error_label.setAlignment(Qt.AlignCenter)
            images_layout.addWidget(original_error_label, 1)
        
        # 中间间隔 - 减小间隔大小
        spacer = QSpacerItem(20, 20, QSizePolicy.Fixed, QSizePolicy.Minimum)
        images_layout.addItem(spacer)
        
        # 右侧：我（当前用户）的打赏图片
        try:
            my_image_path = "d:/Github/Copyleft/core/enums/IMG_7190.JPG"
            my_pixmap = QPixmap(my_image_path)
            if not my_pixmap.isNull():
                # 缩放图片保持比例
                scaled_my_pixmap = my_pixmap.scaledToWidth(300, Qt.SmoothTransformation)
                my_image_label = QLabel()
                my_image_label.setPixmap(scaled_my_pixmap)
                my_image_label.setAlignment(Qt.AlignCenter)
                
                # 创建右侧图片的垂直布局
                right_layout = QVBoxLayout()
                right_layout.addWidget(my_image_label)
                
                # 添加右侧图片说明
                my_note = BodyLabel("我")
                my_note.setAlignment(Qt.AlignCenter)
                right_layout.addWidget(my_note)
                
                images_layout.addLayout(right_layout)
            else:
                my_error_label = BodyLabel("无法加载我的打赏图片")
                my_error_label.setAlignment(Qt.AlignCenter)
                images_layout.addWidget(my_error_label)
        except Exception as e:
            my_error_label = BodyLabel(f"加载我的图片时出错: {str(e)}")
            my_error_label.setAlignment(Qt.AlignCenter)
            images_layout.addWidget(my_error_label)
        
        # 将水平布局添加到主垂直布局
        main_layout.addLayout(images_layout)
        
        main_layout.addStretch(1)
        
        return interface
    
    def create_main_interface(self):
        """创建合并后的主界面"""
        interface = QWidget()
        interface.setObjectName("mainInterface")
        main_layout = QVBoxLayout(interface)
        
        # 标题
        title_label = TitleLabel("图片处理工具")
        main_layout.addWidget(title_label)
        
        # 创建水平布局，左侧设置，右侧处理
        content_layout = QHBoxLayout()
        
        # 左侧设置面板
        settings_panel = QWidget()
        settings_layout = QVBoxLayout(settings_panel)
        
        # 布局设置组
        layout_group = QGroupBox("布局设置")
        layout_form = QFormLayout(layout_group)
        
        # 布局类型选择
        self.layout_combo = ComboBox()
        for item in layout_items_dict.values():
            self.layout_combo.addItem(item.name)
            index = self.layout_combo.count() - 1
            self.layout_combo.setItemData(index, item.value)
        
        # 设置当前布局类型
        current_layout = self.config.get_layout_type()
        found_index = -1
        for i in range(self.layout_combo.count()):
            item_data = self.layout_combo.itemData(i)
            if str(item_data) == str(current_layout):
                found_index = i
                break
        
        if found_index >= 0:
            self.layout_combo.setCurrentIndex(found_index)
        else:
            if self.layout_combo.count() > 0:
                self.layout_combo.setCurrentIndex(0)
                first_layout_value = self.layout_combo.itemData(0)
                self.config.set_layout(first_layout_value)
        self.layout_combo.currentTextChanged.connect(self.on_layout_changed)
        layout_form.addRow("布局类型:", self.layout_combo)
        
        # Logo设置
        self.logo_checkbox = CheckBox("启用Logo")
        self.logo_checkbox.setChecked(self.config.get_data()['layout']['logo_enable'])
        self.logo_checkbox.stateChanged.connect(self.on_logo_changed)
        layout_form.addRow(self.logo_checkbox)
        
        settings_layout.addWidget(layout_group)
        
        # 文字位置设置组
        text_group = QGroupBox("文字位置设置")
        text_layout = QFormLayout(text_group)
        
        # 四个角落的文字设置
        self.position_combos = {}
        positions = ['left_top', 'right_top', 'left_bottom', 'right_bottom']
        position_names = {'left_top': '左上角', 'right_top': '右上角', 
                         'left_bottom': '左下角', 'right_bottom': '右下角'}
        
        for pos in positions:
            combo = ComboBox()
            text_options = [
                (MODEL_NAME, MODEL_VALUE),
                (MAKE_NAME, MAKE_VALUE),
                (LENS_NAME, LENS_VALUE),
                (PARAM_NAME, PARAM_VALUE),
                (DATETIME_NAME, DATETIME_VALUE),
                (DATE_NAME, DATE_VALUE),
                (CUSTOM_NAME, CUSTOM_VALUE),
                (NONE_NAME, NONE_VALUE),
                (LENS_MAKE_LENS_MODEL_NAME, LENS_MAKE_LENS_MODEL_VALUE),
                (CAMERA_MODEL_LENS_MODEL_NAME, CAMERA_MODEL_LENS_MODEL_VALUE),
                (TOTAL_PIXEL_NAME, TOTAL_PIXEL_VALUE),
                (CAMERA_MAKE_CAMERA_MODEL_NAME, CAMERA_MAKE_CAMERA_MODEL_VALUE),
                (FILENAME_NAME, FILENAME_VALUE),
                (DATE_FILENAME_NAME, DATE_FILENAME_VALUE),
                (DATETIME_FILENAME_NAME, DATETIME_FILENAME_VALUE),
                (GEO_INFO, GEO_INFO_VALUE)
            ]
            
            for name, value in text_options:
                combo.addItem(name)
                combo.setItemData(combo.count() - 1, value)
            
            # 设置当前值
            current_value = self.config.get_element_name(pos)
            index = combo.findData(current_value)
            if index >= 0:
                combo.setCurrentIndex(index)
            else:
                if combo.count() > 0:
                    combo.setCurrentIndex(0)
                    first_value = combo.itemData(0)
                    self.config.set_element_name(pos, first_value)
            
            combo.currentTextChanged.connect(lambda text, p=pos: self.on_position_changed(p, text))
            self.position_combos[pos] = combo
            text_layout.addRow(f"{position_names[pos]}:", combo)
        
        settings_layout.addWidget(text_group)
        
        # 高级设置组
        advanced_group = QGroupBox("高级设置")
        advanced_layout = QFormLayout(advanced_group)
        
        # 阴影设置
        self.shadow_checkbox = CheckBox("启用阴影")
        self.shadow_checkbox.setChecked(self.config.has_shadow_enabled())
        self.shadow_checkbox.stateChanged.connect(self.on_shadow_changed)
        advanced_layout.addRow(self.shadow_checkbox)
        
        # 白边设置
        self.margin_checkbox = CheckBox("启用白边")
        self.margin_checkbox.setChecked(self.config.has_white_margin_enabled())
        self.margin_checkbox.stateChanged.connect(self.on_margin_changed)
        advanced_layout.addRow(self.margin_checkbox)
        
        # 按比例填充设置
        self.padding_checkbox = CheckBox("按比例填充")
        self.padding_checkbox.setChecked(self.config.has_padding_with_original_ratio_enabled())
        self.padding_checkbox.stateChanged.connect(self.on_padding_changed)
        advanced_layout.addRow(self.padding_checkbox)
        
        # 等效焦距设置
        self.focal_checkbox = CheckBox("使用等效焦距")
        self.focal_checkbox.setChecked(self.config.use_equivalent_focal_length())
        self.focal_checkbox.stateChanged.connect(self.on_focal_changed)
        advanced_layout.addRow(self.focal_checkbox)
        
        # 图片质量
        self.quality_spin = SpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setValue(self.config.get_quality())
        self.quality_spin.valueChanged.connect(self.on_quality_changed)
        advanced_layout.addRow("图片质量 (1-100):", self.quality_spin)
        
        settings_layout.addWidget(advanced_group)
        settings_layout.addStretch(1)
        
        # 右侧处理面板
        process_panel = QWidget()
        process_layout = QVBoxLayout(process_panel)
        
        # 文件选择组
        file_group = QGroupBox("文件选择")
        file_layout = QVBoxLayout(file_group)
        
        # 输入目录选择
        input_layout = QHBoxLayout()
        self.input_path_edit = LineEdit()
        self.input_path_edit.setText(str(self.config.get_input_dir()))
        input_browse_btn = PrimaryPushButton("浏览...")
        input_browse_btn.clicked.connect(self.browse_input_directory)
        input_layout.addWidget(BodyLabel("输入目录:"))
        input_layout.addWidget(self.input_path_edit)
        input_layout.addWidget(input_browse_btn)
        file_layout.addLayout(input_layout)
        
        # 输出目录选择
        output_layout = QHBoxLayout()
        self.output_path_edit = LineEdit()
        self.output_path_edit.setText(str(self.config.get_output_dir()))
        output_browse_btn = PrimaryPushButton("浏览...")
        output_browse_btn.clicked.connect(self.browse_output_directory)
        output_layout.addWidget(BodyLabel("输出目录:"))
        output_layout.addWidget(self.output_path_edit)
        output_layout.addWidget(output_browse_btn)
        file_layout.addLayout(output_layout)
        
        process_layout.addWidget(file_group)
        
        # 处理控制组
        control_group = QGroupBox("处理控制")
        control_layout = QVBoxLayout(control_group)
        
        # 进度条
        self.progress_bar = ProgressBar()
        self.progress_bar.setVisible(False)
        control_layout.addWidget(self.progress_bar)
        
        # 处理按钮
        self.process_btn = PrimaryPushButton("开始处理")
        self.process_btn.clicked.connect(self.start_processing)
        control_layout.addWidget(self.process_btn)
        
        process_layout.addWidget(control_group)
        
        # 进度统计组
        stats_group = QGroupBox("处理统计")
        stats_layout = QFormLayout(stats_group)
        
        # 统计标签
        self.queued_label = QLabel("0")
        self.processing_label = QLabel("0")
        self.processed_label = QLabel("0")
        self.rate_label = QLabel("0.0")
        
        # 添加到布局
        stats_layout.addRow("排队数:", self.queued_label)
        stats_layout.addRow("正在处理数:", self.processing_label)
        stats_layout.addRow("已处理数:", self.processed_label)
        stats_layout.addRow("每秒处理数:", self.rate_label)
        
        process_layout.addWidget(stats_group)
        process_layout.addStretch(1)
        
        # 设置左右面板比例
        content_layout.addWidget(settings_panel, 2)  # 左侧占2份
        content_layout.addWidget(process_panel, 1)    # 右侧占1份
        
        main_layout.addLayout(content_layout)

        # 添加版本和版权标识
        footer_layout = QHBoxLayout()
        footer_layout.addStretch()
        version_label = BodyLabel("Copyleft v2.5 © 2025 PiggyWu981")
        version_label.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        footer_layout.addWidget(version_label)
        main_layout.addLayout(footer_layout)

        return interface
        
    # 保留旧的界面方法引用，用于兼容性
        
    # 保留旧的界面方法引用，用于兼容性
        
    def on_layout_changed(self, text):
        """布局类型改变事件"""
        index = self.layout_combo.currentIndex()
        if index >= 0:
            layout_value = self.layout_combo.itemData(index)
            self.config.set_layout(layout=layout_value)
            
    def on_logo_changed(self, state):
        """Logo设置改变事件"""
        if state == 2:  # Qt.Checked
            self.config.enable_logo()
        else:
            self.config.disable_logo()
            
    def on_position_changed(self, position, text):
        """文字位置改变事件"""
        combo = self.position_combos[position]
        index = combo.currentIndex()
        if index >= 0:
            value = combo.itemData(index)
            if value is not None:
                self.config.set_element_name(location=position, name=value)
            
    def on_shadow_changed(self, state):
        """阴影设置改变事件"""
        if state == 2:
            self.config.enable_shadow()
        else:
            self.config.disable_shadow()
            
    def on_margin_changed(self, state):
        """白边设置改变事件"""
        if state == 2:
            self.config.enable_white_margin()
        else:
            self.config.disable_white_margin()
            
    def on_padding_changed(self, state):
        """按比例填充设置改变事件"""
        if state == 2:
            self.config.enable_padding_with_original_ratio()
        else:
            self.config.disable_padding_with_original_ratio()
            
    def on_focal_changed(self, state):
        """等效焦距设置改变事件"""
        if state == 2:
            self.config.enable_equivalent_focal_length()
        else:
            self.config.disable_equivalent_focal_length()
            
    def on_quality_changed(self, value):
        """图片质量改变事件"""
        self.config.set_quality(value)
        
    def browse_input_directory(self):
        """浏览输入目录"""
        directory = QFileDialog.getExistingDirectory(self, "选择输入目录", str(self.config.get_input_dir()))
        if directory:
            self.input_path_edit.setText(directory)
            self.config.set_input_dir(directory)
            
    def browse_output_directory(self):
        """浏览输出目录"""
        directory = QFileDialog.getExistingDirectory(self, "选择输出目录", str(self.config.get_output_dir()))
        if directory:
            self.output_path_edit.setText(directory)
            self.config.set_output_dir(directory)
            
    def start_processing(self):
        """开始处理图片"""
        input_dir = self.input_path_edit.text()
        output_dir = self.output_path_edit.text()
        
        if not os.path.exists(input_dir):
            QMessageBox.warning(self, "错误", "输入目录不存在！")
            return
            
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            
        # 保存配置
        self.config.save()
        
        # 禁用处理按钮
        self.process_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # 重置统计标签
        self.queued_label.setText("0")
        self.processing_label.setText("0")
        self.processed_label.setText("0")
        self.rate_label.setText("0.0")
        
        # 启动处理线程
        self.processing_thread = ProcessingThread(self.config, input_dir, output_dir)
        self.processing_thread.progress_updated.connect(self.update_progress)
        self.processing_thread.processing_finished.connect(self.processing_finished)
        self.processing_thread.error_occurred.connect(self.processing_error)
        self.processing_thread.stats_updated.connect(self.update_stats)
        self.processing_thread.start()
        
    def update_progress(self, value):
        """更新进度条"""
        self.progress_bar.setValue(value)
        
    def update_stats(self, queued, processing, processed, rate):
        """更新处理统计信息"""
        self.queued_label.setText(str(queued))
        self.processing_label.setText(str(processing))
        self.processed_label.setText(str(processed))
        self.rate_label.setText(f"{rate:.2f}")
        
    def processing_finished(self):
        """处理完成"""
        self.process_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        # 确保统计信息显示最终状态
        from utils import get_file_list
        self.update_stats(0, 0, int(self.progress_bar.value() * len(get_file_list(self.input_path_edit.text())) / 100), 0)
        QMessageBox.information(self, "完成", "图片处理完成！")
        
    def processing_error(self, error_msg):
        """处理错误"""
        # 在主函数中获取logger
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"图片处理错误: {error_msg}", exc_info=True)
        QMessageBox.warning(self, "错误", error_msg)
        
    def closeEvent(self, event):
        """关闭事件"""
        try:
            # 保存配置
            self.config.save()
        except Exception as e:
            # 在主函数中获取logger
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"保存配置时发生错误: {str(e)}", exc_info=True)
        event.accept()


def main():
    """主函数"""
    try:
        # 启用高DPI支持 - 必须在创建QApplication之前设置
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        
        app = QApplication(sys.argv)
        
        # 设置应用程序信息
        app.setApplicationName("Semi-Utils")
        app.setApplicationVersion("2.5")
        app.setOrganizationName("PiggyWu981")
        
        # 设置Fluent Design主题
        setTheme(Theme.LIGHT)  # 使用亮色主题
        
        # 创建并显示主窗口
        window = MainWindow()
        window.show()
        
        # 运行应用程序
        sys.exit(app.exec_())
        
    except Exception as e:
        # 在主函数中获取logger
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"应用程序启动失败: {str(e)}", exc_info=True)
        QMessageBox.critical(None, "启动错误", f"应用程序启动失败: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    # 启动PyQt5 GUI应用程序
    main()
