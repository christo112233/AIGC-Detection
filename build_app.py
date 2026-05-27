import os
import sys
import shutil
import subprocess
import threading
import time

MODEL_ONLY_FILES = ["model.onnx", "tokenizer.json", "config.json"]

# PyInstaller 构建阶段 -> (进度百分比, 阶段名称)
BUILD_STAGES = [
    ("Analyzing", 15, "分析依赖"),
    ("Building PKG", 40, "打包资源"),
    ("Building EXE", 60, "生成可执行文件"),
    ("Building COLLECT", 80, "收集文件"),
    ("copying", 90, "复制依赖"),
]

class ProgressBar:
    """简易控制台进度条"""
    def __init__(self, total=100, width=40):
        self.total = total
        self.width = width
        self.current = 0
        self.lock = threading.Lock()

    def update(self, value):
        with self.lock:
            self.current = min(value, self.total)
            self._draw()

    def set_status(self, text):
        with self.lock:
            bar = self._bar_str()
            print(f"\r{bar} {self.current:3d}% | {text:<30s}", end="", flush=True)

    def _bar_str(self):
        filled = int(self.width * self.current / self.total)
        bar = "█" * filled + "░" * (self.width - filled)
        return f"[{bar}]"

    def _draw(self):
        bar = self._bar_str()
        print(f"\r{bar} {self.current:3d}%", end="", flush=True)

    def finish(self, text=""):
        with self.lock:
            self.current = 100
            bar = self._bar_str()
            print(f"\r{bar} 100% | {text:<30s}")

    def start(self):
        self.update(0)


def _read_output(stream, progress, stop_event):
    """在后台线程中读取 PyInstaller 输出并更新进度"""
    for line in iter(stream.readline, b""):
        if stop_event.is_set():
            break
        text = line.decode("utf-8", errors="ignore").strip()
        if not text:
            continue
        # 匹配已知构建阶段
        for keyword, pct, name in BUILD_STAGES:
            if keyword in text:
                progress.update(pct)
                progress.set_status(name)
                break
    stream.close()


def main():
    print("=" * 55)
    print("  DeepVeri 构建脚本")
    print("=" * 55)

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("未检测到 PyInstaller，正在安装...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    app_name = "DeepVeri"
    main_script = "main.py"
    model_folder = "AIGC_Model"
    icon_file = "logo.ico"

    if not os.path.exists(main_script):
        print(f"找不到主程序: {main_script}")
        return

    if not os.path.exists(model_folder):
        print(f"找不到模型文件夹: {model_folder}")
        return

    print("\n调用 PyInstaller 打包...\n")

    pyinstaller_args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        f"--name={app_name}",
        "--hidden-import=onnxruntime",
        "--hidden-import=onnxruntime.dml",
        "--hidden-import=onnxruntime.capi.onnxruntime_pybind11_state",
        "--hidden-import=tokenizers",
        "--hidden-import=numpy",
        "--hidden-import=numpy.core._methods",
        "--hidden-import=numpy.lib.format",
        "--exclude-module=PySide6.QtWebEngine",
        "--exclude-module=PySide6.QtWebEngineCore",
        "--exclude-module=PySide6.QtWebEngineWidgets",
        "--exclude-module=PySide6.QtNetwork",
        "--exclude-module=PySide6.QtQml",
        "--exclude-module=PySide6.QtSql",
        "--exclude-module=PySide6.QtMultimedia",
        "--exclude-module=PySide6.QtQuick",
    ]

    if os.path.exists(icon_file):
        pyinstaller_args.append(f"--icon={icon_file}")

    pyinstaller_args.append(main_script)

    progress = ProgressBar()
    progress.start()
    progress.set_status("启动 PyInstaller...")

    process = subprocess.Popen(
        pyinstaller_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    stop_event = threading.Event()
    reader_thread = threading.Thread(
        target=_read_output, args=(process.stdout, progress, stop_event),
        daemon=True,
    )
    reader_thread.start()

    returncode = process.wait()
    stop_event.set()
    reader_thread.join(timeout=2)

    if returncode != 0:
        progress.finish("打包失败")
        print(f"\n退出码: {returncode}")
        return

    progress.update(92)
    progress.set_status("复制模型文件...")

    dist_dir = os.path.join("dist", app_name)
    target_dir = os.path.join(dist_dir, model_folder)
    os.makedirs(target_dir, exist_ok=True)

    for fname in MODEL_ONLY_FILES:
        src = os.path.join(model_folder, fname)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(target_dir, fname))

    progress.finish("构建完成")
    print(f"\n输出目录: {os.path.abspath(dist_dir)}")
    print(f"将整个 [{app_name}] 文件夹压缩发送即可")

if __name__ == "__main__":
    main()
