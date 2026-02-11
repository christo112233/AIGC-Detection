import math
import html
import os
from PySide6.QtWidgets import (
    QWidget, QPushButton, QLabel, QFrame, QTextEdit, QHBoxLayout, QVBoxLayout, QSizePolicy, QGraphicsDropShadowEffect
)
from PySide6.QtCore import (
    Qt, Property, QPropertyAnimation, QEasingCurve, QRectF, QPointF, Signal, QSize
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
    """日夜模式切换开关"""
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
    def thumb_pos(self):
        return self._thumb_x
    
    @thumb_pos.setter
    def thumb_pos(self, val):
        self._thumb_x = val
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_dark = not self._is_dark
            start = self._thumb_x
            end = 30 if self._is_dark else 4
            self.anim.stop()
            self.anim.setStartValue(start)
            self.anim.setEndValue(end)
            self.anim.start()
            self.toggled.emit(self._is_dark)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        # 轨道
        track_color = QColor("#333333") if self._is_dark else QColor("#D0D0D0")
        p.setBrush(track_color)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(0, 0, 56, 28, 14, 14)
        
        # 图标
        p.setFont(QFont("Segoe UI Emoji", 10))
        if self._is_dark:
            p.setPen(QColor("#666"))
            p.drawText(8, 19, "☀️")
        else:
            p.setPen(QColor("#FFF"))
            p.drawText(36, 19, "🌙")

        # 滑块
        thumb_color = QColor("#121214") if self._is_dark else QColor("#FFFFFF")
        p.setBrush(thumb_color)
        p.drawEllipse(int(self._thumb_x), 2, 24, 24)

class ThreeDButton(QPushButton):
    """3D 立体按钮"""
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
    def hover_progress(self):
        return self._hover_progress
    
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
            face_color = QColor(Theme.get('btn_face'))
            side_color = QColor(Theme.get('btn_side'))
            text_color = QColor("white")
        else:
            face_color = QColor(Theme.get('btn_sec_face'))
            side_color = QColor(Theme.get('btn_sec_side'))
            text_color = QColor("white") if Theme.CURRENT_MODE == 'dark' else QColor("#333")

        if self._hover_progress > 0:
            face_color = face_color.lighter(105)
            side_color = side_color.lighter(105)
        
        # 计算 3D 偏移
        current_offset = self._offset_y if not self._is_pressed else 2
        face_h = h - self._offset_y
        
        # 侧面 (阴影层)
        path_side = QPainterPath()
        path_side.addRoundedRect(QRectF(0, self._offset_y, w, face_h), 12, 12)
        painter.setBrush(side_color)
        painter.setPen(Qt.NoPen)
        painter.drawPath(path_side)

        # 正面
        top_y = 0 if not self._is_pressed else (self._offset_y - 2)
        rect_face = QRectF(0, top_y, w, face_h)
        painter.setBrush(face_color)
        painter.drawRoundedRect(rect_face, 12, 12)
        
        # 文字
        painter.setPen(text_color)
        painter.drawText(rect_face, Qt.AlignCenter, self.text())

class ModernProgressBar(QWidget):
    """渐变进度条"""
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

# ---------------------- 复杂可视化组件 ----------------------

class AIGCGaugeWidget(QWidget):
    """AI率仪表盘"""
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
        if val < 30: return QColor(Theme.ACCENT_GREEN)
        if val < 60: return QColor(Theme.ACCENT_YELLOW)
        return QColor(Theme.ACCENT_RED)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        w, h = self.width(), self.height()
        side = min(w, h * 1.5)
        p.translate(w / 2, h * 0.85)
        scale = side / 320
        p.scale(scale, scale)

        color = self.get_color(self._value)
        
        # 光晕
        alpha = 40 if Theme.CURRENT_MODE == 'dark' else 10
        glow = QRadialGradient(0, 0, 150)
        glow.setColorAt(0, QColor(color.red(), color.green(), color.blue(), alpha))
        glow.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
        p.setBrush(glow)
        p.setPen(Qt.NoPen)
        p.drawEllipse(-150, -150, 300, 300)

        # 标题
        p.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        p.setPen(QColor(Theme.get('text_sub')))
        p.drawText(QRectF(-100, -170, 200, 30), Qt.AlignCenter, "整体疑似度")

        # 轨道背景
        track_c = QColor(40, 40, 45) if Theme.CURRENT_MODE == 'dark' else QColor(220, 220, 220)
        p.setPen(QPen(track_c, 18, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(QRectF(-110, -110, 220, 220), 180 * 16, -180 * 16)

        # 进度条
        p.setPen(QPen(color, 18, Qt.SolidLine, Qt.RoundCap))
        span = -(self._value / 100.0) * 180 * 16
        p.drawArc(QRectF(-110, -110, 220, 220), 180 * 16, span)

        # 数值
        p.setPen(QColor(Theme.get('text_main')))
        p.setFont(QFont("Segoe UI", 42, QFont.Bold))
        p.drawText(QRectF(-100, -80, 200, 60), Qt.AlignCenter, f"{int(self._value)}%")

        # 指针
        p.save()
        angle = (self._value / 100.0) * 180 - 90
        p.rotate(angle)
        
        pointer_c = QColor("white") if Theme.CURRENT_MODE == 'dark' else QColor("#333")
        p.setBrush(QBrush(pointer_c))
        p.setPen(Qt.NoPen)
        
        # 指针形状 (QPolygonF 需要 PySide6.QtGui.QPolygonF)
        p.drawPolygon(QPolygonF([QPointF(-6, 0), QPointF(6, 0), QPointF(0, -98)]))
        
        # 中心圆点
        p.setBrush(QBrush(QColor(Theme.get('bg_card'))))
        p.setPen(QPen(pointer_c, 3))
        p.drawEllipse(-8, -8, 16, 16)
        p.restore()

class AIGCPieChart(QWidget):
    """分布饼图"""
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
    def anim_progress(self):
        return self._anim_progress
    
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
        # 饼图中心点 (偏右)
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
            # 空数据显示
            p.setPen(QPen(QColor(60,60,60), 4))
            p.drawEllipse(QPointF(center_x, center_y), radius, radius)
            return

        start_angle = 0
        
        # 绘制扇区
        for i, count in enumerate(self.counts):
            span_angle = (count / total) * 360 * 16 # drawPie 使用 1/16 度单位
            
            # 悬停凸起效果
            r = radius + (5 if i == self.hovered_idx else 0)
            
            c = QColor(self.colors[i])
            if i == self.hovered_idx:
                c = c.lighter(120)
            else:
                c.setAlpha(200)
            
            p.setBrush(c)
            p.setPen(Qt.NoPen)
            
            rect = QRectF(center_x - r, center_y - r, r*2, r*2)
            p.drawPie(rect, start_angle, int(span_angle))
            
            start_angle += int(span_angle)

        # 绘制图例 (左侧)
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

class HeatmapBar(QWidget):
    """热力导航条"""
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
            # 留一点间隙
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
    """支持文件拖入的文本框"""
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
        # 强制只粘贴纯文本
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
        if not content: return
        cursor = self.document().find(content[:50]) # 查找前50字
        if not cursor.isNull():
            cursor.select(QTextCursor.BlockUnderCursor)
            self.setTextCursor(cursor)
            self.ensureCursorVisible()
            self.setFocus()

class ResultBlock(QWidget):
    """可折叠结果卡片"""
    request_scroll = Signal() 
    request_highlight = Signal(str)
    expanded = Signal(int) # 新增：通知外部自己展开了

    def __init__(self, index, content, ai_rate, is_ignored=False, parent=None):
        super().__init__(parent)
        self.index = index
        self.content = content
        self.ai_rate = ai_rate
        self.is_ignored = is_ignored
        self.is_expanded = False 
        
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor) 
        
        # 初始化颜色
        self.update_colors()

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 头部
        self.header_frame = QFrame()
        self.header_layout = QHBoxLayout(self.header_frame)
        self.header_layout.setContentsMargins(15, 12, 15, 12)

        self.idx_lbl = QLabel(f"#{self.index+1}")
        self.idx_lbl.setStyleSheet(f"font-weight: bold;") # 颜色在 update_style 中设置
        
        self.risk_lbl = QLabel(f"{int(self.ai_rate)}% {self.verdict}")
        self.risk_lbl.setStyleSheet(f"font-weight: 900; font-size: 11pt;")
        
        preview_text = self.content[:30].replace("\n", " ") + ("..." if len(self.content) > 30 else "")
        self.preview_lbl = QLabel(preview_text)
        self.preview_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.arrow_lbl = QLabel("▼")

        self.header_layout.addWidget(self.idx_lbl)
        self.header_layout.addWidget(self.risk_lbl)
        self.header_layout.addWidget(self.preview_lbl)
        self.header_layout.addWidget(self.arrow_lbl)

        # 内容
        self.content_frame = QFrame()
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(20, 15, 20, 15)
        
        self.full_text_lbl = QLabel(self.content)
        self.full_text_lbl.setWordWrap(True)
        self.full_text_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        
        self.content_layout.addWidget(self.full_text_lbl)
        self.content_frame.hide() 

        self.main_layout.addWidget(self.header_frame)
        self.main_layout.addWidget(self.content_frame)
        
        # 初始化样式
        self.update_style()

    def update_colors(self):
        """计算当前应该使用的颜色"""
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
        """刷新样式表 (用于主题切换或初始化)"""
        self.update_colors() # 确保颜色是最新的
        
        # 刷新子控件颜色
        self.idx_lbl.setStyleSheet(f"color: {Theme.get('text_sub')}; font-weight: bold;")
        self.risk_lbl.setStyleSheet(f"color: {self.header_text_color}; font-weight: 900; font-size: 11pt;")
        self.preview_lbl.setStyleSheet(f"color: {Theme.get('text_sub')}; margin-left: 10px;")
        self.arrow_lbl.setStyleSheet(f"color: {Theme.get('text_sub')};")
        self.full_text_lbl.setStyleSheet(f"color: {Theme.get('text_main')}; font-size: 10pt; line-height: 1.6;")
        
        # 刷新 Frame 样式 (根据折叠状态)
        if self.is_expanded:
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
        
        self.update() # 触发重绘

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
            # 通知外部：我展开了
            self.expanded.emit(self.index)
        else:
            self.content_frame.hide()
            self.preview_lbl.show()
            self.arrow_lbl.setText("▼")
        
        # 更新样式
        self.update_style()
        self.request_scroll.emit()

    def set_expanded(self, expanded):
        if self.is_expanded != expanded:
            self.toggle_expand()