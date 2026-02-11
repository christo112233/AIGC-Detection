import sys
import os
import torch
import random
import math
import time
import re

# 导入分离的 UI 组件
# 确保 ui_components.py 在同一目录下
from ui_components import (
    Theme, ThemeSwitch, ThreeDButton, ModernProgressBar, 
    AIGCGaugeWidget, AIGCPieChart, HeatmapBar, DragTextEdit, ResultBlock
)

# --- 核心修复：防止 PyInstaller --noconsole 模式下 transformers 报错 ---
class NullWriter:
    def write(self, text): pass
    def flush(self): pass
    def isatty(self): return False

if sys.stdout is None: sys.stdout = NullWriter()
if sys.stderr is None: sys.stderr = NullWriter()

# --- 依赖库安全导入 ---
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

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QFrame,
    QFileDialog, QMessageBox, QSplitter, QGraphicsOpacityEffect, QScrollArea, QCheckBox,
    QPushButton 
)
from PySide6.QtCore import (
    Qt, Signal, QThread, QPropertyAnimation, QEasingCurve, QTimer
)
from PySide6.QtGui import QCursor, QFont

# ---------------------- 路径处理辅助函数 ----------------------
def get_resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path_external = os.path.dirname(sys.executable)
    else:
        base_path_external = os.path.dirname(os.path.abspath(__file__))
    
    external_path = os.path.join(base_path_external, relative_path)
    if os.path.exists(external_path):
        return external_path

    if hasattr(sys, '_MEIPASS'):
        internal_path = os.path.join(sys._MEIPASS, relative_path)
        return internal_path

    return external_path

# ---------------------- 核心检测线程 ----------------------
class AIGCDetectionThread(QThread):
    progress_signal = Signal(int)
    result_signal = Signal(dict)
    status_signal = Signal(str)
    device_signal = Signal(str, bool)

    def __init__(self, text, model_path):
        super().__init__()
        self.text = text
        self.model_path = model_path
        self.MIN_VALID_CHARS = 10
        self.TEMPERATURE = 2.0
        self.POWER_FACTOR = 3.5

    def calculate_human_features(self, text):
        sentences = re.split(r'[。.!！?？;；\n]+', text)
        sentences = [s for s in sentences if len(s.strip()) > 3]
        if len(sentences) < 3: return 0.0
        lengths = [len(s) for s in sentences]
        mean_len = sum(lengths) / len(lengths)
        variance = sum((l - mean_len) ** 2 for l in lengths) / len(lengths)
        std_dev = math.sqrt(variance)
        cv = std_dev / (mean_len + 1e-5)
        bonus = 0.0
        if cv > 0.4: bonus = min((cv - 0.4) * 0.6, 0.3)
        return bonus

    def run(self):
        if not self.model_path or not os.path.exists(self.model_path):
            self.result_signal.emit({"error": "模型路径无效"})
            return

        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
            import torch.nn.functional as F

            use_cuda = torch.cuda.is_available()
            use_mps = hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
            
            if use_cuda:
                device_str = "cuda"
                gpu_name = torch.cuda.get_device_name(0)
                if len(gpu_name) > 20: gpu_name = gpu_name[:20] + "..."
                self.device_signal.emit(f"🚀 显卡加速: {gpu_name} (Torch {torch.__version__})", True)
            elif use_mps:
                device_str = "mps"
                self.device_signal.emit(f"⚡ Mac GPU 加速 (Torch {torch.__version__})", True)
            else:
                device_str = "cpu"
                version = torch.__version__
                extra_info = " [错误: 安装了CPU版Torch]" if "+cpu" in version else (" [未发现NVIDIA显卡]" if not use_cuda else "")
                self.device_signal.emit(f"🐢 CPU 运算 (Torch {version}){extra_info}", False)
            
            torch_device = torch.device(device_str)
            
            self.progress_signal.emit(10)
            self.status_signal.emit("加载本地权重 (config, bin, vocab)...")
            
            tokenizer = AutoTokenizer.from_pretrained(self.model_path, local_files_only=True)
            model = AutoModelForSequenceClassification.from_pretrained(self.model_path, local_files_only=True)
            model.to(torch_device)
            model.eval() 
            self.progress_signal.emit(30)

            ai_label_id = 1 
            if hasattr(model.config, 'id2label') and model.config.id2label:
                for idx, label in model.config.id2label.items():
                    if any(x in str(label).lower() for x in ['fake', 'ai', 'chatgpt', 'generated', '1', 'label_1']):
                        ai_label_id = int(idx); break

            paragraphs = [p for p in self.text.split("\n") if p.strip()]
            if not paragraphs:
                self.result_signal.emit({"total_ai_rate": 0, "paragraphs": []}); return

            results = []
            total_weighted_score = 0; total_valid_weight = 0

            for idx, para in enumerate(paragraphs):
                self.status_signal.emit(f"深度指纹分析中... {idx+1}/{len(paragraphs)}")
                try:
                    inputs = tokenizer(para, return_tensors="pt", truncation=True, max_length=512)
                    inputs = {k: v.to(torch_device) for k, v in inputs.items()}
                    with torch.no_grad():
                        outputs = model(**inputs)
                        logits = outputs.logits
                        scaled_logits = logits / self.TEMPERATURE
                        probs = F.softmax(scaled_logits, dim=-1)
                        raw_ai_score = probs[0][ai_label_id].item()
                        human_bonus = self.calculate_human_features(para)
                        adjusted_score = max(0.0, raw_ai_score - human_bonus)
                        final_ai_score = math.pow(adjusted_score, self.POWER_FACTOR)
                        ai_rate = round(final_ai_score * 100, 2)
                    
                    valid_chars = "".join(para.split())
                    para_len = len(valid_chars)
                    is_ignored = para_len < self.MIN_VALID_CHARS
                    weight = 0 if is_ignored else para_len
                    
                    results.append({"content": para, "ai_rate": ai_rate, "is_ignored": is_ignored})
                    if not is_ignored:
                        total_weighted_score += (ai_rate * weight); total_valid_weight += weight
                except Exception as e:
                    if "upgrade torch" in str(e) and "v2.6" in str(e): raise e 
                    print(f"Segment Error: {e}")
                self.progress_signal.emit(30 + int(((idx + 1) / len(paragraphs)) * 65))

            avg = round(total_weighted_score / total_valid_weight, 2) if total_valid_weight > 0 else 0
            self.result_signal.emit({"total_ai_rate": avg, "paragraphs": results})

        except Exception as e:
            if "upgrade torch" in str(e) and "v2.6" in str(e):
                self.result_signal.emit({"error": "【环境版本冲突】\n请升级 PyTorch 版本。\npip install --upgrade torch torchvision torchaudio"})
            else:
                self.result_signal.emit({"error": f"推理引擎异常:\n{str(e)}"})

# ---------------------- 主窗口 ----------------------
class AIGCSentinel(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AIGC 哨兵 - 智能溯源系统")
        self.resize(1300, 850)
        self.is_model_valid = False; self.model_path = ""
        self.transition_overlay = QLabel(self)
        self.transition_overlay.hide()
        self.transition_overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.transition_effect = QGraphicsOpacityEffect(self.transition_overlay)
        self.transition_overlay.setGraphicsEffect(self.transition_effect)
        self.init_ui()
        self.update_theme()
        self.check_model_status() 

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(40, 40, 40, 30)
        layout.setSpacing(25)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        self.title_lbl = QLabel("AIGC SENTINEL")
        self.title_lbl.setStyleSheet("font-size: 28px; font-weight: 900; letter-spacing: 2px;")
        self.sub_lbl = QLabel("深度学习文本溯源检测平台")
        self.sub_lbl.setStyleSheet(f"font-size: 12px; font-weight: bold; letter-spacing: 1px; color: #2D79FF;")
        title_box.addWidget(self.title_lbl)
        title_box.addWidget(self.sub_lbl)
        header.addLayout(title_box)
        header.addStretch()
        self.theme_switch = ThemeSwitch()
        self.theme_switch.toggled.connect(self.toggle_theme)
        header.addWidget(self.theme_switch)
        header.addSpacing(20)
        self.btn_import = ThreeDButton("导入文档", is_primary=False, parent=self)
        self.btn_import.setFixedWidth(120)
        self.btn_import.clicked.connect(self.import_file)
        self.btn_clear = ThreeDButton("清空", is_primary=False, parent=self)
        self.btn_clear.setFixedWidth(100)
        self.btn_clear.clicked.connect(self.clear_content)
        self.btn_detect = ThreeDButton("⚡ 开始深度检测", parent=self)
        self.btn_detect.setFixedWidth(180)
        self.btn_detect.clicked.connect(self.run_detection)
        header.addWidget(self.btn_import)
        header.addSpacing(10)
        header.addWidget(self.btn_clear)
        header.addSpacing(15)
        header.addWidget(self.btn_detect)
        layout.addLayout(header)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(20)
        self.card_input = QFrame()
        in_layout = QVBoxLayout(self.card_input)
        self.label_input = QLabel("📝 原文输入 (支持 .txt / .docx 拖入)")
        self.label_input.setStyleSheet("font-weight: bold; margin-bottom: 5px;")
        self.input_edit = DragTextEdit()
        self.input_edit.file_dropped.connect(self.handle_file_content)
        in_layout.addWidget(self.label_input)
        in_layout.addWidget(self.input_edit)

        # 结果区域容器
        self.card_output = QFrame() 
        # 使用 HBoxLayout 来放置 滚动区 + 热力图
        output_outer_layout = QHBoxLayout(self.card_output)
        output_outer_layout.setContentsMargins(0, 10, 5, 10)
        
        # 结果主体 (仪表盘 + 饼图 + 列表)
        result_main_widget = QWidget()
        result_main_layout = QVBoxLayout(result_main_widget)
        result_main_layout.setContentsMargins(0,0,0,0)
        
        # 1. 顶部数据可视化区域 (横向均分)
        viz_container = QWidget()
        viz_layout = QHBoxLayout(viz_container)
        viz_layout.setContentsMargins(0, 0, 0, 0)
        
        # 左：仪表盘
        self.gauge = AIGCGaugeWidget()
        
        # 右：饼状图
        self.pie_chart = AIGCPieChart()
        
        viz_layout.addWidget(self.gauge, 1)
        viz_layout.addWidget(self.pie_chart, 1)
        
        result_main_layout.addWidget(viz_container)
        
        # 2. 控制栏 (只看超标 + 标题)
        ctrl_bar = QHBoxLayout()
        self.label_output = QLabel("🔍 逐段溯源分析")
        self.label_output.setStyleSheet("font-weight: bold; font-size: 14px;")
        
        self.chk_only_high_risk = QCheckBox("只显示高风险内容 (>60%)")
        self.chk_only_high_risk.setCursor(Qt.PointingHandCursor)
        self.chk_only_high_risk.stateChanged.connect(self.apply_filter) # 连接过滤信号
        
        ctrl_bar.addWidget(self.label_output)
        ctrl_bar.addStretch()
        ctrl_bar.addWidget(self.chk_only_high_risk)
        ctrl_bar.addSpacing(10)
        
        result_main_layout.addLayout(ctrl_bar)
        
        # 3. 结果列表
        self.result_scroll = QScrollArea()
        self.result_scroll.setWidgetResizable(True)
        self.result_scroll.setFrameShape(QFrame.NoFrame)
        self.result_container = QWidget()
        self.result_layout = QVBoxLayout(self.result_container)
        self.result_layout.setAlignment(Qt.AlignTop)
        self.result_layout.setSpacing(10) # 间距缩小一点
        self.result_scroll.setWidget(self.result_container)
        
        result_main_layout.addWidget(self.result_scroll)
        
        # 热力导航条 (Heatmap Bar)
        self.heatmap = HeatmapBar()
        self.heatmap.clicked_section.connect(self.scroll_to_section) # 连接跳转信号

        output_outer_layout.addWidget(result_main_widget)
        output_outer_layout.addWidget(self.heatmap) # 添加到右侧

        splitter.addWidget(self.card_input)
        splitter.addWidget(self.card_output)
        splitter.setSizes([600, 500])
        layout.addWidget(splitter, stretch=1)

        status_bar = QFrame()
        status_bar.setFixedHeight(30)
        sb_layout = QHBoxLayout(status_bar)
        sb_layout.setContentsMargins(0,0,0,0)
        self.status_icon = QLabel("●")
        self.status_text = QLabel("初始化...")
        self.status_text.setStyleSheet("font-size: 12px; font-weight: bold;")
        self.btn_refresh = QPushButton("🔄 刷新状态")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setFixedSize(80, 24)
        self.btn_refresh.clicked.connect(self.manual_refresh_model)
        sb_layout.addWidget(self.status_icon)
        sb_layout.addWidget(self.status_text)
        sb_layout.addWidget(self.btn_refresh)
        sb_layout.addStretch()
        self.label_device = QLabel("")
        self.label_device.setStyleSheet("color: #666; font-size: 11px; margin-right: 10px;")
        sb_layout.addWidget(self.label_device)
        self.progress_bar = ModernProgressBar()
        self.progress_bar.setFixedWidth(300)
        sb_layout.addWidget(self.progress_bar)
        layout.addWidget(status_bar)

    def manual_refresh_model(self):
        self.status_text.setText("正在扫描本地模型...")
        self.status_text.setStyleSheet("color: #FFD60A; font-weight: bold;")
        QApplication.processEvents()
        QThread.msleep(300)
        self.check_model_status()
        if self.is_model_valid: QMessageBox.information(self, "状态更新", "成功检测到本地模型！")
        else: QMessageBox.warning(self, "状态更新", "仍然未检测到完整模型。")

    def check_model_status(self):
        target_dir = get_resource_path("AIGC_Model")
        if not os.path.exists(target_dir): self.set_model_invalid("未找到 'AIGC_Model' 文件夹"); return
        try:
            files = os.listdir(target_dir)
            has_config = "config.json" in files
            has_bin = "pytorch_model.bin" in files or "model.safetensors" in files
            if has_config and has_bin:
                self.is_model_valid = True; self.model_path = target_dir
                self.status_icon.setStyleSheet(f"color: #00E070; font-size: 16px;")
                self.status_text.setText("本地引擎已加载")
                self.status_text.setStyleSheet("color: #30D158; font-weight: bold;")
            else: self.set_model_invalid(f"缺失文件")
        except Exception as e: self.set_model_invalid(f"读取失败: {str(e)}")

    def set_model_invalid(self, reason):
        self.is_model_valid = False
        self.model_path = ""
        self.status_icon.setStyleSheet(f"color: #FF453A; font-size: 16px;")
        self.status_text.setText(f"⚠️ 无法检测: {reason}")
        self.status_text.setStyleSheet("color: #FF453A; font-weight: bold;")

    def update_device_ui(self, msg, is_gpu):
        self.label_device.setText(msg)
        color = "#00E070" if is_gpu else "#FFD60A"
        self.label_device.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 11px; margin-right: 15px;")

    def toggle_theme(self, is_dark):
        pixmap = self.grab()
        self.transition_overlay.setPixmap(pixmap)
        self.transition_overlay.setGeometry(0, 0, self.width(), self.height())
        self.transition_overlay.show()
        self.transition_effect.setOpacity(1.0)
        
        Theme.toggle()
        self.update_theme()
        
        self.gauge.update()
        self.pie_chart.update()
        self.btn_import.update()
        self.btn_clear.update()
        self.btn_detect.update()
        self.progress_bar.update()
        self.input_edit.update()
        
        # 1. 刷新所有卡片样式 (修复颜色不同步问题)
        for i in range(self.result_layout.count()):
            item = self.result_layout.itemAt(i)
            if item.widget() and isinstance(item.widget(), ResultBlock):
                item.widget().update_style()
                
        if hasattr(self, 'heatmap'): self.heatmap.update() 
        
        btn_bg = "#333" if is_dark else "#DDD"
        btn_txt = "#FFF" if is_dark else "#333"
        self.btn_refresh.setStyleSheet(f"QPushButton {{ background: {btn_bg}; color: {btn_txt}; border-radius: 4px; border: none; font-size: 11px; }} QPushButton:hover {{ background: #2D79FF; color: white; }}")
        
        if not self.is_model_valid: self.status_text.setStyleSheet("color: #FF453A; font-weight: bold;")
        else: self.status_text.setStyleSheet("color: #30D158; font-weight: bold;")
        
        self.anim_fade = QPropertyAnimation(self.transition_effect, b"opacity")
        self.anim_fade.setDuration(350)
        self.anim_fade.setStartValue(1.0)
        self.anim_fade.setEndValue(0.0)
        self.anim_fade.setEasingCurve(QEasingCurve.InOutQuad)
        self.anim_fade.finished.connect(self.transition_overlay.hide)
        self.anim_fade.start()

    def update_theme(self):
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
        self.title_lbl.setStyleSheet(f"font-size: 28px; font-weight: 900; color: {t['text_main']};")
        self.label_input.setStyleSheet(f"color: {t['text_sub']}; font-weight: bold; margin-bottom: 5px;")
        card_style = f"QFrame {{ background-color: {t['bg_card']}; border: 1px solid {t['border']}; border-radius: 16px; }}"
        self.card_input.setStyleSheet(card_style)
        self.card_output.setStyleSheet(card_style)
        self.card_input.setGraphicsEffect(Theme.shadow(30))
        self.card_output.setGraphicsEffect(Theme.shadow(30))
        btn_bg = "#333" if Theme.CURRENT_MODE == 'dark' else "#DDD"
        btn_txt = "#FFF" if Theme.CURRENT_MODE == 'dark' else "#333"
        self.btn_refresh.setStyleSheet(f"QPushButton {{ background: {btn_bg}; color: {btn_txt}; border-radius: 4px; border: none; font-size: 11px; }} QPushButton:hover {{ background: #2D79FF; color: white; }}")

    def resizeEvent(self, event):
        if hasattr(self, 'transition_overlay') and self.transition_overlay.isVisible(): self.transition_overlay.setGeometry(0, 0, self.width(), self.height())
        super().resizeEvent(event)

    def clear_content(self):
        self.input_edit.clear()
        while self.result_layout.count():
            item = self.result_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.gauge.setValue(0)
        self.progress_bar.setValue(0)
        self.heatmap.set_data([])
        self.pie_chart.set_data([0, 0, 0])

    def run_detection(self):
        if not self.is_model_valid: QMessageBox.critical(self, "无法运行", f"未检测到完整模型。"); return
        text = self.input_edit.toPlainText().strip()
        if not text: self.btn_detect.setText("⚠️ 内容为空"); QTimer.singleShot(1500, lambda: self.btn_detect.setText("⚡ 开始深度检测")); return
        self.btn_detect.setEnabled(False)
        self.btn_detect.setText("正在分析...")
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
        self.thread.finished.connect(lambda: [self.btn_detect.setEnabled(True), self.btn_detect.setText("⚡ 开始深度检测"), self.status_text.setText("分析完成") if self.is_model_valid else None, self.progress_bar.setValue(100)])
        self.thread.start()

    def process_results(self, res):
        if "error" in res: QMessageBox.critical(self, "检测中断", res["error"]); return
        self.gauge.setValue(res["total_ai_rate"])
        self.heatmap.set_data(res["paragraphs"]) 
        
        counts = [0, 0, 0] # Human, Mixed, AI
        for p in res["paragraphs"]:
            if p.get("is_ignored"): continue
            rate = p["ai_rate"]
            if rate < 30: counts[0] += 1
            elif rate < 60: counts[1] += 1
            else: counts[2] += 1
        self.pie_chart.set_data(counts)

        for i, p in enumerate(res["paragraphs"]):
            block = ResultBlock(i, p["content"], p["ai_rate"], is_ignored=p.get("is_ignored", False))
            block.request_scroll.connect(self.handle_block_resize) 
            block.request_highlight.connect(self.highlight_source_text) 
            
            # 2. 连接展开信号，实现手风琴效果
            block.expanded.connect(self.on_block_expanded)
            
            self.result_layout.addWidget(block)
            
        self.result_layout.addStretch()
        self.apply_filter()

    # 新增：处理卡片展开 (实现互斥)
    def on_block_expanded(self, expanded_index):
        for i in range(self.result_layout.count()):
            item = self.result_layout.itemAt(i)
            widget = item.widget()
            if widget and isinstance(widget, ResultBlock):
                # 这里的 index 是我们在初始化 ResultBlock 时传入的序号
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
        if index < self.result_layout.count():
            widget = self.result_layout.itemAt(index).widget()
            if widget:
                if widget.isHidden():
                    self.chk_only_high_risk.setChecked(False) 
                    QApplication.processEvents() 
                self.result_scroll.ensureWidgetVisible(widget)
                widget.toggle_expand() 
                self.highlight_source_text(widget.content)

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
            self.input_edit.setPlainText(content); self.status_text.setText(f"已加载: {os.path.basename(path)}")
        except Exception as e: QMessageBox.critical(self, "错误", f"读取失败: {str(e)}")
        finally: QApplication.restoreOverrideCursor()

    def import_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "打开文档", "", "Text/Word (*.txt *.docx)")
        if path: self.handle_file_content(path)

if __name__ == "__main__":
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    app = QApplication(sys.argv); app.setStyle("Fusion")
    font = QFont("Microsoft YaHei", 10); font.setStyleStrategy(QFont.PreferAntialias); app.setFont(font)
    window = AIGCSentinel(); window.show(); sys.exit(app.exec())