import sys
import os

# --- 依赖库安全导入 (用于读取文档) ---
# 使用 try-except 来包装，避免用户环境中未安装这些第三方库时直接崩溃
try:
    import chardet # 用于探测 TXT 文件的编码格式
    HAS_CHARDET = True
except ImportError:
    HAS_CHARDET = False

try:
    import docx # 用于读取 Word (.docx) 格式的文件
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

try:
    import fitz # PyMuPDF 用于读取 PDF 格式的文件 (安装命令: pip install PyMuPDF)
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QFrame,
    QFileDialog, QMessageBox, QSplitter, QGraphicsOpacityEffect, QScrollArea, QCheckBox,
    QPushButton 
)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer, QThread
from PySide6.QtGui import QCursor, QFont

# --- 导入分离的模块 ---
# ui_components.py 中包含了所有自定义的漂亮控件
from ui_components import (
    Theme, ThemeSwitch, ThreeDButton, ModernProgressBar, 
    AIGCGaugeWidget, AIGCPieChart, HeatmapBar, DragTextEdit, ResultBlock, StatsDashboard, DetailedHeatmapWindow
)
# core_engine.py 中包含后台分析逻辑和路径工具
from core_engine import AIGCDetectionThread, get_resource_path

# ---------------------- 主程序窗口 ----------------------
class AIGCSentinel(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DeepVeri - 智能溯源系统")
        self.resize(1300, 850)
        self.is_model_valid = False # 记录模型是否存在
        self.model_path = ""
        self.last_results = []      # 用于记录最近一次的推理结果数组
        self.detailed_heatmap_win = None # 全景热力图窗口实例
        
        # 建立用于平滑主题切换的动画遮罩层 (实现类似截屏渐隐的动画效果)
        self.transition_overlay = QLabel(self)
        self.transition_overlay.hide()
        self.transition_overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True) # 鼠标穿透
        self.transition_effect = QGraphicsOpacityEffect(self.transition_overlay)
        self.transition_overlay.setGraphicsEffect(self.transition_effect)
        
        self.init_ui()           # 初始化所有 UI 组件
        self.update_theme()      # 应用初始主题色
        self.check_model_status()# 检查本地是否有可用模型

    def init_ui(self):
        # 核心中心 Widget 设置
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # === 核心优化: 彻底压榨边缘留白，将所有空间交还给内容层 ===
        layout.setContentsMargins(20, 20, 20, 15) 
        layout.setSpacing(15) 
        # =======================================================

        # ------------------ 顶部 Header ------------------
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        # 标题和副标题
        self.title_lbl = QLabel("DeepVeri")
        self.title_lbl.setStyleSheet("font-size: 24px; font-weight: 900; letter-spacing: 1.5px;") # 缩小字号
        self.sub_lbl = QLabel("深度学习文本溯源检测平台")
        self.sub_lbl.setStyleSheet(f"font-size: 11px; font-weight: bold; letter-spacing: 1px; color: #2D79FF;")
        title_box.addWidget(self.title_lbl)
        title_box.addWidget(self.sub_lbl)
        header.addLayout(title_box)
        header.addStretch() # 占位弹簧，把后面的按钮挤到右边去
        
        # 黑暗/白天模式切换开关
        self.theme_switch = ThemeSwitch()
        self.theme_switch.toggled.connect(self.toggle_theme)
        header.addWidget(self.theme_switch)
        header.addSpacing(15)
        
        # 导入文档按钮
        self.btn_import = ThreeDButton("导入文档", is_primary=False, parent=self)
        self.btn_import.setFixedWidth(100)
        self.btn_import.clicked.connect(self.import_file)
        
        # 清空内容按钮
        self.btn_clear = ThreeDButton("清空", is_primary=False, parent=self)
        self.btn_clear.setFixedWidth(80)
        self.btn_clear.clicked.connect(self.clear_content)
        
        # 开始检测按钮
        self.btn_detect = ThreeDButton("⚡ 开始深度检测", parent=self)
        self.btn_detect.setFixedWidth(140)
        self.btn_detect.clicked.connect(self.run_detection)
        
        header.addWidget(self.btn_import)
        header.addSpacing(10)
        header.addWidget(self.btn_clear)
        header.addSpacing(15)
        header.addWidget(self.btn_detect)
        layout.addLayout(header)

        # ------------------ 中间核心区域 ------------------
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(20)
        
        # 左侧：输入区
        self.card_input = QFrame()
        in_layout = QVBoxLayout(self.card_input)
        
        # --- 新增：带字数统计的横向标题栏 ---
        in_header = QHBoxLayout()
        self.label_input = QLabel("📝 原文输入 (支持 .txt / .docx / .pdf 拖入)")
        self.label_input.setStyleSheet("font-weight: bold; margin-bottom: 5px;")
        
        self.lbl_char_count = QLabel("字数: 0")
        self.lbl_char_count.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        in_header.addWidget(self.label_input)
        in_header.addStretch()
        in_header.addWidget(self.lbl_char_count)
        
        self.input_edit = DragTextEdit()
        self.input_edit.file_dropped.connect(self.handle_file_content)
        self.input_edit.textChanged.connect(self.update_char_count) # 绑定文本实时变化信号
        
        in_layout.addLayout(in_header)
        in_layout.addWidget(self.input_edit)

        # 右侧：结果区域
        self.card_output = QFrame() 
        output_outer_layout = QHBoxLayout(self.card_output)
        output_outer_layout.setContentsMargins(0, 10, 5, 10)
        
        result_main_widget = QWidget()
        result_main_layout = QVBoxLayout(result_main_widget)
        result_main_layout.setContentsMargins(0,0,0,0)
        
        # 可视化组合面板
        self.dashboard = StatsDashboard()
        self.gauge = self.dashboard.gauge
        self.pie_chart = self.dashboard.pie_chart
        result_main_layout.addWidget(self.dashboard)
        
        # 控制栏 (用于勾选只显示高风险段落)
        ctrl_bar = QHBoxLayout()
        self.label_output = QLabel("🔍 逐段溯源分析")
        self.label_output.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.chk_only_high_risk = QCheckBox("只显示高风险内容 (>60%)")
        self.chk_only_high_risk.setCursor(Qt.PointingHandCursor)
        self.chk_only_high_risk.stateChanged.connect(self.apply_filter) 
        ctrl_bar.addWidget(self.label_output)
        ctrl_bar.addStretch()
        ctrl_bar.addWidget(self.chk_only_high_risk)
        ctrl_bar.addSpacing(10)
        result_main_layout.addLayout(ctrl_bar)
        
        # 结果列表 (可滚动的区域)
        self.result_scroll = QScrollArea()
        self.result_scroll.setWidgetResizable(True)
        self.result_scroll.setFrameShape(QFrame.NoFrame)
        self.result_container = QWidget()
        self.result_layout = QVBoxLayout(self.result_container)
        self.result_layout.setAlignment(Qt.AlignTop)
        self.result_layout.setSpacing(10)
        self.result_scroll.setWidget(self.result_container)
        result_main_layout.addWidget(self.result_scroll)
        
        # 侧边热力导航条 (根据段落长度和 AI 浓度绘制的微型地图)
        self.heatmap = HeatmapBar()
        self.heatmap.clicked_section.connect(self.scroll_to_section) 
        
        # --- 核心新增：热力条悬浮提示及双击放大交互 ---
        self.heatmap.setToolTip("💡 双击展开全景热力分析图")
        self.heatmap.double_clicked.connect(self.show_detailed_heatmap)

        output_outer_layout.addWidget(result_main_widget)
        output_outer_layout.addWidget(self.heatmap)

        # 将左右面板加入到拖拽器
        splitter.addWidget(self.card_input)
        splitter.addWidget(self.card_output)
        splitter.setSizes([600, 500]) # 默认比例
        layout.addWidget(splitter, stretch=1)

        # ------------------ 底部状态栏 ------------------
        status_bar = QFrame()
        # 压缩底部状态栏高度 30 -> 24
        status_bar.setFixedHeight(24)
        sb_layout = QHBoxLayout(status_bar)
        sb_layout.setContentsMargins(0,0,0,0)
        
        self.status_icon = QLabel("●")
        self.status_text = QLabel("初始化...")
        self.status_text.setStyleSheet("font-size: 11px; font-weight: bold;")
        
        self.btn_refresh = QPushButton("🔄 刷新状态")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setFixedSize(76, 22) # 更迷你的按钮
        self.btn_refresh.clicked.connect(self.manual_refresh_model)
        
        sb_layout.addWidget(self.status_icon)
        sb_layout.addWidget(self.status_text)
        sb_layout.addWidget(self.btn_refresh)
        sb_layout.addStretch()
        
        # 硬件加速标识显示区
        self.label_device = QLabel("")
        self.label_device.setStyleSheet("color: #666; font-size: 11px; margin-right: 10px;")
        sb_layout.addWidget(self.label_device)
        
        # 进度条
        self.progress_bar = ModernProgressBar()
        self.progress_bar.setFixedWidth(300)
        sb_layout.addWidget(self.progress_bar)
        layout.addWidget(status_bar)

    # ------------------ 模型调度与交互 ------------------
    def manual_refresh_model(self):
        """手动点击刷新模型按钮的逻辑"""
        self.status_text.setText("正在扫描本地模型...")
        self.status_text.setStyleSheet("color: #FFD60A; font-weight: bold;")
        QApplication.processEvents() # 强制刷新 UI 让文字先变过去
        QThread.msleep(300) # 假装读了 300 毫秒营造仪式感
        self.check_model_status()
        if self.is_model_valid: QMessageBox.information(self, "状态更新", "成功检测到本地模型！")
        else: QMessageBox.warning(self, "状态更新", "仍然未检测到完整模型。")

    def check_model_status(self):
        """验证模型目录是否完整包含了推理所需的必要文件"""
        target_dir = get_resource_path("AIGC_Model")
        if not os.path.exists(target_dir): self.set_model_invalid("未找到 'AIGC_Model' 文件夹"); return
        try:
            files = os.listdir(target_dir)
            has_config = "config.json" in files
            # 兼容 bin 权重和 safetensors 权重两种格式
            has_bin = "pytorch_model.bin" in files or "model.safetensors" in files
            if has_config and has_bin:
                self.is_model_valid = True; self.model_path = target_dir
                self.status_icon.setStyleSheet(f"color: #00E070; font-size: 14px;")
                self.status_text.setText("本地引擎已加载")
                self.status_text.setStyleSheet("color: #30D158; font-weight: bold;")
            else: self.set_model_invalid(f"缺失核心文件")
        except Exception as e: self.set_model_invalid(f"读取失败: {str(e)}")

    def set_model_invalid(self, reason):
        """更新 UI 为模型不可用状态"""
        self.is_model_valid = False
        self.model_path = ""
        self.status_icon.setStyleSheet(f"color: #FF453A; font-size: 14px;")
        self.status_text.setText(f"⚠️ 无法检测: {reason}")
        self.status_text.setStyleSheet("color: #FF453A; font-weight: bold;")

    def update_device_ui(self, msg, is_gpu):
        """核心推理线程发来设备类型后，在此处更新状态栏的硬件信息"""
        self.label_device.setText(msg)
        color = "#00E070" if is_gpu else "#FFD60A"
        self.label_device.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 11px; margin-right: 15px;")

    # ------------------ 弹出全景热力图功能 ------------------
    def show_detailed_heatmap(self):
        """当用户双击极细热力条时被触发，打开包含筛选项和整齐列表的次级视窗"""
        if not hasattr(self, 'last_results') or not self.last_results:
            return
            
        # 如果弹窗已经打开，将其激活置顶即可
        if hasattr(self, 'detailed_heatmap_win') and self.detailed_heatmap_win and self.detailed_heatmap_win.isVisible():
            self.detailed_heatmap_win.activateWindow()
        else:
            # 否则生成全新的过滤视图窗口
            self.detailed_heatmap_win = DetailedHeatmapWindow(self.last_results, self)
            # 点击新弹窗里的独立卡片时，依然让主界面发生联动滚动！这极其方便定位
            self.detailed_heatmap_win.request_scroll.connect(self.scroll_to_section)
            self.detailed_heatmap_win.show()

    # ------------------ 主题与界面渲染 ------------------
    def toggle_theme(self, is_dark):
        """白天/黑夜主题切换动画"""
        # 第一步：把当前界面的样子截图，盖在最上面
        pixmap = self.grab()
        self.transition_overlay.setPixmap(pixmap)
        self.transition_overlay.setGeometry(0, 0, self.width(), self.height())
        self.transition_overlay.show()
        self.transition_effect.setOpacity(1.0)
        
        # 第二步：底层其实瞬间切换到了新主题
        Theme.toggle()
        self.update_theme()
        
        # 强制更新所有自定义绘制组件的颜色
        self.dashboard.update_style()
        self.btn_import.update()
        self.btn_clear.update()
        self.btn_detect.update()
        self.progress_bar.update()
        self.input_edit.update()
        
        for i in range(self.result_layout.count()):
            item = self.result_layout.itemAt(i)
            if item.widget() and isinstance(item.widget(), ResultBlock):
                item.widget().update_style()
                
        if hasattr(self, 'heatmap'): self.heatmap.update() 
        
        # 同步可能正在显示的全景分析弹窗主题
        if hasattr(self, 'detailed_heatmap_win') and self.detailed_heatmap_win and self.detailed_heatmap_win.isVisible():
            self.detailed_heatmap_win.update_theme()
        
        btn_bg = "#333" if is_dark else "#DDD"
        btn_txt = "#FFF" if is_dark else "#333"
        self.btn_refresh.setStyleSheet(f"QPushButton {{ background: {btn_bg}; color: {btn_txt}; border-radius: 4px; border: none; font-size: 11px; }} QPushButton:hover {{ background: #2D79FF; color: white; }}")
        
        if not self.is_model_valid: self.status_text.setStyleSheet("color: #FF453A; font-weight: bold;")
        else: self.status_text.setStyleSheet("color: #30D158; font-weight: bold;")
        
        # 第三步：把盖在最上面的旧主题截图透明度慢慢变0，实现平滑渐变
        self.anim_fade = QPropertyAnimation(self.transition_effect, b"opacity")
        self.anim_fade.setDuration(350)
        self.anim_fade.setStartValue(1.0)
        self.anim_fade.setEndValue(0.0)
        self.anim_fade.setEasingCurve(QEasingCurve.InOutQuad)
        self.anim_fade.finished.connect(self.transition_overlay.hide)
        self.anim_fade.start()

    def update_theme(self):
        """读取当前的 Theme 并应用到全体标准控件"""
        t = Theme.COLORS[Theme.CURRENT_MODE]
        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {t['bg_main']}; }}
            QWidget {{ color: {t['text_main']}; font-family: 'Segoe UI', 'Microsoft YaHei'; }}
            QTextEdit {{ background-color: {t['input_bg']}; color: {t['text_main']}; border: 1px solid {t['border']}; border-radius: 12px; padding: 15px; font-size: 11pt; }}
            QTextEdit:focus {{ border: 1px solid #2D79FF; }}
            QSplitter::handle {{ background: transparent; }}
            QScrollArea {{ background: transparent; border: none; }}
            QScrollArea > QWidget > QWidget {{ background: transparent; }}
            QCheckBox {{ spacing: 5px; color: {t['text_sub']}; }}
            QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid {t['border']}; }}
            QCheckBox::indicator:checked {{ background-color: #2D79FF; border-color: #2D79FF; image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIzIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwb2x5bGluZSBwb2ludHM9IjIwIDYgOSAxNyA0IDEyIi8+PC9zdmc+); }}
        """)
        self.title_lbl.setStyleSheet(f"font-size: 24px; font-weight: 900; color: {t['text_main']};")
        self.label_input.setStyleSheet(f"color: {t['text_sub']}; font-weight: bold; margin-bottom: 5px;")
        self.lbl_char_count.setStyleSheet(f"color: {t['text_sub']}; font-size: 11px; margin-bottom: 5px;") # 应用字数标签的主题色
        
        card_style = f"QFrame {{ background-color: {t['bg_card']}; border: 1px solid {t['border']}; border-radius: 16px; }}"
        self.card_input.setStyleSheet(card_style)
        self.card_output.setStyleSheet(card_style)
        self.card_input.setGraphicsEffect(Theme.shadow(30))
        self.card_output.setGraphicsEffect(Theme.shadow(30))
        
        if hasattr(self, 'dashboard'):
            self.dashboard.update_style()
            
        btn_bg = "#333" if Theme.CURRENT_MODE == 'dark' else "#DDD"
        btn_txt = "#FFF" if Theme.CURRENT_MODE == 'dark' else "#333"
        self.btn_refresh.setStyleSheet(f"QPushButton {{ background: {btn_bg}; color: {btn_txt}; border-radius: 4px; border: none; font-size: 11px; }} QPushButton:hover {{ background: #2D79FF; color: white; }}")

    def resizeEvent(self, event):
        # 保证在拉伸窗口时，主题切换的动画遮罩也跟着改变大小
        if hasattr(self, 'transition_overlay') and self.transition_overlay.isVisible(): 
            self.transition_overlay.setGeometry(0, 0, self.width(), self.height())
        super().resizeEvent(event)

    def clear_content(self):
        """重置所有输入输出和统计状态"""
        self.input_edit.clear()
        self.lbl_char_count.setText("字数: 0") # 清空时归零
        self.last_results = []
        while self.result_layout.count():
            item = self.result_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.gauge.setValue(0)
        self.progress_bar.setValue(0)
        self.heatmap.set_data([])
        self.pie_chart.set_data([0, 0, 0])
        self.dashboard.token_counter.set_data(0)  # <--- 新增：清空时重置 Token
        
        if hasattr(self, 'detailed_heatmap_win') and self.detailed_heatmap_win:
            self.detailed_heatmap_win.close() # 联通清除打开的全景图

    # ------------------ 业务逻辑与算法交互 ------------------
    def run_detection(self):
        """点击开始检测按钮触发的核心动作"""
        if not self.is_model_valid: QMessageBox.critical(self, "无法运行", f"未检测到完整模型。"); return
        text = self.input_edit.toPlainText().strip()
        if not text: 
            self.btn_detect.setText("⚠️ 内容为空")
            QTimer.singleShot(1500, lambda: self.btn_detect.setText("⚡ 开始深度检测")) # 1.5秒后恢复文字
            return
            
        # 防止重复点击
        self.btn_detect.setEnabled(False)
        self.btn_detect.setText("正在分析...")
        
        # 清空上一次的分析结果
        while self.result_layout.count():
            item = self.result_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        self.gauge.setValue(0)
        self.progress_bar.setValue(0)
        
        # 启动工作线程去算，主界面保持流畅不卡
        self.thread = AIGCDetectionThread(text, self.model_path)
        self.thread.status_signal.connect(lambda s: self.status_text.setText(s))
        self.thread.progress_signal.connect(self.progress_bar.setValue)
        self.thread.result_signal.connect(self.process_results)
        self.thread.device_signal.connect(self.update_device_ui)
        self.thread.finished.connect(lambda: [self.btn_detect.setEnabled(True), self.btn_detect.setText("⚡ 开始深度检测"), self.status_text.setText("分析完成") if self.is_model_valid else None, self.progress_bar.setValue(100)])
        self.thread.start()

    def process_results(self, res):
        """接收并处理后台线程发来的分析结果字典"""
        if "error" in res: QMessageBox.critical(self, "检测中断", res["error"]); return
        
        # 存放本次完整数据供应全景图使用
        self.last_results = res.get("paragraphs", [])
        
        # 如果旧的全景图开着，无缝刷新它
        if hasattr(self, 'detailed_heatmap_win') and self.detailed_heatmap_win and self.detailed_heatmap_win.isVisible():
            self.detailed_heatmap_win.close()
            self.show_detailed_heatmap() 
        
        # 1. 更新仪表盘
        self.gauge.setValue(res["total_ai_rate"])
        
        # 驱动中间的 Token 数字滚动动画
        self.dashboard.token_counter.set_data(res.get("total_tokens", 0))
        
        # 2. 更新热力图
        self.heatmap.set_data(self.last_results) 
        
        # 3. 统计并更新饼图
        counts = [0, 0, 0] # Human, Mixed, AI
        for p in self.last_results:
            if p.get("is_ignored"): continue
            rate = p["ai_rate"]
            if rate < 30: counts[0] += 1
            elif rate < 60: counts[1] += 1
            else: counts[2] += 1
        self.pie_chart.set_data(counts)

        # 4. 生成每一段的结果卡片块
        for i, p in enumerate(self.last_results):
            block = ResultBlock(i, p["content"], p["ai_rate"], is_ignored=p.get("is_ignored", False))
            block.request_scroll.connect(self.handle_block_resize) # 卡片伸缩时通知外层调整
            block.request_highlight.connect(self.highlight_source_text) # 点击卡片联动左侧文本高亮
            block.expanded.connect(self.on_block_expanded) # 实现手风琴效果
            self.result_layout.addWidget(block)
            
        self.result_layout.addStretch() # 把所有卡片往上顶
        self.apply_filter()

    def on_block_expanded(self, expanded_index):
        """手风琴效果：只允许同时展开一个段落详情"""
        for i in range(self.result_layout.count()):
            item = self.result_layout.itemAt(i)
            widget = item.widget()
            if widget and isinstance(widget, ResultBlock):
                if widget.index != expanded_index and widget.is_expanded:
                    widget.set_expanded(False)

    def highlight_source_text(self, content):
        """通知左侧原文输入框去高亮对应的文字内容"""
        self.input_edit.highlight_paragraph(content)

    def apply_filter(self):
        """勾选/取消勾选'仅看高风险'时候的过滤逻辑"""
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
        """当一个段落卡片展开/收缩时，重新调整包裹它的容器大小，避免滚动条异常"""
        self.result_container.adjustSize()

    def scroll_to_section(self, index):
        """点击最右侧热力条时，让中间列表自动滚动定位到对应的段落卡片"""
        if index < self.result_layout.count():
            widget = self.result_layout.itemAt(index).widget()
            if widget:
                # 如果当前是被过滤掉的隐藏块，强制取消过滤
                if widget.isHidden():
                    self.chk_only_high_risk.setChecked(False) 
                    QApplication.processEvents() 
                self.result_scroll.ensureWidgetVisible(widget) # 滚动过去
                widget.toggle_expand() # 顺便把它展开
                self.highlight_source_text(widget.content) # 左侧原文也跳转过去

    def handle_file_content(self, path):
        """读取 txt, docx 或 pdf 文件的具体内容到文本框"""
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor)) # 变漏斗鼠标
        try:
            ext = os.path.splitext(path)[1].lower(); content = ""
            if ext == '.txt':
                with open(path, 'rb') as f: raw = f.read()
                # 使用 chardet 智能推测 txt 的文本编码（防止乱码）
                encoding = chardet.detect(raw)['encoding'] if HAS_CHARDET and chardet.detect(raw)['confidence'] > 0.6 else 'utf-8'
                try: content = raw.decode(encoding)
                except: content = raw.decode('utf-8', errors='ignore')
            elif ext == '.docx':
                if not HAS_DOCX: QMessageBox.warning(self, "组件缺失", "请安装 python-docx"); return
                try:
                    doc = docx.Document(path); text_parts = []
                    # 1. 抽取段落文字
                    for para in doc.paragraphs:
                        if para.text.strip(): text_parts.append(para.text)
                    # 2. 抽取表格文字 (并做了单元格去重防止合并单元格重复读取)
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
                    import re  # 引入正则库用于清洗文本
                    doc = fitz.open(path); text_parts = []
                    for page in doc:
                        # 使用 blocks 模式，提取按物理位置聚拢的文本块（段落块）
                        blocks = page.get_text("blocks")
                        for b in blocks:
                            if b[6] == 0:  # b[6] 为 0 代表这是文本类型，排除图片等其他元素
                                text = b[4].strip()
                                if text:
                                    # 核心清洗 1：如果换行符前后都是中文字符，则直接抹除换行，实现中文断行无缝拼接
                                    text = re.sub(r'([\u4e00-\u9fa5])\s*\n\s*([\u4e00-\u9fa5])', r'\1\2', text)
                                    # 核心清洗 2：将剩余的其他换行符（如英文单词换行、标点符号换行）替换为空格
                                    text = text.replace('\n', ' ')
                                    text_parts.append(text)
                    content = "\n".join(text_parts)
                except Exception as pdf_err: QMessageBox.warning(self, "解析警告", f"PDF 解析异常: {str(pdf_err)}"); content = ""

            self.input_edit.setPlainText(content); self.status_text.setText(f"已加载: {os.path.basename(path)}")
        except Exception as e: QMessageBox.critical(self, "错误", f"读取失败: {str(e)}")
        finally: QApplication.restoreOverrideCursor() # 恢复正常鼠标指针

    def import_file(self):
        """点击导入文档按钮触发文件选择对话框"""
        path, _ = QFileDialog.getOpenFileName(self, "打开文档", "", "支持的文件 (*.txt *.docx *.pdf)")
        if path: self.handle_file_content(path)

    def update_char_count(self):
        """槽函数：实时更新左侧文本框的字数统计"""
        text = self.input_edit.toPlainText()
        # 使用千分位格式化显示 (如 1,234)
        self.lbl_char_count.setText(f"字数: {len(text):,}")

if __name__ == "__main__":
    # 防止高分屏下 UI 缩放乱套
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    # 全局字体设置，开启抗锯齿
    font = QFont("Microsoft YaHei", 10)
    font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(font)
    window = AIGCSentinel()
    window.show()
    sys.exit(app.exec())