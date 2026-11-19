"""题目记忆库：把遇到过的题目和判分结果记下来，下次同题直接命中。

为什么不用模型微调：
  · 记忆需要的性质是"精确、可审计、可增量更新"，这是数据库的事，不是权重的事；
  · 词达人 mode 11 判错时 `answer_corrects=[]`（平台不给正确答案），
    所以能学到的信息只有两种：
        答对 -> 我提交的那个选项就是正确答案
        答错 -> 我提交的那个选项不是答案（负记忆）
  · 负记忆已经足够：同一道题只有 2 个候选义项时，排除掉错的那个，下次必然选对。

存储结构（config/question_memory.json）：
    {
      "correct": {"<指纹>": {"answer": "verb 包围；围绕", "hits": 3, "ts": "..."}},
      "wrong":   {"<指纹>": ["verb 围绕；与…密切相关"]}
    }

指纹 = 英文题干 ＋ 中文译文 的归一化文本（不含选项：同一题每次选项池可能不同）。
"""
import hashlib
import json
import os
import threading
import time

from log.log import Log
from util.runtime_paths import data_path
from util.text_norm import norm_cn

memory_logger = Log("question_memory").logger

MEMORY_FILE = "question_memory.json"
MAX_ENTRIES = 5000
_lock = threading.Lock()
_cache = None


def _path():
    return data_path("config", MEMORY_FILE)


def _load():
    global _cache
    if _cache is None:
        try:
            with open(_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                data = {}
        except FileNotFoundError:
            data = {}
        except Exception as e:
            memory_logger.error(f"读取题目记忆失败: {e}")
            data = {}
        data.setdefault("correct", {})
        data.setdefault("wrong", {})
        _cache = data
    return _cache


def _save(data):
    try:
        os.makedirs(os.path.dirname(_path()), exist_ok=True)
        with open(_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
    except Exception as e:
        memory_logger.error(f"保存题目记忆失败: {e}")


def _norm_text(text):
    """题干归一化：去掉花括号、合并空白、转小写"""
    raw = str(text or "")
    for ch in ("{", "}", "\u00a0"):
        raw = raw.replace(ch, "")
    return " ".join(raw.split()).lower()


def fingerprint(exam):
    """题目指纹：英文题干 + 中文译文（选项不进指纹，因为每次选项池可能不同）"""
    if not isinstance(exam, dict):
        return None
    stem = exam.get("stem") or {}
    content = _norm_text(stem.get("content"))
    remark = norm_cn(stem.get("remark"))
    if not content and not remark:
        return None
    raw = f"{content}|{remark}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def _option_texts(exam):
    options = exam.get("options") if isinstance(exam, dict) else None
    return [
        o.get("content")
        for o in (options or [])
        if isinstance(o, dict) and o.get("content")
    ]


def _submitted_text(exam, submitted):
    """把提交值（选项下标 / 文本 / dict）还原成选项文本"""
    options = _option_texts(exam)
    if isinstance(submitted, bool):
        return None
    if isinstance(submitted, int):
        if 0 <= submitted < len(options):
            return options[submitted]
        return None
    if isinstance(submitted, str):
        # 汉译英这类直接提交文本，只记短语型答案（短且不含逗号拼接的多选项）
        return submitted.strip() or None
    return None  # dict（连线题）等不记


def record_answer(exam, submitted, correct):
    """
    判分后调用：答对记正解，答错记错项。
    :param exam: 本题的 exam 快照（判分时 public_info.exam 已经换到下一题了，请传快照）
    :param submitted: 提交的答案
    :param correct: answer_result == 1
    """
    fp = fingerprint(exam)
    text = _submitted_text(exam, submitted)
    if not fp or not text:
        return
    with _lock:
        data = _load()
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        if correct:
            entry = data["correct"].get(fp) or {"hits": 0}
            entry["answer"] = text
            entry["hits"] = int(entry.get("hits", 0)) + 1
            entry["ts"] = stamp
            data["correct"][fp] = entry
            # 之前误判为错的记录要清掉
            wrong = data["wrong"].get(fp)
            if wrong:
                wrong = [w for w in wrong if norm_cn(w) != norm_cn(text)]
                if wrong:
                    data["wrong"][fp] = wrong
                else:
                    data["wrong"].pop(fp, None)
            memory_logger.info(f"题目记忆：记为正确 [{text}]（同题第 {entry['hits']} 次）")
        else:
            wrong = data["wrong"].get(fp) or []
            if all(norm_cn(w) != norm_cn(text) for w in wrong):
                wrong.append(text)
            data["wrong"][fp] = wrong
            memory_logger.info(f"题目记忆：记为错项 [{text}]，下次同题排除")
        # 简易容量控制
        for key in ("correct", "wrong"):
            if len(data[key]) > MAX_ENTRIES:
                for old in list(data[key].keys())[: len(data[key]) - MAX_ENTRIES]:
                    data[key].pop(old, None)
        _save(data)


def lookup(exam):
    """
    查题目记忆。
    :return: (正确选项文本或 None, 错项文本列表)
    """
    fp = fingerprint(exam)
    if not fp:
        return None, []
    data = _load()
    entry = data["correct"].get(fp)
    answer = entry.get("answer") if isinstance(entry, dict) else entry
    wrong = list(data["wrong"].get(fp) or [])
    if answer:
        memory_logger.info(f"题目记忆命中（{entry.get('hits', 1) if isinstance(entry, dict) else 1} 次）：{answer}")
    elif wrong:
        memory_logger.info(f"题目记忆：已知 {len(wrong)} 个错项，将排除 {wrong}")
    return answer, wrong


def stats():
    data = _load()
    return len(data["correct"]), len(data["wrong"])
