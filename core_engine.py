import sys
import os
import math
import re
import json
import datetime
import threading
from PySide6.QtCore import QThread, Signal

try:
    import numpy as np
    _NUMPY_OK = True
except ImportError:
    np = None
    _NUMPY_OK = False

# ---------------------- 路径处理辅助函数 ----------------------
def get_resource_path(relative_path):
    """获取资源文件绝对路径"""
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

# ---------------------- 本地历史记录管理 ----------------------
def load_history():
    """读取本地历史记录（最多返回最新的 10 条）"""
    path = get_save_path("deepveri_history.json")
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_history(original_text, total_ai_rate, total_tokens, paragraphs):
    """将单次成功的检测结果保存进历史记录池中"""
    history = load_history()

    if history and history[0].get("original_text") == original_text:
        return

    record = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "original_text": original_text,
        "total_ai_rate": total_ai_rate,
        "total_tokens": total_tokens,
        "paragraphs": paragraphs
    }

    history.insert(0, record)
    history = history[:10]

    path = get_save_path("deepveri_history.json")
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Save history error: {e}")

def clear_all_history():
    """彻底清除所有历史记录，保护隐私"""
    path = get_save_path("deepveri_history.json")
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception as e:
            print(f"Clear history error: {e}")

# ---------------------- 本地配置持久化 (双层架构) ----------------------
def get_save_path(filename):
    """获取用户配置保存路径（支持打包后环境）"""
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, filename)

def load_factory_defaults():
    """加载用户自定义的【全局默认值】"""
    path = get_save_path("deepveri_factory_defaults.json")

    default_config = {
        'temperature': 2.0,
        'power_factor': 1.5,
        'max_chunk_size': 700,
        'min_valid_length': 20,
        'force_cpu': False
    }

    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                user_defaults = json.load(f)
                default_config.update(user_defaults)
        except Exception:
            pass

    return default_config

def save_factory_defaults(config):
    """保存用户自定义的【全局默认值】"""
    path = get_save_path("deepveri_factory_defaults.json")
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Save factory defaults error: {e}")

def load_settings():
    """从本地读取当前运行参数，如果没有则继承【全局默认值】"""
    path = get_save_path("deepveri_settings.json")
    config = load_factory_defaults()

    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                config.update(user_config)
        except Exception:
            pass

    return config

def save_settings(config):
    """将参数永久保存到本地作为下一次的运行参数"""
    path = get_save_path("deepveri_settings.json")
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Save config error: {e}")

# ---------------------- 硬件嗅探辅助 ----------------------
def check_gpu_availability():
    """检测 DirectML / GPU 是否可用"""
    try:
        import onnxruntime as ort
        providers = ort.get_available_providers()
        if 'DmlExecutionProvider' in providers:
            # DirectML 可用，尝试获取设备名
            try:
                name = _get_dml_device_name()
                return True, f"DirectML GPU ({name})"
            except Exception:
                return True, "DirectML GPU 加速"
        else:
            return False, "未检测到 GPU 加速 (DirectML 不可用)"
    except ImportError:
        return False, "ONNX Runtime 未安装"
    except Exception as e:
        return False, f"硬件检测异常: {str(e)[:60]}"

def _get_dml_device_name():
    """通过 Windows 注册表获取主显卡名称"""
    try:
        import winreg
        base = (r"SYSTEM\CurrentControlSet\Control\Class"
                r"\{4d36e968-e325-11ce-bfc1-08002be10318}")
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{base}\\0000")
            name, _ = winreg.QueryValueEx(key, "DriverDesc")
            winreg.CloseKey(key)
            return name
        except OSError:
            return "GPU"
    except Exception:
        return "GPU"

# ---------------------- 共享 ONNX 会话 (全进程唯一) ----------------------
_shared_session = None
_shared_tokenizer = None
_shared_device_type = None
_session_lock = threading.Lock()

def get_shared_session(model_path, force_cpu=False):
    """获取共享 ONNX 会话 + 分词器。自动检测 force_cpu 变化并重建。"""
    global _shared_session, _shared_tokenizer, _shared_device_type

    should_be = "cpu" if force_cpu else "dml"

    # 已有缓存且设备匹配，直接返回（无锁快速路径）
    if _shared_session is not None and _shared_device_type == should_be:
        return _shared_session, _shared_tokenizer, _shared_device_type

    with _session_lock:
        # 双重检查：锁内再次确认是否需要创建
        if _shared_session is not None and _shared_device_type == should_be:
            return _shared_session, _shared_tokenizer, _shared_device_type

        import onnxruntime as ort
        from tokenizers import Tokenizer

        onnx_path = os.path.join(model_path, "model.onnx")
        tokenizer_path = os.path.join(model_path, "tokenizer.json")

        use_gpu = (not force_cpu and
                   'DmlExecutionProvider' in ort.get_available_providers())

        if use_gpu:
            try:
                _shared_session = ort.InferenceSession(
                    onnx_path, providers=['DmlExecutionProvider', 'CPUExecutionProvider'])
                _shared_device_type = "dml"
            except Exception as e:
                use_gpu = False
                print(f"DirectML 失败，回退 CPU: {e}")

        if not use_gpu:
            _shared_session = ort.InferenceSession(
                onnx_path, providers=['CPUExecutionProvider'])
            _shared_device_type = "cpu"

        _shared_tokenizer = Tokenizer.from_file(tokenizer_path)
        return _shared_session, _shared_tokenizer, _shared_device_type

# ---------------------- 共用工具函数 ----------------------
def get_token_length(text):
    """计算文本的有效 token 长度（ASCII 字符权重减半）"""
    ascii_count = sum(1 for char in text if char.isascii())
    return len(text) - (ascii_count * 0.5)

def calculate_human_features(text):
    """基于句长变异系数的人类写作特征加分"""
    sentences = re.split(r'[。.!！?？;；\n]+', text)
    sentences = [s for s in sentences if len(s.strip()) > 3]
    if len(sentences) < 3:
        return 0.0

    lengths = [len(s) for s in sentences]
    mean_len = sum(lengths) / len(lengths)
    variance = sum((l - mean_len) ** 2 for l in lengths) / len(lengths)
    std_dev = math.sqrt(variance)
    cv = std_dev / (mean_len + 1e-5)

    bonus = 0.0
    if cv > 0.4:
        bonus = min((cv - 0.4) * 0.6, 0.3)
    return bonus

def smart_split_paragraph(text, max_chunk_size):
    """四级智能平滑切分算法"""
    max_len = max_chunk_size
    if get_token_length(text) <= max_len:
        return [text]

    result = []
    sentences = re.split(r'(?<=[。.!！?？])', text)
    current_chunk = ""
    current_len = 0

    for s in sentences:
        s_len = get_token_length(s)
        if current_len + s_len <= max_len:
            current_chunk += s
            current_len += s_len
        else:
            if current_chunk:
                result.append(current_chunk)
                current_chunk = ""
                current_len = 0

            if s_len > max_len:
                sub_sentences = re.split(r'(?<=[,，;；])', s)
                for sub_s in sub_sentences:
                    sub_s_len = get_token_length(sub_s)
                    if current_len + sub_s_len <= max_len:
                        current_chunk += sub_s
                        current_len += sub_s_len
                    else:
                        if current_chunk:
                            result.append(current_chunk)
                            current_chunk = ""
                            current_len = 0

                        if sub_s_len > max_len:
                            words = re.split(r'(?<=\s)', sub_s)
                            for w in words:
                                w_len = get_token_length(w)
                                if current_len + w_len <= max_len:
                                    current_chunk += w
                                    current_len += w_len
                                else:
                                    if current_chunk:
                                        result.append(current_chunk)
                                        current_chunk = ""
                                        current_len = 0

                                    if w_len > max_len:
                                        temp_s = ""
                                        temp_len = 0
                                        for char in w:
                                            char_len = 0.5 if char.isascii() else 1.0
                                            if temp_len + char_len > max_len:
                                                result.append(temp_s)
                                                temp_s = char
                                                temp_len = char_len
                                            else:
                                                temp_s += char
                                                temp_len += char_len
                                        if temp_s:
                                            current_chunk = temp_s
                                            current_len = temp_len
                                    else:
                                        current_chunk = w
                                        current_len = w_len
                        else:
                            current_chunk = sub_s
                            current_len = sub_s_len
            else:
                current_chunk = s
                current_len = s_len

    if current_chunk:
        result.append(current_chunk)

    return result

def _softmax(x):
    """numpy softmax"""
    if not _NUMPY_OK:
        raise ImportError("numpy 未安装，无法执行 softmax 计算")
    e_x = np.exp(x - np.max(x, axis=-1, keepdims=True))
    return e_x / e_x.sum(axis=-1, keepdims=True)

_cached_ai_label_id = None
_cached_ai_label_model_path = None

def _load_ai_label_id(model_path):
    """从模型 config.json 读取 AI label id（结果缓存）"""
    global _cached_ai_label_id, _cached_ai_label_model_path
    if _cached_ai_label_id is not None and _cached_ai_label_model_path == model_path:
        return _cached_ai_label_id

    config_path = os.path.join(model_path, "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                model_config = json.load(f)
            id2label = model_config.get('id2label', {})
            for idx, label in id2label.items():
                if any(x in str(label).lower() for x in
                       ['fake', 'ai', 'chatgpt', 'generated', '1', 'label_1']):
                    _cached_ai_label_id = int(idx)
                    _cached_ai_label_model_path = model_path
                    return _cached_ai_label_id
        except Exception:
            pass
    _cached_ai_label_id = 1
    _cached_ai_label_model_path = model_path
    return 1

# ---------------------- 核心检测线程 ----------------------
class AIGCDetectionThread(QThread):
    progress_signal = Signal(int)
    result_signal = Signal(dict)
    status_signal = Signal(str)
    device_signal = Signal(str, bool)
    segment_error_signal = Signal(str)

    def __init__(self, text, model_path, config=None):
        super().__init__()
        self.text = text
        self.model_path = model_path

        self.config = config or {}
        self.TEMPERATURE = self.config.get('temperature', 2.0)
        self.POWER_FACTOR = self.config.get('power_factor', 1.5)
        self.MAX_CHUNK_SIZE = self.config.get('max_chunk_size', 700)
        self.MIN_VALID_CHARS = self.config.get('min_valid_length', 20)
        self.FORCE_CPU = self.config.get('force_cpu', False)

        self._is_running = True

    def stop(self):
        """安全终止检测线程的触发口"""
        self._is_running = False

    def get_token_length(self, text):
        return get_token_length(text)

    def _smart_split_paragraph(self, text):
        return smart_split_paragraph(text, self.MAX_CHUNK_SIZE)

    def calculate_human_features(self, text):
        return calculate_human_features(text)

    def _softmax(self, x):
        return _softmax(x)

    def run(self):
        if not self.model_path or not os.path.exists(self.model_path):
            self.result_signal.emit({"error": "模型路径无效"})
            return

        try:
            import onnxruntime as ort

            onnx_path = os.path.join(self.model_path, "model.onnx")

            if not os.path.exists(onnx_path):
                self.result_signal.emit({
                    "error": "未找到 model.onnx，请先运行 export_onnx.py 导出模型"
                })
                return

            self.progress_signal.emit(5)
            self.status_signal.emit("加载推理引擎...")

            session, tokenizer, device_type = get_shared_session(
                self.model_path, force_cpu=self.FORCE_CPU)
            use_gpu = device_type == "dml"

            if use_gpu:
                self.device_signal.emit("DirectML GPU 加速", True)
            elif self.FORCE_CPU:
                self.device_signal.emit("CPU 运算模式 (用户强制)", False)
            else:
                self.device_signal.emit("CPU 运算模式 (DirectML 不可用)", False)

            ai_label_id = _load_ai_label_id(self.model_path)

            self.progress_signal.emit(30)

            raw_paragraphs = [p for p in self.text.split("\n") if p.strip()]
            paragraphs = []

            for p in raw_paragraphs:
                paragraphs.extend(self._smart_split_paragraph(p))

            if not paragraphs:
                self.result_signal.emit({"total_ai_rate": 0, "paragraphs": [], "total_tokens": 0})
                return

            results = []
            total_weighted_score = 0
            total_valid_weight = 0
            total_tokens = 0
            failed_segments = 0
            total_segments = len(paragraphs)

            for idx, para in enumerate(paragraphs):
                if not self._is_running:
                    self.status_signal.emit("检测已被手动终止，正在结算已完成进度...")
                    break

                self.status_signal.emit(f"深度指纹分析中... {idx+1}/{len(paragraphs)}")

                try:
                    encoded = tokenizer.encode(para)
                    ids = encoded.ids[:512]
                    attn = encoded.attention_mask[:512] if encoded.attention_mask else [1] * len(ids)
                    token_count = len(ids)
                    total_tokens += token_count

                    ort_inputs = {
                        'input_ids': np.array([ids], dtype=np.int64),
                        'attention_mask': np.array([attn], dtype=np.int64),
                    }

                    logits = session.run(['logits'], ort_inputs)[0]

                    # 应用温度系数
                    scaled_logits = logits / self.TEMPERATURE
                    probs = self._softmax(scaled_logits)
                    raw_ai_score = float(probs[0][ai_label_id])

                    human_bonus = self.calculate_human_features(para)
                    adjusted_score = max(0.0, raw_ai_score - human_bonus)

                    # 应用指数惩罚因子
                    final_ai_score = math.pow(adjusted_score, self.POWER_FACTOR)
                    ai_rate = round(final_ai_score * 100, 2)

                    para_len = self.get_token_length(para)

                    is_ignored = para_len < self.MIN_VALID_CHARS
                    weight = 0 if is_ignored else para_len

                    results.append({
                        "content": para,
                        "ai_rate": ai_rate,
                        "is_ignored": is_ignored,
                        "tokens": token_count
                    })

                    if not is_ignored:
                        total_weighted_score += (ai_rate * weight)
                        total_valid_weight += weight

                except Exception as e:
                    err_msg = str(e)
                    is_dml_error = any(x in err_msg for x in (
                        'DmlExecutionProvider', 'EP Error',
                        'device removed', '887A0005'))

                    if is_dml_error and use_gpu:
                        # GPU 不稳定，切 CPU 重试当前段落
                        self.device_signal.emit(
                            " GPU 不稳定，已自动切换 CPU 模式", False)
                        self.status_signal.emit("GPU 不稳定，切换 CPU 推理...")
                        use_gpu = False
                        session, _, _ = get_shared_session(
                            self.model_path, force_cpu=True)
                        try:
                            logits = session.run(['logits'], ort_inputs)[0]
                            scaled_logits = logits / self.TEMPERATURE
                            probs = self._softmax(scaled_logits)
                            raw_ai_score = float(probs[0][ai_label_id])
                            human_bonus = self.calculate_human_features(para)
                            adjusted_score = max(0.0, raw_ai_score - human_bonus)
                            final_ai_score = math.pow(adjusted_score, self.POWER_FACTOR)
                            ai_rate = round(final_ai_score * 100, 2)
                            para_len = self.get_token_length(para)
                            is_ignored = para_len < self.MIN_VALID_CHARS
                            weight = 0 if is_ignored else para_len
                            results.append({
                                "content": para, "ai_rate": ai_rate,
                                "is_ignored": is_ignored, "tokens": token_count})
                            if not is_ignored:
                                total_weighted_score += (ai_rate * weight)
                                total_valid_weight += weight
                        except Exception:
                            failed_segments += 1
                            results.append({
                                "content": para, "ai_rate": 0,
                                "is_ignored": True, "tokens": 0,
                                "inference_error": True})
                    else:
                        failed_segments += 1
                        self.segment_error_signal.emit(
                            f"段落推理异常: {err_msg[:100]}")
                        results.append({
                            "content": para, "ai_rate": 0,
                            "is_ignored": True, "tokens": 0,
                            "inference_error": True})

                self.progress_signal.emit(30 + int(((idx + 1) / len(paragraphs)) * 65))

            if failed_segments >= total_segments:
                self.result_signal.emit({
                    "error": f"所有 {total_segments} 个段落推理均失败。\n"
                             f"请在控制台中启用「强制使用 CPU」后重试。"
                })
                return

            if failed_segments > 0:
                self.status_signal.emit(
                    f" {failed_segments}/{total_segments} 个段落推理失败，结果可能不完整")

            avg = round(total_weighted_score / total_valid_weight, 2) if total_valid_weight > 0 else 0

            self.result_signal.emit({
                "total_ai_rate": avg,
                "paragraphs": results,
                "total_tokens": total_tokens
            })

        except ImportError as e:
            self.result_signal.emit({
                "error": f"缺失依赖库: {e}\n请安装: pip install onnxruntime-directml tokenizers"
            })
        except Exception as e:
            self.result_signal.emit({"error": f"推理引擎异常:\n{str(e)}"})
