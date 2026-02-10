import os
import sys
import re
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import math

# 尝试导入拖拽库
try:
    import windnd

    WINDND_SUPPORT = True
except ImportError:
    WINDND_SUPPORT = False

# 尝试导入 docx 库
try:
    from docx import Document

    DOCX_SUPPORT = True
except ImportError:
    DOCX_SUPPORT = False


# --- 核心：PyInstaller 打包路径自适应函数 ---
def get_resource_path(relative_path):
    """
    自适应获取资源路径，确保在开发环境、_internal 文件夹内、exe 同级目录均能找到模型
    """
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 打包后的临时解压根目录
        base_dir = sys._MEIPASS
    else:
        # 普通 Python 开发环境路径
        base_dir = os.path.dirname(os.path.abspath(__file__))

    # 定义可能的搜索路径优先级
    possible_paths = [
        os.path.join(base_dir, relative_path),  # 1. 根目录
        os.path.join(base_dir, "_internal", relative_path),  # 2. _internal 内部 (新版默认)
        os.path.join(os.path.dirname(sys.executable), relative_path),  # 3. exe 同级目录
        os.path.abspath(relative_path)  # 4. 当前工作目录
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return path

    # 如果都没找到，返回基于 base_dir 的默认路径（后续加载会抛出具体错误供排查）
    return os.path.join(base_dir, relative_path)


# ================= 设置区域 =================
# 自动寻找模型文件夹 AIGC_Model
LOCAL_MODEL_PATH = get_resource_path("AIGC_Model")


# ===========================================

class ModernButton(tk.Canvas):
    """高级圆角立体按钮 - 具有平滑物理过渡动效"""

    def __init__(self, parent, text, command, width=220, height=50, color="#0071E3", text_color="white", font_size=11):
        super().__init__(parent, width=width, height=height + 10, bg=parent["bg"], highlightthickness=0, cursor="hand2")
        self.command = command
        self.base_color = color
        self.shadow_color = self.get_shadow_color(color)
        self.text_color = text_color
        self.text_content = text
        self.base_width = width
        self.base_height = height
        self.font_size = font_size
        self.scale = 1.0

        # 动画状态
        self.press_offset = 0.0  # 0.0 (未按下) 到 1.0 (完全按下)
        self.target_press = 0.0
        self.is_disabled = False
        self.anim_id = None

        self.render()

        self.bind("<Button-1>", self.on_press)
        self.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<Enter>", self.on_hover)
        self.bind("<Leave>", self.on_leave)

    def get_shadow_color(self, hex_color):
        hex_color = hex_color.lstrip('#')
        rgb = tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
        darker_rgb = tuple(max(0, int(c * 0.7)) for c in rgb)
        return '#%02x%02x%02x' % darker_rgb

    def on_hover(self, e):
        if not self.is_disabled:
            self.itemconfig("bg", fill=self.adjust_brightness(self.base_color, 1.1))

    def on_leave(self, e):
        if not self.is_disabled:
            self.itemconfig("bg", fill=self.base_color)

    def adjust_brightness(self, hex_color, factor):
        hex_color = hex_color.lstrip('#')
        rgb = [int(hex_color[i:i + 2], 16) for i in (0, 2, 4)]
        new_rgb = [min(255, int(c * factor)) for c in rgb]
        return '#%02x%02x%02x' % tuple(new_rgb)

    def animate_press(self):
        diff = self.target_press - self.press_offset
        if abs(diff) > 0.01:
            self.press_offset += diff * 0.3
            self.render()
            self.anim_id = self.after(10, self.animate_press)
        else:
            self.press_offset = self.target_press
            self.render()
            self.anim_id = None

    def on_press(self, event):
        if self.is_disabled: return
        if self.anim_id: self.after_cancel(self.anim_id)
        self.target_press = 1.0
        self.animate_press()

    def on_release(self, event):
        if self.is_disabled: return
        if self.anim_id: self.after_cancel(self.anim_id)
        self.target_press = 0.0
        self.animate_press()
        self.after(80, self.command)

    def set_text(self, new_text):
        self.text_content = new_text
        self.render()

    def set_state(self, disabled=False):
        self.is_disabled = disabled
        self.config(cursor="arrow" if disabled else "hand2")
        self.render()

    def render(self):
        self.delete("all")
        w, h = int(self.base_width * self.scale), int(self.base_height * self.scale)
        r = 16 * self.scale
        max_offset = 6 * self.scale
        current_offset = self.press_offset * max_offset

        current_bg = self.base_color if not self.is_disabled else "#A1A1A6"
        current_shadow = self.shadow_color if not self.is_disabled else "#8E8E93"

        self.draw_round_rect(0, max_offset, w, h + max_offset, r, fill=current_shadow, tags="shadow")
        self.draw_round_rect(0, current_offset, w, h + current_offset, r, fill=current_bg, tags="bg")
        self.create_text(w / 2, h / 2 + current_offset, text=self.text_content, fill=self.text_color,
                         font=("Microsoft YaHei UI", int(self.font_size * self.scale), "bold"), tags="txt")

    def draw_round_rect(self, x, y, w, h, r, **kwargs):
        points = [x + r, y, x + w - r, y, x + w, y, x + w, y + r, x + w, y + h - r, x + w, y + h, x + w - r, y + h,
                  x + r, y + h, x, y + h, x, y + h - r, x, y + r, x, y]
        return self.create_polygon(points, **kwargs, smooth=True)

    def update_size(self, scale):
        self.scale = scale
        self.config(width=int(self.base_width * scale), height=int((self.base_height + 10) * scale))
        self.render()

    def update_theme(self, bg_color, color=None, text_color=None):
        self.config(bg=bg_color)
        if color:
            self.base_color = color
            self.shadow_color = self.get_shadow_color(color)
        if text_color: self.text_color = text_color
        self.render()


class ThemeSwitch(tk.Canvas):
    def __init__(self, parent, command):
        super().__init__(parent, width=64, height=32, bg=parent["bg"], highlightthickness=0, cursor="hand2")
        self.command = command
        self.is_dark = False
        self.pos = 4
        self.anim_id = None
        self.bind("<Button-1>", self.toggle)
        self.render()

    def toggle(self, event=None):
        self.is_dark = not self.is_dark
        if self.anim_id: self.after_cancel(self.anim_id)
        self.animate_switch()
        self.command(self.is_dark)

    def animate_switch(self):
        target = 36 if self.is_dark else 4
        step = (target - self.pos) / 4
        if abs(self.pos - target) > 0.5:
            self.pos += step
            self.render()
            self.anim_id = self.after(15, self.animate_switch)
        else:
            self.pos = target
            self.render()
            self.anim_id = None

    def render(self):
        self.delete("all")
        bg = "#3A3A3C" if self.is_dark else "#E5E5E7"
        circle = "#FFFFFF" if not self.is_dark else "#0A84FF"
        self.draw_round_rect(0, 0, 64, 32, 16, fill=bg)
        self.draw_round_rect(self.pos, 4, self.pos + 24, 28, 12, fill=circle)

    def draw_round_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2, x1, y2, x1,
                  y2 - r, x1, y1 + r, x1, y1]
        return self.create_polygon(points, **kwargs, smooth=True)


class AIGCDetectorPro:
    def __init__(self, root):
        self.root = root
        self.root.title("AIGC 哨兵 - 深度智能检测引擎")

        self.ref_width = 1360
        self.ref_height = 900

        self.is_dark = False
        self.fixed_input_bg = "#1C1C1E"
        self.fixed_input_fg = "#F5F5F7"
        self.fixed_border_deep = "#2C2C2E"

        self.themes = {
            "light": {
                "bg": "#F5F5F7", "sidebar": "#FFFFFF", "accent": "#0071E3",
                "text": "#1D1D1F", "text_sub": "#6E6E73", "border": "#D2D2D7",
                "card": "#FFFFFF", "reset": "#E8E8ED", "reset_text": "#1D1D1F", "gauge_bg": "#F2F2F7",
                "shadow": "#E0E0E6"
            },
            "dark": {
                "bg": "#000000", "sidebar": "#1C1C1E", "accent": "#0A84FF",
                "text": "#F5F5F7", "text_sub": "#86868B", "border": "#323234",
                "card": "#1C1C1E", "reset": "#2C2C2E", "reset_text": "#F5F5F7", "gauge_bg": "#2C2C2E",
                "shadow": "#0F0F0F"
            }
        }
        self.current_colors = self.themes["light"].copy()
        self.colors = self.themes["light"]
        self.safe_color, self.warn_color, self.danger_color = "#34C759", "#FF9500", "#FF3B30"

        self.setup_window()
        self.init_variables()
        self.build_ui()
        self.setup_text_tags()
        self.setup_drag_and_drop()

        self.root.bind("<Configure>", self.on_resize)
        threading.Thread(target=self.load_model, daemon=True).start()

    def setup_window(self):
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass
        self.root.geometry(f"{self.ref_width}x{self.ref_height}")
        self.root.configure(bg=self.colors["bg"])

    def init_variables(self):
        self.model = None
        self.tokenizer = None
        self.is_ready = False
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.display_score = 0.0
        self.target_score = 0.0
        self.gauge_anim_id = None
        self.analysis_running = False
        self.transition_steps = 10
        self.is_transitioning = False
        self.resize_after_id = None  # 用于防抖并确保布局渲染完成

    def build_ui(self):
        self.top_bar = tk.Frame(self.root, bg=self.colors["sidebar"], height=80)
        self.top_bar.pack(fill="x")
        self.top_bar.pack_propagate(False)

        self.logo_label = tk.Label(self.top_bar, text="AIGC 哨兵系统", font=("Microsoft YaHei UI", 20, "bold"),
                                   fg=self.colors["text"], bg=self.colors["sidebar"])
        self.logo_label.pack(side="left", padx=50)

        self.switch_frame = tk.Frame(self.top_bar, bg=self.colors["sidebar"])
        self.switch_frame.pack(side="right", padx=50)

        self.theme_switch = ThemeSwitch(self.switch_frame, self.toggle_theme)
        self.theme_switch.pack(side="right")

        self.mode_label = tk.Label(self.switch_frame, text="深色模式", font=("Microsoft YaHei UI", 9, "bold"),
                                   fg=self.colors["text_sub"], bg=self.colors["sidebar"])
        self.mode_label.pack(side="right", padx=15)

        self.status_text = tk.Label(self.top_bar, text="引擎待命", fg=self.colors["text_sub"],
                                    bg=self.colors["sidebar"], font=("Microsoft YaHei UI", 10, "bold"))
        self.status_text.pack(side="right", padx=30)

        self.container = tk.Frame(self.root, bg=self.colors["bg"])
        self.container.pack(fill="both", expand=True, padx=50, pady=30)

        self.left_col = tk.Frame(self.container, bg=self.colors["bg"])
        self.left_col.pack(side="left", fill="both", expand=True)

        self.editor_shadow = tk.Frame(self.left_col, bg=self.colors["shadow"], padx=1, pady=1)
        self.editor_shadow.pack(fill="both", expand=True, pady=(0, 25))

        self.editor_card = tk.Frame(self.editor_shadow, bg=self.fixed_input_bg, highlightthickness=1,
                                    highlightbackground=self.colors["border"])
        self.editor_card.pack(fill="both", expand=True)

        self.editor_header = tk.Frame(self.editor_card, bg=self.fixed_input_bg, padx=25, pady=15)
        self.editor_header.pack(fill="x")

        self.editor_label = tk.Label(self.editor_header, text="待检测内容", font=("Microsoft YaHei UI", 10, "bold"),
                                     fg="#86868B", bg=self.fixed_input_bg)
        self.editor_label.pack(side="left")

        self.btn_import = ModernButton(self.editor_header, "导入文件", self.import_document,
                                       width=120, height=34, color=self.colors["accent"], font_size=9)
        self.btn_import.pack(side="right")

        self.text_inner_shadow = tk.Frame(self.editor_card, bg=self.fixed_border_deep, height=1)
        self.text_inner_shadow.pack(fill="x")

        self.text_input = scrolledtext.ScrolledText(self.editor_card, font=("PingFang SC", 15),
                                                    bg=self.fixed_input_bg, fg=self.fixed_input_fg,
                                                    relief="flat", padx=30, pady=20,
                                                    insertbackground="#0A84FF",
                                                    undo=True)
        self.text_input.pack(fill="both", expand=True)

        self.scan_action_frame = tk.Frame(self.left_col, bg=self.colors["bg"])
        self.scan_action_frame.pack(fill="x", pady=(5, 0))

        self.progress_container = tk.Frame(self.scan_action_frame, bg=self.colors["bg"])
        self.progress_bar_bg = tk.Frame(self.progress_container, bg=self.colors["gauge_bg"], height=8)
        self.progress_bar_bg.pack(side="left", fill="x", expand=True, padx=(0, 15))
        self.progress_bar_fill = tk.Frame(self.progress_bar_bg, bg=self.colors["accent"], width=0, height=8)
        self.progress_bar_fill.place(x=0, y=0)
        self.progress_percent_label = tk.Label(self.progress_container, text="0%", font=("Helvetica", 10, "bold"),
                                               fg=self.colors["accent"], bg=self.colors["bg"])
        self.progress_percent_label.pack(side="right")

        self.btn_run = ModernButton(self.left_col, "立即开始扫描", self.start_analysis, width=220, height=54, font_size=12)
        self.btn_run.pack(anchor="w", pady=(10, 0))

        self.right_col = tk.Frame(self.container, bg=self.colors["bg"], width=440)
        self.right_col.pack(side="right", fill="both", padx=(50, 0))
        self.right_col.pack_propagate(False)

        self.gauge_shadow = tk.Frame(self.right_col, bg=self.colors["shadow"], padx=1, pady=1)
        self.gauge_shadow.pack(fill="x", pady=(0, 25))

        self.gauge_card = tk.Canvas(self.gauge_shadow, bg=self.colors["card"], highlightthickness=1,
                                    highlightbackground=self.colors["border"], height=340)
        self.gauge_card.pack(fill="x")

        self.detail_label = tk.Label(self.right_col, text="风险评估详情", font=("Microsoft YaHei UI", 10, "bold"),
                                     fg=self.colors["text_sub"], bg=self.colors["bg"])
        self.detail_label.pack(anchor="w", pady=(0, 15))

        self.list_wrap = tk.Frame(self.right_col, bg=self.colors["bg"])
        self.list_wrap.pack(fill="both", expand=True)

        self.results_canvas = tk.Canvas(self.list_wrap, bg=self.colors["bg"], highlightthickness=0)
        self.results_inner = tk.Frame(self.results_canvas, bg=self.colors["bg"])
        self.results_window = self.results_canvas.create_window((0, 0), window=self.results_inner, anchor="nw")

        self.results_canvas.pack(side="left", fill="both", expand=True)

        self.results_canvas.bind("<Enter>", lambda e: self.results_canvas.bind_all("<MouseWheel>", self.on_mousewheel))
        self.results_canvas.bind("<Leave>", lambda e: self.results_canvas.unbind_all("<MouseWheel>"))

        self.results_inner.bind("<Configure>",
                                lambda e: self.results_canvas.configure(scrollregion=self.results_canvas.bbox("all")))

        self.btn_reset = ModernButton(self.right_col, "重置数据", self.reset_interface,
                                      width=180, height=46, color=self.colors["reset"],
                                      text_color=self.colors["reset_text"], font_size=10)
        self.btn_reset.pack(side="right", pady=(20, 0))

    def on_mousewheel(self, event):
        if self.results_canvas.bbox("all")[3] > self.results_canvas.winfo_height():
            self.results_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def setup_text_tags(self):
        scale = self.get_scale()
        fs = int(14 * (scale ** 0.8))
        self.text_input.tag_configure("safe_tag", foreground="#30D158", font=("Microsoft YaHei UI", fs, "bold"))
        self.text_input.tag_configure("warn_tag", foreground="#FF9F0A", font=("Microsoft YaHei UI", fs, "bold"))
        self.text_input.tag_configure("danger_tag", foreground="#FF453A", font=("Microsoft YaHei UI", fs, "bold"))
        self.text_input.tag_configure("active_para", background="#2C2C2E", relief="solid", borderwidth=1)
        self.text_input.tag_raise("active_para")

    def setup_drag_and_drop(self):
        if WINDND_SUPPORT:
            windnd.hook_dropfiles(self.root, func=self.on_file_dropped)

    def on_file_dropped(self, files):
        if not files: return
        file_path = files[0].decode('gbk') if isinstance(files[0], bytes) else files[0]
        self.load_file_to_editor(file_path)

    def load_file_to_editor(self, file_path):
        try:
            content = ""
            ext = os.path.splitext(file_path)[1].lower()
            if ext == '.docx' and DOCX_SUPPORT:
                doc = Document(file_path)
                content = "\n".join([para.text for para in doc.paragraphs])
            elif ext in ['.txt', '.py', '.md', '.c']:
                for encoding in ['utf-8', 'gbk']:
                    try:
                        with open(file_path, 'r', encoding=encoding) as f:
                            content = f.read()
                        break
                    except:
                        continue
            if content.strip():
                self.text_input.delete("1.0", tk.END)
                self.text_input.insert(tk.END, content)
                self.status_text.config(text="文件导入成功", fg=self.safe_color)
        except:
            self.status_text.config(text="加载失败", fg=self.danger_color)

    def toggle_theme(self, is_dark):
        self.is_dark = is_dark
        self.target_colors = self.themes["dark"] if is_dark else self.themes["light"]
        self.start_colors = self.current_colors.copy()
        self.is_transitioning = True
        self.animate_theme_transition(0)

    def animate_theme_transition(self, step):
        if step > self.transition_steps:
            self.is_transitioning = False
            self.current_colors = self.target_colors.copy()
            self.colors = self.current_colors
            self.apply_theme_to_ui()
            return
        factor = step / self.transition_steps
        temp_colors = {}
        for key in self.target_colors:
            temp_colors[key] = self.interpolate_color(self.start_colors[key], self.target_colors[key], factor)
        self.current_colors = temp_colors
        self.colors = temp_colors
        self.apply_theme_to_ui()
        self.root.after(16, lambda: self.animate_theme_transition(step + 1))

    def hex_to_rgb(self, hex_color):
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))

    def rgb_to_hex(self, rgb):
        return '#%02x%02x%02x' % tuple(map(int, rgb))

    def interpolate_color(self, start_hex, end_hex, factor):
        start_rgb = self.hex_to_rgb(start_hex)
        end_rgb = self.hex_to_rgb(end_hex)
        result_rgb = [start + (end - start) * factor for start, end in zip(start_rgb, end_rgb)]
        return self.rgb_to_hex(result_rgb)

    def apply_theme_to_ui(self):
        self.root.configure(bg=self.colors["bg"])
        self.top_bar.config(bg=self.colors["sidebar"])
        self.logo_label.config(bg=self.colors["sidebar"], fg=self.colors["text"])
        self.switch_frame.config(bg=self.colors["sidebar"])
        self.mode_label.config(bg=self.colors["sidebar"], fg=self.colors["text_sub"])
        self.status_text.config(bg=self.colors["sidebar"], fg=self.colors["text_sub"])
        self.container.config(bg=self.colors["bg"])
        self.left_col.config(bg=self.colors["bg"])
        self.right_col.config(bg=self.colors["bg"])
        self.scan_action_frame.config(bg=self.colors["bg"])
        self.progress_container.config(bg=self.colors["bg"])
        self.progress_bar_bg.config(bg=self.colors["gauge_bg"])
        self.progress_bar_fill.config(bg=self.colors["accent"])
        self.progress_percent_label.config(bg=self.colors["bg"], fg=self.colors["accent"])
        self.editor_shadow.config(bg=self.colors["shadow"])
        self.gauge_shadow.config(bg=self.colors["shadow"])
        self.editor_card.config(highlightbackground=self.colors["border"])
        self.gauge_card.config(bg=self.colors["card"], highlightbackground=self.colors["border"])
        self.detail_label.config(bg=self.colors["bg"], fg=self.colors["text_sub"])
        self.list_wrap.config(bg=self.colors["bg"])
        self.results_canvas.config(bg=self.colors["bg"])
        self.results_inner.config(bg=self.colors["bg"])
        self.btn_import.update_theme(self.fixed_input_bg, color=self.colors["accent"])
        self.btn_run.update_theme(self.colors["bg"], color=self.colors["accent"])
        self.btn_reset.update_theme(self.colors["bg"], color=self.colors["reset"], text_color=self.colors["reset_text"])
        self.draw_gauge(self.display_score)
        self.refresh_tiles_theme()

    def refresh_tiles_theme(self):
        scale = self.get_scale()
        for tile_shadow in self.results_inner.winfo_children():
            tile_shadow.config(bg=self.colors["shadow"])
            for tile in tile_shadow.winfo_children():
                tile.config(bg=self.colors["card"], highlightbackground=self.colors["border"])
                self._apply_styles_to_subwidgets(tile, scale)

    def _apply_styles_to_subwidgets(self, widget, scale):
        for child in widget.winfo_children():
            if isinstance(child, tk.Label):
                child.config(bg=self.colors["card"])
                text = child.cget("text")
                if "段落" in text:
                    child.config(fg=self.colors["text_sub"], font=("Microsoft YaHei UI", int(9 * scale), "bold"))
                elif "%" in text:
                    child.config(font=("Helvetica", int(11 * scale), "bold"))
            elif isinstance(child, tk.Frame):
                if child.winfo_height() <= 15:
                    child.config(bg=self.colors["gauge_bg"])
                else:
                    child.config(bg=self.colors["card"])
                self._apply_styles_to_subwidgets(child, scale)

    def on_resize(self, event):
        if event.widget != self.root: return

        # 使用 after 延迟执行，确保 Tkinter 已处理完布局改变
        if self.resize_after_id:
            self.root.after_cancel(self.resize_after_id)

        def delayed_resize():
            # 强制同步空闲任务，获取最新的组件物理尺寸
            self.root.update_idletasks()

            scale = self.get_scale()
            self.text_input.config(font=("PingFang SC", int(15 * (scale ** 0.85))))
            self.setup_text_tags()
            self.btn_import.update_size(scale)
            self.btn_run.update_size(scale)
            self.btn_reset.update_size(scale)

            # 更新结果列表宽度
            canvas_w = self.results_canvas.winfo_width()
            if canvas_w > 1:
                self.results_canvas.itemconfig(self.results_window, width=canvas_w)

            self.refresh_tiles_theme()
            self.draw_gauge(self.display_score)
            self.resize_after_id = None

        self.resize_after_id = self.root.after(5, delayed_resize)

    def import_document(self):
        file_path = filedialog.askopenfilename(filetypes=[("文档文件", "*.txt *.docx")])
        if file_path: self.load_file_to_editor(file_path)

    def draw_gauge(self, score):
        # 强制更新组件状态以获取最新物理尺寸
        self.gauge_card.update_idletasks()

        self.display_score = score
        self.gauge_card.delete("all")

        w = self.gauge_card.winfo_width()
        h = self.gauge_card.winfo_height()

        # 兼容性处理：如果组件尚未完全载入，提供默认参考值
        if w <= 1 or h <= 1:
            w, h = 440, 340

        scale = self.get_scale()
        cx, cy = w / 2, h / 2 + 30 * scale
        r = min(w, h) * 0.32

        # 底色圆弧
        self.gauge_card.create_arc(cx - r, cy - r, cx + r, cy + r, start=-30, extent=240,
                                   width=16 * scale, outline=self.colors["gauge_bg"], style="arc")

        # 进度色圆弧
        color = self.safe_color if score <= 30 else (self.warn_color if score <= 70 else self.danger_color)
        if score > 0:
            self.gauge_card.create_arc(cx - r, cy - r, cx + r, cy + r, start=210, extent=-(score / 100) * 240,
                                       width=16 * scale, outline=color, style="arc")

        # 文字渲染
        font_size = int(min(r * 0.5, 54 * (scale ** 0.6)))
        self.gauge_card.create_text(cx, cy - 15 * scale, text=f"{int(score)}%",
                                    font=("Helvetica", font_size, "bold"), fill=self.colors["text"])
        self.gauge_card.create_text(cx, cy + 45 * scale, text="AI 生成概率",
                                    font=("Microsoft YaHei UI", int(max(9, 10 * scale)), "bold"),
                                    fill=self.colors["text_sub"])

    def animate_gauge(self, target):
        if self.gauge_anim_id:
            self.root.after_cancel(self.gauge_anim_id)
            self.gauge_anim_id = None

        self.target_score = target
        diff = target - self.display_score
        if abs(diff) > 0.05:
            self.display_score += diff * 0.1
            self.draw_gauge(self.display_score)
            self.gauge_anim_id = self.root.after(16, lambda: self.animate_gauge(target))
        else:
            self.draw_gauge(target)
            self.gauge_anim_id = None

    def reset_interface(self):
        if self.analysis_running: return
        if self.gauge_anim_id:
            self.root.after_cancel(self.gauge_anim_id)
            self.gauge_anim_id = None

        self.text_input.delete("1.0", tk.END)
        for child in self.results_inner.winfo_children():
            child.destroy()

        self.results_canvas.yview_moveto(0)
        self.animate_gauge(0)
        self.status_text.config(text="系统就绪", fg=self.colors["text_sub"])

        self.progress_container.pack_forget()
        self.progress_bar_fill.config(width=0)
        self.progress_percent_label.config(text="0%")

    def add_result_tile(self, index, target_score):
        scale = self.get_scale()
        color = self.safe_color if target_score <= 30 else (
            self.warn_color if target_score <= 70 else self.danger_color)

        tile_shadow = tk.Frame(self.results_inner, bg=self.colors["shadow"], padx=1, pady=1)
        tile_shadow.pack(fill="x", pady=10, padx=2)

        tile = tk.Frame(tile_shadow, bg=self.colors["card"], highlightthickness=1,
                        highlightbackground=self.colors["border"], padx=20, pady=16, cursor="hand2")
        tile.pack(fill="both", expand=True)

        tile.state = {"anim_val": 0.0, "target_val": 0.0, "is_animating": False, "trans_id": None}

        def run_transition():
            diff = tile.state["target_val"] - tile.state["anim_val"]
            if abs(diff) > 0.01:
                tile.state["anim_val"] += diff * 0.2
                v = tile.state["anim_val"]
                pad_x = 2 - int(v * 4)
                tile_shadow.pack_configure(padx=(max(0, pad_x), max(0, pad_x)))
                current_border = self.interpolate_color(self.colors["border"], self.colors["accent"], v)
                tile.config(highlightbackground=current_border)
                tile.state["trans_id"] = self.root.after(10, run_transition)
            else:
                tile.state["anim_val"] = tile.state["target_val"]
                tile.state["is_animating"] = False
                tile.state["trans_id"] = None

        def on_enter(e):
            if tile.state["trans_id"]: self.root.after_cancel(tile.state["trans_id"])
            tile.state["target_val"] = 1.0
            tile.state["is_animating"] = True
            run_transition()

        def on_leave(e):
            if tile.state["trans_id"]: self.root.after_cancel(tile.state["trans_id"])
            tile.state["target_val"] = 0.0
            tile.state["is_animating"] = True
            run_transition()

        def on_press(e):
            tile_shadow.pack_configure(padx=6)

        def on_release(e):
            tile_shadow.pack_configure(padx=2)

        header = tk.Frame(tile, bg=self.colors["card"])
        header.pack(fill="x")

        tk.Label(header, text=f"段落 {index:02d}", font=("Microsoft YaHei UI", int(9 * scale), "bold"),
                 fg=self.colors["text_sub"], bg=self.colors["card"]).pack(side="left")

        score_label = tk.Label(header, text="0.0%", font=("Helvetica", int(11 * scale), "bold"),
                               fg=color, bg=self.colors["card"])
        score_label.pack(side="right")

        pb_bg = tk.Frame(tile, bg=self.colors["gauge_bg"], height=int(6 * scale))
        pb_bg.pack(fill="x", pady=(12, 0))

        pb_fill = tk.Frame(pb_bg, bg=color, height=int(6 * scale))
        pb_fill.place(relx=0, rely=0, relwidth=0)

        def bind_tree(w):
            w.bind("<Enter>", on_enter, add="+")
            w.bind("<Leave>", on_leave, add="+")
            w.bind("<Button-1>", on_press, add="+")
            w.bind("<ButtonRelease-1>", on_release, add="+")
            for child in w.winfo_children(): bind_tree(child)

        bind_tree(tile)
        self.animate_tile_progress(pb_fill, score_label, 0, target_score)

    def animate_tile_progress(self, fill_widget, label_widget, current, target):
        try:
            if current < target:
                current += max(0.4, (target - current) * 0.1)
                fill_widget.place(relwidth=max(0.01, current / 100))
                label_widget.config(text=f"{current:.1f}%")
                self.root.after(20, lambda: self.animate_tile_progress(fill_widget, label_widget, current, target))
        except tk.TclError:
            pass

    def update_scan_progress(self, current, total):
        try:
            percent = (current / total) * 100
            self.progress_percent_label.config(text=f"{int(percent)}%")
            bar_width = self.progress_bar_bg.winfo_width()
            target_width = int(bar_width * (percent / 100))
            self.progress_bar_fill.config(width=target_width)
        except:
            pass

    def load_model(self):
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(LOCAL_MODEL_PATH)
            self.model = AutoModelForSequenceClassification.from_pretrained(LOCAL_MODEL_PATH)
            self.model.to(self.device).eval()
            self.is_ready = True
            self.root.after(0, lambda: self.status_text.config(text="系统已激活", fg=self.safe_color))
        except:
            pass

    def start_analysis(self):
        if not self.is_ready or self.analysis_running: return
        text = self.text_input.get("1.0", tk.END).strip()
        if len(text) < 10: return

        self.analysis_running = True
        self.btn_run.set_text("扫描中...")
        self.btn_run.set_state(disabled=True)
        self.status_text.config(text="正在深度扫描...", fg=self.colors["accent"])

        self.progress_container.pack(fill="x", pady=(0, 10))
        self.progress_bar_fill.config(width=0)
        self.progress_percent_label.config(text="0%")

        for child in self.results_inner.winfo_children(): child.destroy()
        for tag in self.text_input.tag_names():
            if tag.startswith("para_") or tag == "active_para":
                self.text_input.tag_remove(tag, "1.0", tk.END)

        threading.Thread(target=self.run_inference, args=(text,), daemon=True).start()

    def run_inference(self, text):
        paragraphs = [p.strip() for p in re.split(r'[\r\n]+', text) if len(p.strip()) > 5]
        total = len(paragraphs)
        scored_data = []

        for i, p in enumerate(paragraphs):
            if not self.analysis_running: return

            inputs = self.tokenizer(p, return_tensors="pt", truncation=True, max_length=512).to(self.device)
            with torch.no_grad():
                outputs = self.model(**inputs)
                prob = round(torch.softmax(outputs.logits, dim=-1)[0][1].item() * 100, 1)
            scored_data.append((p, prob))

            self.root.after(0, self.update_scan_progress, i + 1, total)
            self.root.after(i * 100, self.add_result_tile, i + 1, prob)

        avg_score = sum(p[1] for p in scored_data) / len(scored_data) if scored_data else 0
        self.root.after(len(paragraphs) * 100 + 300, lambda: self.finish_analysis(avg_score, scored_data))

    def finish_analysis(self, score, scored_data):
        self.analysis_running = False
        self.animate_gauge(score)

        self.btn_run.set_text("立即开始扫描")
        self.btn_run.set_state(disabled=False)
        self.progress_container.pack_forget()

        self.status_text.config(text="分析已完成", fg=self.colors["text_sub"])
        self.text_input.delete("1.0", tk.END)

        for i, (text, prob) in enumerate(scored_data):
            para_tag = f"para_{i + 1}"
            self.text_input.insert(tk.END, text + " ", para_tag)
            prob_tag = "safe_tag" if prob <= 30 else ("warn_tag" if prob <= 70 else "danger_tag")
            self.text_input.insert(tk.END, f"【AI 概率: {prob}%】", (para_tag, prob_tag))
            self.text_input.insert(tk.END, "\n\n")

    def get_scale(self):
        current_w = self.root.winfo_width()
        return max(0.9, current_w / self.ref_width)


if __name__ == "__main__":
    root = tk.Tk()
    app = AIGCDetectorPro(root)
    root.mainloop()