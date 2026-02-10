import sys
import os
import torch
import random
import math
import time

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
    QApplication, QMainWindow, QTextEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QWidget, QLabel, QFrame,
    QFileDialog, QMessageBox, QSplitter, QGraphicsDropShadowEffect,
    QProgressBar, QSizePolicy, QSpacerItem
)
from PySide6.QtCore import (
    Qt, Signal, QThread, QSize, Property, QPropertyAnimation, 
    QEasingCurve, QRectF, QPointF, QParallelAnimationGroup, QTimer,
    QAbstractAnimation
)
from PySide6.QtGui import (
    QColor, QLinearGradient, QPainter, QFont, QTextCursor, 
    QTextCharFormat, QPen, QPolygonF, QBrush, QPalette, QIcon, QRadialGradient,
    QPainterPath
)

# ---------------------- 核心配色与状态管理 ----------------------
class Theme:
    CURRENT_MODE = 'dark'
    COLORS = {
        'dark': {
            'bg_main': "#121214",
            'bg_card': "#1E1E24",
            'text_main': "#FFFFFF",
            'text_sub': "#A0A0A0",
            'border': "#333333",
            'input_bg': "#16161A",
            'scroll': "#2A2A30",
            'btn_face': "#2D79FF",
            'btn_side': "#1B4DB3",
            'btn_sec_face': "#2A2A30",
            'btn_sec_side': "#1A1A20",
            'shadow': QColor(0, 0, 0, 150)
        },
        'light': {
            'bg_main': "#F2F5F8",
            'bg_card': "#FFFFFF",
            'text_main': "#333333",
            'text_sub': "#666666",
            'border': "#E0E0E0",
            'input_bg': "#FAFAFA",
            'scroll': "#D0D0D0",
            'btn_face': "#2D79FF",
            'btn_side': "#1B4DB3",
            'btn_sec_face': "#FFFFFF",
            'btn_sec_side': "#D1D9E6",
            'shadow': QColor(0, 0, 0, 30)
        }
    }
    ACCENT_GREEN = "#00E070"
    ACCENT_RED = "#FF453A"
    ACCENT_YELLOW = "#FFD60A"

    @classmethod
    def get(cls, key):
        return cls.COLORS[cls.CURRENT_MODE].get(key, "#FF00FF")

    @classmethod
    def toggle(cls):
        cls.CURRENT_MODE = 'light' if cls.CURRENT_MODE == 'dark' else 'dark'

    @staticmethod
    def shadow(radius=20):
        effect = QGraphicsDropShadowEffect()
        effect.setBlurRadius(radius)
        effect.setXOffset(0)
        effect.setYOffset(4)
        c = Theme.COLORS[Theme.CURRENT_MODE]['shadow']
        effect.setColor(c)
        return effect

# ---------------------- 自定义 UI 组件 ----------------------

class ThemeSwitch(QWidget):
    toggled = Signal(bool) 
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(60, 32)
        self.setCursor(Qt.PointingHandCursor)
        self._is_dark = True
        self._thumb_x = 30 
        self.anim = QPropertyAnimation(self, b"thumb_pos", self)
        self.anim.setDuration(250)
        self.anim.setEasingCurve(QEasingCurve.InOutQuad)

    @Property(float)
    def thumb_pos(self): return self._thumb_x
    @thumb_pos.setter
    def thumb_pos(self, val): self._thumb_x = val; self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_dark = not self._is_dark
            start, end = (self._thumb_x, 30) if self._is_dark else (self._thumb_x, 4)
            self.anim.stop(); self.anim.setStartValue(start); self.anim.setEndValue(end); self.anim.start()
            self.toggled.emit(self._is_dark)

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor("#333333") if self._is_dark else QColor("#D0D0D0"))
        p.setPen(Qt.NoPen); p.drawRoundedRect(0, 0, 56, 28, 14, 14)
        p.setFont(QFont("Segoe UI Emoji", 10))
        if self._is_dark: p.setPen(QColor("#666")); p.drawText(8, 19, "☀️")
        else: p.setPen(QColor("#FFF")); p.drawText(36, 19, "🌙")
        p.setBrush(QColor("#121214") if self._is_dark else QColor("#FFFFFF"))
        p.drawEllipse(int(self._thumb_x), 2, 24, 24)

class ThreeDButton(QPushButton):
    def __init__(self, text, is_primary=True, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(50)
        self.setFont(QFont("Microsoft YaHei UI", 10, QFont.Weight.Bold))
        self._is_primary = is_primary
        self._is_pressed = False
        self._offset_y = 5 
        self._hover_progress = 0.0
        self.anim = QPropertyAnimation(self, b"hover_progress", self)
        self.anim.setDuration(150)

    @Property(float)
    def hover_progress(self): return self._hover_progress
    @hover_progress.setter
    def hover_progress(self, val): self._hover_progress = val; self.update()

    def enterEvent(self, e): self.anim.stop(); self.anim.setEndValue(1.0); self.anim.start(); super().enterEvent(e)
    def leaveEvent(self, e): self.anim.stop(); self.anim.setEndValue(0.0); self.anim.start(); super().leaveEvent(e)
    def mousePressEvent(self, e): 
        if e.button() == Qt.LeftButton: self._is_pressed = True; self.update()
        super().mousePressEvent(e)
    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton: self._is_pressed = False; self.update()
        super().mouseReleaseEvent(e)

    def paintEvent(self, event):
        painter = QPainter(self); painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        
        if self._is_primary:
            face_c, side_c, txt_c = QColor(Theme.get('btn_face')), QColor(Theme.get('btn_side')), QColor("white")
        else:
            face_c, side_c = QColor(Theme.get('btn_sec_face')), QColor(Theme.get('btn_sec_side'))
            txt_c = QColor("white") if Theme.CURRENT_MODE == 'dark' else QColor("#333")

        if self._hover_progress > 0:
            face_c = face_c.lighter(105); side_c = side_c.lighter(105)
        
        current_offset = self._offset_y if not self._is_pressed else 2
        face_h = h - self._offset_y
        
        path_side = QPainterPath()
        path_side.addRoundedRect(QRectF(0, self._offset_y, w, face_h), 12, 12)
        painter.setBrush(side_c); painter.setPen(Qt.NoPen); painter.drawPath(path_side)

        top_y = 0 if not self._is_pressed else (self._offset_y - 2)
        rect_face = QRectF(0, top_y, w, face_h)
        painter.setBrush(face_c); painter.drawRoundedRect(rect_face, 12, 12)
        painter.setPen(txt_c); painter.drawText(rect_face, Qt.AlignCenter, self.text())

class ModernProgressBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.setFixedHeight(6); self._value = 0
    def setValue(self, v): self._value = v; self.update()
    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); rect = self.rect()
        bg_c = QColor("#333") if Theme.CURRENT_MODE == 'dark' else QColor("#DDD")
        p.setBrush(bg_c); p.setPen(Qt.NoPen); p.drawRoundedRect(rect, 3, 3)
        if self._value <= 0: return
        w = rect.width() * (self._value / 100.0)
        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0, QColor("#2D79FF")); grad.setColorAt(1, QColor("#00F0FF"))
        p.setBrush(grad); p.drawRoundedRect(QRectF(0, 0, w, rect.height()), 3, 3)

class AIGCGaugeWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.setMinimumHeight(260); self._value = 0
        self.animation = QPropertyAnimation(self, b"value"); self.animation.setDuration(800); self.animation.setEasingCurve(QEasingCurve.OutCubic) 
    @Property(float)
    def value(self): return self._value
    @value.setter
    def value(self, v): self._value = v; self.update()
    def setValue(self, v): self.animation.stop(); self.animation.setStartValue(self._value); self.animation.setEndValue(v); self.animation.start()
    def get_color(self, val):
        if val < 30: return QColor(Theme.ACCENT_GREEN)
        if val < 60: return QColor(Theme.ACCENT_YELLOW)
        return QColor(Theme.ACCENT_RED)
    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height(); side = min(w, h * 1.5)
        p.translate(w / 2, h * 0.85); scale = side / 320; p.scale(scale, scale)
        color = self.get_color(self._value)
        alpha = 40 if Theme.CURRENT_MODE == 'dark' else 10
        glow = QRadialGradient(0, 0, 150); glow.setColorAt(0, QColor(color.red(), color.green(), color.blue(), alpha)); glow.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
        p.setBrush(glow); p.setPen(Qt.NoPen); p.drawEllipse(-150, -150, 300, 300)
        p.setFont(QFont("Microsoft YaHei", 11, QFont.Bold)); p.setPen(QColor(Theme.get('text_sub'))); p.drawText(QRectF(-100, -170, 200, 30), Qt.AlignCenter, "AIGC 疑似度")
        track_color = QColor(40, 40, 45) if Theme.CURRENT_MODE == 'dark' else QColor(220, 220, 220)
        p.setPen(QPen(track_color, 18, Qt.SolidLine, Qt.RoundCap)); p.drawArc(QRectF(-110, -110, 220, 220), 180 * 16, -180 * 16)
        p.setPen(QPen(color, 18, Qt.SolidLine, Qt.RoundCap)); span = -(self._value / 100.0) * 180 * 16; p.drawArc(QRectF(-110, -110, 220, 220), 180 * 16, span)
        p.setPen(QColor(Theme.get('text_main'))); p.setFont(QFont("Segoe UI", 42, QFont.Bold)); p.drawText(QRectF(-100, -80, 200, 60), Qt.AlignCenter, f"{int(self._value)}%")
        p.save(); angle = (self._value / 100.0) * 180 - 90; p.rotate(angle)
        pointer_c = QColor("white") if Theme.CURRENT_MODE == 'dark' else QColor("#333")
        p.setBrush(QBrush(pointer_c)); p.setPen(Qt.NoPen); p.drawPolygon(QPolygonF([QPointF(-6, 0), QPointF(6, 0), QPointF(0, -98)]))
        p.setBrush(QBrush(QColor(Theme.get('bg_card')))); p.setPen(QPen(pointer_c, 3)); p.drawEllipse(-8, -8, 16, 16); p.restore()

class DragTextEdit(QTextEdit):
    file_dropped = Signal(str)
    def __init__(self, parent=None): super().__init__(parent); self.setAcceptDrops(True)
    def dragEnterEvent(self, e): e.accept() if e.mimeData().hasUrls() else e.ignore()
    def dropEvent(self, e):
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if os.path.splitext(path)[1].lower() in ['.txt', '.docx']: self.file_dropped.emit(path)

# ---------------------- 核心检测线程 ----------------------
class AIGCDetectionThread(QThread):
    progress_signal = Signal(int)
    result_signal = Signal(dict)
    status_signal = Signal(str)

    def __init__(self, text, model_path):
        super().__init__()
        self.text = text
        self.model_path = model_path

    def run(self):
        if not self.model_path or not os.path.exists(self.model_path):
            self.result_signal.emit({"error": "模型路径无效"})
            return

        try:
            from transformers import pipeline, AutoModelForSequenceClassification, AutoTokenizer
            device = 0 if torch.cuda.is_available() else -1
            self.progress_signal.emit(10)
            
            self.status_signal.emit("加载本地权重 (config, bin, vocab)...")
            # 这里会自动读取 config.json, pytorch_model.bin, vocab.txt 等所有相关文件
            tokenizer = AutoTokenizer.from_pretrained(self.model_path, local_files_only=True)
            model = AutoModelForSequenceClassification.from_pretrained(self.model_path, local_files_only=True)
            detector = pipeline("text-classification", model=model, tokenizer=tokenizer, device=device)
            self.progress_signal.emit(30)

            paragraphs = [p for p in self.text.split("\n") if p.strip()]
            if not paragraphs:
                self.result_signal.emit({"total_ai_rate": 0, "paragraphs": []})
                return

            results = []
            total_score = 0
            total_chars = 0

            for idx, para in enumerate(paragraphs):
                self.status_signal.emit(f"深度指纹分析中... {idx+1}/{len(paragraphs)}")
                try:
                    inference = detector(para[:512])[0]
                    label = inference['label'].lower()
                    score = inference['score']
                    
                    # --- 修复关键逻辑 ---
                    # 很多模型的 AI 标签是 "LABEL_1"，或者 "1"
                    # 原来的代码漏掉了 '1'，导致 LABEL_1 (AI) 被判定为非关键词
                    # 结果变成了 ai_rate = (1 - score)，即 99% 变成了 1%
                    
                    # 现在的逻辑：只要标签包含 fake, ai, chatgpt, generated, 1, label_1 任意一个，就认为是 AI 标签
                    is_ai_label = any(x in label for x in ['fake', 'ai', 'chatgpt', 'generated', '1', 'label_1'])
                    
                    # 如果是 AI 标签，概率就是 score；如果不是(如 label_0)，概率是 1-score (假设 score 是 label_0 的置信度，这通常不常见)
                    # 通常 Binary Classification 输出 label_0 (Human) 或 label_1 (AI)
                    # 如果输出 label_1, score=0.99 -> ai_rate=99
                    # 如果输出 label_0, score=0.99 -> 这是 Human 的概率 -> ai_rate = 100 - 99 = 1
                    
                    if is_ai_label:
                        ai_rate = round(score * 100, 2)
                    else:
                        # 标签是 Human/Real/0
                        ai_rate = round((1 - score) * 100, 2)
                    
                    results.append({"content": para, "ai_rate": ai_rate})
                    total_score += (ai_rate * len(para))
                    total_chars += len(para)
                except Exception as e:
                    print(f"Segment Error: {e}")
                
                self.progress_signal.emit(30 + int(((idx + 1) / len(paragraphs)) * 65))

            avg = round(total_score / total_chars, 2) if total_chars > 0 else 0
            self.result_signal.emit({"total_ai_rate": avg, "paragraphs": results})

        except Exception as e:
            self.result_signal.emit({"error": f"推理引擎异常:\n{str(e)}"})

# ---------------------- 主窗口 ----------------------

class AIGCSentinel(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AIGC 哨兵 - 智能溯源系统")
        self.resize(1300, 850)
        self.is_model_valid = False
        self.model_path = ""
        self.init_ui(); self.update_theme(); self.check_model_status() 

    def init_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        layout = QVBoxLayout(central); layout.setContentsMargins(40, 40, 40, 30); layout.setSpacing(25)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        self.title_lbl = QLabel("AIGC SENTINEL"); self.title_lbl.setStyleSheet("font-size: 28px; font-weight: 900; letter-spacing: 2px;")
        self.sub_lbl = QLabel("深度学习文本溯源检测平台"); self.sub_lbl.setStyleSheet(f"font-size: 12px; font-weight: bold; letter-spacing: 1px; color: #2D79FF;")
        title_box.addWidget(self.title_lbl); title_box.addWidget(self.sub_lbl)
        header.addLayout(title_box); header.addStretch()

        self.theme_switch = ThemeSwitch(); self.theme_switch.toggled.connect(self.toggle_theme)
        header.addWidget(self.theme_switch); header.addSpacing(20)

        self.btn_import = ThreeDButton("导入文档", is_primary=False, parent=self); self.btn_import.setFixedWidth(120); self.btn_import.clicked.connect(self.import_file)
        self.btn_clear = ThreeDButton("清空", is_primary=False, parent=self); self.btn_clear.setFixedWidth(100); self.btn_clear.clicked.connect(self.clear_content)
        self.btn_detect = ThreeDButton("⚡ 开始深度检测", parent=self); self.btn_detect.setFixedWidth(180); self.btn_detect.clicked.connect(self.run_detection)
        header.addWidget(self.btn_import); header.addSpacing(10); header.addWidget(self.btn_clear); header.addSpacing(15); header.addWidget(self.btn_detect)
        layout.addLayout(header)

        splitter = QSplitter(Qt.Horizontal); splitter.setHandleWidth(20)
        self.card_input = QFrame(); in_layout = QVBoxLayout(self.card_input)
        self.label_input = QLabel("📝 原文输入 (支持 .txt / .docx 拖入)"); self.label_input.setStyleSheet("font-weight: bold; margin-bottom: 5px;")
        self.input_edit = DragTextEdit(); self.input_edit.setPlaceholderText("在此处粘贴文本或拖入文件..."); self.input_edit.file_dropped.connect(self.handle_file_content)
        in_layout.addWidget(self.label_input); in_layout.addWidget(self.input_edit)

        self.card_output = QFrame(); out_layout = QVBoxLayout(self.card_output)
        self.gauge = AIGCGaugeWidget()
        self.label_output = QLabel("🔍 逐段溯源分析"); self.label_output.setStyleSheet("font-weight: bold; margin-top: 10px;")
        self.output_view = QTextEdit(); self.output_view.setReadOnly(True)
        out_layout.addWidget(self.gauge); out_layout.addWidget(self.label_output); out_layout.addWidget(self.output_view); out_layout.setStretch(2, 3)

        splitter.addWidget(self.card_input); splitter.addWidget(self.card_output); splitter.setSizes([600, 500])
        layout.addWidget(splitter, stretch=1)

        status_bar = QFrame(); status_bar.setFixedHeight(30); sb_layout = QHBoxLayout(status_bar); sb_layout.setContentsMargins(0,0,0,0)
        self.status_icon = QLabel("●"); self.status_text = QLabel("初始化...")
        self.status_text.setStyleSheet("font-size: 12px; font-weight: bold;")
        self.btn_refresh = QPushButton("🔄 刷新状态"); self.btn_refresh.setCursor(Qt.PointingHandCursor); self.btn_refresh.setFixedSize(80, 24); self.btn_refresh.clicked.connect(self.manual_refresh_model)
        sb_layout.addWidget(self.status_icon); sb_layout.addWidget(self.status_text); sb_layout.addWidget(self.btn_refresh); sb_layout.addStretch()
        self.progress_bar = ModernProgressBar(); self.progress_bar.setFixedWidth(300); sb_layout.addWidget(self.progress_bar)
        layout.addWidget(status_bar)

    def manual_refresh_model(self):
        self.status_text.setText("正在扫描本地模型...")
        self.status_text.setStyleSheet("color: #FFD60A; font-weight: bold;")
        QApplication.processEvents(); QThread.msleep(300); self.check_model_status()
        if self.is_model_valid: QMessageBox.information(self, "状态更新", "成功检测到本地模型！\n所有组件(Tokenizer/Model)均已就绪。")
        else: QMessageBox.warning(self, "状态更新", "仍然未检测到完整模型。\n请确保文件夹包含: config.json, pytorch_model.bin, vocab.txt 等")

    def check_model_status(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        target_dir = os.path.join(base_dir, "AIGC_Model")
        
        if not os.path.exists(target_dir):
            self.set_model_invalid("未找到 'AIGC_Model' 文件夹")
            return

        try:
            files = os.listdir(target_dir)
            # 严格检查你提到的所有文件，让你放心
            has_config = "config.json" in files
            has_bin = "pytorch_model.bin" in files or "model.safetensors" in files
            has_vocab = "vocab.txt" in files
            
            if has_config and has_bin:
                self.is_model_valid = True
                self.model_path = target_dir
                
                # 在提示文本里明确显示已检测到的文件类型，让你知道 vocab 也被检测到了
                status_str = "本地引擎已加载"
                if has_vocab: status_str += " | Vocab 字典已载入"
                
                self.status_icon.setStyleSheet(f"color: #00E070; font-size: 16px;")
                self.status_text.setText(status_str)
                self.status_text.setStyleSheet("color: #30D158; font-weight: bold;")
            else:
                missing = []
                if not has_config: missing.append("config.json")
                if not has_bin: missing.append("权重文件(.bin)")
                self.set_model_invalid(f"缺失文件: {', '.join(missing)}")
                
        except Exception as e:
            self.set_model_invalid(f"读取失败: {str(e)}")

    def set_model_invalid(self, reason):
        self.is_model_valid = False; self.model_path = ""
        self.status_icon.setStyleSheet(f"color: #FF453A; font-size: 16px;")
        self.status_text.setText(f"⚠️ 无法检测: {reason}"); self.status_text.setStyleSheet("color: #FF453A; font-weight: bold;")

    def toggle_theme(self, is_dark):
        Theme.toggle(); self.update_theme()
        self.gauge.update(); self.btn_import.update(); self.btn_clear.update(); self.btn_detect.update(); self.progress_bar.update()
        btn_bg = "#333" if is_dark else "#DDD"; btn_txt = "#FFF" if is_dark else "#333"
        self.btn_refresh.setStyleSheet(f"QPushButton {{ background: {btn_bg}; color: {btn_txt}; border-radius: 4px; border: none; font-size: 11px; }} QPushButton:hover {{ background: #2D79FF; color: white; }}")
        if not self.is_model_valid: self.status_text.setStyleSheet("color: #FF453A; font-weight: bold;")
        else: self.status_text.setStyleSheet("color: #30D158; font-weight: bold;")

    def update_theme(self):
        t = Theme.COLORS[Theme.CURRENT_MODE]
        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {t['bg_main']}; }}
            QWidget {{ color: {t['text_main']}; font-family: 'Segoe UI', 'Microsoft YaHei'; }}
            QTextEdit {{ background-color: {t['input_bg']}; color: {t['text_main']}; border: 1px solid {t['border']}; border-radius: 12px; padding: 15px; font-size: 11pt; }}
            QTextEdit:focus {{ border: 1px solid #2D79FF; }}
            QSplitter::handle {{ background: transparent; }}
        """)
        self.title_lbl.setStyleSheet(f"font-size: 28px; font-weight: 900; color: {t['text_main']};")
        self.label_input.setStyleSheet(f"color: {t['text_sub']}; font-weight: bold; margin-bottom: 5px;")
        self.label_output.setStyleSheet(f"color: {t['text_sub']}; font-weight: bold; margin-top: 10px;")
        card_style = f"QFrame {{ background-color: {t['bg_card']}; border: 1px solid {t['border']}; border-radius: 16px; }}"
        self.card_input.setStyleSheet(card_style); self.card_output.setStyleSheet(card_style)
        self.card_input.setGraphicsEffect(Theme.shadow(30)); self.card_output.setGraphicsEffect(Theme.shadow(30))
        btn_bg = "#333" if Theme.CURRENT_MODE == 'dark' else "#DDD"; btn_txt = "#FFF" if Theme.CURRENT_MODE == 'dark' else "#333"
        self.btn_refresh.setStyleSheet(f"QPushButton {{ background: {btn_bg}; color: {btn_txt}; border-radius: 4px; border: none; font-size: 11px; }} QPushButton:hover {{ background: #2D79FF; color: white; }}")

    def clear_content(self):
        self.input_edit.clear(); self.output_view.clear(); self.gauge.setValue(0); self.progress_bar.setValue(0)

    def run_detection(self):
        if not self.is_model_valid:
            QMessageBox.critical(self, "无法运行", f"未检测到完整模型。\n{self.status_text.text()}\n请检查 AIGC_Model 文件夹。")
            return
        text = self.input_edit.toPlainText().strip()
        if not text:
            self.btn_detect.setText("⚠️ 内容为空"); QTimer.singleShot(1500, lambda: self.btn_detect.setText("⚡ 开始深度检测")); return
        self.btn_detect.setEnabled(False); self.btn_detect.setText("正在分析..."); self.output_view.clear(); self.gauge.setValue(0); self.progress_bar.setValue(0)
        self.thread = AIGCDetectionThread(text, self.model_path)
        self.thread.status_signal.connect(lambda s: self.status_text.setText(s))
        self.thread.progress_signal.connect(self.progress_bar.setValue)
        self.thread.result_signal.connect(self.process_results)
        self.thread.finished.connect(lambda: [self.btn_detect.setEnabled(True), self.btn_detect.setText("⚡ 开始深度检测"), self.status_text.setText("分析完成") if self.is_model_valid else None, self.progress_bar.setValue(100)])
        self.thread.start()

    def process_results(self, res):
        if "error" in res: QMessageBox.critical(self, "检测中断", res["error"]); return
        self.gauge.setValue(res["total_ai_rate"])
        cursor = self.output_view.textCursor()
        for p in res["paragraphs"]:
            rate = p["ai_rate"]
            color = "#00E070" if rate < 30 else "#FFD60A" if rate < 60 else "#FF453A"
            fmt_text = QTextCharFormat(); fmt_text.setForeground(QColor(Theme.get('text_sub'))); fmt_text.setFontPointSize(10)
            text_preview = p["content"][:150] + ("..." if len(p["content"]) > 150 else "")
            cursor.insertText(text_preview, fmt_text)
            fmt_tag = QTextCharFormat(); fmt_tag.setForeground(QColor(color)); fmt_tag.setFontWeight(QFont.Bold)
            cursor.insertText(f"\n[AI 指数: {rate}%]\n\n", fmt_tag)
        self.output_view.moveCursor(QTextCursor.Start)

    def handle_file_content(self, path):
        try:
            ext = os.path.splitext(path)[1].lower()
            content = ""
            if ext == '.txt':
                with open(path, 'rb') as f: raw = f.read()
                encoding = chardet.detect(raw)['encoding'] if HAS_CHARDET and chardet.detect(raw)['confidence'] > 0.6 else 'utf-8'
                try: content = raw.decode(encoding)
                except: content = raw.decode('utf-8', errors='ignore')
            elif ext == '.docx':
                if not HAS_DOCX: QMessageBox.warning(self, "组件缺失", "请安装 python-docx"); return
                doc = docx.Document(path); content = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
            self.input_edit.setPlainText(content); self.status_text.setText(f"已加载: {os.path.basename(path)}")
        except Exception as e: QMessageBox.critical(self, "错误", f"读取失败: {str(e)}")

    def import_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "打开文档", "", "Text/Word (*.txt *.docx)")
        if path: self.handle_file_content(path)

if __name__ == "__main__":
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    app = QApplication(sys.argv); app.setStyle("Fusion")
    font = QFont("Microsoft YaHei", 10); font.setStyleStrategy(QFont.PreferAntialias); app.setFont(font)
    window = AIGCSentinel(); window.show(); sys.exit(app.exec())