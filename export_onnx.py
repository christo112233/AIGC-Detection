"""一次性脚本：将 BERT 模型导出为 ONNX 格式

使用前确保已安装: pip install onnx torch transformers
"""
import os
import sys

try:
    import onnx as _onnx  # noqa: F401
except ImportError:
    print("错误: 缺少 onnx 库，请先执行: pip install onnx")
    sys.exit(1)

import torch
from transformers import AutoModelForSequenceClassification

model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AIGC_Model")

print("加载 PyTorch 模型...")
model = AutoModelForSequenceClassification.from_pretrained(
    model_path, local_files_only=True)
model.eval()

print("导出 ONNX...")
dummy_ids = torch.randint(0, 21128, (1, 32), dtype=torch.int64)
dummy_mask = torch.ones(1, 32, dtype=torch.int64)

onnx_path = os.path.join(model_path, "model.onnx")
torch.onnx.export(
    model,
    (dummy_ids, dummy_mask),
    onnx_path,
    input_names=["input_ids", "attention_mask"],
    output_names=["logits"],
    dynamic_axes={
        "input_ids": {0: "batch", 1: "seq"},
        "attention_mask": {0: "batch", 1: "seq"},
    },
    opset_version=14,
)

print(f"导出完成: {onnx_path}")
print(f"文件大小: {os.path.getsize(onnx_path) / 1024 / 1024:.1f} MB")
