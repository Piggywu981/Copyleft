"""
Semi-Utils - PyQt5 GUI版本主程序入口点
基于semi-utils开源项目迁移而来
整合了主窗口界面功能，使用PyQt-Fluent-Widgets美化界面
"""
import os
import sys
import logging
import traceback
from pathlib import Path

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import (QApplication, QVBoxLayout, QHBoxLayout, 
                             QWidget, QGroupBox, QFormLayout, QTextEdit,
                             QMessageBox, QFileDialog)

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


class ProcessingThread(QThread):
    """图片处理线程"""
    progress_updated = pyqtSignal(int)
    processing_finished = pyqtSignal()
    error_occurred = pyqtSignal(str)
    
    def __init__(self, config, input_dir, output_dir):
        super().__init__()
        self.config = config
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.processor_chain = ProcessorChain()
        
    def run(self):
        try:
            from core.entity.image_container import ImageContainer
            from utils import ENCODING
            
            file_list = get_file_list(self.input_dir)
            total_files = len(file_list)
            
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
            
            # 处理每个文件
            for i, source_path in enumerate(file_list):
                container = ImageContainer(source_path)
                container.is_use_equivalent_focal_length(self.config.use_equivalent_focal_length())
                
                try:
                    self.processor_chain.process(container)
                    target_path = Path(self.output_dir).joinpath(source_path.name)
                    container.save(target_path, quality=self.config.get_quality())
                    container.close()
                except Exception as e:
                    error_msg = f"处理文件 {source_path.name} 时出错: {str(e)}"
                    # 在ProcessingThread中获取logger
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(error_msg, exc_info=True)
                    self.error_occurred.emit(error_msg)
                
                # 更新进度
                progress = int((i + 1) / total_files * 100)
                self.progress_updated.emit(progress)
            
            self.processing_finished.emit()
            
        except Exception as e:
            error_msg = f"处理过程中发生错误: {str(e)}"
            # 在ProcessingThread中获取logger
            import logging
            logger = logging.getLogger(__name__)
            logger.error(error_msg, exc_info=True)
            self.error_occurred.emit(error_msg)


class MainWindow(FluentWindow):
    """主窗口类 - 使用Fluent Design风格"""
    
    def __init__(self):
        super().__init__()
        self.config = config
        self.processing_thread = None
        self.init_ui()
        
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("Semi-Utils - 图片处理工具")
        self.resize(1000, 700)
        
        # 设置主题颜色
        setThemeColor('#0078D4')  # Microsoft蓝色主题色
        
        # 创建各个界面
        self.basic_interface = self.create_basic_interface()
        self.advanced_interface = self.create_advanced_interface()
        self.processing_interface = self.create_processing_interface()
        
        # 添加界面到导航
        self.addSubInterface(self.basic_interface, FluentIcon.HOME, "基本设置")
        self.addSubInterface(self.advanced_interface, FluentIcon.SETTING, "高级设置")
        self.addSubInterface(self.processing_interface, FluentIcon.PHOTO, "图片处理")
        
        # 设置初始界面
        self.stackedWidget.setCurrentWidget(self.basic_interface)
        self.navigationInterface.setCurrentItem(self.basic_interface.objectName())
        
    def create_basic_interface(self):
        """创建基本设置界面"""
        interface = QWidget()
        interface.setObjectName("basicInterface")  # 设置对象名称
        layout = QVBoxLayout(interface)
        
        # 标题
        title_label = TitleLabel("基本设置")
        layout.addWidget(title_label)
        
        # 布局设置组
        layout_group = QGroupBox("布局设置")
        layout_form = QFormLayout(layout_group)
        
        # 布局类型选择
        self.layout_combo = ComboBox()
        for item in layout_items_dict.values():
            # 使用setItemData而不是addItem的第二个参数
            self.layout_combo.addItem(item.name)
            index = self.layout_combo.count() - 1
            self.layout_combo.setItemData(index, item.value)
        # 设置当前布局类型
        current_layout = self.config.get_layout_type()
        
        # 手动查找匹配的项，因为findData可能有问题
        found_index = -1
        for i in range(self.layout_combo.count()):
            item_data = self.layout_combo.itemData(i)
            if str(item_data) == str(current_layout):
                found_index = i
                break
        
        if found_index >= 0:
            self.layout_combo.setCurrentIndex(found_index)
        else:
            # 如果当前布局类型不在可用列表中，设置为第一个可用项
            if self.layout_combo.count() > 0:
                self.layout_combo.setCurrentIndex(0)
                # 同时更新配置为第一个可用布局类型
                first_layout_value = self.layout_combo.itemData(0)
                self.config.set_layout(first_layout_value)
        self.layout_combo.currentTextChanged.connect(self.on_layout_changed)
        self.layout_combo.currentTextChanged.connect(self.on_layout_changed)
        layout_form.addRow("布局类型:", self.layout_combo)
        
        # Logo设置
        self.logo_checkbox = CheckBox("启用Logo")
        self.logo_checkbox.setChecked(self.config.get_data()['layout']['logo_enable'])
        self.logo_checkbox.stateChanged.connect(self.on_logo_changed)
        layout_form.addRow(self.logo_checkbox)
        
        layout.addWidget(layout_group)
        
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
            # 添加所有可选的文字类型
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
                # 如果当前值不在可用列表中，设置为第一个可用项
                if combo.count() > 0:
                    combo.setCurrentIndex(0)
                    # 同时更新配置为第一个可用值
                    first_value = combo.itemData(0)
                    self.config.set_element_name(pos, first_value)
            
            combo.currentTextChanged.connect(lambda text, p=pos: self.on_position_changed(p, text))
            self.position_combos[pos] = combo
            text_layout.addRow(f"{position_names[pos]}:", combo)
        
        layout.addWidget(text_group)
        
        layout.addStretch(1)
        return interface
        
    def create_advanced_interface(self):
        """创建高级设置界面"""
        interface = QWidget()
        interface.setObjectName("advancedInterface")  # 设置对象名称
        layout = QVBoxLayout(interface)
        
        # 标题
        title_label = TitleLabel("高级设置")
        layout.addWidget(title_label)
        
        # 效果设置组
        effects_group = QGroupBox("效果设置")
        effects_layout = QFormLayout(effects_group)
        
        # 阴影设置
        self.shadow_checkbox = CheckBox("启用阴影")
        self.shadow_checkbox.setChecked(self.config.has_shadow_enabled())
        self.shadow_checkbox.stateChanged.connect(self.on_shadow_changed)
        effects_layout.addRow(self.shadow_checkbox)
        
        # 白边设置
        self.margin_checkbox = CheckBox("启用白边")
        self.margin_checkbox.setChecked(self.config.has_white_margin_enabled())
        self.margin_checkbox.stateChanged.connect(self.on_margin_changed)
        effects_layout.addRow(self.margin_checkbox)
        
        # 按比例填充设置
        self.padding_checkbox = CheckBox("按比例填充")
        self.padding_checkbox.setChecked(self.config.has_padding_with_original_ratio_enabled())
        self.padding_checkbox.stateChanged.connect(self.on_padding_changed)
        effects_layout.addRow(self.padding_checkbox)
        
        # 等效焦距设置
        self.focal_checkbox = CheckBox("使用等效焦距")
        self.focal_checkbox.setChecked(self.config.use_equivalent_focal_length())
        self.focal_checkbox.stateChanged.connect(self.on_focal_changed)
        effects_layout.addRow(self.focal_checkbox)
        
        layout.addWidget(effects_group)
        
        # 质量设置组
        quality_group = QGroupBox("输出设置")
        quality_layout = QFormLayout(quality_group)
        
        # 图片质量
        self.quality_spin = SpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setValue(self.config.get_quality())
        self.quality_spin.valueChanged.connect(self.on_quality_changed)
        quality_layout.addRow("图片质量 (1-100):", self.quality_spin)
        
        layout.addWidget(quality_group)
        
        layout.addStretch(1)
        return interface
        
    def create_processing_interface(self):
        """创建处理界面"""
        interface = QWidget()
        interface.setObjectName("processingInterface")  # 设置对象名称
        layout = QVBoxLayout(interface)
        
        # 标题
        title_label = TitleLabel("图片处理")
        layout.addWidget(title_label)
        
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
        
        layout.addWidget(file_group)
        
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
        
        # 日志显示
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        control_layout.addWidget(BodyLabel("处理日志:"))
        control_layout.addWidget(self.log_text)
        
        layout.addWidget(control_group)
        
        return interface
        
    def on_layout_changed(self, text):
        """布局类型改变事件"""
        index = self.layout_combo.currentIndex()
        if index >= 0:
            layout_value = self.layout_combo.itemData(index)
            self.config.set_layout(layout=layout_value)
            self.log_text.append(f"布局已更改为: {text}")
            
    def on_logo_changed(self, state):
        """Logo设置改变事件"""
        if state == 2:  # Qt.Checked
            self.config.enable_logo()
            self.log_text.append("Logo已启用")
        else:
            self.config.disable_logo()
            self.log_text.append("Logo已禁用")
            
    def on_position_changed(self, position, text):
        """文字位置改变事件"""
        combo = self.position_combos[position]
        index = combo.currentIndex()
        if index >= 0:
            value = combo.itemData(index)
            if value is not None:
                self.config.set_element_name(location=position, name=value)
                position_names = {'left_top': '左上角', 'right_top': '右上角', 
                                 'left_bottom': '左下角', 'right_bottom': '右下角'}
                self.log_text.append(f"{position_names[position]}文字已设置为: {text}")
            
    def on_shadow_changed(self, state):
        """阴影设置改变事件"""
        if state == 2:
            self.config.enable_shadow()
            self.log_text.append("阴影效果已启用")
        else:
            self.config.disable_shadow()
            self.log_text.append("阴影效果已禁用")
            
    def on_margin_changed(self, state):
        """白边设置改变事件"""
        if state == 2:
            self.config.enable_white_margin()
            self.log_text.append("白边效果已启用")
        else:
            self.config.disable_white_margin()
            self.log_text.append("白边效果已禁用")
            
    def on_padding_changed(self, state):
        """按比例填充设置改变事件"""
        if state == 2:
            self.config.enable_padding_with_original_ratio()
            self.log_text.append("按比例填充已启用")
        else:
            self.config.disable_padding_with_original_ratio()
            self.log_text.append("按比例填充已禁用")
            
    def on_focal_changed(self, state):
        """等效焦距设置改变事件"""
        if state == 2:
            self.config.enable_equivalent_focal_length()
            self.log_text.append("等效焦距已启用")
        else:
            self.config.disable_equivalent_focal_length()
            self.log_text.append("等效焦距已禁用")
            
    def on_quality_changed(self, value):
        """图片质量改变事件"""
        self.config.set_quality(value)
        self.log_text.append(f"图片质量已设置为: {value}")
        
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
        self.log_text.append("开始处理图片...")
        
        # 启动处理线程
        self.processing_thread = ProcessingThread(self.config, input_dir, output_dir)
        self.processing_thread.progress_updated.connect(self.update_progress)
        self.processing_thread.processing_finished.connect(self.processing_finished)
        self.processing_thread.error_occurred.connect(self.processing_error)
        self.processing_thread.start()
        
    def update_progress(self, value):
        """更新进度条"""
        self.progress_bar.setValue(value)
        
    def processing_finished(self):
        """处理完成"""
        self.process_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.log_text.append("图片处理完成！")
        QMessageBox.information(self, "完成", "图片处理完成！")
        
    def processing_error(self, error_msg):
        """处理错误"""
        # 在主函数中获取logger
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"图片处理错误: {error_msg}", exc_info=True)
        self.log_text.append(f"错误: {error_msg}")
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
        app = QApplication(sys.argv)
        
        # 设置应用程序信息
        app.setApplicationName("Semi-Utils")
        app.setApplicationVersion("2.0")
        app.setOrganizationName("leslievan")
        
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
