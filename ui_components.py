import math
import html
import os

from PySide6.QtWidgets import (
    QWidget, QPushButton, QLabel, QFrame, QTextEdit, QHBoxLayout, QVBoxLayout, QSizePolicy, QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QScrollArea, QDialog, QCheckBox
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
    """管理纯深色主题的调色板字典类（现代 SaaS 柔和暗黑系）"""
    CURRENT_MODE = 'dark' # 强制锁定深色
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

    @classmethod
    def get(cls, key):
        # 兼容性方法：从 dark 字典中安全获取颜色
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

    def get_base_color(self):
        if self.variant == "primary": return Theme.ACCENT_BLUE
        elif self.variant == "danger": return Theme.ACCENT_RED
        else: return QColor(255, 255, 255, 20)

    @Property(float)
    def hover_progress(self): return self._hover_progress
    @hover_progress.setter
    def hover_progress(self, val):
        self._hover_progress = val
        self.update()

    @Property(float)
    def press_progress(self): return self._press_progress
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
        w, h = self.width(), self.height()
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
            p.drawRoundedRect(1, 1, w-2, h-2, radius-1, radius-1)

        p.setPen(text_c)
        offset_y = 1 if 0.0 < self._press_progress < 0.3 else 0
        p.drawText(QRectF(0, offset_y, w, h), Qt.AlignCenter, self.text())

class ThreeDButton(GlowingButton): pass

class ModernProgressBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(4) 
        self._value = 0
    def setValue(self, v): self._value = v; self.update()
    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        bg_c = QColor(255, 255, 255, 15)
        p.setBrush(bg_c); p.setPen(Qt.NoPen); p.drawRoundedRect(rect, 2, 2)
        if self._value <= 0: return
        w = rect.width() * (self._value / 100.0)
        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0, Theme.ACCENT_BLUE); grad.setColorAt(1, QColor("#00F0FF"))
        p.setBrush(grad); p.drawRoundedRect(QRectF(0, 0, w, rect.height()), 2, 2)

# ---------------------- 复杂可视化组件 ----------------------

class AIGCGaugeWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(160, 140)
        self._value = 0
        self.animation = QPropertyAnimation(self, b"value")
        self.animation.setDuration(800)
        self.animation.setEasingCurve(QEasingCurve.OutCubic) 

    @Property(float)
    def value(self): return self._value
    @value.setter
    def value(self, v): self._value = v; self.update()

    def setValue(self, v):
        self.animation.stop()
        self.animation.setStartValue(self._value)
        self.animation.setEndValue(v)
        self.animation.start()

    def get_color(self, val):
        if val < 30: return Theme.ACCENT_GREEN
        if val < 60: return Theme.ACCENT_YELLOW
        return Theme.ACCENT_RED

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        logical_w, logical_h = 280.0, 190.0 
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
        p.setBrush(glow); p.setPen(Qt.NoPen); p.drawEllipse(-140, -140, 280, 280)

        if self._value < 30: verdict = "人类文本"
        elif self._value < 60: verdict = "疑似混写"
        else: verdict = "疑似AI"

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
        p.setBrush(QBrush(pointer_c)); p.setPen(Qt.NoPen)
        p.drawPolygon(QPolygonF([QPointF(-4, 0), QPointF(4, 0), QPointF(0, -96)]))
        p.setBrush(QBrush(QColor(Theme.get('bg_card')))) 
        p.setPen(QPen(pointer_c, 3))
        p.drawEllipse(-6, -6, 12, 12)
        p.restore()

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
    def anim_progress(self): return self._anim_progress
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
        if needs_update: self.update()

    def set_data(self, counts):
        self.counts = counts
        self.anim.stop(); self.anim.setStartValue(0.0); self.anim.setEndValue(1.0); self.anim.start()

    def _get_logical_params(self):
        logical_w, logical_h = 320.0, 190.0
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
        
        center_x, center_y = 220.0, 105.0 
        base_radius = 80.0 
        inner_radius = base_radius * 0.65 
        
        dx = lx - center_x
        dy = ly - center_y
        dist = math.sqrt(dx*dx + dy*dy)
        
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
        for i in range(3): self.target_offsets[i] = 0.0

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
        
        center_x, center_y = 220.0, 105.0
        base_radius = 80.0 
        
        total = sum(self.counts)
        if total == 0:
            p.setPen(QPen(QColor(255, 255, 255, 20), 16))
            p.drawArc(QRectF(center_x-base_radius, center_y-base_radius, base_radius*2, base_radius*2), 0, 360*16)
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
            c = c.lighter(lightness); c.setAlpha(255) 
            
            p.setBrush(c); p.setPen(Qt.NoPen)
            rect = QRectF(center_x - r, center_y - r, r*2, r*2)
            p.drawPie(rect, start_angle, int(span_angle))
            
            start_angle += int(-segment_fraction * 360 * 16)
            accumulated_fraction += segment_fraction

        inner_radius = base_radius * 0.65
        p.setBrush(QColor(Theme.get('bg_card'))) 
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(center_x, center_y), inner_radius, inner_radius)

        p.setOpacity(self._anim_progress)
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
            
            p.setBrush(c); p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(box_x, legend_y + i*32, 12, 12), 4, 4)  
            
            text_c = QColor(Theme.get('text_main'))
            if i == self.hovered_idx:
                p.setFont(QFont("Microsoft YaHei", 11, QFont.Bold)); text_c = c.lighter(110)
            else:
                p.setFont(QFont("Microsoft YaHei", 11)); text_c.setAlpha(150) 
                
            p.setPen(text_c)
            p.drawText(QRectF(box_x + 22, legend_y + i*32 - 10, 150, 30), Qt.AlignLeft | Qt.AlignVCenter | Qt.TextDontClip, f"{label}: {self.counts[i]}")


# ================= Token 计数器动画组件 =================
class TokenCounterWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(120, 140)
        self._current_value = 0
        self.anim = QPropertyAnimation(self, b"anim_val", self)
        self.anim.setDuration(1200)
        self.anim.setEasingCurve(QEasingCurve.OutQuart)

    @Property(int)
    def anim_val(self): return self._current_value
    @anim_val.setter
    def anim_val(self, v):
        self._current_value = v
        self.update()

    def set_data(self, value):
        self.anim.stop()
        self.anim.setStartValue(0)
        self.anim.setEndValue(value)
        self.anim.start()

    def update_style(self):
        self.update()
        
    def _get_logical_params(self):
        logical_w, logical_h = 160.0, 190.0
        pad = 5
        avail_w = max(1, self.width() - pad * 2)
        avail_h = max(1, self.height() - pad * 2)
        scale = min(avail_w / logical_w, avail_h / logical_h)
        scale = max(0.7, scale) 
        offset_x = pad + (avail_w - logical_w * scale) / 2.0
        offset_y = pad + (avail_h - logical_h * scale) / 2.0
        return logical_w, logical_h, scale, offset_x, offset_y

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        logical_w, logical_h, scale, offset_x, offset_y = self._get_logical_params()
        p.translate(offset_x, offset_y)
        p.scale(scale, scale)

        p.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        p.setPen(QColor(Theme.get('text_sub')))
        p.drawText(QRectF(0, 30, logical_w, 30), Qt.AlignCenter, "⚡  算力消耗 (Tokens)")

        font = QFont("Consolas", 36, QFont.Bold)
        font.setStyleHint(QFont.Monospace) 
        p.setFont(font)
        p.setPen(Theme.ACCENT_BLUE)
        p.drawText(QRectF(0, 80, logical_w, 60), Qt.AlignCenter, f"{self._current_value:,}")


# ================= 高级无界仪表盘排版容器 =================
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

# ================= 高级悬浮太空舱式热力条 =================
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
    def anim_progress(self): return self._anim_progress
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

        if needs_update: self.update()

    def set_data(self, paragraphs):
        self.data = []
        total_len = sum(max(len(p['content']), 10) for p in paragraphs) if paragraphs else 1
        
        for i, p in enumerate(paragraphs):
            score = p['ai_rate']
            is_ignored = p.get('is_ignored', False)
            length = max(len(p['content']), 10)
            
            if is_ignored: c = Theme.ACCENT_GRAY
            elif score < 30: c = Theme.ACCENT_GREEN
            elif score < 60: c = Theme.ACCENT_YELLOW
            else: c = Theme.ACCENT_RED
            
            self.data.append({
                "index": i,
                "color": c,
                "weight": length / total_len
            })
        
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
        if not self.data: return
        y = event.position().y()
        h = self.height()
        
        current_y = 0.0
        new_hover = -1
        for i, item in enumerate(self.data):
            block_h = max(3.0, item['weight'] * h)
            if current_y <= y <= current_y + block_h:
                new_hover = i
                break
            current_y += block_h
            
        if new_hover != self.hovered_idx:
            self.hovered_idx = new_hover

    def mousePressEvent(self, event):
        if self.hovered_idx != -1 and self.hovered_idx < len(self.data):
            self.clicked_section.emit(self.data[self.hovered_idx]['index'])

    def mouseDoubleClickEvent(self, event):
        if self.data: self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)

    def paintEvent(self, event):
        if not self.data: return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        w, h = self.width(), self.height()
        visible_y_start = h * (1.0 - self._anim_progress)
        p.setClipRect(0, int(visible_y_start), int(w), int(h))
        
        center_x = w / 2.0
        
        track_w = self.hover_width + 4
        track_c = QColor(0, 0, 0, 80)
        p.setPen(Qt.NoPen)
        p.setBrush(track_c)
        p.drawRoundedRect(QRectF(center_x - track_w/2, 0, track_w, h), track_w/2, track_w/2)

        current_y = 0.0
        for i, item in enumerate(self.data):
            block_h = max(3.0, item['weight'] * h)
            draw_h = max(2.0, block_h - 1.5) 
            current_w = self.hover_width + self.block_offsets[i]
            
            c = QColor(item['color'])
            if i == self.hovered_idx:
                c = c.lighter(120)
            else:
                if self.hovered_idx != -1: c.setAlpha(100) 
                else: c.setAlpha(230)

            p.setBrush(c)
            rect = QRectF(center_x - current_w/2, current_y + 0.75, current_w, draw_h)
            p.drawRoundedRect(rect, current_w/2, current_w/2)
            
            current_y += block_h


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
    def glow_strength(self): return self._glow_strength
    @glow_strength.setter
    def glow_strength(self, v):
        self._glow_strength = v
        self.update()

    def insertFromMimeData(self, source):
        if source.hasText(): 
            text = source.text()
            styled_html = f"<div style='line-height: 1.6;'>{html.escape(text).replace(chr(10), '<br>')}</div>"
            self.insertHtml(styled_html)
        else: 
            super().insertFromMimeData(source)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.accept()
            self.anim_glow.stop(); self.anim_glow.setEndValue(1.0); self.anim_glow.start()
        else: e.ignore()

    def dragLeaveEvent(self, e):
        self.anim_glow.stop(); self.anim_glow.setEndValue(0.0); self.anim_glow.start()
        super().dragLeaveEvent(e)

    def dropEvent(self, e):
        self.anim_glow.stop(); self.anim_glow.setEndValue(0.0); self.anim_glow.start()
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            ext = os.path.splitext(path)[1].lower()
            if ext in ['.txt', '.docx', '.pdf']:
                self.file_dropped.emit(path) 
                e.acceptProposedAction() 
            else: e.ignore()
        else: e.ignore()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._glow_strength > 0.01:
            p = QPainter(self.viewport())
            p.setRenderHint(QPainter.Antialiasing)
            glow_c = QColor(Theme.ACCENT_BLUE)
            glow_c.setAlpha(int(60 * self._glow_strength)) 
            path = QPainterPath()
            path.addRoundedRect(self.viewport().rect().adjusted(2,2,-2,-2), 12, 12)
            p.setPen(QPen(glow_c, 6 * self._glow_strength))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
            
    def highlight_paragraph(self, content):
        if not content: return
        cursor = self.document().find(content[:50]) 
        if not cursor.isNull():
            start_pos = cursor.selectionStart()
            cursor.setPosition(start_pos)
            cursor.setPosition(start_pos + len(content), QTextCursor.KeepAnchor)
            self.setTextCursor(cursor)
            self.ensureCursorVisible()
            self.setFocus()

class ResultBlock(QWidget):
    request_scroll = Signal() 
    request_highlight = Signal(str)
    expanded = Signal(int)

    def __init__(self, index, content, ai_rate, is_ignored=False, parent=None):
        super().__init__(parent)
        self.index = index
        self.content = content
        self.ai_rate = ai_rate
        self.is_ignored = is_ignored
        self.is_expanded = False 
        
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor) 
        
        self.entry_effect = QGraphicsOpacityEffect(self)
        self.entry_effect.setOpacity(0.0)
        self.setGraphicsEffect(self.entry_effect)
        
        self.entry_anim = QPropertyAnimation(self.entry_effect, b"opacity")
        self.entry_anim.setDuration(600)
        self.entry_anim.setStartValue(0.0)
        self.entry_anim.setEndValue(1.0)
        self.entry_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.entry_anim.finished.connect(self._remove_opacity_effect)
        
        delay = min(self.index * 50, 800)
        QTimer.singleShot(delay, self.entry_anim.start)

        self.update_colors()

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.header_frame = QFrame()
        self.header_layout = QHBoxLayout(self.header_frame)
        self.header_layout.setContentsMargins(15, 10, 15, 10)

        self.idx_lbl = QLabel(f"#{self.index+1}")
        self.risk_lbl = QLabel(f"{int(self.ai_rate)}% {self.verdict}")
        self.risk_lbl.setAlignment(Qt.AlignCenter)
        
        preview_text = self.content[:30].replace("\n", " ") + ("..." if len(self.content) > 30 else "")
        self.preview_lbl = QLabel(preview_text)
        self.preview_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.arrow_lbl = QLabel("▼")

        self.header_layout.addWidget(self.idx_lbl)
        self.header_layout.addSpacing(5)
        self.header_layout.addWidget(self.risk_lbl)
        self.header_layout.addSpacing(10)
        self.header_layout.addWidget(self.preview_lbl)
        self.header_layout.addWidget(self.arrow_lbl)

        self.content_frame = QFrame()
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(20, 15, 20, 20)
        self.content_layout.setAlignment(Qt.AlignTop) 
        
        styled_text = f"<div style='line-height: 1.8;'>{html.escape(self.content)}</div>"
        self.full_text_lbl = QLabel(styled_text)
        self.full_text_lbl.setWordWrap(True)
        self.full_text_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        
        self.content_layout.addWidget(self.full_text_lbl)
        
        self.anim_wrapper = QScrollArea()
        self.anim_wrapper.setFrameShape(QFrame.NoFrame)
        self.anim_wrapper.setWidgetResizable(True)
        self.anim_wrapper.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.anim_wrapper.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.anim_wrapper.setStyleSheet("background: transparent; border: none;")
        self.anim_wrapper.setWidget(self.content_frame)
        
        self.main_layout.addWidget(self.header_frame)
        self.main_layout.addWidget(self.anim_wrapper) 
        
        self.anim_wrapper.hide() 
        self.anim_wrapper.setMaximumHeight(0)
        
        self.anim = QPropertyAnimation(self.anim_wrapper, b"maximumHeight")
        self.anim.setDuration(350)
        self.anim.setEasingCurve(QEasingCurve.OutCubic) 
        self.anim.finished.connect(self._on_anim_finished)

        self.update_style()

    def _remove_opacity_effect(self):
        self.setGraphicsEffect(None)
        self.update()

    def update_colors(self):
        if self.is_ignored:
            self.accent_color = Theme.ACCENT_GRAY.name()
            self.accent_bg = f"rgba({Theme.ACCENT_GRAY.red()}, {Theme.ACCENT_GRAY.green()}, {Theme.ACCENT_GRAY.blue()}, 0.15)"
            self.verdict = "忽略"
        elif self.ai_rate < 30: 
            self.accent_color = Theme.ACCENT_GREEN.name()
            self.accent_bg = f"rgba({Theme.ACCENT_GREEN.red()}, {Theme.ACCENT_GREEN.green()}, {Theme.ACCENT_GREEN.blue()}, 0.15)"
            self.verdict = "人类创作"
        elif self.ai_rate < 60: 
            self.accent_color = Theme.ACCENT_YELLOW.name()
            self.accent_bg = f"rgba({Theme.ACCENT_YELLOW.red()}, {Theme.ACCENT_YELLOW.green()}, {Theme.ACCENT_YELLOW.blue()}, 0.15)"
            self.verdict = "疑似混写"
        else: 
            self.accent_color = Theme.ACCENT_RED.name()
            self.accent_bg = f"rgba({Theme.ACCENT_RED.red()}, {Theme.ACCENT_RED.green()}, {Theme.ACCENT_RED.blue()}, 0.15)"
            self.verdict = "疑似生成"

    def update_style(self):
        self.update_colors()
        
        self.idx_lbl.setStyleSheet(f"color: {Theme.get('text_sub')}; font-weight: bold; font-size: 10pt; font-family: 'Segoe UI';")
        self.risk_lbl.setStyleSheet(f"""
            background-color: {self.accent_bg};
            color: {self.accent_color};
            border-radius: 12px;
            padding: 4px 10px;
            font-weight: 900;
            font-size: 10pt;
            font-family: 'Microsoft YaHei';
        """)
        
        self.preview_lbl.setStyleSheet(f"color: {Theme.get('text_sub')}; margin-left: 5px;")
        self.arrow_lbl.setStyleSheet(f"color: {Theme.get('text_sub')};")
        self.full_text_lbl.setStyleSheet(f"color: {Theme.get('text_main')}; font-size: 10.5pt;")
        
        is_collapsing = (not self.is_expanded) and (self.anim.state() == QPropertyAnimation.Running)
        use_expanded_style = self.is_expanded or is_collapsing

        border_c = Theme.get('border')
        card_bg = Theme.get('bg_card')
        input_bg = Theme.get('input_bg')
        
        hover_bg = QColor(card_bg).lighter(104).name()
        border_hover = "rgba(255, 255, 255, 0.1)"

        if use_expanded_style:
            self.header_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {hover_bg};
                    border: 1px solid {border_c};
                    border-bottom: none;
                    border-top-left-radius: 12px;
                    border-top-right-radius: 12px;
                }}
            """)
            self.content_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {input_bg}; 
                    border: 1px solid {border_c};
                    border-top: none;
                    border-bottom-left-radius: 12px; 
                    border-bottom-right-radius: 12px;
                }}
            """)
        else:
            self.header_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {card_bg}; 
                    border: 1px solid {border_c};
                    border-radius: 12px;
                }}
                QFrame:hover {{
                    background-color: {hover_bg};
                    border: 1px solid {border_hover};
                }}
            """)
        
        self.update() 

    def get_target_height(self):
        w = self.width()
        self.content_frame.setFixedWidth(w)
        self.content_frame.layout().activate() 
        self.content_frame.adjustSize() 
        target_h = self.content_frame.height()
        self.content_frame.setMinimumWidth(0)
        self.content_frame.setMaximumWidth(16777215)
        return target_h

    def _on_anim_finished(self):
        if not self.is_expanded:
            self.anim_wrapper.hide()
            self.update_style() 
        else:
            target_h = self.get_target_height()
            self.anim_wrapper.setMinimumHeight(target_h)
            self.anim_wrapper.setMaximumHeight(target_h)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.is_expanded and self.anim.state() != QPropertyAnimation.Running:
            target_h = self.get_target_height()
            self.anim_wrapper.setMinimumHeight(target_h)
            self.anim_wrapper.setMaximumHeight(target_h)

    def mousePressEvent(self, event):
        self.toggle_expand()
        self.request_highlight.emit(self.content)
        super().mousePressEvent(event)

    def toggle_expand(self):
        if self.anim.state() == QPropertyAnimation.Running:
            return 

        self.is_expanded = not self.is_expanded
        
        if self.is_expanded:
            self.anim_wrapper.setMinimumHeight(0) 
            self.anim_wrapper.setMaximumHeight(0) 
            self.anim_wrapper.show()
            self.preview_lbl.hide() 
            self.arrow_lbl.setText("▲")
            
            target_h = self.get_target_height()
            
            self.anim.stop()
            self.anim.setStartValue(0)
            self.anim.setEndValue(target_h)
            self.anim.start()
            
            self.expanded.emit(self.index)
        else:
            self.preview_lbl.show()
            self.arrow_lbl.setText("▼")
            
            self.anim_wrapper.setMinimumHeight(0)
            
            self.anim.stop()
            self.anim.setStartValue(self.anim_wrapper.height())
            self.anim.setEndValue(0)
            self.anim.start()
        
        self.update_style()
        self.request_scroll.emit()

    def set_expanded(self, expanded):
        if self.is_expanded != expanded:
            self.toggle_expand()

# ================= 全景热力指纹弹窗及其子组件 =================
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

        if self.is_ignored:
            self.accent_color = Theme.ACCENT_GRAY.name()
            self.accent_bg = f"rgba({Theme.ACCENT_GRAY.red()}, {Theme.ACCENT_GRAY.green()}, {Theme.ACCENT_GRAY.blue()}, 0.15)"
            self.verdict = "忽略"
        elif self.ai_rate < 30:
            self.accent_color = Theme.ACCENT_GREEN.name()
            self.accent_bg = f"rgba({Theme.ACCENT_GREEN.red()}, {Theme.ACCENT_GREEN.green()}, {Theme.ACCENT_GREEN.blue()}, 0.15)"
            self.verdict = "人类文本"
        elif self.ai_rate < 60:
            self.accent_color = Theme.ACCENT_YELLOW.name()
            self.accent_bg = f"rgba({Theme.ACCENT_YELLOW.red()}, {Theme.ACCENT_YELLOW.green()}, {Theme.ACCENT_YELLOW.blue()}, 0.15)"
            self.verdict = "疑似混写"
        else:
            self.accent_color = Theme.ACCENT_RED.name()
            self.accent_bg = f"rgba({Theme.ACCENT_RED.red()}, {Theme.ACCENT_RED.green()}, {Theme.ACCENT_RED.blue()}, 0.15)"
            self.verdict = "疑似生成"

        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 5, 15, 5)

        self.idx_lbl = QLabel(f"#{self.index+1}")
        self.idx_lbl.setFixedWidth(40)

        preview_text = self.content[:30].replace("\n", " ") + ("..." if len(self.content) > 30 else "")
        self.preview_lbl = QLabel(preview_text)

        self.score_lbl = QLabel(f"{int(self.ai_rate)}% {self.verdict}" if not self.is_ignored else self.verdict)
        self.score_lbl.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.idx_lbl)
        layout.addWidget(self.preview_lbl, 1)
        layout.addWidget(self.score_lbl)

        self.update_style()

    def update_style(self):
        bg_color = Theme.get('bg_card')
        border_color = Theme.get('border')
        hover_bg = QColor(bg_color).lighter(104).name()
        
        self.setStyleSheet(f"""
            DetailedHeatmapRow {{
                background-color: {bg_color}; 
                border: 1px solid {border_color};
                border-radius: 12px;
            }}
            DetailedHeatmapRow:hover {{
                background-color: {hover_bg};
            }}
        """)
        self.idx_lbl.setStyleSheet(f"color: {Theme.get('text_sub')}; font-family: 'Segoe UI'; font-weight: bold; font-size: 10pt;")
        self.preview_lbl.setStyleSheet(f"color: {Theme.get('text_main')};")
        
        self.score_lbl.setStyleSheet(f"""
            background-color: {self.accent_bg};
            color: {self.accent_color};
            border-radius: 12px;
            padding: 4px 10px;
            font-weight: bold;
            font-size: 10pt;
            font-family: 'Microsoft YaHei';
            border: none;
        """)

    def mousePressEvent(self, event):
        self.clicked.emit(self.index) 
        super().mousePressEvent(event)


class DetailedHeatmapWindow(QDialog):
    request_scroll = Signal(int)

    def __init__(self, paragraphs, parent=None):
        super().__init__(parent)
        self.setWindowTitle("全景热力指纹分析")
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
        
    def showEvent(self, event):
        super().showEvent(event)
        self.anim.start() 

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        self.header_lbl = QLabel("🔍  全景段落过滤视图")
        self.header_lbl.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        layout.addWidget(self.header_lbl)

        filter_layout = QHBoxLayout()
        self.chk_human = QCheckBox("人类文本 (<30%)")
        self.chk_human.setChecked(True)
        self.chk_mixed = QCheckBox("疑似混写 (30-60%)")
        self.chk_mixed.setChecked(True)
        self.chk_ai = QCheckBox("疑似生成 (>60%)")
        self.chk_ai.setChecked(True)

        for chk in [self.chk_human, self.chk_mixed, self.chk_ai]:
            chk.setCursor(Qt.PointingHandCursor)
            chk.stateChanged.connect(self.apply_filter)
            filter_layout.addWidget(chk)
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
        show_human = self.chk_human.isChecked()
        show_mixed = self.chk_mixed.isChecked()
        show_ai = self.chk_ai.isChecked()

        for row in self.rows:
            if row.is_ignored:
                row.hide()
                continue

            if row.ai_rate < 30 and show_human:
                row.show()
            elif 30 <= row.ai_rate < 60 and show_mixed:
                row.show()
            elif row.ai_rate >= 60 and show_ai:
                row.show()
            else:
                row.hide()

    def update_theme(self):
        t = Theme.COLORS['dark']
        
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(t['bg_main']))
        palette.setColor(QPalette.WindowText, QColor(t['text_main']))
        self.setPalette(palette)
        
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
            QDialog {{ background-color: {t['bg_main']}; color: {t['text_main']}; }}
            QCheckBox {{ color: {t['text_sub']}; font-weight: bold; spacing: 8px; }}
            QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 4px; border: 1px solid {t['border']}; }}
            QCheckBox::indicator:checked {{ background-color: #3B82F6; border-color: #3B82F6; image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIzIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwb2x5bGluZSBwb2ludHM9IjIwIDYgOSAxNyA0IDEyIi8+PC9zdmc+); }}
            {scrollbar_css}
        """)
        self.header_lbl.setStyleSheet(f"color: {t['text_main']};")
        self.scroll.setStyleSheet("QScrollArea { background: transparent; border: none; } QScrollArea > QWidget > QWidget { background: transparent; }")
        for row in self.rows:
            row.update_style()