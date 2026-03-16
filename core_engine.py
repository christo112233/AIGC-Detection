import sys
import os
import math
import re
import json
from PySide6.QtCore import QThread, Signal

# --- 核心修复：防止 PyInstaller --noconsole 模式下 transformers 报错 ---
class NullWriter:
    def write(self, text):
        pass

    def flush(self):
        pass

    def isatty(self):
        return False

if sys.stdout is None:
    sys.stdout = NullWriter()
if sys.stderr is None:
    sys.stderr = NullWriter()

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

# ---------------------- 本地配置持久化 ----------------------
def get_save_path(filename):
    """获取用户配置保存路径（支持打包后环境）"""
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, filename)

def load_settings():
    """从本地读取控制台参数，如果没有则使用默认值"""
    path = get_save_path("deepveri_settings.json")
    
    # 按照你的要求，更新底层初始默认值
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
                user_config = json.load(f)
                default_config.update(user_config)
        except Exception:
            pass
            
    return default_config

def save_settings(config):
    """将参数永久保存到本地 JSON 文件中"""
    path = get_save_path("deepveri_settings.json")
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Save config error: {e}")

# ---------------------- 硬件嗅探辅助 ----------------------
def check_gpu_availability():
    """独立的硬件嗅探函数，提供给 UI 的后台线程静默调用"""
    try:
        import torch
        use_cuda = torch.cuda.is_available()
        use_mps = hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
        
        if use_cuda:
            name = torch.cuda.get_device_name(0)
            # 核心修复：彻底移除 [:20] 的强制切断，展示完整显卡型号
            return True, f"NVIDIA GPU ({name})"
        elif use_mps:
            return True, "Apple Metal (MPS加速)"
        else:
            return False, "未检测到支持的 GPU 或驱动"
            
    except Exception as e:
        return False, "Torch 环境异常，无法检测硬件"

# ---------------------- 核心检测线程 ----------------------
class AIGCDetectionThread(QThread):
    progress_signal = Signal(int)
    result_signal = Signal(dict)
    status_signal = Signal(str)
    device_signal = Signal(str, bool)

    def __init__(self, text, model_path, config=None):
        super().__init__()
        self.text = text
        self.model_path = model_path
        
        # 接管来自控制台的动态配置
        self.config = config or {}
        self.TEMPERATURE = self.config.get('temperature', 2.0)
        self.POWER_FACTOR = self.config.get('power_factor', 1.5)
        self.MAX_CHUNK_SIZE = self.config.get('max_chunk_size', 700)
        self.MIN_VALID_CHARS = self.config.get('min_valid_length', 20)
        self.FORCE_CPU = self.config.get('force_cpu', False)
        
        # 控制线程生命周期的信号旗
        self._is_running = True

    def stop(self):
        """安全终止检测线程的触发口"""
        self._is_running = False

    def get_token_length(self, text):
        ascii_count = sum(1 for char in text if char.isascii())
        return len(text) - (ascii_count * 0.5)

    def _smart_split_paragraph(self, text):
        """四级智能平滑切分算法"""
        max_len = self.MAX_CHUNK_SIZE
        if self.get_token_length(text) <= max_len:
            return [text]
            
        result = []
        sentences = re.split(r'(?<=[。.!！?？])', text)
        current_chunk = ""
        current_len = 0
        
        for s in sentences:
            s_len = self.get_token_length(s)
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
                        sub_s_len = self.get_token_length(sub_s)
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
                                    w_len = self.get_token_length(w)
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

    def calculate_human_features(self, text):
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

    def run(self):
        if not self.model_path or not os.path.exists(self.model_path):
            self.result_signal.emit({"error": "模型路径无效"})
            return

        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
            import torch.nn.functional as F

            # 硬件检测逻辑接管
            if self.FORCE_CPU:
                use_cuda = False
                use_mps = False
            else:
                use_cuda = torch.cuda.is_available()
                use_mps = hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
            
            if use_cuda:
                device_str = "cuda"
                gpu_name = torch.cuda.get_device_name(0)
                # 核心修复：移除底层的 [:20] 截断限制
                self.device_signal.emit(f"🚀 显卡加速: {gpu_name}", True)
                torch_device = torch.device("cuda")
            elif use_mps:
                device_str = "mps"
                self.device_signal.emit(f"⚡ Mac GPU 加速", True)
                torch_device = torch.device("mps")
            else:
                device_str = "cpu"
                version = torch.__version__
                extra_info = " [错误: 安装了CPU版Torch]" if "+cpu" in version else (" [用户强制/无GPU]" if not use_cuda else "")
                self.device_signal.emit(f"🐢 CPU 运算模式{extra_info}", False)
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
                        ai_label_id = int(idx)
                        break

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

            for idx, para in enumerate(paragraphs):
                # 检查用户是否按下了终止按钮
                if not self._is_running:
                    self.status_signal.emit("检测已被手动终止，正在结算已完成进度...")
                    break

                self.status_signal.emit(f"深度指纹分析中... {idx+1}/{len(paragraphs)}")
                
                try:
                    inputs = tokenizer(para, return_tensors="pt", truncation=True, max_length=512)
                    token_count = inputs["input_ids"].shape[1]
                    total_tokens += token_count
                    
                    inputs = {k: v.to(torch_device) for k, v in inputs.items()}
                    with torch.no_grad():
                        outputs = model(**inputs)
                        logits = outputs.logits
                        
                        # 应用温度系数
                        scaled_logits = logits / self.TEMPERATURE
                        probs = F.softmax(scaled_logits, dim=-1)
                        raw_ai_score = probs[0][ai_label_id].item()
                        
                        human_bonus = self.calculate_human_features(para)
                        adjusted_score = max(0.0, raw_ai_score - human_bonus)
                        
                        # 应用指数惩罚因子
                        final_ai_score = math.pow(adjusted_score, self.POWER_FACTOR)
                        ai_rate = round(final_ai_score * 100, 2)
                    
                    para_len = self.get_token_length(para)
                    
                    # 判断极短句忽略
                    is_ignored = para_len < self.MIN_VALID_CHARS
                    weight = 0 if is_ignored else para_len
                    
                    results.append({"content": para, "ai_rate": ai_rate, "is_ignored": is_ignored})
                    
                    if not is_ignored:
                        total_weighted_score += (ai_rate * weight)
                        total_valid_weight += weight
                        
                except Exception as e:
                    print(f"Segment Error: {e}")
                
                self.progress_signal.emit(30 + int(((idx + 1) / len(paragraphs)) * 65))

            # 统一计算总分并返回界面
            avg = round(total_weighted_score / total_valid_weight, 2) if total_valid_weight > 0 else 0
            
            self.result_signal.emit({
                "total_ai_rate": avg, 
                "paragraphs": results, 
                "total_tokens": total_tokens
            })

        except Exception as e:
            self.result_signal.emit({"error": f"推理引擎异常:\n{str(e)}"})