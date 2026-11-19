import json
import os
import threading

from log.log import Log
from util.text_norm import norm_cn, norm_cn_no_pos

answer_lib_logger = Log('answer_lib')

LIB_FILE = 'answer_lib.json'
_lock = threading.Lock()
_lib = None


def _lib_path():
    # 原来用 os.getcwd()：打包成 exe 后从快捷方式或其它目录启动时会读不到答案库，
    # 统一改成按数据目录解析（开发模式下就是项目根目录）。
    from util.runtime_paths import data_path

    return data_path('config', LIB_FILE)


def load_lib(force=False):
    global _lib
    if _lib is None or force:
        path = _lib_path()
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    _lib = json.load(f)
            except Exception as e:
                answer_lib_logger.error(f"加载答案库失败: {e}")
                _lib = {}
        else:
            _lib = {}
    return _lib


def _as_list(value):
    """统一答案格式为 list; 空值返回 None"""
    if value is None or value == '' or value == [] or value == {}:
        return None
    return value if isinstance(value, list) else [value]


# 归一化索引缓存: {归一化key: [原始key...]}; 答案库写入后需失效重建
_norm_index = {}
_pos_index = {}
_index_source = None


def _ensure_index(mapping):
    """为 mapping 建立 归一化 / 归一化+去词性 两级索引(带缓存)"""
    global _index_source
    if _index_source is mapping:
        return
    _norm_index.clear()
    _pos_index.clear()
    for key in mapping:
        if not isinstance(key, str) or not key:
            continue
        n1 = norm_cn(key)
        if n1:
            _norm_index.setdefault(n1, []).append(key)
        n2 = norm_cn_no_pos(key)
        if n2:
            _pos_index.setdefault(n2, []).append(key)
    _index_source = mapping


def _invalidate_index():
    global _index_source
    _index_source = None


def _lookup_with_fallback(mapping, word_zh):
    """
    答案库查找，三级回退：
      1. 原样精确命中（最快，覆盖绝大多数）
      2. 归一化命中：忽略空格/标点/全半角/引号括号差异
      3. 归一化 + 去词性前缀命中：题干带 "adj"/"n." 而库中 key 不带（或反之）
    """
    if not word_zh or not isinstance(mapping, dict):
        return None
    hit = _as_list(mapping.get(word_zh))
    if hit:
        return hit
    if not mapping:
        return None
    _ensure_index(mapping)
    for key in _norm_index.get(norm_cn(word_zh), []):
        hit = _as_list(mapping.get(key))
        if hit:
            answer_lib_logger.info(f"答案库归一化命中: '{word_zh}' -> '{key}'")
            return hit
    for key in _pos_index.get(norm_cn_no_pos(word_zh), []):
        hit = _as_list(mapping.get(key))
        if hit:
            answer_lib_logger.info(f"答案库去词性命中: '{word_zh}' -> '{key}'")
            return hit
    return None


def lookup(word_zh):
    """短语级答案查表（带归一化回退）"""
    return _lookup_with_fallback(load_lib(), word_zh)


WORD_KEY = '_word_answers'


def lookup_word(word_zh):
    """单词级答案(mode 42 选项单词/同义变体), 与短语答案分开存储"""
    return _lookup_with_fallback(load_lib().get(WORD_KEY) or {}, word_zh)


def add_word_answer(word_zh, words):
    if not word_zh or not words:
        return
    word_answers = [w for w in words if isinstance(w, str) and w]
    if not word_answers:
        return
    with _lock:
        lib = load_lib()
        word_map = lib.get(WORD_KEY, {})
        if not isinstance(word_map, dict):
            word_map = {}
        old = word_map.get(word_zh, [])
        if not isinstance(old, list):
            old = [old]
        added = False
        for w in word_answers:
            if w not in old:
                old.append(w)
                added = True
        if added:
            word_map[word_zh] = old
            lib[WORD_KEY] = word_map
        else:
            return
        _invalidate_index()
        try:
            with open(_lib_path(), 'w', encoding='utf-8') as f:
                json.dump(lib, f, ensure_ascii=False, indent=2)
        except Exception as e:
            answer_lib_logger.error(f"保存答案库失败: {e}")


def add_answer(word_zh, corrects):
    if not word_zh or not corrects:
        return
    answers = [c for c in corrects if isinstance(c, str) and c]
    if not answers:
        return
    with _lock:
        lib = load_lib()
        old = lib.get(word_zh, [])
        if not isinstance(old, list):
            old = [old]
        added = False
        for a in answers:
            if a not in old:
                old.append(a)
                added = True
        if not added:
            return
        lib[word_zh] = old
        _invalidate_index()
        try:
            with open(_lib_path(), 'w', encoding='utf-8') as f:
                json.dump(lib, f, ensure_ascii=False, indent=2)
        except Exception as e:
            answer_lib_logger.error(f"保存答案库失败: {e}")
