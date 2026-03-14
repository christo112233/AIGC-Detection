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
    QPainterPath, QTransform, QFontMetrics, QTextCursor, QPolygonF, QPixmap
)

# ---------------------- 核心配色管理 ----------------------
class Theme:
    """管理黑白两套主题的调色板字典类"""
    CURRENT_MODE = 'dark'
    COLORS = {
        'dark': {
            'bg_main': "#121214",     # 最底层背景色
            'bg_card': "#1E1E24",     # 卡片背景色
            'text_main': "#FFFFFF",   # 主要文字色
            'text_sub': "#A0A0A0",    # 次要/暗淡文字色
            'border': "#333333",      # 边框线条色
            'input_bg': "#16161A",    # 文本框内景色
            'scroll': "#2A2A30",
            'btn_face': "#2D79FF",    # 按钮亮面色 (主按钮)
            'btn_side': "#1B4DB3",    # 按钮暗面色/侧面 (主按钮)
            'btn_sec_face': "#2A2A30",# 按钮亮面色 (次按钮)
            'btn_sec_side': "#1A1A20",# 按钮暗面色/侧面 (次按钮)
            'shadow': QColor(0, 0, 0, 150) # 阴影色
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
    
    # 全局语义强调色 (用于表达安全/警告/危险)
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
        # 统一生成高级发光阴影特效的工厂方法
        effect = QGraphicsDropShadowEffect()
        effect.setBlurRadius(radius)
        effect.setXOffset(0)
        effect.setYOffset(4)
        effect.setColor(Theme.COLORS[Theme.CURRENT_MODE]['shadow'])
        return effect

# ---------------------- 基础 UI 组件 ----------------------

class ThemeSwitch(QWidget):
    """自定义带动画的日月模式切换小开关"""
    toggled = Signal(bool) 

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(48, 24)
        self.setCursor(Qt.PointingHandCursor)
        self._is_dark = True
        self._thumb_x = 26 # 小圆球的初始横坐标
        
        # 定义平滑移动动画
        self.anim = QPropertyAnimation(self, b"thumb_pos", self)
        self.anim.setDuration(250)
        self.anim.setEasingCurve(QEasingCurve.InOutQuad)

    # 将 thumb_pos 注册为 Qt 属性，以便动画框架对其插值
    @Property(float)
    def thumb_pos(self): return self._thumb_x
    @thumb_pos.setter
    def thumb_pos(self, val):
        self._thumb_x = val
        self.update() # 触发重新绘制

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_dark = not self._is_dark
            start = self._thumb_x
            end = 26 if self._is_dark else 2 
            self.anim.stop()
            self.anim.setStartValue(start)
            self.anim.setEndValue(end)
            self.anim.start() # 执行左右移动动画
            self.toggled.emit(self._is_dark)

    def paintEvent(self, event):
        # 手工绘制开关槽和圆球
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        track_color = QColor("#333333") if self._is_dark else QColor("#D0D0D0")
        p.setBrush(track_color)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(0, 0, 48, 24, 12, 12) # 画背面的胶囊
        
        p.setFont(QFont("Segoe UI Emoji", 9)) 
        if self._is_dark:
            p.setPen(QColor("#666"))
            p.drawText(6, 17, "☀️")
        else:
            p.setPen(QColor("#FFF"))
            p.drawText(28, 17, "🌙")

        thumb_color = QColor("#121214") if self._is_dark else QColor("#FFFFFF")
        p.setBrush(thumb_color)
        p.drawEllipse(int(self._thumb_x), 2, 20, 20) # 画移动的小圆球

class ThreeDButton(QPushButton):
    """拟物化 3D 悬浮按钮，带有点击下陷和高光动画"""
    def __init__(self, text, is_primary=True, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(36) 
        self.setFont(QFont("Microsoft YaHei UI", 9, QFont.Weight.Bold)) 
        self._is_primary = is_primary # 是否为主按钮（决定其颜色）
        self._is_pressed = False
        self._offset_y = 3 # 3D 侧边的厚度
        
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
        # 鼠标进入时，让表面高光慢慢亮起
        self.anim.stop(); self.anim.setEndValue(1.0); self.anim.start()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.anim.stop(); self.anim.setEndValue(0.0); self.anim.start()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        # 点击瞬间改变状态，从而触发不同的厚度绘制
        if e.button() == Qt.LeftButton: self._is_pressed = True; self.update()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton: self._is_pressed = False; self.update()
        super().mouseReleaseEvent(e)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        
        # 决定颜色
        if self._is_primary:
            face_color, side_color, text_color = QColor(Theme.get('btn_face')), QColor(Theme.get('btn_side')), QColor("white")
        else:
            face_color, side_color = QColor(Theme.get('btn_sec_face')), QColor(Theme.get('btn_sec_side'))
            text_color = QColor("white") if Theme.CURRENT_MODE == 'dark' else QColor("#333")

        # 应用悬停高光加成
        if self._hover_progress > 0:
            face_color = face_color.lighter(105); side_color = side_color.lighter(105)
        
        # 如果按钮被按住，上层矩形下移，厚度变小，从而产生机械下陷感
        current_offset = self._offset_y if not self._is_pressed else 1
        face_h = h - self._offset_y
        
        # 画底层的暗色矩形 (相当于按钮的侧面)
        path_side = QPainterPath()
        path_side.addRoundedRect(QRectF(0, self._offset_y, w, face_h), 8, 8) 
        painter.setBrush(side_color); painter.setPen(Qt.NoPen); painter.drawPath(path_side)

        # 画顶层的亮色矩形 (相当于按钮的正面)
        top_y = 0 if not self._is_pressed else (self._offset_y - 1)
        rect_face = QRectF(0, top_y, w, face_h)
        painter.setBrush(face_color); painter.drawRoundedRect(rect_face, 8, 8)
        
        # 画文字
        painter.setPen(text_color)
        painter.drawText(rect_face, Qt.AlignCenter, self.text())

class ModernProgressBar(QWidget):
    """状态栏上的线性渐变极简进度条"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(4) # 细线条风格
        self._value = 0
    def setValue(self, v): self._value = v; self.update()
    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        bg_c = QColor("#333") if Theme.CURRENT_MODE == 'dark' else QColor("#DDD")
        
        # 画背景凹槽
        p.setBrush(bg_c); p.setPen(Qt.NoPen); p.drawRoundedRect(rect, 2, 2)
        if self._value <= 0: return
        
        # 画蓝青渐变进度条
        w = rect.width() * (self._value / 100.0)
        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0, QColor("#2D79FF")); grad.setColorAt(1, QColor("#00F0FF"))
        p.setBrush(grad); p.drawRoundedRect(QRectF(0, 0, w, rect.height()), 2, 2)

# ---------------------- 复杂可视化组件 ----------------------

class AIGCGaugeWidget(QWidget):
    """绘制整体得分的半圆形赛车风仪表盘，带有动效指针和背光"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(150)
        self._value = 0
        
        # 给指针运动绑定平滑物理阻尼动画
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
        
        # 虚拟一个固定逻辑大小，保证在不同缩放下拉伸也能保证完美的半圆形例
        logical_w, logical_h = 280.0, 190.0 
        pad = 10
        avail_w = max(1, self.width() - pad * 2)
        avail_h = max(1, self.height() - pad * 2)
        
        scale = min(avail_w / logical_w, avail_h / logical_h)
        offset_x = pad + (avail_w - logical_w * scale) / 2.0
        offset_y = pad + (avail_h - logical_h * scale) / 2.0
        
        p.translate(offset_x, offset_y)
        p.scale(scale, scale)
        p.translate(140, 170) # 把原点移动到半圆圆心处

        color = self.get_color(self._value)
        
        # 画底部模糊的发光辐射圈 (营造科幻科技感)
        alpha = 40 if Theme.CURRENT_MODE == 'dark' else 10
        glow = QRadialGradient(0, 0, 150)
        glow.setColorAt(0, QColor(color.red(), color.green(), color.blue(), alpha))
        glow.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
        p.setBrush(glow); p.setPen(Qt.NoPen); p.drawEllipse(-150, -150, 300, 300)

        # 文本信息
        if self._value < 30: verdict = "人类文本"
        elif self._value < 60: verdict = "疑似混写"
        else: verdict = "疑似AI"
        
        # 提升文本标题和状态栏文字尺寸，与右侧保持一致
        p.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
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

        # 仪表盘轨道底色
        track_c = QColor(40, 40, 45) if Theme.CURRENT_MODE == 'dark' else QColor(220, 220, 220)
        p.setPen(QPen(track_c, 18, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(QRectF(-110, -110, 220, 220), 180 * 16, -180 * 16)

        # 仪表盘实际颜色值 (基于当前 value 画带颜色的弧)
        p.setPen(QPen(color, 18, Qt.SolidLine, Qt.RoundCap))
        span = -(self._value / 100.0) * 180 * 16
        p.drawArc(QRectF(-110, -110, 220, 220), 180 * 16, span)

        # 稍微放大百分比中心数字，使其更有视觉冲击力
        p.setPen(QColor(Theme.get('text_main')))
        p.setFont(QFont("Segoe UI", 44, QFont.Bold))
        p.drawText(QRectF(-100, -80, 200, 60), Qt.AlignCenter, f"{int(self._value)}%")

        # 画旋转指针
        p.save()
        angle = (self._value / 100.0) * 180 - 90 # 将 0-100 映射为 -90度 到 +90度
        p.rotate(angle)
        pointer_c = QColor("white") if Theme.CURRENT_MODE == 'dark' else QColor("#333")
        p.setBrush(QBrush(pointer_c)); p.setPen(Qt.NoPen)
        p.drawPolygon(QPolygonF([QPointF(-6, 0), QPointF(6, 0), QPointF(0, -98)]))
        p.setBrush(QBrush(QColor(Theme.get('bg_main')))) 
        p.setPen(QPen(pointer_c, 3))
        p.drawEllipse(-8, -8, 16, 16) # 指针根部的小圆圈
        p.restore()

class AIGCPieChart(QWidget):
    """绘制不同判定级别段落比例的动态饼图 (环状图)"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(150, 150) 
        self.counts = [0, 0, 0]
        self.labels = ["人类文本", "疑似混写", "疑似AI"]
        self.colors = [Theme.ACCENT_GREEN, Theme.ACCENT_YELLOW, Theme.ACCENT_RED]
        self.hovered_idx = -1
        
        # 出场展开动画
        self._anim_progress = 0.0
        self.anim = QPropertyAnimation(self, b"anim_progress", self)
        self.anim.setDuration(1200)
        self.anim.setEasingCurve(QEasingCurve.OutQuart)
        
        self.setMouseTracking(True) # 开启鼠标移动追踪
        
        # 悬停时扇形向外突出的动画插值器
        self.hover_offsets = [0.0, 0.0, 0.0]
        self.target_offsets = [0.0, 0.0, 0.0]
        self.hover_timer = QTimer(self)
        self.hover_timer.timeout.connect(self._smooth_hover_anim)
        self.hover_timer.start(16) # 大约 60帧 每秒刷新平滑过渡

    @Property(float)
    def anim_progress(self): return self._anim_progress
    @anim_progress.setter
    def anim_progress(self, val): 
        self._anim_progress = val
        self.update()

    def _smooth_hover_anim(self):
        """让饼图切片在鼠标放上去或离开时，不要瞬间突变，而是平滑弹进弹出"""
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
        """计算逻辑绘图坐标到物理像素的缩放比例"""
        logical_w, logical_h = 320.0, 190.0
        pad = 5
        avail_w = max(1, self.width() - pad * 2)
        avail_h = max(1, self.height() - pad * 2)
        
        scale = min(avail_w / logical_w, avail_h / logical_h)
        offset_x = pad + (avail_w - logical_w * scale) / 2.0
        offset_y = pad + (avail_h - logical_h * scale) / 2.0
        return logical_w, logical_h, scale, offset_x, offset_y

    def mouseMoveEvent(self, event):
        """鼠标移动时，通过三角函数判断鼠标是否落在某个圆环切片上"""
        logical_w, logical_h, scale, offset_x, offset_y = self._get_logical_params()
        
        # 坐标反变换，将屏幕点击点还原为逻辑绘图系的坐标
        pos = event.position()
        lx = (pos.x() - offset_x) / scale
        ly = (pos.y() - offset_y) / scale
        
        center_x, center_y = 220.0, 105.0 
        base_radius = 85.0
        inner_radius = base_radius * 0.6 
        
        dx = lx - center_x
        dy = ly - center_y
        dist = math.sqrt(dx*dx + dy*dy) # 到圆心的欧式距离
        
        new_hover_idx = -1
        # 判断距离是否正好卡在外圆与内圆的圆环带之间
        if inner_radius - 5 <= dist <= base_radius + 25: 
            math_angle = math.degrees(math.atan2(-dy, dx))
            sweep_angle = (90 - math_angle) % 360 # 转为绘制系统的 0-360 角度系
            
            total = sum(self.counts)
            if total > 0:
                current_angle = 0
                for i, count in enumerate(self.counts):
                    span = (count / total) * 360
                    if current_angle <= sweep_angle < current_angle + span:
                        if dist <= base_radius + self.hover_offsets[i] + 5:
                            new_hover_idx = i # 确定命中了哪个扇形
                        break
                    current_angle += span
        
        # 更新目标偏移量给动画引擎去插值
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
        
        # 提升右侧饼图大标题的字号
        p.setOpacity(self._anim_progress)
        p.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
        p.setPen(QColor(Theme.get('text_sub')))
        p.drawText(QRectF(15, 10, logical_w - 30, 30), Qt.AlignLeft | Qt.AlignVCenter, "段落成分分布")
        
        center_x, center_y = 220.0, 105.0
        base_radius = 85.0 
        
        total = sum(self.counts)
        if total == 0: # 数据为空时画个空心圈
            p.setPen(QPen(QColor(60,60,60), 4))
            p.drawEllipse(QPointF(center_x, center_y), base_radius, base_radius)
            return

        start_angle = 90 * 16 
        accumulated_fraction = 0.0 
        
        # 顺次画出每个分类的饼图片段
        for i, count in enumerate(self.counts):
            segment_fraction = count / total
            if self._anim_progress <= accumulated_fraction:
                break
            allowed_fraction = min(segment_fraction, self._anim_progress - accumulated_fraction)
            span_angle = - (allowed_fraction * 360 * 16) 
            
            # 拿到刚才平滑出来的外凸偏移量
            offset = self.hover_offsets[i]
            r = base_radius + offset 
            
            c = QColor(self.colors[i])
            # 悬浮时让颜色更亮一些
            lightness = 100 + int((offset / 12.0) * 20)
            alpha = 200 + int((offset / 12.0) * 55)
            c = c.lighter(lightness); c.setAlpha(alpha)
            
            p.setBrush(c); p.setPen(Qt.NoPen)
            rect = QRectF(center_x - r, center_y - r, r*2, r*2)
            p.drawPie(rect, start_angle, int(span_angle))
            
            start_angle += int(-segment_fraction * 360 * 16)
            accumulated_fraction += segment_fraction

        # 在实心圆正中心画一个背景色的同心圆，这样饼图就变成了圆环图
        inner_radius = base_radius * 0.6
        p.setBrush(QColor(Theme.get('bg_main'))) 
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(center_x, center_y), inner_radius, inner_radius)

        p.setOpacity(self._anim_progress)
        if self._anim_progress > 0.6: 
            if self.hovered_idx != -1:
                pct = int(self.counts[self.hovered_idx] / total * 100) if total else 0
                p.setPen(QColor(self.colors[self.hovered_idx]).lighter(110))
                
                # 提升饼图中心的悬浮百分比字号
                p.setFont(QFont("Segoe UI", 22, QFont.Bold))
                p.drawText(QRectF(center_x - 45, center_y - 20, 90, 40), Qt.AlignCenter, f"{pct}%")
            else:
                p.setPen(QColor(Theme.get('text_sub')))
                
                # 提升饼图中心未悬浮时的字号
                p.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
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
                # 放大侧边图例的字号，视觉效果更好
                p.setFont(QFont("Microsoft YaHei", 12, QFont.Bold)); text_c = c.lighter(110)
            else:
                p.setFont(QFont("Microsoft YaHei", 12)); text_c.setAlpha(180) 
                
            p.setPen(text_c)
            # 这里继续保留 Qt.TextDontClip 防止缩放被裁切
            p.drawText(QRectF(box_x + 24, legend_y + i*32 - 10, 150, 30), Qt.AlignLeft | Qt.AlignVCenter | Qt.TextDontClip, f"{label}: {self.counts[i]}")


# ================= Token 计数器动画组件 =================
class TokenCounterWidget(QWidget):
    """带数字滚动动画的 Token 消耗显示器"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignCenter)
        self.layout.setSpacing(5)

        self.lbl_title = QLabel("⚡ 算力消耗 (Tokens)")
        self.lbl_title.setAlignment(Qt.AlignCenter)

        self.lbl_value = QLabel("0")
        self.lbl_value.setAlignment(Qt.AlignCenter)

        self.layout.addWidget(self.lbl_title)
        self.layout.addWidget(self.lbl_value)

        self._current_value = 0
        self.anim = QPropertyAnimation(self, b"anim_val", self)
        self.anim.setDuration(1200)
        self.anim.setEasingCurve(QEasingCurve.OutQuart)

    @Property(int)
    def anim_val(self): return self._current_value
    @anim_val.setter
    def anim_val(self, v):
        self._current_value = v
        self.lbl_value.setText(f"{v:,}") # 格式化为千分位，如 1,234

    def set_data(self, value):
        self.anim.stop()
        self.anim.setStartValue(0)
        self.anim.setEndValue(value)
        self.anim.start()

    def update_style(self):
        # 对齐 Token 模块字号，字体更加粗重统一
        self.lbl_title.setStyleSheet(f"color: {Theme.get('text_sub')}; font-size: 13px; font-weight: bold;")
        self.lbl_value.setStyleSheet(f"color: {Theme.ACCENT_BLUE}; font-size: 32px; font-weight: 900; font-family: 'Segoe UI';")


# ================= 仪表盘排版容器 =================
class StatsDashboard(QFrame):
    """一个仅仅用于容纳 gauge 和 pie_chart 两个组件的水平容器"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(0)
        
        self.gauge = AIGCGaugeWidget()
        self.token_counter = TokenCounterWidget() 
        self.pie_chart = AIGCPieChart()
        
        # 中间的垂直分割线 1
        self.divider1 = QFrame()
        self.divider1.setFixedWidth(1)
        
        # 中间的垂直分割线 2 
        self.divider2 = QFrame()
        self.divider2.setFixedWidth(1)
        
        # 重新编排布局比例，给饼图(7)分配更大的空间，防止挤压
        self.layout.addWidget(self.gauge, 6)
        self.layout.addWidget(self.divider1)
        self.layout.addWidget(self.token_counter, 4)
        self.layout.addWidget(self.divider2)
        self.layout.addWidget(self.pie_chart, 7)
        
    def update_style(self):
        self.setStyleSheet("StatsDashboard { background: transparent; border: none; }")
        divider_style = f"QFrame {{ background-color: {Theme.get('border')}; margin: 15px 0px; }}"
        self.divider1.setStyleSheet(divider_style)
        self.divider2.setStyleSheet(divider_style)
        
        self.gauge.update()
        self.pie_chart.update()
        self.token_counter.update_style() 

# ================= 右侧热力导航条 =================
class HeatmapBar(QWidget):
    """
    极细长的条状热力导航栏组件，用于放在最右侧。
    它根据每个段落的字数占比（高度）以及被判定的嫌疑程度（颜色）绘制一根全局指纹条。
    """
    clicked_section = Signal(int)
    double_clicked = Signal() # --- 新增：双击信号 ---

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(24) 
        self.data = [] 
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        
        # 从上往下刷的进场动画
        self._anim_progress = 0.0
        self.anim = QPropertyAnimation(self, b"anim_progress", self)
        self.anim.setDuration(1200) 
        self.anim.setEasingCurve(QEasingCurve.OutExpo)

        self.hover_width = 6.0 
        self.target_width = 6.0
        self.hovered_idx = -1
        self.block_offsets = []
        
        # 让选中的区块能有一个丝滑变胖突出的动画
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
        """传入所有的段落解析数据，计算各块的相对高度"""
        self.data = []
        # 按字数算总重量，保底长度为 10
        total_len = sum(max(len(p['content']), 10) for p in paragraphs) if paragraphs else 1
        
        for i, p in enumerate(paragraphs):
            score = p['ai_rate']
            is_ignored = p.get('is_ignored', False)
            length = max(len(p['content']), 10)
            
            # 分配对应严重程度的颜色
            if is_ignored: c = QColor(Theme.ACCENT_GRAY)
            elif score < 30: c = QColor(Theme.ACCENT_GREEN)
            elif score < 60: c = QColor(Theme.ACCENT_YELLOW)
            else: c = QColor(Theme.ACCENT_RED)
            
            self.data.append({
                "index": i,
                "color": c,
                "weight": length / total_len # 该块在整条柱子中所占的比例高度
            })
        
        self.block_offsets = [0.0] * len(self.data)
        self.hovered_idx = -1
        
        self.anim.stop()
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()

    def enterEvent(self, event):
        # 鼠标移入热力条区域，热力条整体变宽
        self.target_width = 12.0 
        
    def leaveEvent(self, event):
        # 移出缩窄
        self.target_width = 6.0  
        self.hovered_idx = -1

    def mouseMoveEvent(self, event):
        if not self.data: return
        y = event.position().y()
        h = self.height()
        
        current_y = 0.0
        new_hover = -1
        # 循环叠加高度，找到鼠标悬停点属于哪个数据块
        for i, item in enumerate(self.data):
            block_h = max(3.0, item['weight'] * h)
            if current_y <= y <= current_y + block_h:
                new_hover = i
                break
            current_y += block_h
            
        if new_hover != self.hovered_idx:
            self.hovered_idx = new_hover

    def mousePressEvent(self, event):
        # 发生点击时，告诉主界面滚到对应的小卡片
        if self.hovered_idx != -1 and self.hovered_idx < len(self.data):
            self.clicked_section.emit(self.data[self.hovered_idx]['index'])

    def mouseDoubleClickEvent(self, event):
        # --- 新增：捕捉双击事件并发出信号 ---
        if self.data:
            self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)

    def paintEvent(self, event):
        if not self.data: return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        w, h = self.width(), self.height()
        
        # 使用 ClipRect 裁剪实现自上向下的扫光出场动画效果
        visible_y_start = h * (1.0 - self._anim_progress)
        p.setClipRect(0, int(visible_y_start), int(w), int(h))
        
        center_x = w / 2.0
        
        # 绘制背景的轨道槽
        track_w = self.hover_width
        track_c = QColor(Theme.get('border'))
        track_c.setAlpha(100)
        p.setPen(Qt.NoPen)
        p.setBrush(track_c)
        p.drawRoundedRect(QRectF(center_x - track_w/2, 0, track_w, h), track_w/2, track_w/2)

        # 遍历数据累加高度并画色块
        current_y = 0.0
        for i, item in enumerate(self.data):
            block_h = max(3.0, item['weight'] * h)
            draw_h = max(1.5, block_h - 1.0)  # 中间留出 1 像素间隙透气
            
            # 当前块的动态宽度 (悬停加粗)
            current_w = track_w + self.block_offsets[i]
            
            c = QColor(item['color'])
            if i == self.hovered_idx:
                c = c.lighter(120)
            else:
                if self.hovered_idx != -1: c.setAlpha(120) # 悬停别处时自己变暗
                else: c.setAlpha(200)

            p.setBrush(c)
            rect = QRectF(center_x - current_w/2, current_y + 0.5, current_w, draw_h)
            p.drawRoundedRect(rect, current_w/2, current_w/2)
            
            current_y += block_h


class DragTextEdit(QTextEdit):
    """
    左侧的大文本框，不仅能贴文本，还能把 txt/docx 直接拖进来读取。
    拖拽悬停时带有外框蓝色呼吸发光特效。
    """
    file_dropped = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True) # 允许拖拽入内
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
        # 如果是富文本，也强制当纯文本粘进去，防止格式扰乱模型
        if source.hasText(): self.insertPlainText(source.text())
        else: super().insertFromMimeData(source)

    def dragEnterEvent(self, e):
        # 拖拽文件到控件正上方时亮起蓝框
        if e.mimeData().hasUrls():
            e.accept()
            self.anim_glow.stop(); self.anim_glow.setEndValue(1.0); self.anim_glow.start()
            self.anim_scale.stop(); self.anim_scale.setEndValue(1.02); self.anim_scale.start()
        else: e.ignore()

    def dragLeaveEvent(self, e):
        # 拖出未松手，恢复原样
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
            # 将验证接收名单中加上 .pdf
            if ext in ['.txt', '.docx', '.pdf']:
                self.file_dropped.emit(path) 
                e.acceptProposedAction() 
            else: e.ignore()
        else: e.ignore()

    def paintEvent(self, event):
        super().paintEvent(event)
        # 如果呼吸发光值大于 0，手工在边沿画一圈带半透明效果的蓝色粗线
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
        """主界面发信号过来时，利用底层的 QTextDocument 游标系统，寻找对应的段落并把它选中高亮"""
        if not content: return
        cursor = self.document().find(content[:50]) # 拿前 50 个字做模糊匹配
        if not cursor.isNull():
            cursor.select(QTextCursor.BlockUnderCursor)
            self.setTextCursor(cursor)
            self.ensureCursorVisible() # 将视野自动滚动到被选中的文字处
            self.setFocus()

class ResultBlock(QWidget):
    """
    终极段落卡片:
    引入动态预判机制，根据文字实际所需高度动态约束滚动遮罩，不留一丝冗余空间。
    它是列表中的每一项。
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
        
        # 每个块创建后其实是透明的，通过透明度动画一个一个显示，造成瀑布流加载的感觉
        self.entry_effect = QGraphicsOpacityEffect(self)
        self.entry_effect.setOpacity(0.0)
        self.setGraphicsEffect(self.entry_effect)
        
        self.entry_anim = QPropertyAnimation(self.entry_effect, b"opacity")
        self.entry_anim.setDuration(600)
        self.entry_anim.setStartValue(0.0)
        self.entry_anim.setEndValue(1.0)
        self.entry_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.entry_anim.finished.connect(self._remove_opacity_effect)
        
        # 按照 index 顺序制造延迟加载出现的效果
        delay = min(self.index * 60, 1000)
        QTimer.singleShot(delay, self.entry_anim.start)

        self.update_colors()

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # ====== 头部区域 (就是那条默认状态下能看到的横条) ======
        self.header_frame = QFrame()
        self.header_layout = QHBoxLayout(self.header_frame)
        self.header_layout.setContentsMargins(15, 8, 15, 8)

        self.idx_lbl = QLabel(f"#{self.index+1}")
        self.risk_lbl = QLabel(f"{int(self.ai_rate)}% {self.verdict}")
        
        # 生成简略摘要
        preview_text = self.content[:30].replace("\n", " ") + ("..." if len(self.content) > 30 else "")
        self.preview_lbl = QLabel(preview_text)
        self.preview_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.arrow_lbl = QLabel("▼")

        self.header_layout.addWidget(self.idx_lbl)
        self.header_layout.addWidget(self.risk_lbl)
        self.header_layout.addWidget(self.preview_lbl)
        self.header_layout.addWidget(self.arrow_lbl)

        # ====== 内容区域 (点击展开后显示的长文本框) ======
        self.content_frame = QFrame()
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(20, 15, 20, 15)
        self.content_layout.setAlignment(Qt.AlignTop) 
        
        # 使用 HTML 标签为文本设置一点行距，更加美观
        styled_text = f"<div style='line-height: 1.6;'>{html.escape(self.content)}</div>"
        self.full_text_lbl = QLabel(styled_text)
        self.full_text_lbl.setWordWrap(True) # 允许长句子自己断行
        self.full_text_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse) # 允许选中文本复制
        
        self.content_layout.addWidget(self.full_text_lbl)
        
        # 视口裁切层，完美防止动画抽搐
        # 这里使用一个高度从 0 慢慢变到目标高度的 QScrollArea 作为容器
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
        self.anim_wrapper.setMaximumHeight(0) # 初始处于完全收起状态
        
        self.anim = QPropertyAnimation(self.anim_wrapper, b"maximumHeight")
        self.anim.setDuration(300)
        self.anim.setEasingCurve(QEasingCurve.OutCubic) 
        self.anim.finished.connect(self._on_anim_finished)

        self.update_style()

    def _remove_opacity_effect(self):
        # 为了保证字体清晰不糊，入场动画结束后必须卸载 QGraphicsOpacityEffect
        self.setGraphicsEffect(None)
        self.update()

    def update_colors(self):
        """根据分数初始化对应判定的颜色色系"""
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
        """被外部或自己调用来应用当前的主题样式"""
        self.update_colors()
        
        self.idx_lbl.setStyleSheet(f"color: {Theme.get('text_sub')}; font-weight: bold;")
        self.risk_lbl.setStyleSheet(f"color: {self.header_text_color}; font-weight: 900; font-size: 11pt;")
        self.preview_lbl.setStyleSheet(f"color: {Theme.get('text_sub')}; margin-left: 10px;")
        self.arrow_lbl.setStyleSheet(f"color: {Theme.get('text_sub')};")
        self.full_text_lbl.setStyleSheet(f"color: {Theme.get('text_main')}; font-size: 10.5pt;")
        
        is_collapsing = (not self.is_expanded) and (self.anim.state() == QPropertyAnimation.Running)
        use_expanded_style = self.is_expanded or is_collapsing

        if use_expanded_style:
            # 展开时：上下卡片拼接，底边无圆角，合并起来像一个完整的信封
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
            # 收起时：悬浮会有微微提亮，左侧平时透明，悬停时会有色带
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
        self.content_frame.setFixedWidth(w) # 强行赋予宽度以便它开始折行计算
        self.content_frame.layout().activate() # 强制布局刷新
        self.content_frame.adjustSize() # 自适应包裹
        target_h = self.content_frame.height() # 量一下此时多高
        
        # 解除强绑定，恢复随窗口缩放响应的特性
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
        # 如果窗口在展开状态下被拉伸，文字可能会重排变成更多/更少行
        # 这里自动重新计算并无缝更新紧凑高度
        if self.is_expanded and self.anim.state() != QPropertyAnimation.Running:
            target_h = self.get_target_height()
            self.anim_wrapper.setMinimumHeight(target_h)
            self.anim_wrapper.setMaximumHeight(target_h)

    def mousePressEvent(self, event):
        # 只要点击了该条目块，不管是头部还是内容，都触发折叠和通知左边高亮
        self.toggle_expand()
        self.request_highlight.emit(self.content)
        super().mousePressEvent(event)

    def toggle_expand(self):
        """触发展开或者收起的拉伸缩放动画"""
        if self.anim.state() == QPropertyAnimation.Running:
            return 

        self.is_expanded = not self.is_expanded
        
        if self.is_expanded:
            self.anim_wrapper.setMinimumHeight(0) # 释放最小约束以供动画运行
            self.anim_wrapper.setMaximumHeight(0) 
            self.anim_wrapper.show()
            self.preview_lbl.hide() # 藏起简略摘要
            self.arrow_lbl.setText("▲")
            
            target_h = self.get_target_height() # 计算即将拉伸到的目标高度
            
            self.anim.stop()
            self.anim.setStartValue(0)
            self.anim.setEndValue(target_h)
            self.anim.start()
            
            self.expanded.emit(self.index) # 通知外侧的手风琴管理器去关闭其他的
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
        """给外部提供的接口（比如手风琴管理器）用于强制收起"""
        if self.is_expanded != expanded:
            self.toggle_expand()


# ================= 新增：全景热力指纹弹窗及其子组件 =================
class DetailedHeatmapRow(QFrame):
    """弹窗列表里的独立子行"""
    clicked = Signal(int)

    def __init__(self, index, content, ai_rate, is_ignored=False, parent=None):
        super().__init__(parent)
        self.index = index
        self.content = content
        self.ai_rate = ai_rate
        self.is_ignored = is_ignored
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(50) # 固定高度，绝不拥挤

        if self.is_ignored:
            self.accent_color = Theme.ACCENT_GRAY
            self.verdict = "过短忽略"
        elif self.ai_rate < 30:
            self.accent_color = Theme.ACCENT_GREEN
            self.verdict = "人类文本"
        elif self.ai_rate < 60:
            self.accent_color = Theme.ACCENT_YELLOW
            self.verdict = "疑似混写"
        else:
            self.accent_color = Theme.ACCENT_RED
            self.verdict = "疑似生成"

        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 5, 15, 5)

        idx_lbl = QLabel(f"#{self.index+1}")
        idx_lbl.setFixedWidth(40)
        idx_lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))

        preview_text = self.content[:30].replace("\n", " ") + ("..." if len(self.content) > 30 else "")
        self.preview_lbl = QLabel(preview_text)

        score_lbl = QLabel(f"{int(self.ai_rate)}% {self.verdict}" if not self.is_ignored else self.verdict)
        score_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        score_lbl.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))

        layout.addWidget(idx_lbl)
        layout.addWidget(self.preview_lbl, 1)
        layout.addWidget(score_lbl)

        self.idx_lbl = idx_lbl
        self.score_lbl = score_lbl

        self.update_style()

    def update_style(self):
        bg_color = Theme.get('bg_card')
        border_color = Theme.get('border')
        self.setStyleSheet(f"""
            DetailedHeatmapRow {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-left: 4px solid {self.accent_color};
                border-radius: 8px;
            }}
            DetailedHeatmapRow:hover {{
                background-color: {QColor(bg_color).lighter(105).name()};
            }}
        """)
        self.idx_lbl.setStyleSheet(f"color: {Theme.get('text_sub')};")
        self.preview_lbl.setStyleSheet(f"color: {Theme.get('text_main')};")
        self.score_lbl.setStyleSheet(f"color: {self.accent_color};")

    def mousePressEvent(self, event):
        self.clicked.emit(self.index) # 点击列表直接触发外层滚动信号
        super().mousePressEvent(event)


class DetailedHeatmapWindow(QDialog):
    """带筛选功能的独立弹窗组件"""
    request_scroll = Signal(int)

    def __init__(self, paragraphs, parent=None):
        super().__init__(parent)
        self.setWindowTitle("全景热力指纹分析")
        self.resize(550, 700)
        self.paragraphs = paragraphs
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
        
        # 弹窗丝滑淡入动画
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
        self.anim.start() # 每次显示时触发淡入动画

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 头部标题
        self.header_lbl = QLabel("🔍 全景段落过滤视图")
        self.header_lbl.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        layout.addWidget(self.header_lbl)

        # 多功能筛选面板
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

        # 列表滚动区
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.container = QWidget()
        self.list_layout = QVBoxLayout(self.container)
        self.list_layout.setAlignment(Qt.AlignTop)
        self.list_layout.setSpacing(10)
        self.scroll.setWidget(self.container)

        layout.addWidget(self.scroll)

        # 挂载所有排版清晰的单行卡片
        for i, p in enumerate(self.paragraphs):
            row = DetailedHeatmapRow(i, p["content"], p["ai_rate"], p.get("is_ignored", False))
            row.clicked.connect(self.request_scroll.emit) # 将子级信号接通向外层发散
            self.list_layout.addWidget(row)
            self.rows.append(row)

    def apply_filter(self):
        """核心勾选筛选逻辑"""
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
        """完全同步主界面的主题调度"""
        t = Theme.COLORS[Theme.CURRENT_MODE]
        self.setStyleSheet(f"""
            QDialog {{ background-color: {t['bg_main']}; color: {t['text_main']}; }}
            QCheckBox {{ color: {t['text_sub']}; font-weight: bold; spacing: 8px; }}
            QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 4px; border: 1px solid {t['border']}; }}
            QCheckBox::indicator:checked {{ background-color: #2D79FF; border-color: #2D79FF; image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIzIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwb2x5bGluZSBwb2ludHM9IjIwIDYgOSAxNyA0IDEyIi8+PC9zdmc+); }}
        """)
        self.header_lbl.setStyleSheet(f"color: {t['text_main']};")
        self.scroll.setStyleSheet("QScrollArea { background: transparent; border: none; } QScrollArea > QWidget > QWidget { background: transparent; }")
        for row in self.rows:
            row.update_style()