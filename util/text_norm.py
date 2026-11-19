"""文本归一化工具。

词达人的题干释义（stem.remark）、选项文本、词典例句的中文译文来自不同接口，
同一条中文可能带不同的标点、空格、全半角、词性前缀（如 "adj 客观的，公正的"），
直接字符串相等比较会大量漏配。此模块提供统一的宽松比较基准。

零依赖（只 import re/unicodedata），避免与项目内的 log/api 模块产生循环引用。
"""
import re
import unicodedata

# 标点、空白、全角空格、各类括号与引号
_PUNCT_RE = re.compile(
    r"[\s\u3000\u00a0"
    r"（）()【】\[\]{}<>"
    r"《》〈〉「」『』"
    r"“”\"'‘’`´"
    r"，,。.、；;：:！!？?·•—–\-_~～/\\|]+"
)

# 词性前缀：adj / n. / v / vt / 副词 等
_POS_RE = re.compile(
    r"^(?:adj|adv|n|v|vt|vi|prep|conj|pron|num|art|int|aux|"
    r"noun|verb|adjective|adverb|phrase|abbr)\b\.?\s*",
    re.IGNORECASE,
)


def norm_cn(text):
    """归一化：统一全半角 + 去除所有标点/空白 + 转小写。用于中文释义比较。"""
    if not text:
        return ""
    s = unicodedata.normalize("NFKC", str(text))
    return _PUNCT_RE.sub("", s).lower()


def strip_pos(text):
    """剥掉开头的词性标记，可能连缀多个（如 "adj n. 客观的"）。"""
    if not text:
        return ""
    s = str(text).strip()
    for _ in range(3):
        new = _POS_RE.sub("", s).strip()
        if new == s:
            break
        s = new
    return s


def norm_cn_no_pos(text):
    """归一化 + 去词性前缀。用于题干带词性、选项不带（或反之）的场景。"""
    return norm_cn(strip_pos(text))
