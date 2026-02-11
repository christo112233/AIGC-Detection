import sys
import os
import torch
import random
import math
import time
import html
import re

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
    QScrollArea, QCheckBox
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

# ---------------------- 核心配色 ----------------------
class Theme:
    CURRENT_MODE = 'dark'
    COLORS = {
        'dark': {
            'bg_main': "#121214", 'bg_card': "#1E1E24", 'text_main': "#FFFFFF", 'text_sub': "#A0A0A0",
            'border': "#333333", 'input_bg': "#16161A", 'scroll': "#2A2A30",
            'btn_face': "#2D79FF", 'btn_side': "#1B4DB3", 'btn_sec_face': "#2A2A30", 'btn_sec_side': "#1A1A20",
            'shadow': QColor(0, 0, 0, 150)
        },
        'light': {
            'bg_main': "#F2F5F8", 'bg_card': "#FFFFFF", 'text_main': "#333333", 'text_sub': "#666666",
            'border': "#E0E0E0", 'input_bg': "#FAFAFA", 'scroll': "#D0D0D0",
            'btn_face': "#2D79FF", 'btn_side': "#1B4DB3", 'btn_sec_face': "#FFFFFF", 'btn_sec_side': "#D1D9E6",
            'shadow': QColor(0, 0, 0, 30)
        }
    }
    ACCENT_GREEN = "#00E070"
    ACCENT_RED = "#FF453A"
    ACCENT_YELLOW = "#FFD60A"
    ACCENT_BLUE = "#2D79FF"
    ACCENT_GRAY = "#666666"

    @classmethod
    def get(cls, key): return cls.COLORS[cls.CURRENT_MODE].get(key, "#FF00FF")
    @classmethod
    def toggle(cls): cls.CURRENT_MODE = 'light' if cls.CURRENT_MODE == 'dark' else 'dark'
    @staticmethod
    def shadow(radius=20):
        e = QGraphicsDropShadowEffect()
        e.setBlurRadius(radius)
        e.setXOffset(0)
        e.setYOffset(4)
        e.setColor(Theme.COLORS[Theme.CURRENT_MODE]['shadow'])
        return e

# ---------------------- 基础组件 ----------------------
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
    def thumb_pos(self, val): 
        self._thumb_x = val
        self.update()
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_dark = not self._is_dark
            start, end = (self._thumb_x, 30) if self._is_dark else (self._thumb_x, 4)
            self.anim.stop()
            self.anim.setStartValue(start)
            self.anim.setEndValue(end)
            self.anim.start()
            self.toggled.emit(self._is_dark)
    
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor("#333") if self._is_dark else QColor("#D0D0D0"))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(0, 0, 56, 28, 14, 14)
        p.setFont(QFont("Segoe UI Emoji", 10))
        if self._is_dark: 
            p.setPen(QColor("#666"))
            p.drawText(8, 19, "☀️")
        else: 
            p.setPen(QColor("#FFF"))
            p.drawText(36, 19, "🌙")
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
    def hover_progress(self, val): 
        self._hover_progress = val
        self.update()
    
    def enterEvent(self, e): 
        self.anim.stop()
        self.anim.setEndValue(1.0)
        self.anim.start()
        super().enterEvent(e)
    
    def leaveEvent(self, e): 
        self.anim.stop()
        self.anim.setEndValue(0.0)
        self.anim.start()
        super().leaveEvent(e)
    
    def mousePressEvent(self, e): 
        if e.button() == Qt.LeftButton: 
            self._is_pressed = True
            self.update()
        super().mousePressEvent(e)
    
    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton: 
            self._is_pressed = False
            self.update()
        super().mouseReleaseEvent(e)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        if self._is_primary: 
            face_c, side_c, txt_c = QColor(Theme.get('btn_face')), QColor(Theme.get('btn_side')), QColor("white")
        else: 
            face_c, side_c = QColor(Theme.get('btn_sec_face')), QColor(Theme.get('btn_sec_side'))
            txt_c = QColor("white") if Theme.CURRENT_MODE == 'dark' else QColor("#333")
        
        if self._hover_progress > 0: 
            face_c = face_c.lighter(105)
            side_c = side_c.lighter(105)
        
        current_offset = self._offset_y if not self._is_pressed else 2
        face_h = h - self._offset_y
        
        path_side = QPainterPath()
        path_side.addRoundedRect(QRectF(0, self._offset_y, w, face_h), 12, 12)
        painter.setBrush(side_c)
        painter.setPen(Qt.NoPen)
        painter.drawPath(path_side)
        
        top_y = 0 if not self._is_pressed else (self._offset_y - 2)
        rect_face = QRectF(0, top_y, w, face_h)
        painter.setBrush(face_c)
        painter.drawRoundedRect(rect_face, 12, 12)
        painter.setPen(txt_c)
        painter.drawText(rect_face, Qt.AlignCenter, self.text())

class ModernProgressBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(6)
        self._value = 0
    
    def setValue(self, v): 
        self._value = v
        self.update()
    
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        bg_c = QColor("#333") if Theme.CURRENT_MODE == 'dark' else QColor("#DDD")
        p.setBrush(bg_c)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(rect, 3, 3)
        if self._value <= 0: return
        w = rect.width() * (self._value / 100.0)
        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0, QColor("#2D79FF"))
        grad.setColorAt(1, QColor("#00F0FF"))
        p.setBrush(grad)
        p.drawRoundedRect(QRectF(0, 0, w, rect.height()), 3, 3)

class AIGCGaugeWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        self._value = 0
        self.animation = QPropertyAnimation(self, b"value")
        self.animation.setDuration(800)
        self.animation.setEasingCurve(QEasingCurve.OutCubic) 
    
    @Property(float)
    def value(self): return self._value
    @value.setter
    def value(self, v): 
        self._value = v
        self.update()
    
    def setValue(self, v):
        self.animation.stop()
        self.animation.setStartValue(self._value)
        self.animation.setEndValue(v)
        self.animation.start()
        
    def get_color(self, val): 
        return QColor(Theme.ACCENT_GREEN) if val < 30 else QColor(Theme.ACCENT_YELLOW) if val < 60 else QColor(Theme.ACCENT_RED)
    
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        side = min(w, h * 1.5)
        p.translate(w / 2, h * 0.85)
        scale = side / 320
        p.scale(scale, scale)
        color = self.get_color(self._value)
        
        glow = QRadialGradient(0, 0, 150)
        glow.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 40 if Theme.CURRENT_MODE == 'dark' else 10))
        glow.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
        p.setBrush(glow)
        p.setPen(Qt.NoPen)
        p.drawEllipse(-150, -150, 300, 300)
        
        p.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        p.setPen(QColor(Theme.get('text_sub')))
        p.drawText(QRectF(-100, -170, 200, 30), Qt.AlignCenter, "整体疑似度")
        
        p.setPen(QPen(QColor(40, 40, 45) if Theme.CURRENT_MODE == 'dark' else QColor(220, 220, 220), 18, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(QRectF(-110, -110, 220, 220), 180 * 16, -180 * 16)
        
        p.setPen(QPen(color, 18, Qt.SolidLine, Qt.RoundCap))
        span = -(self._value / 100.0) * 180 * 16
        p.drawArc(QRectF(-110, -110, 220, 220), 180 * 16, span)
        
        p.setPen(QColor(Theme.get('text_main')))
        p.setFont(QFont("Segoe UI", 42, QFont.Bold))
        p.drawText(QRectF(-100, -80, 200, 60), Qt.AlignCenter, f"{int(self._value)}%")
        
        p.save()
        angle = (self._value / 100.0) * 180 - 90
        p.rotate(angle)
        pointer_c = QColor("white") if Theme.CURRENT_MODE == 'dark' else QColor("#333")
        p.setBrush(QBrush(pointer_c))
        p.setPen(Qt.NoPen)
        p.drawPolygon(QPolygonF([QPointF(-6, 0), QPointF(6, 0), QPointF(0, -98)]))
        p.setBrush(QBrush(QColor(Theme.get('bg_card'))))
        p.setPen(QPen(pointer_c, 3))
        p.drawEllipse(-8, -8, 16, 16)
        p.restore()

class AIGCPieChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(220, 180)
        self.counts = [0, 0, 0] # Human, Mixed, AI
        self.labels = ["人类文本", "疑似混写", "疑似AI"]
        self.colors = [Theme.ACCENT_GREEN, Theme.ACCENT_YELLOW, Theme.ACCENT_RED]
        self.hovered_idx = -1
        self._anim_progress = 0.0
        self.anim = QPropertyAnimation(self, b"anim_progress", self)
        self.anim.setDuration(1000)
        self.anim.setEasingCurve(QEasingCurve.OutElastic)
        self.setMouseTracking(True)

    @Property(float)
    def anim_progress(self): return self._anim_progress
    @anim_progress.setter
    def anim_progress(self, val): 
        self._anim_progress = val
        self.update()

    def set_data(self, counts):
        self.counts = counts
        self.anim.stop()
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()

    def mouseMoveEvent(self, event):
        center = QPointF(self.width() * 0.65, self.height() / 2)
        pos = event.position()
        dx = pos.x() - center.x()
        dy = pos.y() - center.y()
        dist = math.sqrt(dx*dx + dy*dy)
        radius = min(self.width(), self.height()) * 0.35
        if dist <= radius:
            angle = math.degrees(math.atan2(-dy, dx)) 
            if angle < 0: angle += 360
            total = sum(self.counts)
            if total == 0: 
                self.hovered_idx = -1
                self.update()
                return
            current_angle = 0
            for i, count in enumerate(self.counts):
                span = (count / total) * 360
                if current_angle <= angle < current_angle + span:
                    self.hovered_idx = i
                    self.update()
                    return
                current_angle += span
        if self.hovered_idx != -1: 
            self.hovered_idx = -1
            self.update()

    def leaveEvent(self, event): 
        self.hovered_idx = -1
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        center_x = w * 0.65
        center_y = h / 2
        radius = min(w, h) * 0.35 * self._anim_progress
        total = sum(self.counts)
        if total == 0:
            p.setPen(QPen(QColor(60,60,60), 4))
            p.drawEllipse(QPointF(center_x, center_y), radius, radius)
            return
        start_angle = 0
        for i, count in enumerate(self.counts):
            span_angle = (count / total) * 360 * 16
            r = radius + (5 if i == self.hovered_idx else 0)
            c = QColor(self.colors[i])
            if i == self.hovered_idx: c = c.lighter(120)
            else: c.setAlpha(200)
            p.setBrush(c)
            p.setPen(Qt.NoPen)
            rect = QRectF(center_x - r, center_y - r, r*2, r*2)
            p.drawPie(rect, start_angle, int(span_angle))
            start_angle += int(span_angle)
        
        legend_x = 20
        legend_y = h / 2 - 30
        p.setFont(QFont("Microsoft YaHei", 9))
        for i, label in enumerate(self.labels):
            c = QColor(self.colors[i])
            p.setBrush(c)
            p.drawRoundedRect(legend_x, int(legend_y + i*25), 12, 12, 3, 3)
            p.setPen(QColor(Theme.get('text_main')))
            count_text = f"{label}: {self.counts[i]}"
            if i == self.hovered_idx: 
                p.setFont(QFont("Microsoft YaHei", 9, QFont.Bold))
                p.setPen(c)
            else: 
                p.setFont(QFont("Microsoft YaHei", 9))
            p.drawText(legend_x + 20, int(legend_y + i*25 + 10), count_text)

# --- HeatmapBar 组件 (修复定义位置) ---
class HeatmapBar(QWidget):
    clicked_section = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(16)
        self.data = [] 
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("background-color: rgba(0,0,0,0.1); border-radius: 4px;")

    def set_data(self, paragraphs):
        self.data = []
        total_len = sum(max(len(p['content']), 10) for p in paragraphs) if paragraphs else 1
        
        for i, p in enumerate(paragraphs):
            score = p['ai_rate']
            is_ignored = p.get('is_ignored', False)
            length = max(len(p['content']), 10)
            
            if is_ignored: c = QColor(Theme.ACCENT_GRAY)
            elif score < 30: c = QColor(Theme.ACCENT_GREEN)
            elif score < 60: c = QColor(Theme.ACCENT_YELLOW)
            else: c = QColor(Theme.ACCENT_RED)
            
            self.data.append({
                "index": i,
                "color": c,
                "weight": length / total_len
            })
        self.update()

    def paintEvent(self, event):
        if not self.data: return
        p = QPainter(self)
        p.setPen(Qt.NoPen)
        h = self.height()
        w = self.width()
        current_y = 0.0
        for item in self.data:
            block_h = max(2.0, item['weight'] * h)
            p.setBrush(item['color'])
            p.drawRect(2, int(current_y), w-4, int(block_h))
            current_y += block_h 

    def mousePressEvent(self, event):
        if not self.data: return
        y = event.position().y()
        h = self.height()
        current_y = 0.0
        for item in self.data:
            block_h = max(2.0, item['weight'] * h)
            if current_y <= y <= current_y + block_h:
                self.clicked_section.emit(item['index'])
                return
            current_y += block_h

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
            self.anim_glow.stop()
            self.anim_glow.setEndValue(1.0)
            self.anim_glow.start()
            self.anim_scale.stop()
            self.anim_scale.setEndValue(1.02)
            self.anim_scale.start()
        else: e.ignore()

    def dragLeaveEvent(self, e):
        self.anim_glow.stop()
        self.anim_glow.setEndValue(0.0)
        self.anim_glow.start()
        self.anim_scale.stop()
        self.anim_scale.setEndValue(1.0)
        self.anim_scale.start()
        super().dragLeaveEvent(e)

    def dropEvent(self, e):
        self.anim_glow.stop()
        self.anim_glow.setEndValue(0.0)
        self.anim_glow.start()
        self.anim_scale.stop()
        self.anim_scale.setEndValue(1.0)
        self.anim_scale.start()
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            ext = os.path.splitext(path)[1].lower()
            if ext in ['.txt', '.docx']:
                self.file_dropped.emit(path)
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
            
    def highlight_paragraph(self, content):
        """高亮并滚动到指定段落"""
        if not content: return
        cursor = self.document().find(content[:50])
        if not cursor.isNull():
            cursor.select(QTextCursor.BlockUnderCursor)
            self.setTextCursor(cursor)
            self.ensureCursorVisible()
            self.setFocus()

class ResultBlock(QWidget):
    request_scroll = Signal() 
    request_highlight = Signal(str)

    def __init__(self, index, content, ai_rate, is_ignored=False, parent=None):
        super().__init__(parent)
        self.index = index
        self.content = content
        self.ai_rate = ai_rate
        self.is_ignored = is_ignored
        self.is_expanded = False 
        
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor) 

        if self.is_ignored:
            self.accent_color = Theme.ACCENT_GRAY
            self.verdict = "过短忽略"
            self.header_text_color = "#888"
        elif ai_rate < 30: 
            self.accent_color = Theme.ACCENT_GREEN
            self.verdict = "人类创作"
            self.header_text_color = Theme.ACCENT_GREEN
        elif ai_rate < 60: 
            self.accent_color = Theme.ACCENT_YELLOW
            self.verdict = "疑似混写"
            self.header_text_color = Theme.ACCENT_YELLOW
        else: 
            self.accent_color = Theme.ACCENT_RED
            self.verdict = "疑似生成"
            self.header_text_color = Theme.ACCENT_RED

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.header_frame = QFrame()
        self.header_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.get('bg_card')};
                border: 1px solid {Theme.get('border')};
                border-radius: 8px;
            }}
            QFrame:hover {{
                border: 1px solid {self.accent_color};
                background-color: {QColor(Theme.get('bg_card')).lighter(105).name()};
            }}
        """)
        self.header_layout = QHBoxLayout(self.header_frame)
        self.header_layout.setContentsMargins(15, 12, 15, 12)

        idx_lbl = QLabel(f"#{self.index+1}")
        idx_lbl.setStyleSheet(f"color: {Theme.get('text_sub')}; font-weight: bold;")
        
        risk_lbl = QLabel(f"{int(self.ai_rate)}% {self.verdict}")
        risk_lbl.setStyleSheet(f"color: {self.header_text_color}; font-weight: 900; font-size: 11pt;")
        
        preview_text = self.content[:30].replace("\n", " ") + ("..." if len(self.content) > 30 else "")
        self.preview_lbl = QLabel(preview_text)
        self.preview_lbl.setStyleSheet(f"color: {Theme.get('text_sub')}; margin-left: 10px;")
        self.preview_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.arrow_lbl = QLabel("▼")
        self.arrow_lbl.setStyleSheet(f"color: {Theme.get('text_sub')};")

        self.header_layout.addWidget(idx_lbl)
        self.header_layout.addWidget(risk_lbl)
        self.header_layout.addWidget(self.preview_lbl)
        self.header_layout.addWidget(self.arrow_lbl)

        self.content_frame = QFrame()
        self.content_frame.setStyleSheet(f"background-color: {Theme.get('input_bg')}; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;")
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(20, 15, 20, 15)
        
        self.full_text_lbl = QLabel(self.content)
        self.full_text_lbl.setWordWrap(True)
        self.full_text_lbl.setStyleSheet(f"color: {Theme.get('text_main')}; font-size: 10pt; line-height: 1.6;")
        self.full_text_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        
        self.content_layout.addWidget(self.full_text_lbl)
        self.content_frame.hide() 

        self.main_layout.addWidget(self.header_frame)
        self.main_layout.addWidget(self.content_frame)

    def mousePressEvent(self, event):
        self.toggle_expand()
        self.request_highlight.emit(self.content)
        super().mousePressEvent(event)

    def toggle_expand(self):
        self.is_expanded = not self.is_expanded
        
        if self.is_expanded:
            self.content_frame.show()
            self.preview_lbl.hide() 
            self.arrow_lbl.setText("▲")
            self.header_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {Theme.get('bg_card')};
                    border: 1px solid {self.accent_color};
                    border-bottom: none;
                    border-top-left-radius: 8px;
                    border-top-right-radius: 8px;
                    border-bottom-left-radius: 0px;
                    border-bottom-right-radius: 0px;
                }}
            """)
            self.content_frame.setStyleSheet(f"""
                background-color: {Theme.get('input_bg')}; 
                border: 1px solid {self.accent_color};
                border-top: none;
                border-bottom-left-radius: 8px; 
                border-bottom-right-radius: 8px;
            """)
        else:
            self.content_frame.hide()
            self.preview_lbl.show()
            self.arrow_lbl.setText("▼")
            self.header_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {Theme.get('bg_card')};
                    border: 1px solid {Theme.get('border')};
                    border-radius: 8px;
                }}
                QFrame:hover {{
                    border: 1px solid {self.accent_color};
                }}
            """)
        
        self.request_scroll.emit()

    def set_expanded(self, expanded):
        if self.is_expanded != expanded:
            self.toggle_expand()

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
                torch_device = torch.device("cuda")
            elif use_mps:
                device_str = "mps"
                self.device_signal.emit(f"⚡ Mac GPU 加速 (Torch {torch.__version__})", True)
                torch_device = torch.device("mps")
            else:
                device_str = "cpu"
                version = torch.__version__
                extra_info = " [错误: 安装了CPU版Torch]" if "+cpu" in version else (" [未发现NVIDIA显卡]" if not use_cuda else "")
                self.device_signal.emit(f"🐢 CPU 运算 (Torch {version}){extra_info}", False)
                torch_device = torch.device("cpu")
            
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
                self.is_model_valid = True
                self.model_path = target_dir
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
        for i in range(self.result_layout.count()):
            w = self.result_layout.itemAt(i).widget()
            if w: w.update()
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
            self.result_layout.addWidget(block)
            
        self.result_layout.addStretch()
        self.apply_filter()

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