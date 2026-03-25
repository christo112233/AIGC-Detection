import math
import html
import os

from PySide6.QtWidgets import (
    QWidget, QPushButton, QLabel, QFrame, QTextEdit, QHBoxLayout, QVBoxLayout, 
    QSizePolicy, QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QScrollArea, 
    QDialog, QCheckBox, QSlider, QGridLayout, QLineEdit, QMessageBox, QApplication
)
from PySide6.QtCore import (
    Qt, Property, QPropertyAnimation, QEasingCurve, QRectF, QPointF, Signal, QSize, QTimer
)
from PySide6.QtGui import (
    QColor, QPainter, QFont, QPen, QBrush, QLinearGradient, QRadialGradient,
    QPainterPath, QTransform, QFontMetrics, QTextCursor, QPolygonF, QPixmap, QPalette
)

# ---------------------- 核心配色管理 ----------------------
class Theme:
    """管理纯深色主题的调色板字典类"""
    CURRENT_MODE = 'dark' 
    COLORS = {
        'dark': {
            'bg_main': "#0D0D11",     
            'bg_card': "#15151A",     
            'text_main': "#F3F4F6",   
            'text_sub': "#9CA3AF",    
            'border': "rgba(255, 255, 255, 0.06)", 
            'input_bg': "#101014",    
            'scroll': "#2A2A30",
            'btn_face': "#3B82F6",    
            'btn_side': "#2563EB",    
            'btn_sec_face': "rgba(255, 255, 255, 0.05)",
            'btn_sec_side': "rgba(255, 255, 255, 0.02)",
            'shadow': QColor(0, 0, 0, 100) 
        }
    }
    
    ACCENT_GREEN = QColor(16, 185, 129)  
    ACCENT_RED = QColor(239, 68, 68)     
    ACCENT_YELLOW = QColor(245, 158, 11) 
    ACCENT_BLUE = QColor(59, 130, 246)   
    ACCENT_GRAY = QColor(156, 163, 175)  

    # --- 核心美化：横竖滚动条统一全圆角隐藏式设计 ---
    SCROLLBAR_CSS = """
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

    @classmethod
    def get(cls, key):
        return cls.COLORS['dark'].get(key, "#FF00FF")

    @staticmethod
    def shadow(radius=25):
        effect = QGraphicsDropShadowEffect()
        effect.setBlurRadius(radius)
        effect.setXOffset(0)
        effect.setYOffset(8)
        effect.setColor(Theme.COLORS['dark']['shadow'])
        return effect

# ---------------------- 基础 UI 组件 ----------------------

class GlowingButton(QPushButton):
    """高级现代流光按钮，支持动态更改主题色(Variant)"""
    def __init__(self, text, variant="primary", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(36)
        self.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        self.variant = variant
        self.click_pos = QPointF(0, 0)
        self._hover_progress = 0.0
        self._press_progress = 0.0
        
        self.hover_anim = QPropertyAnimation(self, b"hover_progress", self)
        self.hover_anim.setDuration(250)
        self.hover_anim.setEasingCurve(QEasingCurve.OutSine)
        
        self.press_anim = QPropertyAnimation(self, b"press_progress", self)
        self.press_anim.setDuration(400)
        self.press_anim.setEasingCurve(QEasingCurve.OutQuart)

    def setVariant(self, variant):
        self.variant = variant
        self.update()

    def get_base_color(self):
        if self.variant == "primary":
            return Theme.ACCENT_BLUE
        elif self.variant == "danger":
            return Theme.ACCENT_RED
        else:
            return QColor(255, 255, 255, 20)

    @Property(float)
    def hover_progress(self):
        return self._hover_progress

    @hover_progress.setter
    def hover_progress(self, val):
        self._hover_progress = val
        self.update()

    @Property(float)
    def press_progress(self):
        return self._press_progress

    @press_progress.setter
    def press_progress(self, val):
        self._press_progress = val
        self.update()

    def enterEvent(self, e):
        self.hover_anim.stop()
        self.hover_anim.setEndValue(1.0)
        self.hover_anim.start()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.hover_anim.stop()
        self.hover_anim.setEndValue(0.0)
        self.hover_anim.start()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.click_pos = e.position() 
            self.press_anim.stop()
            self.press_anim.setStartValue(0.0)
            self.press_anim.setEndValue(1.0)
            self.press_anim.start()
        super().mousePressEvent(e)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()
        radius = h / 2.0 
        
        base_c = self.get_base_color()
        p.setPen(Qt.NoPen)
        
        if self.variant in ["primary", "danger"]:
            bg_c = base_c.lighter(100 + int(self._hover_progress * 15))
            text_c = QColor("white")
        else:
            alpha = int(20 + self._hover_progress * 25)
            bg_c = QColor(255, 255, 255, alpha)
            text_c = QColor(Theme.get('text_main'))

        rect_path = QPainterPath()
        rect_path.addRoundedRect(0, 0, w, h, radius, radius)
        p.setBrush(bg_c)
        p.drawPath(rect_path)
        
        if self._press_progress > 0.0:
            p.save()
            p.setClipPath(rect_path)
            ripple_c = QColor("white") if self.variant != "secondary" else QColor(Theme.get('text_main'))
            ripple_c.setAlpha(int(60 * (1.0 - self._press_progress)))
            p.setBrush(ripple_c)
            ripple_r = w * self._press_progress
            p.drawEllipse(self.click_pos, ripple_r, ripple_r)
            p.restore()

        if self.variant in ["primary", "danger"] and self._hover_progress > 0:
            glow_c = QColor(base_c)
            glow_c.setAlpha(int(80 * self._hover_progress))
            p.setPen(QPen(glow_c, 3))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(1, 1, w - 2, h - 2, radius - 1, radius - 1)

        p.setPen(text_c)
        offset_y = 1 if 0.0 < self._press_progress < 0.3 else 0
        p.drawText(QRectF(0, offset_y, w, h), Qt.AlignCenter, self.text())
        p.end()

class ThreeDButton(GlowingButton):
    pass

class ModernProgressBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(4) 
        self._value = 0

    def setValue(self, v):
        self._value = v
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        
        bg_c = QColor(255, 255, 255, 15)
        p.setBrush(bg_c)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(rect, 2, 2)
        
        if self._value <= 0:
            p.end()
            return
            
        w = rect.width() * (self._value / 100.0)
        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0, Theme.ACCENT_BLUE)
        grad.setColorAt(1, QColor("#00F0FF"))
        
        p.setBrush(grad)
        p.drawRoundedRect(QRectF(0, 0, w, rect.height()), 2, 2)
        p.end()

# ---------------------- 可视化组件 ----------------------
class AIGCGaugeWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(160, 140)
        self._value = 0
        self.animation = QPropertyAnimation(self, b"value")
        self.animation.setDuration(800)
        self.animation.setEasingCurve(QEasingCurve.OutCubic) 

    @Property(float)
    def value(self):
        return self._value

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
        if val < 30:
            return Theme.ACCENT_GREEN
        elif val < 60:
            return Theme.ACCENT_YELLOW
        else:
            return Theme.ACCENT_RED

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        logical_w = 280.0
        logical_h = 190.0
        pad = 10
        
        avail_w = max(1, self.width() - pad * 2)
        avail_h = max(1, self.height() - pad * 2)
        
        scale = min(avail_w / logical_w, avail_h / logical_h)
        scale = max(0.65, scale)
        
        offset_x = pad + (avail_w - logical_w * scale) / 2.0
        offset_y = pad + (avail_h - logical_h * scale) / 2.0
        
        p.translate(offset_x, offset_y)
        p.scale(scale, scale)
        p.translate(140, 170) 
        
        color = self.get_color(self._value)
        
        alpha = 30
        glow = QRadialGradient(0, 0, 140)
        glow.setColorAt(0, QColor(color.red(), color.green(), color.blue(), alpha))
        glow.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
        p.setBrush(glow)
        p.setPen(Qt.NoPen)
        p.drawEllipse(-140, -140, 280, 280)

        if self._value < 30:
            verdict = "人类文本"
        elif self._value < 60:
            verdict = "疑似混写"
        else:
            verdict = "疑似AI"

        p.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        fm = QFontMetrics(p.font())
        title_str = "综合判定 " 
        title_w = fm.horizontalAdvance(title_str)
        verdict_w = fm.horizontalAdvance(verdict)
        total_w = title_w + verdict_w
        
        start_x = -total_w / 2
        p.setPen(QColor(Theme.get('text_sub')))
        p.drawText(QRectF(start_x, -165, title_w, 30), Qt.AlignLeft | Qt.AlignVCenter, title_str)
        
        p.setPen(color)
        p.drawText(QRectF(start_x + title_w, -165, verdict_w, 30), Qt.AlignLeft | Qt.AlignVCenter, verdict)

        track_c = QColor(255, 255, 255, 10)
        p.setPen(QPen(track_c, 16, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(QRectF(-110, -110, 220, 220), 180 * 16, -180 * 16)

        p.setPen(QPen(color, 16, Qt.SolidLine, Qt.RoundCap))
        span = -(self._value / 100.0) * 180 * 16
        p.drawArc(QRectF(-110, -110, 220, 220), 180 * 16, span)

        p.setPen(QColor(Theme.get('text_main')))
        p.setFont(QFont("Segoe UI", 46, QFont.Bold))
        p.drawText(QRectF(-100, -80, 200, 60), Qt.AlignCenter, f"{int(self._value)}%")

        p.save()
        angle = (self._value / 100.0) * 180 - 90
        p.rotate(angle)
        
        pointer_c = QColor(Theme.get('text_main'))
        p.setBrush(QBrush(pointer_c))
        p.setPen(Qt.NoPen)
        p.drawPolygon(QPolygonF([QPointF(-4, 0), QPointF(4, 0), QPointF(0, -96)]))
        
        p.setBrush(QBrush(QColor(Theme.get('bg_card')))) 
        p.setPen(QPen(pointer_c, 3))
        p.drawEllipse(-6, -6, 12, 12)
        p.restore()
        p.end()

class AIGCPieChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(180, 140)
        self.counts = [0, 0, 0]
        self.labels = ["人类文本", "疑似混写", "疑似AI"]
        self.colors = [Theme.ACCENT_GREEN, Theme.ACCENT_YELLOW, Theme.ACCENT_RED]
        self.hovered_idx = -1
        
        self._anim_progress = 0.0
        self.anim = QPropertyAnimation(self, b"anim_progress", self)
        self.anim.setDuration(1200)
        self.anim.setEasingCurve(QEasingCurve.OutQuart)
        
        self.setMouseTracking(True)
        self.hover_offsets = [0.0, 0.0, 0.0]
        self.target_offsets = [0.0, 0.0, 0.0]
        
        self.hover_timer = QTimer(self)
        self.hover_timer.timeout.connect(self._smooth_hover_anim)
        self.hover_timer.start(16)

    @Property(float)
    def anim_progress(self):
        return self._anim_progress

    @anim_progress.setter
    def anim_progress(self, val):
        self._anim_progress = val
        self.update()

    def _smooth_hover_anim(self):
        needs_update = False
        for i in range(3):
            diff = self.target_offsets[i] - self.hover_offsets[i]
            if abs(diff) > 0.05:
                self.hover_offsets[i] += diff * 0.15
                needs_update = True
            else:
                if self.hover_offsets[i] != self.target_offsets[i]:
                    self.hover_offsets[i] = self.target_offsets[i]
                    needs_update = True
        if needs_update:
            self.update()

    def set_data(self, counts):
        self.counts = counts
        self.anim.stop()
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()

    def _get_logical_params(self):
        logical_w = 320.0
        logical_h = 190.0
        pad = 5
        
        avail_w = max(1, self.width() - pad * 2)
        avail_h = max(1, self.height() - pad * 2)
        
        scale = min(avail_w / logical_w, avail_h / logical_h)
        scale = max(0.65, scale)
        
        offset_x = pad + (avail_w - logical_w * scale) / 2.0
        offset_y = pad + (avail_h - logical_h * scale) / 2.0
        
        return logical_w, logical_h, scale, offset_x, offset_y

    def mouseMoveEvent(self, event):
        logical_w, logical_h, scale, offset_x, offset_y = self._get_logical_params()
        
        pos = event.position()
        lx = (pos.x() - offset_x) / scale
        ly = (pos.y() - offset_y) / scale
        
        center_x = 220.0
        center_y = 105.0 
        base_radius = 80.0
        inner_radius = base_radius * 0.65 
        
        dx = lx - center_x
        dy = ly - center_y
        dist = math.sqrt(dx * dx + dy * dy)
        
        new_hover_idx = -1
        if inner_radius - 5 <= dist <= base_radius + 25: 
            math_angle = math.degrees(math.atan2(-dy, dx))
            sweep_angle = (90 - math_angle) % 360
            
            total = sum(self.counts)
            if total > 0:
                current_angle = 0
                for i, count in enumerate(self.counts):
                    span = (count / total) * 360
                    if current_angle <= sweep_angle < current_angle + span:
                        if dist <= base_radius + self.hover_offsets[i] + 5:
                            new_hover_idx = i
                        break
                    current_angle += span
                    
        if new_hover_idx != self.hovered_idx:
            self.hovered_idx = new_hover_idx
            for i in range(3):
                self.target_offsets[i] = 12.0 if i == self.hovered_idx else 0.0

    def leaveEvent(self, event):
        self.hovered_idx = -1
        for i in range(3):
            self.target_offsets[i] = 0.0

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        logical_w, logical_h, scale, offset_x, offset_y = self._get_logical_params()
        
        p.translate(offset_x, offset_y)
        p.scale(scale, scale)
        
        p.setOpacity(self._anim_progress)
        p.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        p.setPen(QColor(Theme.get('text_sub')))
        p.drawText(QRectF(15, 10, logical_w - 30, 30), Qt.AlignLeft | Qt.AlignVCenter, "段落成分分布")
        
        center_x = 220.0
        center_y = 105.0
        base_radius = 80.0
        total = sum(self.counts)
        
        if total == 0:
            p.setPen(QPen(QColor(255, 255, 255, 20), 16))
            p.drawArc(QRectF(center_x - base_radius, center_y - base_radius, base_radius * 2, base_radius * 2), 0, 360 * 16)
            p.end()
            return

        start_angle = 90 * 16 
        accumulated_fraction = 0.0 
        
        for i, count in enumerate(self.counts):
            segment_fraction = count / total
            if self._anim_progress <= accumulated_fraction:
                break
                
            allowed_fraction = min(segment_fraction, self._anim_progress - accumulated_fraction)
            span_angle = - (allowed_fraction * 360 * 16) 
            
            offset = self.hover_offsets[i]
            r = base_radius + offset 
            
            c = QColor(self.colors[i])
            lightness = 100 + int((offset / 12.0) * 15)
            c = c.lighter(lightness)
            c.setAlpha(255) 
            
            p.setBrush(c)
            p.setPen(Qt.NoPen)
            rect = QRectF(center_x - r, center_y - r, r * 2, r * 2)
            p.drawPie(rect, start_angle, int(span_angle))
            
            start_angle += int(-segment_fraction * 360 * 16)
            accumulated_fraction += segment_fraction
            
        p.setBrush(QColor(Theme.get('bg_card')))
        p.setPen(Qt.NoPen)
        inner_radius = base_radius * 0.65
        p.drawEllipse(QPointF(center_x, center_y), inner_radius, inner_radius)
        
        if self._anim_progress > 0.6: 
            if self.hovered_idx != -1:
                pct = int(self.counts[self.hovered_idx] / total * 100) if total else 0
                p.setPen(QColor(self.colors[self.hovered_idx]))
                p.setFont(QFont("Segoe UI", 24, QFont.Bold))
                p.drawText(QRectF(center_x - 45, center_y - 20, 90, 40), Qt.AlignCenter, f"{pct}%")
            else:
                p.setPen(QColor(Theme.get('text_sub')))
                p.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
                p.drawText(QRectF(center_x - 45, center_y - 20, 90, 40), Qt.AlignCenter, f"共 {total} 段")
                
        legend_x = 15.0
        legend_y = 65.0
        
        for i, label in enumerate(self.labels):
            c = QColor(self.colors[i])
            offset = self.hover_offsets[i]
            box_x = legend_x + (offset * 0.5) 
            
            p.setBrush(c)
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(box_x, legend_y + i * 32, 12, 12), 4, 4)
            
            text_c = QColor(Theme.get('text_main'))
            if i == self.hovered_idx:
                p.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
                text_c = c.lighter(110)
            else:
                p.setFont(QFont("Microsoft YaHei", 11))
                text_c.setAlpha(150)
                
            p.setPen(text_c)
            p.drawText(QRectF(box_x + 22, legend_y + i * 32 - 10, 150, 30), Qt.AlignLeft | Qt.AlignVCenter | Qt.TextDontClip, f"{label}: {self.counts[i]}")
            
        p.end()

class TokenCounterWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(120, 140)
        self._current_value = 0
        self.anim = QPropertyAnimation(self, b"anim_val", self)
        self.anim.setDuration(1200)
        self.anim.setEasingCurve(QEasingCurve.OutQuart)

    @Property(int)
    def anim_val(self):
        return self._current_value

    @anim_val.setter
    def anim_val(self, v):
        self._current_value = v
        self.update()

    def set_data(self, v):
        self.anim.stop()
        self.anim.setStartValue(0)
        self.anim.setEndValue(v)
        self.anim.start()

    def update_style(self):
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        pad = 5
        avail_w = max(1, self.width() - pad * 2)
        avail_h = max(1, self.height() - pad * 2)
        
        logical_w = 190.0
        logical_h = 190.0
        
        scale = max(0.7, min(avail_w / logical_w, avail_h / logical_h))
        
        offset_x = pad + (avail_w - logical_w * scale) / 2.0
        offset_y = pad + (avail_h - logical_h * scale) / 2.0
        
        p.translate(offset_x, offset_y)
        p.scale(scale, scale)
        
        p.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        p.setPen(QColor(Theme.get('text_sub')))
        p.drawText(QRectF(0, 30, logical_w, 30), Qt.AlignCenter, "⚡  算力消耗 (Tokens)")
        
        p.setFont(QFont("Consolas", 36, QFont.Bold))
        p.setPen(Theme.ACCENT_BLUE)
        p.drawText(QRectF(0, 80, logical_w, 60), Qt.AlignCenter, f"{self._current_value:,}")
        p.end()

class StatsDashboard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)
        
        self.gauge = AIGCGaugeWidget()
        self.token_counter = TokenCounterWidget()
        self.pie_chart = AIGCPieChart()
        
        self.layout.addWidget(self.gauge, 7)
        self.layout.addWidget(self.token_counter, 4)
        self.layout.addWidget(self.pie_chart, 8)

    def update_style(self):
        self.setStyleSheet("StatsDashboard { background: transparent; border: none; }")
        self.gauge.update()
        self.pie_chart.update()
        self.token_counter.update_style()

class HeatmapBar(QWidget):
    clicked_section = Signal(int)
    double_clicked = Signal() 

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(28)
        self.data = []
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        
        self._anim_progress = 0.0
        self.anim = QPropertyAnimation(self, b"anim_progress", self)
        self.anim.setDuration(1200)
        self.anim.setEasingCurve(QEasingCurve.OutExpo)
        
        self.hover_width = 8.0
        self.target_width = 8.0
        self.hovered_idx = -1
        self.block_offsets = []
        
        self.hover_timer = QTimer(self)
        self.hover_timer.timeout.connect(self._smooth_anim)
        self.hover_timer.start(16)

    @Property(float)
    def anim_progress(self):
        return self._anim_progress

    @anim_progress.setter
    def anim_progress(self, val):
        self._anim_progress = val
        self.update()

    def _smooth_anim(self):
        needs_update = False
        diff = self.target_width - self.hover_width
        
        if abs(diff) > 0.05:
            self.hover_width += diff * 0.2
            needs_update = True
            
        for i in range(len(self.block_offsets)):
            target = 8.0 if i == self.hovered_idx else 0.0
            diff_b = target - self.block_offsets[i]
            if abs(diff_b) > 0.05:
                self.block_offsets[i] += diff_b * 0.25
                needs_update = True
                
        if needs_update:
            self.update()

    def set_data(self, paragraphs):
        self.data = []
        total = sum(max(len(p['content']), 10) for p in paragraphs) if paragraphs else 1
        
        for i, p in enumerate(paragraphs):
            score = p['ai_rate']
            length = max(len(p['content']), 10)
            
            if p.get('is_ignored'):
                c = Theme.ACCENT_GRAY
            elif score < 30:
                c = Theme.ACCENT_GREEN
            elif score < 60:
                c = Theme.ACCENT_YELLOW
            else:
                c = Theme.ACCENT_RED
                
            self.data.append({"index": i, "color": c, "weight": length / total})
            
        self.block_offsets = [0.0] * len(self.data)
        self.hovered_idx = -1
        self.anim.stop()
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()

    def enterEvent(self, event):
        self.target_width = 14.0 

    def leaveEvent(self, event):
        self.target_width = 8.0
        self.hovered_idx = -1

    def mouseMoveEvent(self, event):
        if not self.data:
            return
            
        y = event.position().y()
        h = self.height()
        cur_y = 0.0
        new_hover = -1
        
        for i, it in enumerate(self.data):
            bh = max(3.0, it['weight'] * h)
            if cur_y <= y <= cur_y + bh:
                new_hover = i
                break
            cur_y += bh
            
        if new_hover != self.hovered_idx:
            self.hovered_idx = new_hover

    def mousePressEvent(self, event):
        if -1 < self.hovered_idx < len(self.data):
            self.clicked_section.emit(self.data[self.hovered_idx]['index'])

    def mouseDoubleClickEvent(self, event):
        if self.data:
            self.double_clicked.emit()

    def paintEvent(self, event):
        if not self.data:
            return
            
        p = QPainter(self)
        w = self.width()
        h = self.height()
        
        p.setRenderHint(QPainter.Antialiasing)
        p.setClipRect(0, int(h * (1.0 - self._anim_progress)), int(w), int(h))
        
        tw = self.hover_width + 4
        p.setBrush(QColor(0, 0, 0, 80))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(w / 2 - tw / 2, 0, tw, h), tw / 2, tw / 2)
        
        cur_y = 0.0
        for i, it in enumerate(self.data):
            bh = max(3.0, it['weight'] * h)
            dh = max(2.0, bh - 1.5)
            cw = self.hover_width + self.block_offsets[i]
            c = QColor(it['color'])
            
            if i == self.hovered_idx:
                c = c.lighter(120)
            else:
                if self.hovered_idx != -1:
                    c.setAlpha(100)
                else:
                    c.setAlpha(230)
                    
            p.setBrush(c)
            p.drawRoundedRect(QRectF(w / 2 - cw / 2, cur_y + 0.75, cw, dh), cw / 2, cw / 2)
            cur_y += bh
        p.end()

class DragTextEdit(QTextEdit):
    file_dropped = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setPlaceholderText("在此处粘贴文本或拖入文件...")
        self._glow_strength = 0.0
        
        self.anim_glow = QPropertyAnimation(self, b"glow_strength", self)
        self.anim_glow.setDuration(400)
        self.anim_glow.setEasingCurve(QEasingCurve.OutQuad)

    @Property(float)
    def glow_strength(self):
        return self._glow_strength

    @glow_strength.setter
    def glow_strength(self, v):
        self._glow_strength = v
        self.update()

    def insertFromMimeData(self, src):
        if src.hasText():
            styled = f"<div style='line-height: 1.6;'>{html.escape(src.text()).replace(chr(10), '<br>')}</div>"
            self.insertHtml(styled)
        else:
            super().insertFromMimeData(src)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.accept()
            self.anim_glow.stop()
            self.anim_glow.setEndValue(1.0)
            self.anim_glow.start()
        else:
            e.ignore()

    def dragLeaveEvent(self, e):
        self.anim_glow.stop()
        self.anim_glow.setEndValue(0.0)
        self.anim_glow.start()
        super().dragLeaveEvent(e)

    def dropEvent(self, e):
        self.anim_glow.stop()
        self.anim_glow.setEndValue(0.0)
        self.anim_glow.start()
        
        urls = e.mimeData().urls()
        if urls:
            p = urls[0].toLocalFile()
            if os.path.splitext(p)[1].lower() in ['.txt', '.docx', '.pdf']:
                self.file_dropped.emit(p)
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
            
            c = QColor(Theme.ACCENT_BLUE)
            c.setAlpha(int(60 * self._glow_strength))
            
            p.setPen(QPen(c, 6 * self._glow_strength))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(self.viewport().rect().adjusted(2, 2, -2, -2), 12, 12)
            p.end()

    def highlight_paragraph(self, content):
        if not content:
            return
            
        cursor = self.document().find(content[:50]) 
        if not cursor.isNull():
            start = cursor.selectionStart()
            cursor.setPosition(start)
            cursor.setPosition(start + len(content), QTextCursor.KeepAnchor)
            self.setTextCursor(cursor)
            self.ensureCursorVisible()
            self.setFocus()


# ================= 惊艳的空状态呼吸灯组件 =================
class BreathingLogo(QLabel):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)
        self.setFont(QFont("Segoe UI", 72, QFont.Bold))
        self.setStyleSheet(f"color: {Theme.ACCENT_BLUE.name()};")
        self.anim = None
        self.eff = None
        
        # 初始启动
        self.resume_effect()

    def _toggle_direction(self):
        if not self.anim:
            return
        if self.anim.direction() == QPropertyAnimation.Forward:
            self.anim.setDirection(QPropertyAnimation.Backward)
        else:
            self.anim.setDirection(QPropertyAnimation.Forward)
        self.anim.start()

    def pause_effect(self):
        """剥离自身特效，防止在外层做淡入淡出时发生特效嵌套死锁"""
        if self.anim:
            self.anim.stop()
            try:
                self.anim.finished.disconnect(self._toggle_direction)
            except:
                pass
            self.anim = None
            
        # 【核心修复】：Qt 的 setGraphicsEffect(None) 会在底层 C++ 中直接销毁原有的 Effect 对象
        self.setGraphicsEffect(None)
        self.eff = None

    def resume_effect(self):
        """恢复自身的呼吸特效（每次重新构建以完美规避 C++ 底层销毁陷阱）"""
        self.pause_effect() # 确保清理干净
        
        self.eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.eff)
        
        self.anim = QPropertyAnimation(self.eff, b"opacity")
        self.anim.setDuration(1500) 
        self.anim.setStartValue(0.15)
        self.anim.setEndValue(0.9)
        self.anim.setEasingCurve(QEasingCurve.InOutSine)
        self.anim.finished.connect(self._toggle_direction)
        self.anim.start()

class EmptyStateWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 40, 20, 40)
        lay.addStretch()
        
        self.logo = BreathingLogo("✨")
        lay.addWidget(self.logo)
        
        self.title = QLabel("DeepVeri 处于就绪状态")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setFont(QFont("Microsoft YaHei", 18, QFont.Bold))
        self.title.setStyleSheet(f"color: {Theme.get('text_main')}; margin-top: 20px;")
        lay.addWidget(self.title)
        
        self.sub = QLabel("请在左侧输入文本或拖入文档，点击「开始深度检测」\n系统将为您展开像素级的 AI 生成检测。")
        self.sub.setAlignment(Qt.AlignCenter)
        self.sub.setFont(QFont("Microsoft YaHei", 11))
        self.sub.setStyleSheet(f"color: {Theme.get('text_sub')}; line-height: 1.6; margin-top: 10px;")
        lay.addWidget(self.sub)
        
        lay.addStretch()
        self.setStyleSheet("background: transparent; border: none;")

    def pause_breathing(self):
        self.logo.pause_effect()

    def resume_breathing(self):
        self.logo.resume_effect()

# ================= 极致流体的结果卡片 =================
class ResultBlock(QWidget):
    request_scroll = Signal()
    request_highlight = Signal(str)
    expanded = Signal(int)

    def __init__(self, index, content, ai_rate, tokens=0, is_ignored=False, use_animation=True, parent=None):
        super().__init__(parent)
        self.index = index
        self.content = content
        self.ai_rate = ai_rate
        self.is_ignored = is_ignored
        self.is_expanded = False
        self.is_init = False
        
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor) 
        
        if use_animation:
            self.eff = QGraphicsOpacityEffect(self)
            self.setGraphicsEffect(self.eff)
            self.eff.setOpacity(0.0)
            
            self.anim = QPropertyAnimation(self.eff, b"opacity")
            self.anim.setDuration(600)
            self.anim.setStartValue(0.0)
            self.anim.setEndValue(1.0)
            self.anim.setEasingCurve(QEasingCurve.OutCubic)
            self.anim.finished.connect(self._remove_opacity_effect)
            
            QTimer.singleShot(min(index * 30, 600), self.anim.start)
        else:
            self.setGraphicsEffect(None)
            
        self.update_colors()
        
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(0)
        
        self.head = QFrame()
        hl = QHBoxLayout(self.head)
        hl.setContentsMargins(15, 10, 15, 10)
        
        self.idx_l = QLabel(f"#{index + 1}")
        
        self.token_l = QLabel(f"⚡ {tokens} Tokens")
        self.token_l.setStyleSheet(f"color: {Theme.ACCENT_BLUE.name()}; font-size: 11px; font-weight: bold; font-family: Consolas; background-color: rgba(59, 130, 246, 0.1); border-radius: 6px; padding: 3px 8px;")
        
        self.risk_l = QLabel(f"{int(ai_rate)}% {self.verdict}")
        self.risk_l.setAlignment(Qt.AlignCenter)
        
        preview_text = content[:30].replace("\n", " ") + ("..." if len(content) > 30 else "")
        self.prev_l = QLabel(preview_text)
        self.prev_l.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        
        self.btn_copy = QPushButton("📋")
        self.btn_copy.setFixedSize(26, 26)
        self.btn_copy.setCursor(Qt.PointingHandCursor)
        self.btn_copy.setToolTip("一键复制此高危段落")
        self.btn_copy.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {Theme.get('text_sub')};
                border-radius: 6px;
                font-size: 14px;
                padding-bottom: 2px;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.1);
                color: {Theme.get('text_main')};
            }}
        """)
        self.btn_copy.clicked.connect(self._copy_content)
        
        self.arr_l = QLabel("▼")
        
        hl.addWidget(self.idx_l)
        hl.addSpacing(8)
        hl.addWidget(self.token_l)
        hl.addSpacing(8)
        hl.addWidget(self.risk_l)
        hl.addSpacing(12)
        hl.addWidget(self.prev_l)
        hl.addSpacing(5)
        hl.addWidget(self.btn_copy)
        hl.addSpacing(2)
        hl.addWidget(self.arr_l)
        
        self.lay.addWidget(self.head)
        
        self.wrap = QScrollArea()
        self.wrap.setFrameShape(QFrame.NoFrame)
        self.wrap.setWidgetResizable(True) # 开启自适应机制，放弃定宽焊死
        self.wrap.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.wrap.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.wrap.setStyleSheet("background: transparent; border: none;")
        self.wrap.hide()
        self.wrap.setMaximumHeight(0)
        self.lay.addWidget(self.wrap)
        
        self.h_anim = QPropertyAnimation(self.wrap, b"maximumHeight")
        self.h_anim.finished.connect(self._on_anim_finished)
        
        self.update_style()

    def _remove_opacity_effect(self):
        self.setGraphicsEffect(None)
        self.update()

    def update_colors(self):
        if self.is_ignored:
            r, g, b = Theme.ACCENT_GRAY.red(), Theme.ACCENT_GRAY.green(), Theme.ACCENT_GRAY.blue()
        elif self.ai_rate < 30:
            r, g, b = Theme.ACCENT_GREEN.red(), Theme.ACCENT_GREEN.green(), Theme.ACCENT_GREEN.blue()
        elif self.ai_rate < 60:
            r, g, b = Theme.ACCENT_YELLOW.red(), Theme.ACCENT_YELLOW.green(), Theme.ACCENT_YELLOW.blue()
        else:
            r, g, b = Theme.ACCENT_RED.red(), Theme.ACCENT_RED.green(), Theme.ACCENT_RED.blue()
            
        self.acc_c = QColor(r, g, b).name()
        self.acc_bg = f"rgba({r}, {g}, {b}, 0.15)"
        
        if self.is_ignored:
            self.verdict = "忽略"
        elif self.ai_rate < 30:
            self.verdict = "人类创作"
        elif self.ai_rate < 60:
            self.verdict = "疑似混写"
        else:
            self.verdict = "疑似生成"

    def update_style(self):
        self.idx_l.setStyleSheet(f"color: {Theme.get('text_sub')}; font-weight: bold; font-family: 'Segoe UI';")
        self.risk_l.setStyleSheet(f"background-color: {self.acc_bg}; color: {self.acc_c}; border-radius: 12px; padding: 4px 10px; font-weight: 900; font-family: 'Microsoft YaHei';")
        self.prev_l.setStyleSheet(f"color: {Theme.get('text_sub')}; margin-left: 5px;")
        self.arr_l.setStyleSheet(f"color: {Theme.get('text_sub')};")
        
        bg = Theme.get('bg_card')
        bd = Theme.get('border')
        h_bg = QColor(bg).lighter(104).name()
        
        if self.is_expanded:
            self.head.setStyleSheet(f"QFrame {{ background-color: {h_bg}; border: 1px solid {bd}; border-bottom: none; border-top-left-radius: 12px; border-top-right-radius: 12px; }}")
        else:
            self.head.setStyleSheet(f"QFrame {{ background-color: {bg}; border: 1px solid {bd}; border-radius: 12px; }} QFrame:hover {{ background-color: {h_bg}; border: 1px solid rgba(255, 255, 255, 0.1); }}")

    def _ensure_content_initialized(self):
        if self.is_init:
            return
            
        cf = QFrame()
        cl = QVBoxLayout(cf)
        cl.setContentsMargins(20, 15, 20, 20)
        
        self.txt_l = QLabel(f"<div style='line-height: 1.8;'>{html.escape(self.content)}</div>")
        self.txt_l.setWordWrap(True)
        self.txt_l.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.txt_l.setStyleSheet(f"color: {Theme.get('text_main')}; font-size: 10.5pt;")
        
        cl.addWidget(self.txt_l)
        
        cf.setStyleSheet(f"QFrame {{ background-color: {Theme.get('input_bg')}; border: 1px solid {Theme.get('border')}; border-top: none; border-bottom-left-radius: 12px; border-bottom-right-radius: 12px; }}")
        
        self.inner_eff = QGraphicsOpacityEffect()
        self.inner_eff.setOpacity(0.0)
        cf.setGraphicsEffect(self.inner_eff)
        
        self.fade_anim = QPropertyAnimation(self.inner_eff, b"opacity")
        
        self.wrap.setWidget(cf)
        self.is_init = True

    def toggle_expand(self):
        # 允许半途折返，极致流畅
        self._ensure_content_initialized()
        self.is_expanded = not self.is_expanded
        
        if self.is_expanded:
            self.wrap.show()
            self.prev_l.hide()
            self.arr_l.setText("▲")
            
            # --- 核心修复：短暂约束宽度供高度计算，计算完瞬间释放防乱码 ---
            vp_w = self.wrap.viewport().width()
            if vp_w < 50: vp_w = self.width() - 10
            self.wrap.widget().setFixedWidth(vp_w)
            target_h = self.wrap.widget().sizeHint().height()
            self.wrap.widget().setMinimumWidth(0)
            self.wrap.widget().setMaximumWidth(16777215)
            
            self.h_anim.stop()
            self.h_anim.setStartValue(self.wrap.height())
            self.h_anim.setEndValue(target_h)
            self.h_anim.setEasingCurve(QEasingCurve.OutQuint) # 爆速流体弹开曲线
            self.h_anim.setDuration(400)
            
            self.fade_anim.stop()
            self.fade_anim.setStartValue(self.inner_eff.opacity())
            self.fade_anim.setEndValue(1.0)
            self.fade_anim.setDuration(350)
            
            self.h_anim.start()
            self.fade_anim.start()
            self.expanded.emit(self.index)
        else:
            self.prev_l.show()
            self.arr_l.setText("▼")
            
            self.h_anim.stop()
            self.h_anim.setStartValue(self.wrap.height())
            self.h_anim.setEndValue(0)
            self.h_anim.setEasingCurve(QEasingCurve.InOutQuad) # 极致丝滑缓冲缩回
            self.h_anim.setDuration(350)
            
            self.fade_anim.stop()
            self.fade_anim.setStartValue(self.inner_eff.opacity())
            self.fade_anim.setEndValue(0.0)
            self.fade_anim.setDuration(200)
            
            self.h_anim.start()
            self.fade_anim.start()
            
        self.update_style()
        self.request_scroll.emit()

    def _on_anim_finished(self):
        if not self.is_expanded:
            self.wrap.hide()
        else:
            # 彻底摒弃暴力的 minimumHeight 硬锁定，消除塌陷跳动感
            self.wrap.setMaximumHeight(16777215) 

    def _copy_content(self):
        QApplication.clipboard().setText(self.content)
        self.btn_copy.setText("✅")
        self.btn_copy.setStyleSheet(f"QPushButton {{ background: transparent; color: {Theme.ACCENT_GREEN.name()}; border-radius: 6px; font-size: 14px; }}")
        QTimer.singleShot(2000, self._reset_copy_btn)

    def _reset_copy_btn(self):
        self.btn_copy.setText("📋")
        self.btn_copy.setStyleSheet(f"QPushButton {{ background: transparent; color: {Theme.get('text_sub')}; border-radius: 6px; font-size: 14px; padding-bottom: 2px; }} QPushButton:hover {{ background: rgba(255,255,255,0.1); color: {Theme.get('text_main')}; }}")

    def mousePressEvent(self, e):
        self.toggle_expand()
        self.request_highlight.emit(self.content)

    def set_expanded(self, exp):
        if self.is_expanded != exp:
            self.toggle_expand()

# ================= 全景视图 =================
class DetailedHeatmapRow(QFrame):
    clicked = Signal(int)

    def __init__(self, index, content, ai_rate, is_ignored=False, parent=None):
        super().__init__(parent)
        self.index = index
        self.content = content
        self.ai_rate = ai_rate
        self.is_ignored = is_ignored
        
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(52)
        
        self.update_colors()
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 5, 15, 5)
        
        self.idx_lbl = QLabel(f"#{index + 1}")
        self.idx_lbl.setFixedWidth(40)
        
        self.score_lbl = QLabel(f"{int(ai_rate)}% {self.verdict}" if not is_ignored else "忽略")
        self.score_lbl.setAlignment(Qt.AlignCenter)
        
        preview_text = content[:30].replace("\n", " ") + ("..." if len(content) > 30 else "")
        self.preview_lbl = QLabel(preview_text)
        
        layout.addWidget(self.idx_lbl)
        layout.addWidget(self.preview_lbl, 1)
        layout.addWidget(self.score_lbl)
        
        self.update_style()

    def update_colors(self):
        if self.is_ignored:
            r, g, b = 156, 163, 175
        elif self.ai_rate < 30:
            r, g, b = 16, 185, 129
        elif self.ai_rate < 60:
            r, g, b = 245, 158, 11
        else:
            r, g, b = 239, 68, 68
            
        self.accent_color = QColor(r, g, b).name()
        self.accent_bg = f"rgba({r}, {g}, {b}, 0.15)"
        
        if self.is_ignored:
            self.verdict = "忽略"
        elif self.ai_rate < 30:
            self.verdict = "人类"
        elif self.ai_rate < 60:
            self.verdict = "混合"
        else:
            self.verdict = "AI"

    def update_style(self):
        bg = Theme.get('bg_card')
        bd = Theme.get('border')
        hover_bg = QColor(bg).lighter(104).name()
        
        self.setStyleSheet(f"DetailedHeatmapRow {{ background-color: {bg}; border: 1px solid {bd}; border-radius: 12px; }} DetailedHeatmapRow:hover {{ background-color: {hover_bg}; }}")
        self.idx_lbl.setStyleSheet(f"color: {Theme.get('text_sub')}; font-weight: bold; font-family: 'Segoe UI';")
        self.preview_lbl.setStyleSheet(f"color: {Theme.get('text_main')};")
        self.score_lbl.setStyleSheet(f"background-color: {self.accent_bg}; color: {self.accent_color}; border-radius: 12px; padding: 4px 10px; font-weight: bold; border: none; font-family: 'Microsoft YaHei';")

    def mousePressEvent(self, event):
        self.clicked.emit(self.index)

class DetailedHeatmapWindow(QDialog):
    request_scroll = Signal(int)

    def __init__(self, paragraphs, parent=None):
        super().__init__(parent)
        self.setWindowTitle("全景 AI 检测视图") 
        self.resize(550, 700)
        self.paragraphs = paragraphs
        
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
        self.setWindowOpacity(0.0)
        
        self.anim = QPropertyAnimation(self, b"windowOpacity")
        self.anim.setDuration(300)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        
        self.rows = []
        self.init_ui()
        self.update_theme()

    def showEvent(self, e):
        super().showEvent(e)
        self.anim.start()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        self.header = QLabel("🔍  全景 AI 检测视图") 
        self.header.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        layout.addWidget(self.header)
        
        filter_layout = QHBoxLayout()
        self.chks = [
            QCheckBox("人类文本 (<30%)"),
            QCheckBox("疑似混写 (30-60%)"),
            QCheckBox("疑似生成 (>60%)")
        ]
        
        for c in self.chks:
            c.setChecked(True)
            c.setCursor(Qt.PointingHandCursor)
            c.stateChanged.connect(self.apply_filter)
            filter_layout.addWidget(c)
            
        filter_layout.addStretch()
        layout.addLayout(filter_layout)
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        
        self.container = QWidget()
        self.list_layout = QVBoxLayout(self.container)
        self.list_layout.setAlignment(Qt.AlignTop)
        self.list_layout.setSpacing(10)
        
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)
        
        for i, p in enumerate(self.paragraphs):
            row = DetailedHeatmapRow(i, p["content"], p["ai_rate"], p.get("is_ignored", False))
            row.clicked.connect(self.request_scroll.emit)
            self.list_layout.addWidget(row)
            self.rows.append(row)

    def apply_filter(self):
        h, m, a = [c.isChecked() for c in self.chks]
        for r in self.rows:
            if r.is_ignored:
                r.hide()
                continue
            should_show = (r.ai_rate < 30 and h) or (30 <= r.ai_rate < 60 and m) or (r.ai_rate >= 60 and a)
            r.setVisible(should_show)

    def update_theme(self):
        t = Theme.COLORS['dark']
        
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(t['bg_main']))
        palette.setColor(QPalette.WindowText, QColor(t['text_main']))
        self.setPalette(palette)
        
        self.setStyleSheet(f"""
            QDialog {{ background-color: {t['bg_main']}; color: {t['text_main']}; }}
            QCheckBox {{ color: {t['text_sub']}; font-weight: bold; spacing: 8px; }}
            QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 4px; border: 1px solid {t['border']}; }}
            QCheckBox::indicator:checked {{ background-color: #3B82F6; border-color: #3B82F6; image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIzIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwb2x5bGluZSBwb2ludHM9IjIwIDYgOSAxNyA0IDEyIi8+PC9zdmc+); }}
            {Theme.SCROLLBAR_CSS}
        """)
        
        self.scroll.setStyleSheet("QScrollArea { background: transparent; border: none; } QScrollArea > QWidget > QWidget { background: transparent; }")
        
        for r in self.rows:
            r.update_style()

# ================= 🚀 开发者控制台 =================
class DeveloperConsole(QDialog):
    """底层引擎高级参数接管控制台"""
    def __init__(self, current_config, has_gpu, gpu_name, is_default_mode=False, parent=None):
        super().__init__(parent)
        self.is_default_mode = is_default_mode
        self.setWindowTitle("修改默认值" if is_default_mode else "开发者控制台")
        self.resize(500, 650)
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
        
        self.config = dict(current_config)
        self.has_gpu = has_gpu
        self.gpu_name = gpu_name
        
        self.setWindowOpacity(0.0)
        self.anim = QPropertyAnimation(self, b"windowOpacity")
        self.anim.setDuration(250)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        
        self.inputs = {}
        self.init_ui()
        self.update_theme()
        self.load_data()

    def showEvent(self, e):
        super().showEvent(e)
        self.anim.start()

    def init_ui(self):
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(30, 30, 30, 20)
        main_lay.setSpacing(25)

        # 标题区
        head_lay = QVBoxLayout()
        if not self.is_default_mode:
            title = QLabel("⚙️ 开发者控制台")
            title.setFont(QFont("Microsoft YaHei", 18, QFont.Bold))
            sub_title = QLabel("危险操作！调整不当可能导致模型输出崩溃或彻底失去准确性。")
            sub_title.setStyleSheet("color: #EF4444; font-size: 11px;")
        else:
            title = QLabel("⚙️ 修改全局默认值")
            title.setFont(QFont("Microsoft YaHei", 18, QFont.Bold))
            sub_title = QLabel("您正在修改系统的基准默认值，这会影响以后所有【恢复默认】的行为。")
            sub_title.setStyleSheet("color: #10B981; font-size: 11px;")
            
        head_lay.addWidget(title)
        head_lay.addWidget(sub_title)
        main_lay.addLayout(head_lay)

        # --- 核心区 1：硬件调度 ---
        hw_group = QFrame()
        hw_group.setObjectName("ControlGroup")
        hw_lay = QVBoxLayout(hw_group)
        hw_lay.setSpacing(15)
        
        hw_title = QLabel("🖥️ 硬件运算调度 (Hardware Execution)")
        hw_title.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        hw_lay.addWidget(hw_title)
        
        btn_lay = QHBoxLayout()
        self.btn_gpu = QPushButton(f"智能 / GPU 加速")
        self.btn_cpu = QPushButton("强制使用 CPU")
        
        for btn in [self.btn_gpu, self.btn_cpu]:
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(35)
            btn.setCheckable(True)
            btn_lay.addWidget(btn)
            
        self.btn_gpu.clicked.connect(lambda: self.switch_hw(False))
        self.btn_cpu.clicked.connect(lambda: self.switch_hw(True))
        hw_lay.addLayout(btn_lay)
        
        self.hw_warn_lbl = QLabel("")
        self.hw_warn_lbl.setWordWrap(True)
        hw_lay.addWidget(self.hw_warn_lbl)
        main_lay.addWidget(hw_group)

        # --- 核心区 2：模型推理参数 ---
        param_group = QFrame()
        param_group.setObjectName("ControlGroup")
        p_lay = QVBoxLayout(param_group)
        p_lay.setSpacing(25)
        
        p_title = QLabel("🧮 算法阈值与权重 (Algorithm Thresholds)")
        p_title.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        p_lay.addWidget(p_title)
        
        def add_number_input(key, label_text, default_val, is_float):
            row = QHBoxLayout()
            
            lbl = QLabel(label_text)
            lbl.setFixedWidth(260)
            
            input_field = QLineEdit()
            input_field.setText(str(default_val))
            input_field.setFixedWidth(100)
            input_field.setAlignment(Qt.AlignCenter)
            
            input_field.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {Theme.get('input_bg')};
                    color: {Theme.ACCENT_BLUE.name()};
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 6px;
                    padding: 6px 10px;
                    font-family: Consolas;
                    font-weight: bold;
                    font-size: 14px;
                }}
                QLineEdit:focus {{
                    border: 1px solid {Theme.ACCENT_BLUE.name()};
                }}
            """)
            
            row.addWidget(lbl)
            row.addStretch()
            row.addWidget(input_field)
            p_lay.addLayout(row)
            
            self.inputs[key] = (input_field, is_float)

        c = self.config
        add_number_input('temperature', "温度系数 (Temperature) 🌶️", c.get('temperature', 2.0), True)
        add_number_input('power_factor', "指数惩罚因子 (Power Factor) 📈", c.get('power_factor', 1.5), True)
        add_number_input('max_chunk_size', "动态切分阈值 (Max Chunk) ✂️", c.get('max_chunk_size', 700), False)
        add_number_input('min_valid_length', "极短句屏蔽字数 (Min Length) 🛡️", c.get('min_valid_length', 20), False)

        main_lay.addWidget(param_group)
        main_lay.addStretch()

        # 底部操作区
        bot_lay = QHBoxLayout()
        
        if not self.is_default_mode:
            btn_reset = GlowingButton("恢复默认", variant="secondary")
            btn_reset.setFixedWidth(100)
            btn_reset.clicked.connect(self.reset_default)
            
            btn_edit_defaults = GlowingButton("修改默认", variant="secondary")
            btn_edit_defaults.setFixedWidth(110)
            btn_edit_defaults.clicked.connect(self.open_defaults_editor)
            
            bot_lay.addWidget(btn_reset)
            bot_lay.addWidget(btn_edit_defaults)
            
        bot_lay.addStretch()
        
        btn_apply_text = "保存" if self.is_default_mode else "保存并生效"
        btn_apply_width = 100 if self.is_default_mode else 120
        
        btn_apply = GlowingButton(btn_apply_text, variant="primary")
        btn_apply.setFixedWidth(btn_apply_width)
        btn_apply.clicked.connect(self.accept)
        
        bot_lay.addWidget(btn_apply)
        main_lay.addLayout(bot_lay)

    def open_defaults_editor(self):
        from core_engine import load_factory_defaults, save_factory_defaults
        defaults = load_factory_defaults()
        dlg = DeveloperConsole(defaults, self.has_gpu, self.gpu_name, is_default_mode=True, parent=self)
        if dlg.exec() == QDialog.Accepted:
            save_factory_defaults(dlg.config)
            QMessageBox.information(self, "成功", "全局默认值已成功修改！\n点击【恢复默认】即可载入您的新配置。")

    def switch_hw(self, force_cpu):
        if not self.has_gpu and not force_cpu:
            self.hw_warn_lbl.setText("❌ 系统未检测到受支持的 GPU 或驱动，已永久锁定为 CPU 运算模式。")
            self.hw_warn_lbl.setStyleSheet("color: #EF4444; font-weight: bold; margin-top: 5px;")
            self.btn_gpu.setChecked(False)
            self.btn_cpu.setChecked(True)
            self.config['force_cpu'] = True
            return
            
        self.config['force_cpu'] = force_cpu
        self.btn_cpu.setChecked(force_cpu)
        self.btn_gpu.setChecked(not force_cpu)
        
        if force_cpu:
            self.hw_warn_lbl.setText("⚠️ 强制使用 CPU 会导致推理极其缓慢 (10倍以上耗时)，仅供显存耗尽时应急调试使用。")
            self.hw_warn_lbl.setStyleSheet("color: #F59E0B; font-weight: bold; margin-top: 5px;")
        else:
            self.hw_warn_lbl.setText(f"✅ 当前已交由硬件加速接管：{self.gpu_name}")
            self.hw_warn_lbl.setStyleSheet("color: #10B981; font-weight: bold; margin-top: 5px;")

    def load_data(self):
        c = self.config
        self.inputs['temperature'][0].setText(str(c.get('temperature', 2.0)))
        self.inputs['power_factor'][0].setText(str(c.get('power_factor', 1.5)))
        self.inputs['max_chunk_size'][0].setText(str(c.get('max_chunk_size', 700)))
        self.inputs['min_valid_length'][0].setText(str(c.get('min_valid_length', 20)))
        self.switch_hw(c.get('force_cpu', False))

    def reset_default(self):
        from core_engine import load_factory_defaults
        self.config = load_factory_defaults()
        self.load_data()

    def accept(self):
        for key, (field, is_float) in self.inputs.items():
            txt = field.text().strip()
            try:
                val = float(txt) if is_float else int(float(txt))
                self.config[key] = val
            except ValueError:
                pass
        super().accept()

    def update_theme(self):
        t = Theme.COLORS['dark']
        
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(t['bg_main']))
        palette.setColor(QPalette.WindowText, QColor(t['text_main']))
        self.setPalette(palette)
        
        self.setStyleSheet(f"""
            QDialog {{ background-color: {t['bg_main']}; color: {t['text_main']}; }}
            QLabel {{ color: {t['text_main']}; }}
            #ControlGroup {{ 
                background-color: {t['bg_card']}; 
                border: 1px solid {t['border']}; 
                border-radius: 12px; 
            }}
            QPushButton {{
                background-color: rgba(255, 255, 255, 0.05); color: {t['text_main']}; 
                border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; font-weight: bold;
            }}
            QPushButton:checked {{
                background-color: {Theme.ACCENT_BLUE.name()}; color: white; border: none;
            }}
            {Theme.SCROLLBAR_CSS}
        """)

# ================= 🚀 历史记录抽屉 UI =================
class HistoryRow(QFrame):
    """历史记录列表单行组件"""
    restore_clicked = Signal(dict)
    
    def __init__(self, record, parent=None):
        super().__init__(parent)
        self.record = record
        self.setFixedHeight(70)
        self.setCursor(Qt.PointingHandCursor)
        
        timestamp = record.get("timestamp", "未知时间")
        ai_rate = record.get("total_ai_rate", 0)
        
        # 获取纯文本预览
        raw_text = record.get("original_text", "")
        text_preview = raw_text[:40].replace("\n", " ") + ("..." if len(raw_text) > 40 else "")
        
        self.update_colors(ai_rate)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(15)
        
        # 左侧：时间和 Tokens
        time_lay = QVBoxLayout()
        time_lbl = QLabel(timestamp)
        time_lbl.setStyleSheet(f"color: {Theme.get('text_main')}; font-weight: bold; font-family: 'Segoe UI';")
        
        token_lbl = QLabel(f"Tokens: {record.get('total_tokens', 0)}")
        token_lbl.setStyleSheet(f"color: {Theme.get('text_sub')}; font-size: 10px;")
        
        time_lay.addWidget(time_lbl)
        time_lay.addWidget(token_lbl)
        
        # 中间：预览文本
        preview_lbl = QLabel(text_preview)
        preview_lbl.setStyleSheet(f"color: {Theme.get('text_sub')};")
        preview_lbl.setWordWrap(True)
        
        # 右侧：得分 Badge
        score_lbl = QLabel(f"{int(ai_rate)}%")
        score_lbl.setAlignment(Qt.AlignCenter)
        score_lbl.setFixedSize(45, 24)
        score_lbl.setStyleSheet(f"background-color: {self.accent_bg}; color: {self.accent_color}; border-radius: 12px; font-weight: bold;")
        
        # 载入按钮
        btn_restore = GlowingButton("载入", variant="primary")
        btn_restore.setFixedSize(60, 28)
        btn_restore.clicked.connect(lambda: self.restore_clicked.emit(self.record))
        
        layout.addLayout(time_lay)
        layout.addWidget(preview_lbl, 1)
        layout.addWidget(score_lbl)
        layout.addWidget(btn_restore)
        
        self.update_style()

    def update_colors(self, ai_rate):
        if ai_rate < 30:
            r, g, b = 16, 185, 129
        elif ai_rate < 60:
            r, g, b = 245, 158, 11
        else:
            r, g, b = 239, 68, 68
            
        self.accent_color = QColor(r, g, b).name()
        self.accent_bg = f"rgba({r}, {g}, {b}, 0.15)"

    def update_style(self):
        bg = Theme.get('bg_card')
        bd = Theme.get('border')
        hover_bg = QColor(bg).lighter(104).name()
        
        self.setStyleSheet(f"HistoryRow {{ background-color: {bg}; border: 1px solid {bd}; border-radius: 12px; }} HistoryRow:hover {{ background-color: {hover_bg}; }}")


class HistoryWindow(QDialog):
    """历史记录模态窗口"""
    request_restore = Signal(dict)
    request_clear = Signal()
    
    def __init__(self, history_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("本地检测历史")
        self.resize(600, 500)
        self.history_data = history_data
        
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
        self.setWindowOpacity(0.0)
        
        self.anim = QPropertyAnimation(self, b"windowOpacity")
        self.anim.setDuration(250)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        
        self.init_ui()
        self.update_theme()

    def showEvent(self, e):
        super().showEvent(e)
        self.anim.start()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 头部
        header_lay = QHBoxLayout()
        title = QLabel("🕒 历史检测记录 (最近10次)")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        
        btn_clear = GlowingButton("🗑️ 清空所有记录", variant="danger")
        btn_clear.setFixedWidth(140)
        btn_clear.clicked.connect(self.request_clear.emit)
        
        header_lay.addWidget(title)
        header_lay.addStretch()
        header_lay.addWidget(btn_clear)
        layout.addLayout(header_lay)
        
        # 滚动列表
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        
        self.container = QWidget()
        self.list_layout = QVBoxLayout(self.container)
        self.list_layout.setAlignment(Qt.AlignTop)
        self.list_layout.setSpacing(10)
        
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)
        
        if not self.history_data:
            empty_lbl = QLabel("暂无任何本地检测记录。")
            empty_lbl.setAlignment(Qt.AlignCenter)
            empty_lbl.setStyleSheet("color: #9CA3AF; font-size: 13px; margin-top: 50px;")
            self.list_layout.addWidget(empty_lbl)
        else:
            for record in self.history_data:
                row = HistoryRow(record)
                row.restore_clicked.connect(self.handle_restore)
                self.list_layout.addWidget(row)

    def handle_restore(self, record):
        self.request_restore.emit(record)
        self.accept()

    def clear_list(self):
        """动态清空列表 UI 并显示占位符"""
        while self.list_layout.count() > 0:
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        empty_lbl = QLabel("暂无任何本地检测记录。")
        empty_lbl.setAlignment(Qt.AlignCenter)
        empty_lbl.setStyleSheet("color: #9CA3AF; font-size: 13px; margin-top: 50px;")
        self.list_layout.addWidget(empty_lbl)

    def update_theme(self):
        t = Theme.COLORS['dark']
        
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(t['bg_main']))
        palette.setColor(QPalette.WindowText, QColor(t['text_main']))
        self.setPalette(palette)
        
        self.setStyleSheet(f"""
            QDialog {{ background-color: {t['bg_main']}; color: {t['text_main']}; }}
            {Theme.SCROLLBAR_CSS}
        """)
        self.scroll.setStyleSheet("QScrollArea { background: transparent; border: none; } QScrollArea > QWidget > QWidget { background: transparent; }")