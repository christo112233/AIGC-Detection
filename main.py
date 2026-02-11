import sys
import os
import torch
import random
import math
import time
import html

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
    QApplication, QMainWindow, QTextEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QWidget, QLabel, QFrame,
    QFileDialog, QMessageBox, QSplitter, QGraphicsDropShadowEffect,
    QProgressBar, QSizePolicy, QSpacerItem, QGraphicsOpacityEffect,
    QScrollArea
)
from PySide6.QtCore import (
    Qt, Signal, QThread, QSize, Property, QPropertyAnimation, 
    QEasingCurve, QRectF, QPointF, QParallelAnimationGroup, QTimer,
    QAbstractAnimation, QByteArray, QSequentialAnimationGroup, QMimeData
)
from PySide6.QtGui import (
    QColor, QLinearGradient, QPainter, QFont, QTextCursor, 
    QTextCharFormat, QPen, QPolygonF, QBrush, QPalette, QIcon, QRadialGradient,
    QPainterPath, QPixmap, QTransform, QFontMetrics, QCursor
)

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
    ACCENT_BLUE = "#2D79FF"
    ACCENT_GRAY = "#666666"

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

# ---------------------- 交互增强组件 ----------------------

class DragTextEdit(QTextEdit):
    file_dropped = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setPlaceholderText("在此处粘贴文本或拖入文件...")
        
        self._glow_strength = 0.0
        self._scale_factor = 1.0
        
        self.anim_glow = QPropertyAnimation(self, b"glow_strength", self)
        self.anim_glow.setDuration(300)
        self.anim_glow.setEasingCurve(QEasingCurve.OutQuad)
        
        self.anim_scale = QPropertyAnimation(self, b"scale_factor", self)
        self.anim_scale.setDuration(300)
        self.anim_scale.setEasingCurve(QEasingCurve.OutBack)

    @Property(float)
    def glow_strength(self): return self._glow_strength
    @glow_strength.setter
    def glow_strength(self, v): self._glow_strength = v; self.update()

    @Property(float)
    def scale_factor(self): return self._scale_factor
    @scale_factor.setter
    def scale_factor(self, v): self._scale_factor = v; self.update()

    def insertFromMimeData(self, source):
        if source.hasText():
            self.insertPlainText(source.text())
        else:
            super().insertFromMimeData(source)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.accept()
            self.anim_glow.stop(); self.anim_glow.setEndValue(1.0); self.anim_glow.start()
            self.anim_scale.stop(); self.anim_scale.setEndValue(1.02); self.anim_scale.start()
        else: e.ignore()

    def dragLeaveEvent(self, e):
        self.anim_glow.stop(); self.anim_glow.setEndValue(0.0); self.anim_glow.start()
        self.anim_scale.stop(); self.anim_scale.setEndValue(1.0); self.anim_scale.start()
        super().dragLeaveEvent(e)

    def dropEvent(self, e):
        self.anim_glow.stop(); self.anim_glow.setEndValue(0.0); self.anim_glow.start()
        self.anim_scale.stop(); self.anim_scale.setEndValue(1.0); self.anim_scale.start()
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            ext = os.path.splitext(path)[1].lower()
            if ext in ['.txt', '.docx']:
                self.file_dropped.emit(path)
                # 修复 1：显式接受操作，防止系统认为拖拽失败
                e.acceptProposedAction()
            else:
                e.ignore()
        else:
            e.ignore()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._glow_strength > 0.01:
            p = QPainter(self.viewport())
            p.setRenderHint(QPainter.Antialiasing)
            glow_c = QColor(Theme.ACCENT_BLUE)
            glow_c.setAlpha(int(150 * self._glow_strength))
            path = QPainterPath()
            path.addRoundedRect(self.viewport().rect().adjusted(2,2,-2,-2), 8, 8)
            p.setPen(QPen(glow_c, 4 * self._glow_strength))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)

class ResultBlock(QWidget):
    def __init__(self, content, ai_rate, is_ignored=False, parent=None):
        super().__init__(parent)
        self.content = content
        self.ai_rate = ai_rate
        self.is_ignored = is_ignored 
        
        self.setFixedHeight(0)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        
        if self.is_ignored:
            self.accent_color = Theme.ACCENT_GRAY
            self.verdict = "过短忽略"
        elif ai_rate < 30: 
            self.accent_color = Theme.ACCENT_GREEN
            self.verdict = "人类创作"
        elif ai_rate < 60: 
            self.accent_color = Theme.ACCENT_YELLOW
            self.verdict = "疑似混写"
        else: 
            self.accent_color = Theme.ACCENT_RED
            self.verdict = "疑似生成"

        self.content_widget = QWidget(self)
        self.content_widget.move(100, 0)

        self.layout = QVBoxLayout(self.content_widget)
        self.layout.setContentsMargins(15, 12, 15, 12)
        
        self.text_label = QLabel("")
        self.text_label.setWordWrap(True)
        text_color = "#777" if is_ignored else Theme.get('text_sub')
        self.text_label.setStyleSheet(f"color: {text_color}; font-size: 11pt; line-height: 1.6;")
        self.text_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.text_label.setTextFormat(Qt.RichText) 
        
        self.layout.addWidget(self.text_label)

        self._typewriter_idx = 0
        self._opacity = 0.0
        self._slide_offset_x = 80.0 

        self.anim_entry = QPropertyAnimation(self, b"entry_val", self)
        self.anim_entry.setDuration(700)
        self.anim_entry.setEasingCurve(QEasingCurve.OutCubic)
        
        self.timer_type = QTimer(self)
        self.timer_type.setInterval(5)
        self.timer_type.timeout.connect(self._step_typewriter)

    @Property(float)
    def entry_val(self): return self._opacity
    @entry_val.setter
    def entry_val(self, v):
        self._opacity = v
        self._slide_offset_x = 80.0 * (1.0 - v)
        self.content_widget.move(int(self._slide_offset_x), 0)
        self.update() 

    def start_reveal(self, delay=0):
        QTimer.singleShot(delay, self._begin)

    def _begin(self):
        if self.is_ignored:
            tag_preview = "  [字数过少，已忽略]"
        else:
            tag_preview = f"  [AI: {int(self.ai_rate)}%]"
            
        full_text_preview = self.content + tag_preview
        
        available_w = max(100, self.width() - 60) 
        font = self.text_label.font()
        fm = QFontMetrics(font)
        rect = fm.boundingRect(0, 0, available_w, 10000, Qt.TextWordWrap | Qt.AlignLeft, full_text_preview)
        
        target_h = rect.height() + 50 
        
        self.setFixedHeight(target_h)
        self.content_widget.resize(self.width(), target_h)
        
        self.anim_entry.setStartValue(0.0)
        self.anim_entry.setEndValue(1.0)
        self.anim_entry.start()
        
        self.timer_type.start()

    def _step_typewriter(self):
        batch = 6 
        self._typewriter_idx += batch
        
        current_plain = self.content[:self._typewriter_idx]
        escaped_text = html.escape(current_plain)
        self.text_label.setText(escaped_text)
        
        if self._typewriter_idx >= len(self.content):
            self.timer_type.stop()
            final_plain = html.escape(self.content)
            c = QColor(self.accent_color)
            color_hex = c.name() 
            
            if self.is_ignored:
                tag_html = f"&nbsp;&nbsp;<span style='color:{color_hex}; font-size:9pt; font-style:italic;'>[字数过少，不计入总分]</span>"
            else:
                tag_html = f"&nbsp;&nbsp;<span style='color:{color_hex}; font-weight:bold; font-size:10pt;'>[AI: {int(self.ai_rate)}% | {self.verdict}]</span>"
            
            self.text_label.setText(final_plain + tag_html)

    def paintEvent(self, event):
        if self._opacity > 0:
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            p.setOpacity(self._opacity)
            
            trans = QTransform()
            trans.translate(self._slide_offset_x, 0)
            p.setTransform(trans)
            
            bg_c = QColor(Theme.get('input_bg'))
            if self.is_ignored:
                bg_c.setAlpha(150)
            elif self.ai_rate > 60:
                bg_c = QColor(Theme.ACCENT_RED)
                bg_c.setAlpha(15) 
            
            p.setBrush(bg_c)
            p.setPen(Qt.NoPen)
            draw_rect = self.rect().adjusted(5, 2, -5, -2)
            p.drawRoundedRect(draw_rect, 8, 8)
            
            line_c = QColor(self.accent_color)
            line_c.setAlpha(180)
            p.setBrush(line_c)
            p.drawRoundedRect(QRectF(5, 10, 3, self.height()-20), 1.5, 1.5)

    def resizeEvent(self, event):
        self.content_widget.resize(self.width(), self.height())
        super().resizeEvent(event)


# ---------------------- 核心检测线程 ----------------------
class AIGCDetectionThread(QThread):
    progress_signal = Signal(int)
    result_signal = Signal(dict)
    status_signal = Signal(str)
    device_signal = Signal(str, bool) # 硬件信息信号

    def __init__(self, text, model_path):
        super().__init__()
        self.text = text
        self.model_path = model_path
        self.MIN_VALID_CHARS = 10
        self.TEMPERATURE = 1.8 

    def run(self):
        if not self.model_path or not os.path.exists(self.model_path):
            self.result_signal.emit({"error": "模型路径无效"})
            return

        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
            import torch.nn.functional as F

            # ---------------------- 硬件检测 ----------------------
            use_cuda = torch.cuda.is_available()
            use_mps = hasattr(torch.backends, "mps") and torch.backends.mps.is_available() # Mac M1/M2
            
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
                extra_info = ""
                # 如果版本号包含 cpu，明确提示用户
                if "+cpu" in version:
                    extra_info = " [错误: 安装了CPU版Torch]"
                elif not use_cuda:
                    extra_info = " [未发现NVIDIA显卡]"
                
                self.device_signal.emit(f"🐢 CPU 运算 (Torch {version}){extra_info}", False)
            
            torch_device = torch.device(device_str)
            # ----------------------------------------------------

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
                    label_str = str(label).lower()
                    if any(x in label_str for x in ['fake', 'ai', 'chatgpt', 'generated', '1', 'label_1']):
                        ai_label_id = int(idx)
                        break

            # 核心修改：严格按 \n 切分段落，保留用户意图
            paragraphs = [p for p in self.text.split("\n") if p.strip()]
            
            if not paragraphs:
                self.result_signal.emit({"total_ai_rate": 0, "paragraphs": []})
                return

            results = []
            total_weighted_score = 0
            total_valid_weight = 0

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
                        ai_score = probs[0][ai_label_id].item()
                        
                        ai_score = math.pow(ai_score, 2.5)
                        
                        ai_rate = round(ai_score * 100, 2)
                    
                    # 关键修改：计算有效字符长度（去除所有空白字符）
                    valid_chars = "".join(para.split())
                    para_len = len(valid_chars)
                    
                    is_ignored = False
                    weight = 0
                    
                    if para_len < self.MIN_VALID_CHARS:
                        is_ignored = True
                        weight = 0
                    else:
                        is_ignored = False
                        weight = para_len
                    
                    results.append({
                        "content": para, 
                        "ai_rate": ai_rate,
                        "is_ignored": is_ignored
                    })
                    
                    if not is_ignored:
                        total_weighted_score += (ai_rate * weight)
                        total_valid_weight += weight
                        
                except Exception as e:
                    # 捕获异常时，检查是否是版本不兼容问题
                    err_str = str(e)
                    if "upgrade torch" in err_str and "v2.6" in err_str:
                        # 抛出特定异常供外层捕获
                        raise e 
                    print(f"Segment Error: {e}")
                
                self.progress_signal.emit(30 + int(((idx + 1) / len(paragraphs)) * 65))

            if total_valid_weight > 0:
                avg = round(total_weighted_score / total_valid_weight, 2)
            else:
                avg = 0
                
            self.result_signal.emit({"total_ai_rate": avg, "paragraphs": results})

        except Exception as e:
            error_str = str(e)
            if "upgrade torch" in error_str and "v2.6" in error_str:
                self.result_signal.emit({
                    "error": "【环境版本冲突】\n\n检测到您的 PyTorch 版本过旧，无法加载当前的 .bin 模型文件。\n\n解决方案：\n请在终端运行以下命令升级 PyTorch：\n\npip install --upgrade torch torchvision torchaudio"
                })
            else:
                self.result_signal.emit({"error": f"推理引擎异常:\n{error_str}"})

# ---------------------- 主窗口 ----------------------

class AIGCSentinel(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AIGC 哨兵 - 智能溯源系统")
        self.resize(1300, 850)
        self.is_model_valid = False
        self.model_path = ""
        
        self.transition_overlay = QLabel(self)
        self.transition_overlay.hide()
        self.transition_overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.transition_effect = QGraphicsOpacityEffect(self.transition_overlay)
        self.transition_overlay.setGraphicsEffect(self.transition_effect)
        
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
        self.input_edit = DragTextEdit(); self.input_edit.file_dropped.connect(self.handle_file_content)
        in_layout.addWidget(self.label_input); in_layout.addWidget(self.input_edit)

        self.card_output = QFrame(); out_layout = QVBoxLayout(self.card_output)
        self.gauge = AIGCGaugeWidget()
        self.label_output = QLabel("🔍 逐段溯源分析"); self.label_output.setStyleSheet("font-weight: bold; margin-top: 10px;")
        
        self.result_scroll = QScrollArea()
        self.result_scroll.setWidgetResizable(True)
        self.result_scroll.setFrameShape(QFrame.NoFrame)
        self.result_container = QWidget()
        self.result_layout = QVBoxLayout(self.result_container)
        self.result_layout.setAlignment(Qt.AlignTop)
        self.result_layout.setSpacing(15)
        self.result_scroll.setWidget(self.result_container)
        
        out_layout.addWidget(self.gauge); out_layout.addWidget(self.label_output); out_layout.addWidget(self.result_scroll); out_layout.setStretch(2, 3)

        splitter.addWidget(self.card_input); splitter.addWidget(self.card_output); splitter.setSizes([600, 500])
        layout.addWidget(splitter, stretch=1)

        status_bar = QFrame(); status_bar.setFixedHeight(30); sb_layout = QHBoxLayout(status_bar); sb_layout.setContentsMargins(0,0,0,0)
        self.status_icon = QLabel("●"); self.status_text = QLabel("初始化...")
        self.status_text.setStyleSheet("font-size: 12px; font-weight: bold;")
        self.btn_refresh = QPushButton("🔄 刷新状态"); self.btn_refresh.setCursor(Qt.PointingHandCursor); self.btn_refresh.setFixedSize(80, 24); self.btn_refresh.clicked.connect(self.manual_refresh_model)
        
        sb_layout.addWidget(self.status_icon); sb_layout.addWidget(self.status_text); sb_layout.addWidget(self.btn_refresh); sb_layout.addStretch()
        
        # --- 硬件显示标签 ---
        self.label_device = QLabel("")
        self.label_device.setStyleSheet("color: #666; font-size: 11px; margin-right: 10px;")
        sb_layout.addWidget(self.label_device) # 添加到布局
        # -------------------

        self.progress_bar = ModernProgressBar(); self.progress_bar.setFixedWidth(300); sb_layout.addWidget(self.progress_bar)
        layout.addWidget(status_bar)

    def manual_refresh_model(self):
        self.status_text.setText("正在扫描本地模型...")
        self.status_text.setStyleSheet("color: #FFD60A; font-weight: bold;")
        QApplication.processEvents(); QThread.msleep(300); self.check_model_status()
        if self.is_model_valid: QMessageBox.information(self, "状态更新", "成功检测到本地模型！\n所有组件(Tokenizer/Model)均已就绪。")
        else: QMessageBox.warning(self, "状态更新", "仍然未检测到完整模型。\n请确保文件夹包含: config.json, pytorch_model.bin, vocab.txt 等")

    def check_model_status(self):
        target_dir = get_resource_path("AIGC_Model")
        
        if not os.path.exists(target_dir):
            self.set_model_invalid("未找到 'AIGC_Model' 文件夹")
            return

        try:
            files = os.listdir(target_dir)
            has_config = "config.json" in files
            has_bin = "pytorch_model.bin" in files or "model.safetensors" in files
            has_vocab = "vocab.txt" in files
            
            if has_config and has_bin:
                self.is_model_valid = True
                self.model_path = target_dir
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

    def update_device_ui(self, msg, is_gpu):
        self.label_device.setText(msg)
        color = "#00E070" if is_gpu else "#FFD60A" # Green for GPU, Yellow for CPU
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
        self.btn_import.update()
        self.btn_clear.update()
        self.btn_detect.update()
        self.progress_bar.update()
        self.input_edit.update() 
        
        for i in range(self.result_layout.count()):
            w = self.result_layout.itemAt(i).widget()
            if w: w.update()

        btn_bg = "#333" if is_dark else "#DDD"
        btn_txt = "#FFF" if is_dark else "#333"
        self.btn_refresh.setStyleSheet(f"QPushButton {{ background: {btn_bg}; color: {btn_txt}; border-radius: 4px; border: none; font-size: 11px; }} QPushButton:hover {{ background: #2D79FF; color: white; }}")
        
        if not self.is_model_valid: self.status_text.setStyleSheet("color: #FF453A; font-weight: bold;")
        else: self.status_text.setStyleSheet("color: #30D158; font-weight: bold;")

        self.anim_fade = QPropertyAnimation(self.transition_effect, b"opacity")
        self.anim_fade.setDuration(350); self.anim_fade.setStartValue(1.0); self.anim_fade.setEndValue(0.0); self.anim_fade.setEasingCurve(QEasingCurve.InOutQuad)
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
        """)
        self.title_lbl.setStyleSheet(f"font-size: 28px; font-weight: 900; color: {t['text_main']};")
        self.label_input.setStyleSheet(f"color: {t['text_sub']}; font-weight: bold; margin-bottom: 5px;")
        self.label_output.setStyleSheet(f"color: {t['text_sub']}; font-weight: bold; margin-top: 10px;")
        card_style = f"QFrame {{ background-color: {t['bg_card']}; border: 1px solid {t['border']}; border-radius: 16px; }}"
        self.card_input.setStyleSheet(card_style); self.card_output.setStyleSheet(card_style)
        self.card_input.setGraphicsEffect(Theme.shadow(30)); self.card_output.setGraphicsEffect(Theme.shadow(30))
        btn_bg = "#333" if Theme.CURRENT_MODE == 'dark' else "#DDD"; btn_txt = "#FFF" if Theme.CURRENT_MODE == 'dark' else "#333"
        self.btn_refresh.setStyleSheet(f"QPushButton {{ background: {btn_bg}; color: {btn_txt}; border-radius: 4px; border: none; font-size: 11px; }} QPushButton:hover {{ background: #2D79FF; color: white; }}")

    def resizeEvent(self, event):
        if hasattr(self, 'transition_overlay') and self.transition_overlay.isVisible():
            self.transition_overlay.setGeometry(0, 0, self.width(), self.height())
        super().resizeEvent(event)

    def clear_content(self):
        self.input_edit.clear()
        while self.result_layout.count():
            item = self.result_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.gauge.setValue(0); self.progress_bar.setValue(0)

    def run_detection(self):
        if not self.is_model_valid:
            QMessageBox.critical(self, "无法运行", f"未检测到完整模型。\n{self.status_text.text()}\n请检查 AIGC_Model 文件夹。")
            return
        text = self.input_edit.toPlainText().strip()
        if not text:
            self.btn_detect.setText("⚠️ 内容为空"); QTimer.singleShot(1500, lambda: self.btn_detect.setText("⚡ 开始深度检测")); return
        self.btn_detect.setEnabled(False); self.btn_detect.setText("正在分析...")
        
        while self.result_layout.count():
            item = self.result_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        self.gauge.setValue(0); self.progress_bar.setValue(0)
        self.thread = AIGCDetectionThread(text, self.model_path)
        self.thread.status_signal.connect(lambda s: self.status_text.setText(s))
        self.thread.progress_signal.connect(self.progress_bar.setValue)
        self.thread.result_signal.connect(self.process_results)
        self.thread.device_signal.connect(self.update_device_ui) # 连接硬件检测信号
        self.thread.finished.connect(lambda: [self.btn_detect.setEnabled(True), self.btn_detect.setText("⚡ 开始深度检测"), self.status_text.setText("分析完成") if self.is_model_valid else None, self.progress_bar.setValue(100)])
        self.thread.start()

    def process_results(self, res):
        if "error" in res: QMessageBox.critical(self, "检测中断", res["error"]); return
        self.gauge.setValue(res["total_ai_rate"])
        
        delay_counter = 0
        for p in res["paragraphs"]:
            # 传递 is_ignored 参数到 UI 卡片
            block = ResultBlock(p["content"], p["ai_rate"], is_ignored=p.get("is_ignored", False))
            self.result_layout.addWidget(block)
            block.start_reveal(delay_counter)
            delay_counter += 150
            
        self.result_layout.addStretch()

    def handle_file_content(self, path):
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        try:
            ext = os.path.splitext(path)[1].lower()
            content = ""
            if ext == '.txt':
                with open(path, 'rb') as f: raw = f.read()
                encoding = chardet.detect(raw)['encoding'] if HAS_CHARDET and chardet.detect(raw)['confidence'] > 0.6 else 'utf-8'
                try: content = raw.decode(encoding)
                except: content = raw.decode('utf-8', errors='ignore')
            elif ext == '.docx':
                if not HAS_DOCX: 
                    QMessageBox.warning(self, "组件缺失", "请安装 python-docx 库以支持 Word 文档")
                    return
                try:
                    doc = docx.Document(path)
                    text_parts = []
                    # 修复：同时读取段落和表格
                    for para in doc.paragraphs:
                        if para.text.strip(): text_parts.append(para.text)
                    
                    # 关键修复：加入表格去重逻辑
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
                except Exception as doc_err:
                    QMessageBox.warning(self, "解析警告", f"文档解析异常: {str(doc_err)}")
                    content = ""

            self.input_edit.setPlainText(content)
            self.status_text.setText(f"已加载: {os.path.basename(path)}")
        except Exception as e: 
            QMessageBox.critical(self, "错误", f"读取失败: {str(e)}")
        finally:
            QApplication.restoreOverrideCursor()

    def import_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "打开文档", "", "Text/Word (*.txt *.docx)")
        if path: self.handle_file_content(path)

if __name__ == "__main__":
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    app = QApplication(sys.argv); app.setStyle("Fusion")
    font = QFont("Microsoft YaHei", 10); font.setStyleStrategy(QFont.PreferAntialias); app.setFont(font)
    window = AIGCSentinel(); window.show(); sys.exit(app.exec())