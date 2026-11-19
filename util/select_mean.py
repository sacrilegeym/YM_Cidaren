import difflib
import os
import random
import re

from api.main_api import query_word
from log.log import Log
from util.text_norm import norm_cn, strip_pos
from util.word_revert import word_revert

# log module
select_module = Log("select_mean")

# 释义开头的词性标记 -> 词性族
_POS_PREFIX = re.compile(r"^(adj|adv|noun|verb|vt|vi|n|v)\b\.?", re.IGNORECASE)
_POS_FAMILY = {
    'n': 'noun', 'noun': 'noun',
    'v': 'verb', 'verb': 'verb', 'vt': 'verb', 'vi': 'verb',
    'adj': 'adj', 'adv': 'adv',
}
# spaCy 的 coarse POS -> 词性族
_SPACY_POS = {
    'NOUN': 'noun', 'PROPN': 'noun',
    'VERB': 'verb', 'AUX': 'verb',
    'ADJ': 'adj', 'ADV': 'adv',
}


#
def handle_query_word_mean(public_info) -> None:
    # {'course_id': 'CET4_pre', 'list_id': 'CET4_pre_03', 'word': 'pack', 'update_version': '2402041319', 'means': [{'mean': ['verb', '收拾（行李）；装（箱）'], 'ph_info': {'ph_en': 'pæk', 'ph_en_url': '/Resource/unitAudio_EN/CET4_pre_03/pack.mp3', 'ph_us': 'pæk', 'ph_us_url': '/Resource/unitAudio_US/CET4_pre_03/pack.mp3'}, 'usages': [{'usage': None, 'phrases': [], 'phrases_infos': [], 'examples': [{'sen_id': '688', 'sen_content': "Mary, I hope you're {packed} and ready to leave.", 'sen_mean_cn': '玛丽，我希望你收拾好行李准备离开。', 'sen_source': '[CET4 07年12月]', 'sen_source_code': 'CET4_0712_LL1_1M_1', 'audio_file': '/CET4_pre_03/pack/688.mp3'}, {'sen_id': '695', 'sen_content': "I've {packed} it, but I can't remember which bag it's in.", 'sen_mean_cn': '我把它装好了，但我记不起它在哪个包里了。', 'sen_source': '[CET4 07年12月]', 'sen_source_code': 'CET4_0712_LL1_4W_3', 'audio_file': '/CET4_pre_03/pack/695.mp3'}, {'sen_id': '562846', 'sen_content': 'We can {pack} a suitcase with flashlights, a radio, food, drinking water and some tools.', 'sen_mean_cn': '我们可以把手电筒、收音机、食物、饮用水和一些工具打包装入手提箱。', 'sen_source': '[CET6 13年06月]', 'sen_source_code': 'CET6_13063_LP2_1_5_01', 'audio_file': '/CET4_pre_03/pack/562846.mp3'}, {'sen_id': '521628', 'sen_content': 'She hurriedly {packed} a bag and bought a train ticket for home.', 'sen_mean_cn': '她赶快收拾了一下手提包，买了车票回家。', 'sen_source': '', 'sen_source_code': '', 'audio_file': '/CET4_pre_03/pack/521628.mp3'}, {'sen_id': '521637', 'sen_content': 'She {packed} her few belongings in a bag and left.', 'sen_mean_cn': '她把她的几件东西装进包里便离开了。', 'sen_source': '', 'sen_source_code': '', 'audio_file': '/CET4_pre_03/pack/521637.mp3'}]}]}, {'mean': ['noun', '包；盒'], 'ph_info': {'ph_en': 'pæk', 'ph_en_url': '/Resource/unitAudio_EN/CET4_pre_03/pack.mp3', 'ph_us': 'pæk', 'ph_us_url': '/Resource/unitAudio_US/CET4_pre_03/pack.mp3'}, 'usages': [{'usage': None, 'phrases': [], 'phrases_infos': [], 'examples': [{'sen_id': '2185', 'sen_content': "Likewise, a married man who smokes more than a {pack} a day is likely to live as long as a divorced man who doesn't smoke.", 'sen_mean_cn': '同样地，一个每天吸烟超过一包的已婚男人很可能和一个不吸烟的离婚男人一样长寿。', 'sen_source': '[CET4 10年12月]', 'sen_source_code': 'CET4_1012_RP2_02_03', 'audio_file': '/CET4_pre_03/pack/2185.mp3'}, {'sen_id': '521639', 'sen_content': 'Each {pack} contains a book and accompanying CD.', 'sen_mean_cn': '每包内装书一本，并附光盘一张。', 'sen_source': '', 'sen_source_code': '', 'audio_file': '/CET4_pre_03/pack/521639.mp3'}, {'sen_id': '562705', 'sen_content': 'Envelopes are cheaper if you buy them in {packs} of 100.', 'sen_mean_cn': '信封如果按每包100个地成包购买会便宜一些。', 'sen_source': '', 'sen_source_code': '', 'audio_file': '/CET4_pre_03/pack/562705.mp3'}]}, {'usage': {'marked': 'a {pack} of <i>sth</i> ', 'text': 'a pack of sth ', 'cn': '一包/盒…', 'eg': 'a {pack} of cigarettes', 'eg_cn': ''}, 'phrases': ['a {pack} of … 一包……'], 'phrases_infos': [{'sen_id': '156901', 'sen_content': 'a {pack} of …', 'sen_mean_cn': '一包……', 'audio_file': '/CET4_pre_03/pack/156901.mp3'}], 'examples': [{'sen_id': '477487', 'sen_content': 'He reached into a drawer for a {pack} of cigarettes.', 'sen_mean_cn': '他把手伸进抽屉里，掏出一包香烟。', 'sen_source': '', 'sen_source_code': '', 'audio_file': '/CET4_pre_03/pack/477487.mp3'}]}]}], 'version': '2', 'has_au': 1, 'au_addr': 'https://resource-cdn.vocabgo.com', 'au_word': 'pack', 'word_info': {'store_status': 0}}
    means = []
    if public_info.word_query_result.get('options'):
        # {'course_id': 'XSJ_4', 'list_id': 'XSJ_4_7_A', 'word': 'detached', 'update_version': '2402041319', 'ph_en': 'dɪˈtætʃt', 'ph_us': 'dɪˈtætʃt', 'options': [{'content': {'mean': 'adj  超然的；冷漠的', 'ph_info': {'ph_en': 'dɪˈtætʃt', 'ph_en_url': '/Resource/unitAudio_EN/XSJ_4_7_A/detached.mp3', 'ph_us': 'dɪˈtætʃt', 'ph_us_url': '/Resource/unitAudio_US/XSJ_4_7_A/detached.mp3'}, 'usage_infos': [{'sen_id': '83415', 'sen_content': '{detached} observer', 'sen_mean_cn': '超然的旁观者', 'audio_file': '/XSJ_4_7_A/detached/83415.mp3'}, {'sen_id': '83416', 'sen_content': '{detached} attitude', 'sen_mean_cn': '超然的态度', 'audio_file': '/XSJ_4_7_A/detached/83416.mp3'}], 'usage': ['{detached} observer 超然的旁观者', '{detached} attitude 超然的态度'], 'example': [{'sen_id': '150878', 'sen_content': 'She wanted him to stop being so cool, so {detached}.', 'sen_mean_cn': '她希望他不再那么冷酷无情，那么无动于衷。', 'sen_source': '', 'sen_source_code': '', 'audio_file': '/XSJ_4_7_A/detached/150878.mp3'}, {'sen_id': '282590', 'sen_content': 'Through all the arguments among other committee members, she kept a {detached} attitude.', 'sen_mean_cn': '在其他委员会成员辩论时，她始终保持超然的态度。', 'sen_source': '', 'sen_source_code': '', 'audio_file': '/XSJ_4_7_A/detached/282590.mp3'}, {'sen_id': '445016', 'sen_content': 'Throughout the novel, the whole story is seen through the eyes of a {detached} observer.', 'sen_mean_cn': '小说自始至终是从一个超然的旁观者的角度来看整个故事的。', 'sen_source': '', 'sen_source_code': '', 'audio_file': '/XSJ_4_7_A/detached/445016.mp3'}, {'sen_id': '150879', 'sen_content': 'He tries to remain emotionally {detached} from the prisoners, but fails.', 'sen_mean_cn': '他试图不带感情地对待那些犯人，但是做不到。', 'sen_source': '', 'sen_source_code': '', 'audio_file': '/XSJ_4_7_A/detached/150879.mp3'}]}}, {'content': {'mean': 'adj 客观的，公正的', 'ph_info': {'ph_en': 'dɪˈtætʃt', 'ph_en_url': '/Resource/unitAudio_EN/XSJ_4_7_A/detached.mp3', 'ph_us': 'dɪˈtætʃt', 'ph_us_url': '/Resource/unitAudio_US/XSJ_4_7_A/detached.mp3'}, 'usage_infos': [{'sen_id': '89188', 'sen_content': '{detached} evaluation', 'sen_mean_cn': '客观公正的评估', 'audio_file': '/XSJ_4_7_A/detached/89188.mp3'}, {'sen_id': '89189', 'sen_content': 'take a {detached} view', 'sen_mean_cn': '采用公正客观的视角', 'audio_file': '/XSJ_4_7_A/detached/89189.mp3'}], 'usage': ['{detached} evaluation 客观公正的评估', 'take a {detached} view 采用公正客观的视角'], 'example': [{'sen_id': '150929', 'sen_content': 'As a judge, he has always been {detached} in dealing with cases.', 'sen_mean_cn': '作为法官，他在处理案件时总是客观公正的。', 'sen_source': '', 'sen_source_code': '', 'audio_file': '/XSJ_4_7_A/detached/150929.mp3'}, {'sen_id': '150922', 'sen_content': 'Evaluation of public servants shall be {detached}.', 'sen_mean_cn': '对公务员的考核应当客观公正。', 'sen_source': '', 'sen_source_code': '', 'audio_file': '/XSJ_4_7_A/detached/150922.mp3'}, {'sen_id': '150915', 'sen_content': 'A judge must be {detached} when weighing evidence.', 'sen_mean_cn': '法官在掂量证据时应该客观公正。', 'sen_source': '', 'sen_source_code': '', 'audio_file': '/XSJ_4_7_A/detached/150915.mp3'}]}}], 'version': '1', 'has_au': 1, 'au_addr': 'https://resource-cdn.vocabgo.com', 'au_word': 'detached', 'word_info': {'store_status': 0}}
        for mean in public_info.word_query_result['options']:
            means.append(re.sub("（.*）", "", mean['content']['mean']))
    else:
        for mean in public_info.word_query_result['means']:
            means.append(' '.join(mean['mean']))
            # means.append(re.sub("（.*）", "", mean['content']['mean']))
    select_module.logger.info(f"提取到正确选项：{means}")
    public_info.word_means = means


# extract options
def filler_option(public_info) -> list:
    """
    提取题目中返回的选项以及排序优化
    :param public_info:
    :return:
    """
    # 试题选项
    options = []
    source = []
    # 填充选项
    for option_info in public_info.exam["options"]:
        option = option_info['content']
        source.append(option)
        if option in public_info.word_list:
            options.insert(0, option)
        else:
            options.append(option)
    public_info.source_option = source
    select_module.logger.info(f"提取到题目选项{options}")
    return options


_SEG_SPLIT = re.compile(r"[；;，,、/（）()\s…\.·]+")
_SEG_TAIL = re.compile(r"[的地得了着]+$")

# 单字义项（"期""号""棍""会"）经常是唯一能在译文里找到的线索，
# 但这些虚词单字在中文里到处都是，放进打分只会制造噪声。
_SEG_STOP_CHARS = set("的地得了着是在有和与或个一不把被使让为以对从到就还也都很吗呢吧啊之其而且但所这那它他她你我们")


def _gloss_segments(gloss):
    """
    把一条中文释义切成可比较的词段 -> {词段: 权重}。
    "adj 首席的，主管的" -> {'首席': 2, '主管': 2, '席': 1, '管': 1}
    "verb 把……看作；认为" -> {'把': 1, '看作': 2, '认为': 2, '作': 1, '为'(虚词丢弃)}
    "noun 版次，期，号" -> {'版次': 2, '期': 1, '号': 1, '次': 1}

    多字词段权重 = 字数；单字权重 = 1，且过滤虚词。
    另外补两类单字：
      · **词尾中心语**：中文复合名词的中心语在词尾，
        "协会"对"医学会"、「棍」对「拐棍」、「期」对「一期」都靠这个命中；
      · **词首修饰字**：译文常用近义复合词替换，
        平台"年终端分红"对应 bonus 的"红利"（共享「红」）、"奖"在"奖金"里，
        只认整段或词尾都会漏。
    """
    best = {}

    def add(seg, weight):
        if not seg:
            return
        if len(seg) == 1 and seg in _SEG_STOP_CHARS:
            return
        if weight > best.get(seg, 0):
            best[seg] = weight

    for piece in _SEG_SPLIT.split(strip_pos(gloss)):
        if not piece:
            continue
        for candidate in (piece, _SEG_TAIL.sub("", piece)):
            norm = norm_cn(candidate)
            if len(norm) >= 2:
                add(norm, len(norm))
                add(norm[-1], 1)  # 词尾中心语
                add(norm[0], 1)   # 词首修饰字
            elif len(norm) == 1:
                add(norm, 1)
    return best


def _gloss_pos(gloss):
    """读释义开头的词性标记 -> noun/verb/adj/adv，读不到返回 None"""
    match = _POS_PREFIX.match(str(gloss or "").strip())
    if not match:
        return None
    return _POS_FAMILY.get(match.group(1).lower())


_nlp = None


def _get_nlp():
    """按需加载 spaCy 模型（复用项目自带的那份 en_core_web_sm）"""
    global _nlp
    if _nlp is None:
        import spacy
        from util.runtime_paths import resource_path

        _nlp = spacy.load(resource_path("en_core_web_sm"))
    return _nlp


def stem_word_pos(exam):
    """
    从题干英文句子推断被考单词此刻的词性（noun/verb/adj/adv）。

    mode 11 的题干形如 'Jack {sacrificed} his life to save the child...'，
    平台会把同一个释义按不同词性拆成两个选项（"noun 牺牲；舍弃" / "verb 牺牲；舍弃"），
    正解是句中词性对应的那条 —— 中文译文完全分不出来，但 spaCy 能直接标出
    （sacrificed -> VERB）。题干只有单词（无句子）时返回 None，不参与判断。
    """
    if not isinstance(exam, dict):
        return None
    stem = exam.get('stem') or {}
    content = stem.get('content') or ''
    match = re.search(r"\{([^}]+)\}", content)
    if not match:
        return None
    target = match.group(1).strip()
    if not target or ' ' in target:
        return None
    sentence = re.sub(r"[{}]", "", content)
    sentence = re.sub(r"\s+", " ", sentence).strip()
    if not sentence:
        return None
    try:
        doc = _get_nlp()(sentence)
    except Exception:
        return None
    lower = target.lower()
    for token in doc:
        if token.text.lower() == lower or token.lemma_.lower() == lower:
            return _SPACY_POS.get(token.pos_)
    return None


def sense_score(gloss, remark_norm):
    """
    用题干中文译文给一条候选释义打分：释义词段在译文里出现得越多、越长，分越高。

    mode 11/15/16/21/22 的题干是一句英文 + 它的中文译文（stem.remark），
    选项里常常同时出现同一个词的多个义项（如 impact 的"影响/撞击/产生影响"），
    平台要的是**该句语境下**的那个义项。正确义项的中文必然出现在题干译文里，
    错误义项不会 —— 这比"哪个选项排在前面"可靠得多。

    分两段加权：多字词段按字数计分；单字（含词尾中心语，如"协会"的"会"、
    "棒；杖；棍"的"棍"）只计 1 分且**总额封顶 2 分**，
    避免若干"碰巧撞上的单字"压过真正命中的多字词段。
    """
    if not remark_norm:
        return 0
    multi = 0
    single = 0
    for seg, weight in _gloss_segments(gloss).items():
        if seg not in remark_norm:
            continue
        if weight >= 2:
            multi += weight
        else:
            single += 1
    return multi + min(single, 2)


def _norm_sentence(text):
    """句子归一化：去花括号、合并空白、小写 —— 用于比对题干与词典例句"""
    raw = str(text or "")
    for ch in ("{", "}", "\u00a0"):
        raw = raw.replace(ch, "")
    return " ".join(raw.split()).lower()


def sense_from_examples(exam, word_query_result):
    """
    用平台自己的词典例句反查义项（确定性判据）。

    词达人的题目句子通常直接取自该词的例句库，而每条例句在接口返回里
    归属于某个具体义项。所以只要"题干句子 == 某条例句"，那个义项就是标准答案：

        tough     题干 'Many homeless people are facing a {tough} winter.'
                  -> 例句命中义项 'adj 艰苦的；棘手的'（正确项正是"棘手的；艰苦的"）
        character -> 'noun 性格，个性；特点'
        cure      -> 'verb 治愈，治好'

    :return: 命中的义项文本（如 'adj 艰苦的；棘手的'），未命中返回 None
    """
    if not isinstance(exam, dict) or not isinstance(word_query_result, dict):
        return None
    target = _norm_sentence((exam.get("stem") or {}).get("content"))
    if not target:
        return None

    entries = word_query_result.get("means") or word_query_result.get("options") or []
    if not isinstance(entries, list):
        return None

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        # 取这一条义项的文本（两种接口结构都兼容）
        mean_text = None
        if isinstance(entry.get("mean"), list):
            mean_text = " ".join(str(x) for x in entry["mean"])
        else:
            content = entry.get("content")
            if isinstance(content, dict):
                mean_text = content.get("mean")
        if not mean_text:
            continue
        # 收集这条义项下的全部例句
        examples = []
        for usage in (entry.get("usages") or []):
            if isinstance(usage, dict):
                examples.extend(usage.get("examples") or [])
        content = entry.get("content")
        if isinstance(content, dict):
            examples.extend(content.get("example") or [])
        for example in examples:
            if not isinstance(example, dict):
                continue
            if _norm_sentence(example.get("sen_content")) == target:
                return mean_text
    return None


def select_mean(public_info) -> int:
    """
    英译汉 选择匹配的意思

    步骤：
      1. 收集所有"命中本词某个义项"的选项，记录匹配层级
         （0=归一化后相等，1=字符多重集相等（选项内文字顺序被平台打乱），2=释义被包含）
      2. 只有一个候选 → 直接提交
      3. 多个候选（同词多义项）→ 用题干中文译文消歧：
         释义词段在译文里出现得越多越可信；同分再按 匹配层级 → 义项主次 → 选项顺序
      4. 一个候选都没有 → difflib 相似度兜底 → 仍不达标才随机
    """
    options = filler_option(public_info)
    means = [m for m in (getattr(public_info, 'word_means', None) or []) if m]
    if not options:
        return 0
    if not means:
        select_module.logger.warning("无候选释义，随机提交")
        return random.randint(0, len(options) - 1)
    norm_options = [norm_cn(option) for option in options]
    norm_means = [norm_cn(mean) for mean in means]

    # 0 题目记忆：答对过的直接复用；答错过的先排除（负记忆）
    remembered_answer, known_wrong = None, []
    try:
        from util.question_memory import lookup as memory_lookup

        remembered_answer, known_wrong = memory_lookup(getattr(public_info, "exam", None))
    except Exception as e:
        select_module.logger.error(f"读取题目记忆失败: {e}")
    if remembered_answer:
        target = norm_cn(remembered_answer)
        for index, option in enumerate(norm_options):
            if option and (option == target or sorted(option) == sorted(target)):
                select_module.logger.info(
                    f"题目记忆命中，直接选第{index + 1}个选项[{options[index]}]"
                )
                return index
    banned = {norm_cn(text) for text in (known_wrong or []) if text}

    # 0.5 词典例句反查：题干句子若与平台例句库某条例句一致，直接用该例句所属义项
    #     这是确定性判据（题目句子本来就取自例句库），优先级仅次于已验证的记忆
    try:
        sense = sense_from_examples(
            getattr(public_info, "exam", None),
            getattr(public_info, "word_query_result", None),
        )
    except Exception as e:
        sense = None
        select_module.logger.error(f"词典例句反查失败: {e}")
    if sense:
        target_sense = norm_cn(sense)
        for index, option in enumerate(norm_options):
            if not option or not target_sense:
                continue
            if (option == target_sense
                    or sorted(option) == sorted(target_sense)
                    or target_sense in option
                    or option in target_sense):
                select_module.logger.info(
                    f"词典例句反查命中义项[{sense}]，选第{index + 1}个选项[{options[index]}]"
                )
                return index
        select_module.logger.info(f"例句反查到义项[{sense}]，但选项中没有对应释义，继续规则判断")

    # 1 收集候选
    candidates = []
    for index, option in enumerate(norm_options):
        if not option:
            continue
        if option in banned:
            select_module.logger.info(f"题目记忆：排除已知错项第{index + 1}个[{options[index]}]")
            continue
        for mean_index, mean in enumerate(norm_means):
            if not mean:
                continue
            if option == mean:
                candidates.append((index, mean_index, 0))
                break
            if sorted(option) == sorted(mean):
                candidates.append((index, mean_index, 1))
                break
            if mean in option:
                candidates.append((index, mean_index, 2))
                break

    if candidates:
        if len(candidates) == 1:
            index, mean_index, tier = candidates[0]
            select_module.logger.info(f"唯一候选第{index + 1}个选项[{options[index]}]（层级{tier}）")
            return index
        # 2 多义项消歧：用题干译文 + 题干词性
        stem = public_info.exam.get('stem') if isinstance(public_info.exam, dict) else None
        remark = stem.get('remark') if isinstance(stem, dict) else None
        remark_norm = norm_cn(remark)
        word_pos = stem_word_pos(public_info.exam)
        scored = []
        for index, mean_index, tier in candidates:
            pos_match = 1 if (word_pos and _gloss_pos(options[index]) == word_pos) else 0
            score = sense_score(options[index], remark_norm)
            # 覆盖度 = 得分 / 释义字数。同分时短释义的证据更集中，
            # 例如 surrounded 的两个义项都得 1 分（都只撞上"围"），
            # "包围；围绕"(4字) 比 "围绕；与…密切相关"(7字) 更该被选中。
            gloss_len = len(norm_cn(strip_pos(options[index]))) or 1
            coverage = score / gloss_len
            scored.append((score, pos_match, coverage, tier, mean_index, index))
        # 排序优先级：译文得分 > 题干词性匹配 > 覆盖度 > 匹配层级 > 义项主次 > 选项顺序
        #
        # 注：试过把词性提到得分前面（救 cure 那题），但会让 extent/straight/as
        # 三道原本正确的题变错（spaCy 对这些词的词性判断与题目义项不一致），
        # 所以词性只作为同分时的加强项。cure 这类由"词典例句反查"在上游解决。
        best = max(
            scored,
            key=lambda item: (item[0], item[1], item[2], -item[3], -item[4], -item[5]),
        )
        picked = options[best[5]]
        if best[0] > 0:
            select_module.logger.info(
                f"义项消歧(译文得分{best[0]}, 词性={word_pos or '-'}, 词性匹配={best[1]}, 覆盖度{best[2]:.2f})"
                f"选第{best[5] + 1}个选项[{picked}]"
                f"，候选={[(options[i], s, round(c, 2), p) for s, p, c, _, _, i in scored]}"
            )
        elif best[1] > 0:
            select_module.logger.info(
                f"多候选无译文线索，按题干词性({word_pos})选第{best[5] + 1}个选项[{picked}]"
            )
        else:
            select_module.logger.info(
                f"多候选无译文线索，按义项主次选第{best[5] + 1}个选项[{picked}]"
            )
        return best[5]

    # 3 相似度兜底
    best_ratio = None
    for index, option in enumerate(norm_options):
        for mean in norm_means:
            if not option or not mean:
                continue
            ratio = difflib.SequenceMatcher(None, option, mean).ratio()
            if best_ratio is None or ratio > best_ratio[0]:
                best_ratio = (ratio, index)
    if best_ratio and best_ratio[0] >= 0.6:
        select_module.logger.info(
            f"相似度{best_ratio[0]:.2f}选第{best_ratio[1] + 1}个选项[{options[best_ratio[1]]}]"
        )
        return best_ratio[1]

    # 匹配失败 随机提交一个
    select_module.logger.warning("匹配失败，随机提交")
    return random.randint(0, len(options) - 1)


# select match word
def _gloss_match(target_norm, gloss_norm, min_ratio=0.75):
    """
    比较"题干中文"与"某个选项单词的词义"，返回 (层级, 相似度) 或 None。
    层级越小越可信：
      0 = 归一化后完全相等
      1 = 字符多重集相等（平台把义项内词序打乱，如"刻板的；严格的" vs "严格的；刻板的"）
      2 = 互相包含（一侧是另一侧的子串）
      3 = difflib 相似度达阈值
    """
    if not target_norm or not gloss_norm:
        return None
    if target_norm == gloss_norm:
        return 0, 1.0
    if sorted(target_norm) == sorted(gloss_norm):
        return 1, 1.0
    if gloss_norm in target_norm or target_norm in gloss_norm:
        return 2, 0.9
    ratio = difflib.SequenceMatcher(None, target_norm, gloss_norm).ratio()
    if ratio >= min_ratio:
        return 3, ratio
    return None


def select_match_word(public_info, word_mean) -> int:
    """
    看义选词（mode 17/18）：给出中文释义，从若干英文单词里选对的那个。

    逐个选项查它自己的词义再比对。旧实现只做精确/字符集等值，遇到
    "题干去掉词性、词库带词性" 或 "义项词序颠倒" 就会整体失配，然后去猜第 3 个选项
    （实测 25 题里失配 14 次）。这里改成分层打分：全选项比较后取最可信的那个，
    只有完全比不出线索时才退回原本的猜测。
    """
    options = filler_option(public_info)
    target = norm_cn(word_mean)
    if not target or not options:
        select_module.logger.error("题干预设为空,猜第3个选项")
        return 2

    best = None  # (层级, -相似度, 提交下标)
    for word in options:
        query_word(public_info, word)
        handle_query_word_mean(public_info)
        for mean in (public_info.word_means or []):
            hit = _gloss_match(target, norm_cn(mean))
            if not hit:
                continue
            tier, ratio = hit
            index = public_info.source_option.index(word)
            candidate = (tier, -ratio, index)
            if best is None or candidate[:2] < best[:2]:
                best = candidate
        if best and best[0] == 0:
            break  # 已经精确命中，不必再多发请求

    if best:
        select_module.logger.info(f"词义匹配成功: 第{best[2] + 1}个选项（层级{best[0]}）")
        return best[2]

    select_module.logger.error("匹配失败,猜第3个选项")
    return 2


def is_word_exist(public_info, option) -> bool:
    """
    word是否存在word_list中
    :param public_info:
    :param option: word
    :return: None
    """
    if option in public_info.word_list:
        # word is exist word_list
        query_word(public_info, option)
        return True
    else:
        select_module.logger.info('转原型')
        revert_option = word_revert(option)
        if revert_option in public_info.word_list:
            query_word(public_info, revert_option)
            return True
    return False


# extract sentence word
def word_examples(public_info, options) -> str:
    """
    匹配单词例句中的单词,也就是例句中的单词
    :param public_info:
    :param options: words
    :return: word
    """
    exam_zh = norm_cn(public_info.exam['stem']['remark'])
    for word in options:
        if is_word_exist(public_info, word):
            if public_info.word_query_result.get('means'):
                query_result = public_info.word_query_result['means']
                for means in query_result:
                    for examples in means['usages']:
                        for sentences in examples['examples']:
                            # match same mean（归一化比较，避免标点/空格/引号差异漏配）
                            if exam_zh and norm_cn(sentences["sen_mean_cn"]) == exam_zh:
                                # answer
                                return re.findall(r'{(.+?)}', sentences['sen_content'])[0]
            else:
                query_result = public_info.word_query_result['options']
                for contents in query_result:
                    for example in contents['content']['example']:
                        if exam_zh and norm_cn(example["sen_mean_cn"]) == exam_zh:
                            # answer
                            return re.findall(r'{(.+?)}', example['sen_content'])[0]

    return ''
