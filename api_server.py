import os
import math
import threading
import queue
import logging

try:
    import numpy as np
    _NUMPY_OK = True
except ImportError:
    np = None
    _NUMPY_OK = False

try:
    from flask import Flask, request, jsonify
    FLASK_AVAILABLE = True
except ImportError as e:
    FLASK_AVAILABLE = False
    print(f"API Server Warning: Missing dependency {e}")

# ================= 从 core_engine 导入共用工具函数 =================
from core_engine import (
    get_token_length, calculate_human_features, smart_split_paragraph,
    _softmax, _load_ai_label_id
)

# ================= 线程安全的模型工作者 =================
class APIModelWorker(threading.Thread):
    def __init__(self, model_path, config, task_queue):
        super().__init__(daemon=True)
        self.model_path = model_path
        self.config = config
        self.task_queue = task_queue

    def run(self):
        from core_engine import get_shared_session

        onnx_path = os.path.join(self.model_path, "model.onnx")
        if not os.path.exists(onnx_path):
            print("API 微服务: 未找到 model.onnx")
            return

        force_cpu = self.config.get('force_cpu', False)
        session, tokenizer, device_type = get_shared_session(
            self.model_path, force_cpu=force_cpu)

        ai_label_id = _load_ai_label_id(self.model_path)

        print(f"API 微服务推理引擎已就绪 ({device_type})，正在监听请求...")

        while True:
            task = self.task_queue.get()
            if task is None:
                break

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
                    encoded = tokenizer.encode(para)
                    ids = encoded.ids[:512]
                    attn = (encoded.attention_mask[:512]
                            if encoded.attention_mask else [1] * len(ids))

                    ort_inputs = {
                        'input_ids': np.array([ids], dtype=np.int64),
                        'attention_mask': np.array([attn], dtype=np.int64),
                    }

                    logits = session.run(['logits'], ort_inputs)[0]

                    scaled_logits = logits / temp
                    probs = _softmax(scaled_logits)
                    raw_ai_score = float(probs[0][ai_label_id])

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
                resp_queue.put({"ai_ratio": 0.0, "status": f"error: {str(e)}"})

# ================= Web 服务装载层 =================
_notify_callback = None
_worker = None
_worker_model_path = None
_worker_config = None

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
            _notify_callback()

        data = request.get_json(silent=True)
        if not data or 'text' not in data:
            return jsonify({"ai_ratio": 0.0, "status": "error: missing 'text' field"}), 400

        text = data['text'].strip()
        if not text:
            return jsonify({"ai_ratio": 0.0, "status": "too_short"}), 200

        resp_q = queue.Queue()
        _task_queue.put({"text": text, "resp_queue": resp_q})
        try:
            result = resp_q.get(timeout=30)
        except queue.Empty:
            return jsonify({"ai_ratio": 0.0, "status": "error: request timeout"}), 500
        return jsonify(result), 200

def start_api_server(model_path, config, port=5005, notify_callback=None):
    """在 GUI 启动前调用的挂载函数"""
    global _notify_callback, _worker, _worker_model_path, _worker_config

    if not FLASK_AVAILABLE:
        print("❌ 未检测到 Flask，API 微服务挂载取消。(请在终端运行 pip install flask)")
        return

    _notify_callback = notify_callback
    _worker_model_path = model_path
    _worker_config = config

    _worker = APIModelWorker(model_path, config, _task_queue)
    _worker.start()

    threading.Thread(
        target=lambda: app.run(host='127.0.0.1', port=port, use_reloader=False, debug=False),
        daemon=True
    ).start()

    print(f"🌐 节点联动 API 已于后台静默暴露: http://127.0.0.1:{port}/api/check")


def restart_api_worker():
    """停止旧 Worker 并启动新的（force_cpu 切换后调用）"""
    global _worker, _worker_model_path, _worker_config

    if _worker is None or _worker_model_path is None:
        return

    _task_queue.put(None)
    _worker.join(timeout=5)

    _worker = APIModelWorker(_worker_model_path, _worker_config, _task_queue)
    _worker.start()
    print("⚡ API 微服务: Worker 已用新配置重启")
