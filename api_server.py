import os
import math
import re
import threading
import queue
import logging

try:
    from flask import Flask, request, jsonify
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    import torch.nn.functional as F
    FLASK_AVAILABLE = True
except ImportError as e:
    FLASK_AVAILABLE = False
    print(f"API Server Warning: Missing dependency {e}")

# ================= 工具函数 (与 GUI 解耦，保证独立安全) =================
def get_token_length(text):
    ascii_count = sum(1 for char in text if char.isascii())
    return len(text) - (ascii_count * 0.5)

def calculate_human_features(text):
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
    """独立的平滑切分算法，应对超长文本拦截"""
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

# ================= 线程安全的模型工作者 =================
class APIModelWorker(threading.Thread):
    def __init__(self, model_path, config, task_queue):
        super().__init__(daemon=True)
        self.model_path = model_path
        self.config = config
        self.task_queue = task_queue

    def run(self):
        use_cuda = torch.cuda.is_available()
        use_mps = hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
        
        if self.config.get('force_cpu', False):
            device = torch.device("cpu")
        elif use_cuda:
            device = torch.device("cuda")
        elif use_mps:
            device = torch.device("mps")
        else:
            device = torch.device("cpu")

        try:
            tokenizer = AutoTokenizer.from_pretrained(self.model_path, local_files_only=True)
            model = AutoModelForSequenceClassification.from_pretrained(self.model_path, local_files_only=True)
            model.to(device)
            model.eval()
        except Exception as e:
            print(f"API 微服务加载模型异常: {e}")
            return

        ai_label_id = 1
        if hasattr(model.config, 'id2label') and model.config.id2label:
            for idx, label in model.config.id2label.items():
                if any(x in str(label).lower() for x in ['fake', 'ai', 'chatgpt', 'generated', '1']):
                    ai_label_id = int(idx)
                    break

        print("⚡ API 微服务推理引擎已就绪，正在监听请求...")

        while True:
            task = self.task_queue.get()
            if task is None: break
            
            text = task['text']
            resp_queue = task['resp_queue']
            
            try:
                raw_paragraphs = [p for p in text.split("\n") if p.strip()]
                paragraphs = []
                max_chunk = self.config.get('max_chunk_size', 700)
                
                for p in raw_paragraphs:
                    paragraphs.extend(smart_split_paragraph(p, max_chunk))

                if not paragraphs:
                    resp_queue.put({"ai_ratio": 0.0, "status": "too_short"})
                    continue

                total_weighted_score = 0
                total_valid_weight = 0
                temp = self.config.get('temperature', 2.0)
                power = self.config.get('power_factor', 1.5)
                min_len = self.config.get('min_valid_length', 20)

                for para in paragraphs:
                    inputs = tokenizer(para, return_tensors="pt", truncation=True, max_length=512)
                    inputs = {k: v.to(device) for k, v in inputs.items()}
                    
                    with torch.no_grad():
                        outputs = model(**inputs)
                        scaled_logits = outputs.logits / temp
                        probs = F.softmax(scaled_logits, dim=-1)
                        raw_ai_score = probs[0][ai_label_id].item()

                        human_bonus = calculate_human_features(para)
                        adjusted_score = max(0.0, raw_ai_score - human_bonus)
                        final_ai_score = math.pow(adjusted_score, power)
                        ai_rate = final_ai_score * 100

                    para_len = get_token_length(para)
                    is_ignored = para_len < min_len
                    weight = 0 if is_ignored else para_len

                    if not is_ignored:
                        total_weighted_score += (ai_rate * weight)
                        total_valid_weight += weight

                if total_valid_weight > 0:
                    avg_score = total_weighted_score / total_valid_weight
                    ratio = round(avg_score / 100.0, 4)
                    resp_queue.put({"ai_ratio": ratio, "status": "success"})
                else:
                    resp_queue.put({"ai_ratio": 0.0, "status": "too_short"})

            except Exception as e:
                print(f"API 微服务推理出错: {e}")
                resp_queue.put({"ai_ratio": 0.0, "status": f"error: {str(e)}"})

# ================= Web 服务装载层 =================
_notify_callback = None  # 用于向主界面发送心跳信号的回调钩子

if FLASK_AVAILABLE:
    app = Flask(__name__)
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    _task_queue = queue.Queue()

    @app.route('/api/ping', methods=['GET'])
    def api_ping():
        """轻量级心跳接口，不占用任何算力"""
        if _notify_callback:
            _notify_callback()
        return jsonify({"status": "alive"}), 200

    @app.route('/api/check', methods=['POST'])
    def api_check():
        """主检测接口"""
        if _notify_callback:
            _notify_callback()  # 触发绿灯信号
            
        data = request.get_json(silent=True)
        if not data or 'text' not in data:
            return jsonify({"ai_ratio": 0.0, "status": "error: missing 'text' field"}), 400

        text = data['text'].strip()
        if not text:
            return jsonify({"ai_ratio": 0.0, "status": "too_short"}), 200

        resp_q = queue.Queue()
        _task_queue.put({"text": text, "resp_queue": resp_q})
        result = resp_q.get() 
        return jsonify(result), 200

def start_api_server(model_path, config, port=5005, notify_callback=None):
    """
    在 GUI 启动前调用的挂载函数
    :param notify_callback: 必须是一个无参函数 (通常是 PySide6 的 Signal.emit)
    """
    if not FLASK_AVAILABLE:
        print("❌ 未检测到 Flask，API 微服务挂载取消。(请在终端运行 pip install flask)")
        return

    global _notify_callback
    _notify_callback = notify_callback

    worker = APIModelWorker(model_path, config, _task_queue)
    worker.start()

    threading.Thread(
        target=lambda: app.run(host='127.0.0.1', port=port, use_reloader=False, debug=False),
        daemon=True
    ).start()
    
    print(f"🌐 节点联动 API 已于后台静默暴露: http://127.0.0.1:{port}/api/check")