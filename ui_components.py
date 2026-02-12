import math
import html
import os
from PySide6.QtWidgets import (
    QWidget, QPushButton, QLabel, QFrame, QTextEdit, QHBoxLayout, QVBoxLayout, QSizePolicy, QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QScrollArea
)
from PySide6.QtCore import (
    Qt, Property, QPropertyAnimation, QEasingCurve, QRectF, QPointF, Signal, QSize, QTimer
)
from PySide6.QtGui import (
    QColor, QPainter, QFont, QPen, QBrush, QLinearGradient, QRadialGradient,
    QPainterPath, QTransform, QFontMetrics, QTextCursor, QPolygonF, QPixmap
)

# ---------------------- 核心配色管理 ----------------------
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
        effect.setColor(Theme.COLORS[Theme.CURRENT_MODE]['shadow'])
        return effect

# ---------------------- 基础 UI 组件 ----------------------

class ThemeSwitch(QWidget):
    toggled = Signal(bool) 

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(48, 24)
        self.setCursor(Qt.PointingHandCursor)
        self._is_dark = True
        self._thumb_x = 26 
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
            start = self._thumb_x
            end = 26 if self._is_dark else 2 
            self.anim.stop()
            self.anim.setStartValue(start)
            self.anim.setEndValue(end)
            self.anim.start()
            self.toggled.emit(self._is_dark)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        track_color = QColor("#333333") if self._is_dark else QColor("#D0D0D0")
        p.setBrush(track_color)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(0, 0, 48, 24, 12, 12)
        
        p.setFont(QFont("Segoe UI Emoji", 9)) 
        if self._is_dark:
            p.setPen(QColor("#666"))
            p.drawText(6, 17, "☀️")
        else:
            p.setPen(QColor("#FFF"))
            p.drawText(28, 17, "🌙")

        thumb_color = QColor("#121214") if self._is_dark else QColor("#FFFFFF")
        p.setBrush(thumb_color)
        p.drawEllipse(int(self._thumb_x), 2, 20, 20)

class ThreeDButton(QPushButton):
    def __init__(self, text, is_primary=True, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(36) 
        self.setFont(QFont("Microsoft YaHei UI", 9, QFont.Weight.Bold)) 
        self._is_primary = is_primary
        self._is_pressed = False
        self._offset_y = 3 
        
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
        self.anim.stop(); self.anim.setEndValue(1.0); self.anim.start()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.anim.stop(); self.anim.setEndValue(0.0); self.anim.start()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton: self._is_pressed = True; self.update()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton: self._is_pressed = False; self.update()
        super().mouseReleaseEvent(e)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        
        if self._is_primary:
            face_color, side_color, text_color = QColor(Theme.get('btn_face')), QColor(Theme.get('btn_side')), QColor("white")
        else:
            face_color, side_color = QColor(Theme.get('btn_sec_face')), QColor(Theme.get('btn_sec_side'))
            text_color = QColor("white") if Theme.CURRENT_MODE == 'dark' else QColor("#333")

        if self._hover_progress > 0:
            face_color = face_color.lighter(105); side_color = side_color.lighter(105)
        
        current_offset = self._offset_y if not self._is_pressed else 1
        face_h = h - self._offset_y
        
        path_side = QPainterPath()
        path_side.addRoundedRect(QRectF(0, self._offset_y, w, face_h), 8, 8) 
        painter.setBrush(side_color); painter.setPen(Qt.NoPen); painter.drawPath(path_side)

        top_y = 0 if not self._is_pressed else (self._offset_y - 1)
        rect_face = QRectF(0, top_y, w, face_h)
        painter.setBrush(face_color); painter.drawRoundedRect(rect_face, 8, 8)
        
        painter.setPen(text_color)
        painter.drawText(rect_face, Qt.AlignCenter, self.text())

class ModernProgressBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(4) 
        self._value = 0
    def setValue(self, v): self._value = v; self.update()
    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        bg_c = QColor("#333") if Theme.CURRENT_MODE == 'dark' else QColor("#DDD")
        p.setBrush(bg_c); p.setPen(Qt.NoPen); p.drawRoundedRect(rect, 2, 2)
        if self._value <= 0: return
        w = rect.width() * (self._value / 100.0)
        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0, QColor("#2D79FF")); grad.setColorAt(1, QColor("#00F0FF"))
        p.setBrush(grad); p.drawRoundedRect(QRectF(0, 0, w, rect.height()), 2, 2)

# ---------------------- 复杂可视化组件 ----------------------

class AIGCGaugeWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(150)
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
        if val < 30: return QColor(Theme.ACCENT_GREEN)
        if val < 60: return QColor(Theme.ACCENT_YELLOW)
        return QColor(Theme.ACCENT_RED)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        logical_w, logical_h = 280.0, 190.0 
        pad = 10
        avail_w = max(1, self.width() - pad * 2)
        avail_h = max(1, self.height() - pad * 2)
        
        scale = min(avail_w / logical_w, avail_h / logical_h)
        offset_x = pad + (avail_w - logical_w * scale) / 2.0
        offset_y = pad + (avail_h - logical_h * scale) / 2.0
        
        p.translate(offset_x, offset_y)
        p.scale(scale, scale)
        p.translate(140, 170) 

        color = self.get_color(self._value)
        
        alpha = 40 if Theme.CURRENT_MODE == 'dark' else 10
        glow = QRadialGradient(0, 0, 150)
        glow.setColorAt(0, QColor(color.red(), color.green(), color.blue(), alpha))
        glow.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
        p.setBrush(glow); p.setPen(Qt.NoPen); p.drawEllipse(-150, -150, 300, 300)

        if self._value < 30: verdict = "人类文本"
        elif self._value < 60: verdict = "疑似混写"
        else: verdict = "疑似AI"

        p.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        fm = QFontMetrics(p.font())
        title_str = "整体疑似度  " 
        title_w = fm.horizontalAdvance(title_str)
        verdict_w = fm.horizontalAdvance(verdict)
        total_w = title_w + verdict_w
        
        start_x = -total_w / 2
        p.setPen(QColor(Theme.get('text_sub')))
        p.drawText(QRectF(start_x, -165, title_w, 30), Qt.AlignLeft | Qt.AlignVCenter, title_str)
        p.setPen(color)
        p.drawText(QRectF(start_x + title_w, -165, verdict_w, 30), Qt.AlignLeft | Qt.AlignVCenter, verdict)

        track_c = QColor(40, 40, 45) if Theme.CURRENT_MODE == 'dark' else QColor(220, 220, 220)
        p.setPen(QPen(track_c, 18, Qt.SolidLine, Qt.RoundCap))
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
        p.setBrush(QBrush(pointer_c)); p.setPen(Qt.NoPen)
        p.drawPolygon(QPolygonF([QPointF(-6, 0), QPointF(6, 0), QPointF(0, -98)]))
        p.setBrush(QBrush(QColor(Theme.get('bg_main')))) 
        p.setPen(QPen(pointer_c, 3))
        p.drawEllipse(-8, -8, 16, 16)
        p.restore()

class AIGCPieChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(150, 150) 
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
        offset_x = pad + (avail_w - logical_w * scale) / 2.0
        offset_y = pad + (avail_h - logical_h * scale) / 2.0
        return logical_w, logical_h, scale, offset_x, offset_y

    def mouseMoveEvent(self, event):
        logical_w, logical_h, scale, offset_x, offset_y = self._get_logical_params()
        
        pos = event.position()
        lx = (pos.x() - offset_x) / scale
        ly = (pos.y() - offset_y) / scale
        
        center_x, center_y = 220.0, 105.0 
        base_radius = 85.0
        inner_radius = base_radius * 0.6 
        
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
        base_radius = 85.0 
        
        total = sum(self.counts)
        if total == 0:
            p.setPen(QPen(QColor(60,60,60), 4))
            p.drawEllipse(QPointF(center_x, center_y), base_radius, base_radius)
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
            lightness = 100 + int((offset / 12.0) * 20)
            alpha = 200 + int((offset / 12.0) * 55)
            c = c.lighter(lightness); c.setAlpha(alpha)
            
            p.setBrush(c); p.setPen(Qt.NoPen)
            rect = QRectF(center_x - r, center_y - r, r*2, r*2)
            p.drawPie(rect, start_angle, int(span_angle))
            
            start_angle += int(-segment_fraction * 360 * 16)
            accumulated_fraction += segment_fraction

        inner_radius = base_radius * 0.6
        p.setBrush(QColor(Theme.get('bg_main'))) 
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(center_x, center_y), inner_radius, inner_radius)

        p.setOpacity(self._anim_progress)
        if self._anim_progress > 0.6: 
            if self.hovered_idx != -1:
                pct = int(self.counts[self.hovered_idx] / total * 100) if total else 0
                p.setPen(QColor(self.colors[self.hovered_idx]).lighter(110))
                p.setFont(QFont("Segoe UI", 18, QFont.Bold))
                p.drawText(QRectF(center_x - 45, center_y - 20, 90, 40), Qt.AlignCenter, f"{pct}%")
            else:
                p.setPen(QColor(Theme.get('text_sub')))
                p.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
                p.drawText(QRectF(center_x - 45, center_y - 20, 90, 40), Qt.AlignCenter, f"共 {total} 段")

        legend_x = 15.0
        legend_y = 65.0
        
        for i, label in enumerate(self.labels):
            c = QColor(self.colors[i])
            offset = self.hover_offsets[i]
            box_x = legend_x + (offset * 0.5) 
            
            p.setBrush(c); p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(box_x, legend_y + i*32, 14, 14), 3, 3) 
            
            text_c = QColor(Theme.get('text_main'))
            if i == self.hovered_idx:
                p.setFont(QFont("Microsoft YaHei", 11, QFont.Bold)); text_c = c.lighter(110)
            else:
                p.setFont(QFont("Microsoft YaHei", 11)); text_c.setAlpha(180) 
                
            p.setPen(text_c)
            p.drawText(QRectF(box_x + 24, legend_y + i*32 - 2, 120, 18), Qt.AlignLeft | Qt.AlignVCenter, f"{label}: {self.counts[i]}")

class StatsDashboard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(0)
        
        self.gauge = AIGCGaugeWidget()
        self.pie_chart = AIGCPieChart()
        
        self.divider = QFrame()
        self.divider.setFixedWidth(1)
        
        self.layout.addWidget(self.gauge, 1)
        self.layout.addWidget(self.divider)
        self.layout.addWidget(self.pie_chart, 1)
        
    def update_style(self):
        self.setStyleSheet("StatsDashboard { background: transparent; border: none; }")
        self.divider.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.get('border')};
                margin: 15px 0px;
            }}
        """)
        self.gauge.update()
        self.pie_chart.update()

class HeatmapBar(QWidget):
    clicked_section = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(24) 
        self.data = [] 
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        
        self._anim_progress = 0.0
        self.anim = QPropertyAnimation(self, b"anim_progress", self)
        self.anim.setDuration(1200) 
        self.anim.setEasingCurve(QEasingCurve.OutExpo)

        self.hover_width = 6.0 
        self.target_width = 6.0
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
            
            if is_ignored: c = QColor(Theme.ACCENT_GRAY)
            elif score < 30: c = QColor(Theme.ACCENT_GREEN)
            elif score < 60: c = QColor(Theme.ACCENT_YELLOW)
            else: c = QColor(Theme.ACCENT_RED)
            
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
        self.target_width = 12.0 
        
    def leaveEvent(self, event):
        self.target_width = 6.0  
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

    def paintEvent(self, event):
        if not self.data: return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        w, h = self.width(), self.height()
        
        visible_y_start = h * (1.0 - self._anim_progress)
        p.setClipRect(0, int(visible_y_start), int(w), int(h))
        
        center_x = w / 2.0
        
        track_w = self.hover_width
        track_c = QColor(Theme.get('border'))
        track_c.setAlpha(100)
        p.setPen(Qt.NoPen)
        p.setBrush(track_c)
        p.drawRoundedRect(QRectF(center_x - track_w/2, 0, track_w, h), track_w/2, track_w/2)

        current_y = 0.0
        for i, item in enumerate(self.data):
            block_h = max(3.0, item['weight'] * h)
            draw_h = max(1.5, block_h - 1.0) 
            
            current_w = track_w + self.block_offsets[i]
            
            c = QColor(item['color'])
            if i == self.hovered_idx:
                c = c.lighter(120)
            else:
                if self.hovered_idx != -1: c.setAlpha(120) 
                else: c.setAlpha(200)

            p.setBrush(c)
            rect = QRectF(center_x - current_w/2, current_y + 0.5, current_w, draw_h)
            p.drawRoundedRect(rect, current_w/2, current_w/2)
            
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
    def glow_strength(self, v):
        self._glow_strength = v
        self.update()

    @Property(float)
    def scale_factor(self): return self._scale_factor
    @scale_factor.setter
    def scale_factor(self, v):
        self._scale_factor = v
        self.update()

    def insertFromMimeData(self, source):
        if source.hasText(): self.insertPlainText(source.text())
        else: super().insertFromMimeData(source)

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
                e.acceptProposedAction() 
            else: e.ignore()
        else: e.ignore()

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
        if not content: return
        cursor = self.document().find(content[:50]) 
        if not cursor.isNull():
            cursor.select(QTextCursor.BlockUnderCursor)
            self.setTextCursor(cursor)
            self.ensureCursorVisible()
            self.setFocus()

class ResultBlock(QWidget):
    """
    终极段落卡片:
    引入动态预判机制，根据文字实际所需高度动态约束滚动遮罩，不留一丝冗余空间。
    """
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
        
        delay = min(self.index * 60, 1000)
        QTimer.singleShot(delay, self.entry_anim.start)

        self.update_colors()

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 头部区域
        self.header_frame = QFrame()
        self.header_layout = QHBoxLayout(self.header_frame)
        self.header_layout.setContentsMargins(15, 8, 15, 8)

        self.idx_lbl = QLabel(f"#{self.index+1}")
        self.risk_lbl = QLabel(f"{int(self.ai_rate)}% {self.verdict}")
        
        preview_text = self.content[:30].replace("\n", " ") + ("..." if len(self.content) > 30 else "")
        self.preview_lbl = QLabel(preview_text)
        self.preview_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.arrow_lbl = QLabel("▼")

        self.header_layout.addWidget(self.idx_lbl)
        self.header_layout.addWidget(self.risk_lbl)
        self.header_layout.addWidget(self.preview_lbl)
        self.header_layout.addWidget(self.arrow_lbl)

        # 内容区域
        self.content_frame = QFrame()
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(20, 15, 20, 15)
        self.content_layout.setAlignment(Qt.AlignTop) 
        
        styled_text = f"<div style='line-height: 1.6;'>{html.escape(self.content)}</div>"
        self.full_text_lbl = QLabel(styled_text)
        self.full_text_lbl.setWordWrap(True)
        self.full_text_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        
        self.content_layout.addWidget(self.full_text_lbl)
        
        # 视口裁切层，完美防止动画抽搐
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
        self.anim.setDuration(300)
        self.anim.setEasingCurve(QEasingCurve.OutCubic) 
        self.anim.finished.connect(self._on_anim_finished)

        self.update_style()

    def _remove_opacity_effect(self):
        self.setGraphicsEffect(None)
        self.update()

    def update_colors(self):
        if self.is_ignored:
            self.accent_color = Theme.ACCENT_GRAY
            self.verdict = "过短忽略"
            self.header_text_color = "#888"
        elif self.ai_rate < 30: 
            self.accent_color = Theme.ACCENT_GREEN
            self.verdict = "人类创作"
            self.header_text_color = Theme.ACCENT_GREEN
        elif self.ai_rate < 60: 
            self.accent_color = Theme.ACCENT_YELLOW
            self.verdict = "疑似混写"
            self.header_text_color = Theme.ACCENT_YELLOW
        else: 
            self.accent_color = Theme.ACCENT_RED
            self.verdict = "疑似生成"
            self.header_text_color = Theme.ACCENT_RED

    def update_style(self):
        self.update_colors()
        
        self.idx_lbl.setStyleSheet(f"color: {Theme.get('text_sub')}; font-weight: bold;")
        self.risk_lbl.setStyleSheet(f"color: {self.header_text_color}; font-weight: 900; font-size: 11pt;")
        self.preview_lbl.setStyleSheet(f"color: {Theme.get('text_sub')}; margin-left: 10px;")
        self.arrow_lbl.setStyleSheet(f"color: {Theme.get('text_sub')};")
        self.full_text_lbl.setStyleSheet(f"color: {Theme.get('text_main')}; font-size: 10.5pt;")
        
        is_collapsing = (not self.is_expanded) and (self.anim.state() == QPropertyAnimation.Running)
        use_expanded_style = self.is_expanded or is_collapsing

        if use_expanded_style:
            self.header_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {Theme.get('bg_card')};
                    border: 1px solid {Theme.get('border')};
                    border-left: 4px solid {self.accent_color};
                    border-bottom: none;
                    border-top-left-radius: 8px;
                    border-top-right-radius: 8px;
                    border-bottom-left-radius: 0px;
                    border-bottom-right-radius: 0px;
                }}
            """)
            self.content_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {Theme.get('input_bg')}; 
                    border: 1px solid {Theme.get('border')};
                    border-left: 4px solid {self.accent_color};
                    border-top: none;
                    border-bottom-left-radius: 8px; 
                    border-bottom-right-radius: 8px;
                }}
            """)
        else:
            self.header_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {Theme.get('bg_card')};
                    border: 1px solid {Theme.get('border')};
                    border-left: 4px solid transparent;
                    border-radius: 8px;
                }}
                QFrame:hover {{
                    border-left: 4px solid {self.accent_color};
                    background-color: {QColor(Theme.get('bg_card')).lighter(105).name()};
                }}
            """)
        
        self.update() 

    def get_target_height(self):
        """精准计算内部内容所需的高度，坚决不给多余的留白空间"""
        w = self.width()
        self.content_frame.setFixedWidth(w)
        self.content_frame.layout().activate() # 强制布局刷新
        self.content_frame.adjustSize() # 自适应包裹
        target_h = self.content_frame.height()
        
        # 解除强绑定，恢复缩放响应特性
        self.content_frame.setMinimumWidth(0)
        self.content_frame.setMaximumWidth(16777215)
        return target_h

    def _on_anim_finished(self):
        if not self.is_expanded:
            self.anim_wrapper.hide()
            self.update_style() 
        else:
            # 锁定高度，消除 QScrollArea 自带的多余留白
            target_h = self.get_target_height()
            self.anim_wrapper.setMinimumHeight(target_h)
            self.anim_wrapper.setMaximumHeight(target_h)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 如果窗口在展开状态下被拉伸，自动重新计算并无缝更新紧凑高度
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
            self.anim_wrapper.setMinimumHeight(0) # 释放最小约束以供动画运行
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