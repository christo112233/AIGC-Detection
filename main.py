import sys
import os

# --- 依赖库安全导入 (用于读取文档) ---
try:
    import chardet 
    HAS_CHARDET = True
except ImportError:
    HAS_CHARDET = False

try:
    import docx 
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

try:
    import fitz 
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

import html
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QFrame,
    QFileDialog, QMessageBox, QSplitter, QScrollArea, QCheckBox, QPushButton 
)
from PySide6.QtCore import Qt, QTimer, QThread
from PySide6.QtGui import QCursor, QFont, QColor, QPalette 

# --- 导入分离的模块 ---
from ui_components import (
    Theme, ThreeDButton, GlowingButton, ModernProgressBar, 
    AIGCGaugeWidget, AIGCPieChart, HeatmapBar, DragTextEdit, ResultBlock, StatsDashboard, DetailedHeatmapWindow
)
from core_engine import AIGCDetectionThread, get_resource_path

# ---------------------- 主程序窗口 ----------------------
class AIGCSentinel(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DeepVeri - 智能溯源系统")
        self.resize(1300, 850)
        self.is_model_valid = False 
        self.model_path = ""
        self.last_results = []      
        self.detailed_heatmap_win = None 
        
        # --- 性能优化：更智能的渲染引擎 ---
        self.render_queue = []
        self.render_timer = QTimer(self)
        # 将频率降低至 30ms，给 UI 线程留出足够的“呼吸”间隙处理布局计算
        self.render_timer.timeout.connect(self._process_render_item)
        
        # 强制锁定为深色模式
        Theme.CURRENT_MODE = 'dark'
        
        self.init_ui()           
        self.update_theme()      
        self.check_model_status()

    def init_ui(self):
        central = QWidget()
        central.setObjectName("centralWidget") 
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # === 核心优化: 彻底压榨边缘留白 ===
        layout.setContentsMargins(20, 20, 20, 15) 
        layout.setSpacing(15) 

        # ------------------ 顶部 Header ------------------
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        self.title_lbl = QLabel("DeepVeri")
        self.title_lbl.setStyleSheet("font-size: 24px; font-weight: 900; letter-spacing: 1.5px;") 
        self.sub_lbl = QLabel("深度学习文本溯源检测平台")
        self.sub_lbl.setStyleSheet(f"font-size: 11px; font-weight: bold; letter-spacing: 1px; color: #2D79FF;")
        title_box.addWidget(self.title_lbl)
        title_box.addWidget(self.sub_lbl)
        header.addLayout(title_box)
        
        header.addSpacing(40)
        
        self.btn_clear = GlowingButton("🗑️  清空内容", variant="danger", parent=self)
        self.btn_clear.setFixedWidth(105)
        self.btn_clear.setToolTip("清空当前所有内容与检测结果")
        self.btn_clear.clicked.connect(self.clear_content)
        header.addWidget(self.btn_clear)
        
        header.addStretch() 
        
        self.btn_import = GlowingButton("📂  导入文档", variant="secondary", parent=self)
        self.btn_import.setFixedWidth(115)
        self.btn_import.clicked.connect(self.import_file)
        
        self.btn_merge = GlowingButton("✂️  合并排版", variant="secondary", parent=self)
        self.btn_merge.setFixedWidth(115)
        self.btn_merge.setToolTip("消除换行碎片，强制启用智能动态长文切分算法")
        self.btn_merge.clicked.connect(self.merge_all_lines)
        
        self.btn_detect = GlowingButton("⚡  开始深度检测", variant="primary", parent=self)
        self.btn_detect.setFixedWidth(160)
        self.btn_detect.clicked.connect(self.run_detection)
        
        header.addWidget(self.btn_import)
        header.addSpacing(12)
        header.addWidget(self.btn_merge)
        header.addSpacing(12)
        header.addWidget(self.btn_detect)
        layout.addLayout(header)

        # ------------------ 中间核心区域 ------------------
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(20)
        
        self.card_input = QFrame()
        in_layout = QVBoxLayout(self.card_input)
        
        in_header = QHBoxLayout()
        self.label_input = QLabel("📝  原文输入 (支持 .txt / .docx / .pdf 拖入)")
        self.label_input.setStyleSheet("font-weight: bold; margin-bottom: 5px;")
        
        self.lbl_char_count = QLabel("字数: 0")
        self.lbl_char_count.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        in_header.addWidget(self.label_input)
        in_header.addStretch()
        in_header.addWidget(self.lbl_char_count)
        
        self.input_edit = DragTextEdit()
        self.input_edit.file_dropped.connect(self.handle_file_content)
        self.input_edit.textChanged.connect(self.update_char_count) 
        
        in_layout.addLayout(in_header)
        in_layout.addWidget(self.input_edit)

        # 右侧：结果区域
        self.card_output = QFrame() 
        output_outer_layout = QHBoxLayout(self.card_output)
        output_outer_layout.setContentsMargins(0, 10, 5, 10)
        
        result_main_widget = QWidget()
        result_main_layout = QVBoxLayout(result_main_widget)
        result_main_layout.setContentsMargins(0,0,0,0)
        
        self.dashboard = StatsDashboard()
        self.gauge = self.dashboard.gauge
        self.pie_chart = self.dashboard.pie_chart
        result_main_layout.addWidget(self.dashboard)
        
        ctrl_bar = QHBoxLayout()
        self.label_output = QLabel("🔍  逐段溯源分析")
        self.label_output.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.chk_only_high_risk = QCheckBox("只显示高风险内容 (>60%)")
        self.chk_only_high_risk.setCursor(Qt.PointingHandCursor)
        self.chk_only_high_risk.stateChanged.connect(self.apply_filter) 
        ctrl_bar.addWidget(self.label_output)
        ctrl_bar.addStretch()
        ctrl_bar.addWidget(self.chk_only_high_risk)
        ctrl_bar.addSpacing(10)
        result_main_layout.addLayout(ctrl_bar)
        
        self.result_scroll = QScrollArea()
        self.result_scroll.setWidgetResizable(True)
        self.result_scroll.setFrameShape(QFrame.NoFrame)
        self.result_container = QWidget()
        self.result_layout = QVBoxLayout(self.result_container)
        self.result_layout.setAlignment(Qt.AlignTop)
        self.result_layout.setSpacing(10)
        self.result_scroll.setWidget(self.result_container)
        result_main_layout.addWidget(self.result_scroll)
        
        self.heatmap = HeatmapBar()
        self.heatmap.clicked_section.connect(self.scroll_to_section) 
        
        self.heatmap.setToolTip("💡 双击展开全景热力分析图")
        self.heatmap.double_clicked.connect(self.show_detailed_heatmap)

        output_outer_layout.addWidget(result_main_widget)
        output_outer_layout.addWidget(self.heatmap)

        splitter.addWidget(self.card_input)
        splitter.addWidget(self.card_output)
        splitter.setSizes([600, 500]) 
        layout.addWidget(splitter, stretch=1)

        # ------------------ 底部状态栏 ------------------
        status_bar = QFrame()
        status_bar.setFixedHeight(24)
        sb_layout = QHBoxLayout(status_bar)
        sb_layout.setContentsMargins(0,0,0,0)
        
        self.status_icon = QLabel("●")
        self.status_text = QLabel("初始化...")
        
        self.btn_refresh = QPushButton("🔄  刷新")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setFixedSize(70, 20) 
        self.btn_refresh.clicked.connect(self.manual_refresh_model)
        
        sb_layout.addWidget(self.status_icon)
        sb_layout.addWidget(self.status_text)
        sb_layout.addSpacing(5)
        sb_layout.addWidget(self.btn_refresh)
        sb_layout.addStretch()
        
        self.label_device = QLabel("")
        self.label_device.setStyleSheet("color: #666; font-size: 11px; margin-right: 10px;")
        sb_layout.addWidget(self.label_device)
        
        self.progress_bar = ModernProgressBar()
        self.progress_bar.setFixedWidth(300)
        sb_layout.addWidget(self.progress_bar)
        layout.addWidget(status_bar)

    # ------------------ 模型调度与交互 ------------------
    def manual_refresh_model(self):
        self.btn_refresh.setEnabled(False) 
        bg_color = Theme.COLORS['dark']['bg_main']
        self.status_text.setText(" ")
        self.status_text.setStyleSheet(f"background-color: {bg_color};")
        self.status_text.repaint()
        QApplication.processEvents() 
        
        self.status_text.setText("正在扫描本地模型...")
        self.status_text.setStyleSheet(f"color: {Theme.ACCENT_YELLOW.name()}; background-color: {bg_color}; font-weight: bold; font-family: 'Microsoft YaHei'; padding: 0 4px;")
        self.status_text.repaint()
        QApplication.processEvents() 
        QThread.msleep(300) 
        self.check_model_status()
        if self.is_model_valid: QMessageBox.information(self, "状态更新", "成功检测到本地模型！")
        else: QMessageBox.warning(self, "状态更新", "仍然未检测到完整模型。")
        self.btn_refresh.setEnabled(True)

    def check_model_status(self):
        target_dir = get_resource_path("AIGC_Model")
        if not os.path.exists(target_dir): self.set_model_invalid("未找到 'AIGC_Model' 文件夹"); return
        try:
            files = os.listdir(target_dir)
            has_config = "config.json" in files
            has_bin = "pytorch_model.bin" in files or "model.safetensors" in files
            bg_color = Theme.COLORS['dark']['bg_main']
            if has_config and has_bin:
                self.is_model_valid = True; self.model_path = target_dir
                self.status_icon.setStyleSheet(f"color: {Theme.ACCENT_GREEN.name()}; font-size: 14px;")
                self.status_text.setText("本地引擎已加载")
                self.status_text.setStyleSheet(f"color: {Theme.ACCENT_GREEN.name()}; background-color: {bg_color}; font-weight: bold; font-family: 'Microsoft YaHei'; padding: 0 4px;")
            else: self.set_model_invalid(f"缺失核心文件")
        except Exception as e: self.set_model_invalid(f"读取失败: {str(e)}")

    def set_model_invalid(self, reason):
        self.is_model_valid = False
        self.model_path = ""
        bg_color = Theme.COLORS['dark']['bg_main']
        self.status_icon.setStyleSheet(f"color: {Theme.ACCENT_RED.name()}; font-size: 14px;")
        self.status_text.setText(f"⚠️ 无法检测: {reason}")
        self.status_text.setStyleSheet(f"color: {Theme.ACCENT_RED.name()}; background-color: {bg_color}; font-weight: bold; font-family: 'Microsoft YaHei'; padding: 0 4px;")

    def update_device_ui(self, msg, is_gpu):
        self.label_device.setText(msg)
        color = Theme.ACCENT_GREEN.name() if is_gpu else Theme.ACCENT_YELLOW.name()
        self.label_device.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 11px; margin-right: 15px;")

    def show_detailed_heatmap(self):
        if not hasattr(self, 'last_results') or not self.last_results:
            return
        if hasattr(self, 'detailed_heatmap_win') and self.detailed_heatmap_win and self.detailed_heatmap_win.isVisible():
            self.detailed_heatmap_win.activateWindow()
        else:
            self.detailed_heatmap_win = DetailedHeatmapWindow(self.last_results, self)
            self.detailed_heatmap_win.request_scroll.connect(self.scroll_to_section)
            self.detailed_heatmap_win.show()

    # ------------------ 主题与界面渲染 ------------------
    def update_theme(self):
        t = Theme.COLORS['dark']
        
        palette = QApplication.palette()
        palette.setColor(QPalette.Window, QColor(t['bg_main']))
        palette.setColor(QPalette.WindowText, QColor(t['text_main']))
        palette.setColor(QPalette.Base, QColor(t['input_bg']))
        palette.setColor(QPalette.AlternateBase, QColor(t['bg_card']))
        palette.setColor(QPalette.ToolTipBase, QColor(t['bg_card']))
        palette.setColor(QPalette.ToolTipText, QColor(t['text_main']))
        palette.setColor(QPalette.Text, QColor(t['text_main']))
        palette.setColor(QPalette.Button, QColor(t['bg_card']))
        palette.setColor(QPalette.ButtonText, QColor(t['text_main']))
        palette.setColor(QPalette.BrightText, QColor("white"))
        palette.setColor(QPalette.Highlight, Theme.ACCENT_BLUE)
        palette.setColor(QPalette.HighlightedText, QColor("white"))
        QApplication.setPalette(palette)
        
        scrollbar_css = """
            QScrollBar:vertical { border: none; background: transparent; width: 8px; margin: 0px; }
            QScrollBar::handle:vertical { background: rgba(255, 255, 255, 0.15); border-radius: 4px; min-height: 30px; }
            QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 0.3); }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; background: none; border: none; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
            
            QScrollBar:horizontal { border: none; background: transparent; height: 8px; margin: 0px; }
            QScrollBar::handle:horizontal { background: rgba(255, 255, 255, 0.15); border-radius: 4px; min-width: 30px; }
            QScrollBar::handle:horizontal:hover { background: rgba(255, 255, 255, 0.3); }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; background: none; border: none; }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
        """
        
        self.setStyleSheet(f"""
            QMainWindow, #centralWidget {{ background-color: {t['bg_main']}; }}
            QSplitter::handle {{ background: transparent; }}
            QScrollArea {{ background: transparent; border: none; }}
            QScrollArea > QWidget > QWidget {{ background: transparent; }}
            QCheckBox {{ color: {t['text_sub']}; font-family: 'Segoe UI', 'Microsoft YaHei'; }}
            QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 6px; border: 1px solid {t['border']}; }}
            QCheckBox::indicator:checked {{ background-color: #3B82F6; border-color: #3B82F6; image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIzIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwb2x5bGluZSBwb2ludHM9IjIwIDYgOSAxNyA0IDEyIi8+PC9zdmc+); }}
            {scrollbar_css}
        """)
        
        self.input_edit.setStyleSheet(f"""
            QTextEdit {{ 
                background-color: {t['input_bg']}; 
                color: {t['text_main']}; 
                border: 1px solid rgba(255, 255, 255, 0.04); 
                border-radius: 16px; 
                padding: 24px 22px; 
                font-size: 11.5pt; 
                font-family: 'Segoe UI', 'Microsoft YaHei';
                selection-background-color: #3B82F6;
                selection-color: white;
            }}
            QTextEdit:focus {{ 
                border: 1px solid rgba(59, 130, 246, 0.5); 
                background-color: {QColor(t['input_bg']).lighter(102).name()};
            }}
        """)
        
        self.title_lbl.setStyleSheet(f"font-size: 24px; font-weight: 900; color: {t['text_main']}; font-family: 'Segoe UI', 'Microsoft YaHei';")
        self.label_input.setStyleSheet(f"color: {t['text_sub']}; font-weight: bold; margin-bottom: 5px; font-family: 'Segoe UI', 'Microsoft YaHei';")
        self.lbl_char_count.setStyleSheet(f"color: {t['text_sub']}; font-size: 11px; margin-bottom: 5px; font-family: 'Segoe UI', 'Microsoft YaHei';") 
        self.label_output.setStyleSheet(f"color: {t['text_sub']}; font-weight: bold; font-size: 14px; font-family: 'Segoe UI', 'Microsoft YaHei';")
        
        card_style = f"QFrame {{ background-color: {t['bg_card']}; border: 1px solid {t['border']}; border-radius: 16px; }}"
        self.card_input.setStyleSheet(card_style)
        self.card_output.setStyleSheet(card_style)
        self.card_input.setGraphicsEffect(Theme.shadow(35))
        self.card_output.setGraphicsEffect(Theme.shadow(35))
        
        if hasattr(self, 'dashboard'):
            self.dashboard.update_style()
        
        btn_refresh_bg = "rgba(255, 255, 255, 0.05)"
        btn_refresh_txt = "#9CA3AF"
        self.btn_refresh.setStyleSheet(f"""
            QPushButton {{
                background-color: {btn_refresh_bg};
                color: {btn_refresh_txt};
                border-radius: 10px;
                border: 1px solid rgba(255, 255, 255, 0.05);
                font-size: 11px;
                font-weight: bold;
                font-family: 'Microsoft YaHei';
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background-color: #3B82F6;
                color: white;
                border: 1px solid #3B82F6;
            }}
            QPushButton:pressed {{
                background-color: #2563EB;
            }}
        """)
        
        bg = Theme.COLORS['dark']['bg_main']
        if not self.is_model_valid: self.status_text.setStyleSheet(f"color: {Theme.ACCENT_RED.name()}; background-color: {bg}; font-weight: bold; font-family: 'Microsoft YaHei'; padding: 0 4px;")
        else: self.status_text.setStyleSheet(f"color: {Theme.ACCENT_GREEN.name()}; background-color: {bg}; font-weight: bold; font-family: 'Microsoft YaHei'; padding: 0 4px;")

    def clear_content(self):
        self.render_timer.stop() 
        self.render_queue = []
        self.input_edit.clear()
        self.lbl_char_count.setText("字数: 0") 
        self.last_results = []
        while self.result_layout.count():
            item = self.result_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.gauge.setValue(0)
        self.progress_bar.setValue(0)
        self.heatmap.set_data([])
        self.pie_chart.set_data([0, 0, 0])
        self.dashboard.token_counter.set_data(0)  
        
        if hasattr(self, 'detailed_heatmap_win') and self.detailed_heatmap_win:
            self.detailed_heatmap_win.close() 

    def merge_all_lines(self):
        text = self.input_edit.toPlainText()
        if not text.strip(): return
        
        import re
        text = re.sub(r'([\u4e00-\u9fa5])\s*\n\s*([\u4e00-\u9fa5])', r'\1\2', text)
        text = text.replace('\n', ' ')
        
        html_content = f"<div style='line-height: 1.6;'>{html.escape(text).replace(chr(10), '<br>')}</div>"
        self.input_edit.setHtml(html_content)
        
        self.status_text.setText("✅ 已合并排版结构，长文将自动切片计算")

    # ------------------ 业务逻辑与算法交互 ------------------
    def run_detection(self):
        if not self.is_model_valid: QMessageBox.critical(self, "无法运行", f"未检测到完整模型。"); return
        text = self.input_edit.toPlainText().strip()
        if not text: 
            self.btn_detect.setText("⚠️ 内容为空")
            QTimer.singleShot(1500, lambda: self.btn_detect.setText("⚡  开始深度检测")) 
            return
            
        self.btn_detect.setEnabled(False)
        self.btn_detect.setText("正在分析...")
        
        self.render_timer.stop()
        self.render_queue = []
        while self.result_layout.count():
            item = self.result_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        self.gauge.setValue(0)
        self.progress_bar.setValue(0)
        
        self.thread = AIGCDetectionThread(text, self.model_path)
        self.thread.status_signal.connect(lambda s: self.status_text.setText(s))
        self.thread.progress_signal.connect(self.progress_bar.setValue)
        self.thread.result_signal.connect(self.process_results)
        self.thread.device_signal.connect(self.update_device_ui)
        self.thread.finished.connect(lambda: [self.btn_detect.setEnabled(True), self.btn_detect.setText("⚡  开始深度检测"), self.status_text.setText("分析完成") if self.is_model_valid else None, self.progress_bar.setValue(100)])
        self.thread.start()

    def process_results(self, res):
        if "error" in res: QMessageBox.critical(self, "检测中断", res["error"]); return
        
        self.last_results = res.get("paragraphs", [])
        
        # 1. 第一阶段渲染：立即更新顶层非密集型视觉元素（让用户先看到“重点”）
        self.gauge.setValue(res["total_ai_rate"])
        self.dashboard.token_counter.set_data(res.get("total_tokens", 0))
        self.heatmap.set_data(self.last_results) 
        
        counts = [0, 0, 0] 
        for p in self.last_results:
            if p.get("is_ignored"): continue
            rate = p["ai_rate"]
            if rate < 30: counts[0] += 1
            elif rate < 60: counts[1] += 1
            else: counts[2] += 1
        self.pie_chart.set_data(counts)

        # 2. 第二阶段渲染：将密集型段落卡片任务推入队列，并给予 200ms 的视觉稳定延迟
        self.render_queue = list(enumerate(self.last_results))
        QTimer.singleShot(200, lambda: self.render_timer.start(30)) 
        
        if hasattr(self, 'detailed_heatmap_win') and self.detailed_heatmap_win and self.detailed_heatmap_win.isVisible():
            self.detailed_heatmap_win.close()
            self.show_detailed_heatmap() 

    def _process_render_item(self):
        """核心修复：降低单次主线程负担，配合 UpdatesEnabled 抑制频繁重绘引起的掉帧"""
        if not self.render_queue:
            self.render_timer.stop()
            self.result_layout.addStretch() 
            self.apply_filter() 
            return

        # 暂时关闭容器更新，防止 layout 每添加一个 widget 就全屏重绘
        self.result_container.setUpdatesEnabled(False)
        
        # 每一帧处理 1 段，确保 CPU 有足够的时间去渲染之前的阴影和透明度动画
        idx, p = self.render_queue.pop(0)
        block = ResultBlock(idx, p["content"], p["ai_rate"], is_ignored=p.get("is_ignored", False))
        block.request_scroll.connect(self.handle_block_resize) 
        block.request_highlight.connect(self.highlight_source_text) 
        block.expanded.connect(self.on_block_expanded) 
        self.result_layout.addWidget(block)
        
        if self.chk_only_high_risk.isChecked() and p["ai_rate"] <= 60:
            block.hide()

        # 重新启用更新
        self.result_container.setUpdatesEnabled(True)
        self.result_container.update()

    def on_block_expanded(self, expanded_index):
        for i in range(self.result_layout.count()):
            item = self.result_layout.itemAt(i)
            widget = item.widget()
            if widget and isinstance(widget, ResultBlock):
                if widget.index != expanded_index and widget.is_expanded:
                    widget.set_expanded(False)

    def highlight_source_text(self, content):
        self.input_edit.highlight_paragraph(content)

    def apply_filter(self):
        show_only_high = self.chk_only_high_risk.isChecked()
        for i in range(self.result_layout.count()):
            item = self.result_layout.itemAt(i)
            widget = item.widget()
            if widget and isinstance(widget, ResultBlock):
                if show_only_high:
                    if widget.ai_rate > 60: widget.show()
                    else: widget.hide()
                else:
                    widget.show()

    def handle_block_resize(self):
        self.result_container.adjustSize()

    def scroll_to_section(self, index):
        target_widget = None
        for i in range(self.result_layout.count()):
            widget = self.result_layout.itemAt(i).widget()
            if widget and isinstance(widget, ResultBlock) and widget.index == index:
                target_widget = widget
                break
        
        if target_widget:
            if target_widget.isHidden():
                self.chk_only_high_risk.setChecked(False) 
                QApplication.processEvents() 
            self.result_scroll.ensureWidgetVisible(target_widget) 
            if not target_widget.is_expanded:
                target_widget.toggle_expand() 
            self.highlight_source_text(target_widget.content) 

    def handle_file_content(self, path):
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor)) 
        try:
            ext = os.path.splitext(path)[1].lower(); content = ""
            if ext == '.txt':
                with open(path, 'rb') as f: raw = f.read()
                encoding = chardet.detect(raw)['encoding'] if HAS_CHARDET and chardet.detect(raw)['confidence'] > 0.6 else 'utf-8'
                try: content = raw.decode(encoding)
                except: content = raw.decode('utf-8', errors='ignore')
            elif ext == '.docx':
                if not HAS_DOCX: QMessageBox.warning(self, "组件缺失", "请安装 python-docx"); return
                try:
                    doc = docx.Document(path); text_parts = []
                    for para in doc.paragraphs:
                        if para.text.strip(): text_parts.append(para.text)
                    for table in doc.tables:
                        for row in table.rows:
                            unique_cells = []
                            seen_cells = set()
                            for cell in row.cells:
                                if cell not in seen_cells:
                                    unique_cells.append(cell)
                                    seen_cells.add(cell)
                            row_text_list = []
                            for cell in unique_cells:
                                txt = cell.text.strip()
                                if txt: row_text_list.append(txt)
                            if row_text_list:
                                text_parts.append(" ".join(row_text_list))
                    content = "\n".join(text_parts)
                except Exception as doc_err: QMessageBox.warning(self, "解析警告", f"文档解析异常: {str(doc_err)}"); content = ""
            elif ext == '.pdf':
                if not HAS_PDF: QMessageBox.warning(self, "组件缺失", "请安装 PyMuPDF 库以支持 PDF 读取:\npip install PyMuPDF"); return
                try:
                    import re 
                    doc = fitz.open(path); text_parts = []
                    for page in doc:
                        blocks = page.get_text("blocks")
                        for b in blocks:
                            if b[6] == 0:  
                                text = b[4].strip()
                                if text:
                                    text = re.sub(r'([\u4e00-\u9fa5])\s*\n\s*([\u4e00-\u9fa5])', r'\1\2', text)
                                    text = text.replace('\n', ' ')
                                    text_parts.append(text)
                    content = "\n".join(text_parts)
                except Exception as pdf_err: QMessageBox.warning(self, "解析警告", f"PDF 解析异常: {str(pdf_err)}"); content = ""
            
            html_content = f"<div style='line-height: 1.6;'>{html.escape(content).replace(chr(10), '<br>')}</div>"
            self.input_edit.setHtml(html_content)
            self.status_text.setText(f"已加载: {os.path.basename(path)}")
            
        except Exception as e: QMessageBox.critical(self, "错误", f"读取失败: {str(e)}")
        finally: QApplication.restoreOverrideCursor() 

    def import_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "打开文档", "", "支持的文件 (*.txt *.docx *.pdf)")
        if path: self.handle_file_content(path)

    def update_char_count(self):
        text = self.input_edit.toPlainText()
        self.lbl_char_count.setText(f"字数: {len(text):,}")

if __name__ == "__main__":
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    font = QFont("Microsoft YaHei", 10)
    font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(font)
    window = AIGCSentinel()
    window.show()
    sys.exit(app.exec())