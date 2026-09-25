# -*- coding: utf-8 -*-
"""
Task & Points AI Engine for Arizona RP Report Generator
Uses lightweight pure Python tensor math on task_ai_weights.json (no PyTorch required).
Inference speed: ~0.3 ms per text string.
"""
import os
import sys
import json

_WEIGHTS_CACHE = None

def get_weights_paths():
    base_dirs = []
    if getattr(sys, 'frozen', False):
        base_dirs.append(getattr(sys, '_MEIPASS', ''))
    base_dirs.extend([
        os.path.dirname(os.path.abspath(__file__)),
        r"C:\soft\Arizona-Helper-Repo",
        r"C:\soft\Arizona-Helper-Repo\moonloader",
        r"C:\Users\root\AppData\Local\Programs\Arizona Games Launcher\bin\arizona\moonloader",
    ])
    paths = []
    for b in base_dirs:
        if b:
            paths.append(os.path.join(b, "task_ai_weights.json"))
            paths.append(os.path.join(b, "ai_weights.json"))
    return paths

def load_task_ai():
    global _WEIGHTS_CACHE
    if _WEIGHTS_CACHE is not None:
        return _WEIGHTS_CACHE

    for p in get_weights_paths():
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and "conv_w" in data and "points" in data:
                    alphabet = data.get("chars", "")
                    char2idx = {c: i + 1 for i, c in enumerate(alphabet)}
                    data["_char2idx"] = char2idx
                    data["_emb_dim"] = len(data["emb"][0]) if data.get("emb") else 0
                    data["_num_filters"] = len(data["conv_b"]) if data.get("conv_b") else 0
                    data["_num_classes"] = len(data["classes"]) if data.get("classes") else 0
                    _WEIGHTS_CACHE = data
                    return _WEIGHTS_CACHE
            except Exception:
                continue
    return None

def predict_task_and_points(text):
    """
    Takes an arbitrary text string (e.g. chat log line, report description, OCR text).
    Returns dict:
      {
         "class_id": int,
         "task": str,
         "points": int,
         "confidence": float
      }
    """
    w = load_task_ai()
    if not w or not text:
        return {
            "class_id": -1,
            "task": "Не определено",
            "points": 0,
            "confidence": 0.0
        }

    char2idx = w["_char2idx"]
    max_len = w.get("max_len", 64)
    emb_dim = w["_emb_dim"]
    num_filters = w["_num_filters"]
    num_classes = w["_num_classes"]
    zero_vec = [0.0] * emb_dim

    # 1. Padded sequence embeddings
    padded = []
    for i in range(max_len):
        c = text[i] if i < len(text) else ""
        idx = char2idx.get(c, 0)
        if idx < len(w["emb"]):
            padded.append(w["emb"][idx])
        else:
            padded.append(zero_vec)

    # 2. 1D Convolution + ReLU + Global Max Pooling
    pooled = [-99999.0] * num_filters
    conv_w = w["conv_w"]
    conv_b = w["conv_b"]

    for t in range(max_len):
        left = padded[t - 1] if t > 0 else zero_vec
        mid = padded[t]
        right = padded[t + 1] if t < max_len - 1 else zero_vec
        for f in range(num_filters):
            wf = conv_w[f]
            s = conv_b[f]
            for c in range(emb_dim):
                wfc = wf[c]
                s += left[c] * wfc[0] + mid[c] * wfc[1] + right[c] * wfc[2]
            if s < 0.0:
                s = 0.0 # ReLU
            if s > pooled[f]:
                pooled[f] = s

    # 3. Dense / FC Classification Head
    fc_w = w["fc_w"]
    fc_b = w["fc_b"]
    scores = []
    for k in range(num_classes):
        out = fc_b[k]
        wfk = fc_w[k]
        for f in range(num_filters):
            out += pooled[f] * wfk[f]
        scores.append(out)

    # 4. Argmax & Softmax confidence
    best_idx = 0
    best_score = scores[0]
    for k in range(1, num_classes):
        if scores[k] > best_score:
            best_score = scores[k]
            best_idx = k

    max_s = max(scores)
    exp_scores = [pow(2.718281828, s - max_s) for s in scores]
    conf = (exp_scores[best_idx] / (sum(exp_scores) or 1.0)) * 100.0

    return {
        "class_id": best_idx,
        "task": w["classes"][best_idx],
        "points": w["points"][best_idx],
        "confidence": conf
    }

if __name__ == "__main__":
    test_lines = [
        "Вы посадили в КПЗ преступника Vasya_Pupkin /time 19:42",
        "Вы выписали штраф нарушителю на сумму 50000$",
        "эвакуация авто на штрафстоянку",
        "битва за завод касс скрины 19:30 19:40 19:50 победа",
        "патруль 30 минут с докладами в рацию",
        "блокпост 60 минут",
        "провели тренировку младшему составу",
        "провели допрос задержанного",
        "привет, как дела? куплю дом в гетто",
    ]
    for line in test_lines:
        res = predict_task_and_points(line)
        print(f"'{line}' -> [{res['points']} баллов] {res['task']} ({res['confidence']:.1f}%)")
