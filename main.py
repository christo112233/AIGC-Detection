import sys
import os
import torch
import random
import math

# --- 编码检测库安全导入 ---
try:
    import chardet
    HAS_CHARDET = True
except ImportError:
    HAS_CHARDET = False

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTextEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QWidget, QLabel, QFrame,
    QFileDialog, QMessageBox, QSplitter, QGraphicsDropShadowEffect
)
from PySide6.QtCore import (
    Qt, Signal, QThread, QSize, Property, QPropertyAnimation, QEasingCurve, QRectF, QPointF
)
from PySide6.QtGui import (
    QColor, QLinearGradient, QPainter, QFont, QTextCursor, QTextCharFormat, QPen, QPolygonF, QBrush
)

# --- Word 处理库安全导入 ---
try:
    import docx
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

# ---------------------- 自定义 UI 组件 ----------------------

class GlowButton(QPushButton):
    """具有悬停发光效果的自定义按钮"""
    def __init__(self, text, color="#0071E3", parent=None):
        super().__init__(text, parent)
        self._base_color = color
        self.setFixedHeight(45)
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(QFont("Microsoft YaHei UI", 10, QFont.Weight.Bold))
        self.update_style()

    def update_style(self, hover=False):
        color = QColor(self._base_color).lighter(115).name() if hover else self._base_color
        self.setStyleSheet(f"""
            QPushButton {{
                background: {color};
                color: white;
                border-radius: 12px;
                padding: 0 20px;
                border: none;
            }}
        """)

    def enterEvent(self, event):
        self.update_style(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update_style(False)
        super().leaveEvent(event)

class AIGCGaugeWidget(QWidget):
    """自定义 AIGC 概率仪表盘 (布局微调版)"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(240) # 减小高度，腾出空间给下方列表
        self._value = 0
        self.animation = QPropertyAnimation(self, b"value")
        self.animation.setDuration(1500)
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

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        side = min(width, height * 1.5)
        
        # 调整中心点，稍微靠下，留出上方空间
        painter.translate(width / 2, height * 0.9)
        painter.scale(side / 320, side / 320)

        # 1. 绘制顶部说明文字 (进一步上移至 -160，避免贴近圆环)
        painter.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        painter.setPen(QColor(160, 160, 160))
        painter.drawText(QRectF(-100, -160, 200, 30), Qt.AlignCenter, "AIGC 疑似度概率")

        # 2. 轨道底色
        rect = QRectF(-110, -110, 220, 220)
        pen = QPen(QColor(45, 45, 50), 20, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, 180 * 16, -180 * 16)

        # 3. 进度条
        color = self.get_color_for_value(self._value)
        grad_pen = QPen(color, 20, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(grad_pen)
        span_angle = -(self._value / 100.0) * 180 * 16
        painter.drawArc(rect, 180 * 16, span_angle)

        # 4. 数值显示
        painter.setPen(QColor("white"))
        painter.setFont(QFont("Segoe UI", 36, QFont.Bold))
        painter.drawText(QRectF(-100, -75, 200, 60), Qt.AlignCenter, f"{int(self._value)}%")

        # 5. 绘制指针
        painter.save()
        angle = (self._value / 100.0) * 180 - 90
        painter.rotate(angle)
        pointer = QPolygonF([QPointF(-6, 0), QPointF(6, 0), QPointF(0, -98)])
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor("white")))
        painter.drawPolygon(pointer)
        painter.setBrush(QBrush(QColor("#1E1E24")))
        painter.setPen(QPen(QColor("white"), 2))
        painter.drawEllipse(-8, -8, 16, 16)
        painter.restore()

    def get_color_for_value(self, val):
        if val < 30: return QColor("#30D158")
        if val < 60: return QColor("#FFD60A")
        return QColor("#FF453A")

class DragTextEdit(QTextEdit):
    """支持拖拽的编辑器"""
    file_dropped = Signal(str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.accept()
        else: event.ignore()
    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if os.path.splitext(path)[1].lower() in ['.txt', '.docx']:
                self.file_dropped.emit(path)

# ---------------------- 核心检测线程 ----------------------

class AIGCDetectionThread(QThread):
    progress_signal = Signal(int)
    result_signal = Signal(dict)
    status_signal = Signal(str)

    def __init__(self, text):
        super().__init__()
        self.text = text
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.model_path = self._find_valid_path()

    def _find_valid_path(self):
        paths = [os.path.join(self.base_dir, "AIGC_Model"), "./AIGC_Model"]
        for p in paths:
            if os.path.exists(p) and os.path.exists(os.path.join(p, "config.json")): return p
        return None

    def run(self):
        try:
            if not self.model_path:
                self.status_signal.emit("本地模型未找到，启动演示模式...")
                self._run_mock()
                return

            from transformers import pipeline, AutoModelForSequenceClassification, AutoTokenizer
            device = 0 if torch.cuda.is_available() else -1
            self.progress_signal.emit(10)
            
            tokenizer = AutoTokenizer.from_pretrained(self.model_path, local_files_only=True)
            model = AutoModelForSequenceClassification.from_pretrained(self.model_path, local_files_only=True)
            detector = pipeline("text-classification", model=model, tokenizer=tokenizer, device=device)
            self.progress_signal.emit(30)

            paragraphs = [p for p in self.text.split("\n") if p.strip()]
            results = []
            total_score = 0
            total_chars = 0

            for idx, para in enumerate(paragraphs):
                self.status_signal.emit(f"深度指纹分析中... {idx+1}/{len(paragraphs)}")
                inference = detector(para[:512])[0]
                label = inference['label'].lower()
                score = inference['score']
                ai_rate = round(score * 100 if any(x in label for x in ['fake', 'ai', '1']) else (1 - score) * 100, 2)
                
                results.append({"content": para, "ai_rate": ai_rate})
                total_score += (ai_rate * len(para))
                total_chars += len(para)
                self.progress_signal.emit(30 + int(((idx + 1) / len(paragraphs)) * 65))

            avg_rate = round(total_score / total_chars, 2) if total_chars > 0 else 0
            self.result_signal.emit({"total_ai_rate": avg_rate, "paragraphs": results, "is_real_model": True})

        except Exception as e:
            self.result_signal.emit({"error": f"推理引擎异常: {str(e)}"})

    def _run_mock(self):
        paragraphs = [p for p in self.text.split("\n") if p.strip()]
        results = []
        total_score = 0
        total_chars = 0
        for idx, para in enumerate(paragraphs):
            QThread.msleep(150)
            ai_rate = round(random.uniform(5, 95), 2)
            results.append({"content": para, "ai_rate": ai_rate})
            total_score += (ai_rate * len(para))
            total_chars += len(para)
            self.progress_signal.emit(10 + int(((idx + 1) / len(paragraphs)) * 85))
        avg = round(total_score / total_chars, 2) if total_chars > 0 else 0
        self.result_signal.emit({"total_ai_rate": avg, "paragraphs": results, "is_real_model": False})

# ---------------------- 主窗口 ----------------------

class AIGCSentinel(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AIGC 哨兵 - 智能文本检测专业版")
        self.resize(1280, 920)
        self.init_ui()
        self.check_model_status()

    def init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(30, 30, 30, 30); self.main_layout.setSpacing(20)

        # 头部区域
        header = QHBoxLayout()
        title_v = QVBoxLayout()
        title = QLabel("AIGC 文本溯源哨兵")
        title.setStyleSheet("color: white; font-size: 26pt; font-weight: 900; border:none; background:transparent;")
        title_v.addWidget(title)
        
        sub_desc = QLabel("基于深度学习的语义指纹识别系统")
        sub_desc.setStyleSheet("color: #777; font-size: 10pt; border:none; background:transparent;")
        title_v.addWidget(sub_desc)
        header.addLayout(title_v); header.addStretch()
        
        self.import_btn = GlowButton("📁 导入文件", "#2A2A2E")
        self.clear_btn = GlowButton("🗑️ 清空内容", "#2A2A2E")
        self.detect_btn = GlowButton("⚡ 立即检测", "#0071E3")
        
        self.import_btn.clicked.connect(self.import_file)
        self.clear_btn.clicked.connect(self.clear_content)
        self.detect_btn.clicked.connect(self.run_detection)
        
        header.addWidget(self.import_btn)
        header.addWidget(self.clear_btn)
        header.addWidget(self.detect_btn)
        self.main_layout.addLayout(header)

        # 主内容区 (Splitter)
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(12)
        self.splitter.setStyleSheet("QSplitter::handle { background: transparent; }")
        
        # 左侧：输入卡片
        in_card = self.create_card("📝 待检测原文内容")
        self.input_edit = DragTextEdit()
        self.input_edit.file_dropped.connect(self.handle_file_content)
        self.input_edit.setPlaceholderText("可直接拖入 .txt 或 .docx 文件，或手动粘贴文本...")
        self.input_edit.setStyleSheet(self.get_edit_style("#0071E3"))
        in_card.layout().addWidget(self.input_edit)

        # 右侧：输出卡片 (垂直分割)
        out_card = QFrame()
        out_card.setStyleSheet("background: #1E1E24; border: 1px solid #333; border-radius: 18px;")
        out_layout = QVBoxLayout(out_card)
        out_layout.setContentsMargins(18, 18, 18, 18)
        
        # 仪表盘部分
        self.gauge = AIGCGaugeWidget()
        out_layout.addWidget(self.gauge)
        
        line = QFrame(); line.setFrameShape(QFrame.HLine); line.setStyleSheet("background: #333;"); line.setFixedHeight(1)
        out_layout.addWidget(line)
        
        lbl_detail = QLabel("🔍 段落级溯源细节:")
        lbl_detail.setStyleSheet("color: #999; font-size: 9pt; border: none; margin-top: 10px; background:transparent;")
        out_layout.addWidget(lbl_detail)
        
        # 溯源细节列表部分
        self.output_view = QTextEdit()
        self.output_view.setReadOnly(True)
        self.output_view.setStyleSheet(self.get_edit_style("#30D158"))
        out_layout.addWidget(self.output_view)
        
        # 设置拉伸因子：让仪表盘占 1 份，列表占 3 份
        out_layout.setStretch(0, 1) # 仪表盘
        out_layout.setStretch(3, 3) # 列表 (索引对应组件位置)

        self.splitter.addWidget(in_card); self.splitter.addWidget(out_card)
        self.main_layout.addWidget(self.splitter, stretch=1)

        # 底部状态栏
        self.status_bar = QFrame(); self.status_bar.setFixedHeight(45); self.status_bar.setStyleSheet("background: #16161D; border-radius: 12px;")
        sb_layout = QHBoxLayout(self.status_bar)
        
        self.model_status_lbl = QLabel("● 引擎状态检测中...")
        self.model_status_lbl.setStyleSheet("color: #888; background:transparent; font-weight: bold; padding-left: 5px;")
        
        self.status_lbl = QLabel("● 系统就绪"); self.status_lbl.setStyleSheet("color: #30D158; background:transparent;")
        
        self.prog_bar = QFrame(); self.prog_bar.setFixedWidth(300); self.prog_bar.setFixedHeight(6); self.prog_bar.setStyleSheet("background: #222; border-radius: 3px;")
        self.prog_fill = QFrame(self.prog_bar); self.prog_fill.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0071E3, stop:1 #0A84FF); border-radius: 3px;")
        self.prog_fill.setGeometry(0, 0, 0, 6)
        
        sb_layout.addWidget(self.model_status_lbl)
        sb_layout.addStretch()
        sb_layout.addWidget(self.status_lbl)
        sb_layout.addWidget(self.prog_bar)
        self.main_layout.addWidget(self.status_bar)

    def check_model_status(self):
        """探测本地模型是否存在并更新 UI 提示"""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(base_dir, "AIGC_Model")
        
        if os.path.exists(model_path) and os.path.exists(os.path.join(model_path, "config.json")):
            self.model_status_lbl.setText("● 本地推理引擎已就绪")
            self.model_status_lbl.setStyleSheet("color: #30D158; background:transparent; font-weight: bold;")
        else:
            self.model_status_lbl.setText("⚠️ 未检测到本地模型 (演示模式)")
            self.model_status_lbl.setStyleSheet("color: #FF453A; background:transparent; font-weight: bold;")

    def create_card(self, title_text):
        card = QFrame()
        card.setStyleSheet("background: #1E1E24; border: 1px solid #333; border-radius: 18px;")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        lbl = QLabel(title_text); lbl.setStyleSheet("color: white; font-weight: 800; border: none; font-size: 11pt; background:transparent;")
        layout.addWidget(lbl)
        return card

    def get_edit_style(self, color):
        return f"""
            QTextEdit {{ 
                background: #16161A; color: #DDD; border: 1px solid #2A2A2E; 
                border-radius: 12px; padding: 15px; font-size: 11pt; 
                font-family: 'Segoe UI', 'Microsoft YaHei'; 
            }} 
            QTextEdit:focus {{ border: 1px solid {color}; }}
        """

    def paintEvent(self, e):
        p = QPainter(self); p.fillRect(self.rect(), QColor(15, 15, 18))

    def clear_content(self):
        self.input_edit.clear()
        self.output_view.clear()
        self.gauge.setValue(0)
        self.prog_fill.setFixedWidth(0)
        self.status_lbl.setText("● 内容已清空")

    def handle_file_content(self, path):
        ext = os.path.splitext(path)[1].lower()
        try:
            if ext == '.txt':
                with open(path, 'rb') as f: raw_data = f.read()
                encoding = 'utf-8'
                if HAS_CHARDET:
                    detect = chardet.detect(raw_data)
                    encoding = detect['encoding'] if detect['confidence'] > 0.6 else 'utf-8'
                try:
                    content = raw_data.decode(encoding)
                except:
                    try:
                        content = raw_data.decode('gbk')
                    except:
                        content = raw_data.decode('utf-8', errors='ignore')
                self.input_edit.setPlainText(content)
            elif ext == '.docx':
                if not HAS_DOCX:
                    QMessageBox.warning(self, "依赖缺失", "解析 Word 需要安装: pip install python-docx")
                    return
                doc = docx.Document(path)
                self.input_edit.setPlainText("\n".join([p.text for p in doc.paragraphs if p.text.strip()]))
            self.status_lbl.setText(f"● 已成功载入: {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, "文件读取错误", f"详情: {str(e)}")

    def import_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择待检文档", "", "文档文件 (*.txt *.docx)")
        if path: self.handle_file_content(path)

    def run_detection(self):
        text = self.input_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "输入为空", "请先输入文本或导入文档再进行检测。")
            return
        self.detect_btn.setEnabled(False)
        self.output_view.clear()
        self.gauge.setValue(0)
        self.thread = AIGCDetectionThread(text)
        self.thread.status_signal.connect(lambda s: self.status_lbl.setText(f"○ {s}"))
        self.thread.progress_signal.connect(lambda v: self.prog_fill.setFixedWidth(int(v * 3)))
        self.thread.result_signal.connect(self.process_results)
        self.thread.finished.connect(lambda: self.detect_btn.setEnabled(True))
        self.thread.start()

    def process_results(self, res):
        if "error" in res:
            QMessageBox.critical(self, "检测失败", res["error"])
            return
        total_rate = res["total_ai_rate"]
        self.gauge.setValue(total_rate)
        cursor = self.output_view.textCursor()
        for p in res["paragraphs"]:
            rate = p["ai_rate"]
            color = "#30D158" if rate <= 30 else "#FFD60A" if rate < 60 else "#FF453A"
            fmt = QTextCharFormat(); fmt.setForeground(QColor("#CCC")); fmt.setFontPointSize(10)
            text_preview = p["content"][:220] + ("..." if len(p["content"]) > 220 else "")
            cursor.insertText(text_preview, fmt)
            tag = QTextCharFormat(); tag.setForeground(QColor(color)); tag.setFontWeight(QFont.Bold)
            cursor.insertText(f" [AI率: {rate}%]\n\n", tag)
        self.status_lbl.setText("● 分析检测报告已生成")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei", 9))
    window = AIGCSentinel()
    window.show()
    sys.exit(app.exec())