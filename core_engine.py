import sys
import os
import math
import re
from PySide6.QtCore import QThread, Signal


# --- 核心修复：防止 PyInstaller --noconsole 模式下 transformers 报错 ---
class NullWriter:
    def write(self, text): pass
    def flush(self): pass
    def isatty(self): return False

if sys.stdout is None: sys.stdout = NullWriter()
if sys.stderr is None: sys.stderr = NullWriter()

# ---------------------- 路径处理辅助函数 ----------------------
def get_resource_path(relative_path):
    """
    获取资源绝对路径，兼容开发环境与 PyInstaller 打包后的环境
    """
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

# ---------------------- 核心检测线程 ----------------------
class AIGCDetectionThread(QThread):
    """
    独立的后台运算线程，防止模型推理时卡死主界面
    """
    progress_signal = Signal(int)
    result_signal = Signal(dict)
    status_signal = Signal(str)
    device_signal = Signal(str, bool)

    def __init__(self, text, model_path):
        super().__init__()
        self.text = text
        self.model_path = model_path
        self.MIN_VALID_CHARS = 20
        self.TEMPERATURE = 2.0
        self.POWER_FACTOR = 3.5

    def calculate_human_features(self, text):
        """计算人类写作特征（句长方差/突发性）来降低误判"""
        sentences = re.split(r'[。.!！?？;；\n]+', text)
        sentences = [s for s in sentences if len(s.strip()) > 3]
        if len(sentences) < 3: return 0.0
        lengths = [len(s) for s in sentences]
        mean_len = sum(lengths) / len(lengths)
        variance = sum((l - mean_len) ** 2 for l in lengths) / len(lengths)
        std_dev = math.sqrt(variance)
        cv = std_dev / (mean_len + 1e-5)
        bonus = 0.0
        if cv > 0.4: bonus = min((cv - 0.4) * 0.6, 0.3)
        return bonus

    def run(self):
        if not self.model_path or not os.path.exists(self.model_path):
            self.result_signal.emit({"error": "模型路径无效"})
            return

        try:
            # 延迟导入，保证界面秒开
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
            import torch.nn.functional as F

            # --- 硬件检测逻辑 ---
            use_cuda = torch.cuda.is_available()
            use_mps = hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
            
            if use_cuda:
                device_str = "cuda"
                gpu_name = torch.cuda.get_device_name(0)
                if len(gpu_name) > 20: gpu_name = gpu_name[:20] + "..."
                self.device_signal.emit(f"🚀 显卡加速: {gpu_name} (Torch {torch.__version__})", True)
                torch_device = torch.device("cuda")
            elif use_mps:
                device_str = "mps"
                self.device_signal.emit(f"⚡ Mac GPU 加速 (Torch {torch.__version__})", True)
                torch_device = torch.device("mps")
            else:
                device_str = "cpu"
                version = torch.__version__
                extra_info = " [错误: 安装了CPU版Torch]" if "+cpu" in version else (" [未发现NVIDIA显卡]" if not use_cuda else "")
                self.device_signal.emit(f"🐢 CPU 运算 (Torch {version}){extra_info}", False)
                torch_device = torch.device("cpu")
            
            self.progress_signal.emit(10)
            self.status_signal.emit("加载本地权重 (config, bin, vocab)...")
            
            # 加载模型
            tokenizer = AutoTokenizer.from_pretrained(self.model_path, local_files_only=True)
            model = AutoModelForSequenceClassification.from_pretrained(self.model_path, local_files_only=True)
            model.to(torch_device)
            model.eval() 
            self.progress_signal.emit(30)

            # 获取 AI 标签 ID
            ai_label_id = 1 
            if hasattr(model.config, 'id2label') and model.config.id2label:
                for idx, label in model.config.id2label.items():
                    if any(x in str(label).lower() for x in ['fake', 'ai', 'chatgpt', 'generated', '1', 'label_1']):
                        ai_label_id = int(idx); break

            # =================================================================
            # 【核心升级：智能长文本防截断切分算法】
            # =================================================================
            raw_paragraphs = [p for p in self.text.split("\n") if p.strip()]
            paragraphs = []
            
            for p in raw_paragraphs:
                # 400 个中文字符通常远不到 512 个 Token，属于安全线
                if len(p) < 400:
                    paragraphs.append(p)
                else:
                    # 如果段落超长，使用正则寻找所有句子结束符，并在结束符后切分
                    # (?<=[。.!！?？]) 表示匹配这些标点符号之后的位置，这样切分不会丢失标点
                    sentences = re.split(r'(?<=[。.!！?？])', p)
                    current_chunk = ""
                    
                    for s in sentences:
                        # 极端防崩溃：如果一句话本身没有标点且超过了 400 字，强制暴力切断
                        if len(s) > 400:
                            if current_chunk: 
                                paragraphs.append(current_chunk)
                                current_chunk = ""
                            # 按 400 字硬切
                            for i in range(0, len(s), 400):
                                paragraphs.append(s[i:i+400])
                                
                        # 正常拼接：如果加上这句话超过 400 字，把之前的推入列表，重新开始拼接
                        elif len(current_chunk) + len(s) > 400:
                            paragraphs.append(current_chunk)
                            current_chunk = s
                        else:
                            current_chunk += s
                            
                    # 把最后剩余的尾巴加进去
                    if current_chunk:
                        paragraphs.append(current_chunk)
            # =================================================================

            if not paragraphs:
                self.result_signal.emit({"total_ai_rate": 0, "paragraphs": [], "total_tokens": 0}); return

            results = []
            total_weighted_score = 0; total_valid_weight = 0
            total_tokens = 0 # 用于统计消耗的真实算力

            # 逐段推理
            for idx, para in enumerate(paragraphs):
                self.status_signal.emit(f"深度指纹分析中... {idx+1}/{len(paragraphs)}")
                try:
                    # 这里依然保留 max_length=512 和 truncation=True 作为绝对的安全底线
                    # 但由于上面的算法，它实际上永远不会触发截断丢失文本了
                    inputs = tokenizer(para, return_tensors="pt", truncation=True, max_length=512)
                    
                    # 统计当前切分段落产生的真实 Token 数量
                    token_count = inputs["input_ids"].shape[1]
                    total_tokens += token_count
                    
                    inputs = {k: v.to(torch_device) for k, v in inputs.items()}
                    with torch.no_grad():
                        outputs = model(**inputs)
                        logits = outputs.logits
                        scaled_logits = logits / self.TEMPERATURE
                        probs = F.softmax(scaled_logits, dim=-1)
                        raw_ai_score = probs[0][ai_label_id].item()
                        
                        human_bonus = self.calculate_human_features(para)
                        adjusted_score = max(0.0, raw_ai_score - human_bonus)
                        final_ai_score = math.pow(adjusted_score, self.POWER_FACTOR)
                        ai_rate = round(final_ai_score * 100, 2)
                    
                    chinese_count = len(re.findall(r'[\u4e00-\u9fa5]', para))
                    alnum_count = len(re.findall(r'[a-zA-Z0-9]', para))
                    para_len = chinese_count + (alnum_count * 0.5)
                    
                    is_ignored = para_len < self.MIN_VALID_CHARS
                    weight = 0 if is_ignored else para_len
                    
                    results.append({"content": para, "ai_rate": ai_rate, "is_ignored": is_ignored})
                    if not is_ignored:
                        total_weighted_score += (ai_rate * weight); total_valid_weight += weight
                except Exception as e:
                    if "upgrade torch" in str(e) and "v2.6" in str(e): raise e 
                    print(f"Segment Error: {e}")
                
                self.progress_signal.emit(30 + int(((idx + 1) / len(paragraphs)) * 65))

            avg = round(total_weighted_score / total_valid_weight, 2) if total_valid_weight > 0 else 0
            # 将总体分率和消耗的 Token 一起发送给界面
            self.result_signal.emit({"total_ai_rate": avg, "paragraphs": results, "total_tokens": total_tokens})

        except Exception as e:
            if "upgrade torch" in str(e) and "v2.6" in str(e):
                self.result_signal.emit({"error": "【环境版本冲突】\n请升级 PyTorch 版本。\npip install --upgrade torch torchvision torchaudio"})
            else:
                self.result_signal.emit({"error": f"推理引擎异常:\n{str(e)}"})