import json
import os

from log.log import Log


class PublicInfo:
    # 这俩暂时不知道有啥用
    task_type: str
    task_type_int: int

    #
    def __init__(self, path):
        self.get_word_list_result = {}
        self.path = path
        with open(os.path.join(self.path, "config", "config.json"), 'r', encoding='utf-8') as f:
            # 用户配置文件
            user_config = json.load(f)
            if user_config['min_time'] >= 2 and user_config['max_time'] >= 2:
                self._min_time = user_config['min_time']
                self._max_time = user_config['max_time']
            else:
                self._min_time = 2
                self._max_time = 2
            self._spend_min_time = user_config['spend_min_time']
            self._spend_max_time = user_config['spend_max_time']
            self._br_choices = user_config['br_choices']
            self._headers_accept_encoding = user_config['accept_encoding']
            self._version = user_config['version']
            self._know_version = user_config['know_version']
            self._read = user_config['read']
            self._play_music = user_config.get('play_music', True)  # 默认为True
            self._music_path = user_config.get('music_path', "")  # 默认为空，使用默认音乐
            # 自学习开关(独立控制两个记忆库的写入; 关闭只停写入, 读取不受影响)
            self._self_learn_lib = user_config.get('self_learn_lib', True)  # 答案库 self_learn: 判分答案写入 answer_lib
            self._self_learn_pool = user_config.get('self_learn_pool', True)  # 词表池 self_learn: word_pool.json 持久化
            # 每题目标用时(秒)与抖动比例：限时题型（班级测试单选 10 秒之类）靠它精准控节奏。
            # <=0 表示回退到旧的 min_time/max_time 随机区间。
            self._question_seconds = float(user_config.get('question_seconds', 8) or 0)
            self._question_jitter = float(user_config.get('question_jitter', 0.12) or 0)
            # 显式区间：每题在 [min, max] 之间随机（min == max 即固定用时）。
            # 没配区间时按 question_seconds ± jitter 推导，兼容老配置。
            default_span = self._question_seconds * self._question_jitter
            self._question_seconds_min = float(
                user_config.get('question_seconds_min', max(0.1, self._question_seconds - default_span)) or 0
            )
            self._question_seconds_max = float(
                user_config.get('question_seconds_max', max(0.1, self._question_seconds + default_span)) or 0
            )
            if self._question_seconds_min > self._question_seconds_max:
                self._question_seconds_min, self._question_seconds_max = (
                    self._question_seconds_max, self._question_seconds_min)
            self._question_seconds_min = max(0.1, self._question_seconds_min)
            self._question_seconds_max = max(self._question_seconds_min, self._question_seconds_max)

        # 任务列表
        self.task_list = ""
        # 答题对错计数(供进度条右侧统计显示)
        self.right_count = 0
        self.wrong_count = 0
        # 跳过计数(无匹配答案跳过未提交的题)
        self.skip_count = 0
        # query_answer
        self._topic_code = ''
        self.word_query_result = ''
        self.word_means = ''
        self.exam = ''
        # all word
        self.word_list = []
        # 中文释义 -> 英文短语映射(用于汉译英术语课程)
        self.word_dict = {}
        # 跨进程加载历史词表(全局词表池, mode 73 兜底跨单元前缀单词)
        try:
            with open(os.path.join(self.path, "config", "word_pool.json"), 'r', encoding='utf-8') as f:
                self.word_dict = json.load(f)
        except Exception:
            pass
        # translate
        self.zh_en = ''
        # all unit info
        self.all_unit = []
        self.not_complete_unit = {}
        self.task_id = ''
        self.now_unit = ''
        self.course_id = ''
        self._task_name = ''
        # class task
        self.class_task = []
        # 任务类型选择（默认1）
        self._task_choices = 1
        # unit task amount
        self.task_total_count = ''
        self.now_page = ''
        self.release_id = ''
        # self_built
        self.get_book_words_data = []
        self.is_self_built = False  # bool
        self.all_unit_name = []
        self.source_option = []
        pub_info = Log("public_info")
        pub_info.logger.info("公共组件初始化成功")

    @property
    # only read
    def topic_code(self):
        return self._topic_code

    @topic_code.setter
    # only write
    def topic_code(self, value):
        self._topic_code = value

    @topic_code.deleter
    # only del
    def topic_code(self):
        del self._topic_code

    @property
    def token(self):
        return self._token

    @property
    def task_type_choices(self):
        return self._task_choices

    @property
    def min_time(self) -> int:
        return self._min_time

    @property
    def max_time(self) -> int:
        return self._max_time

    @property
    def question_seconds(self) -> float:
        """每题目标用时（秒）；<=0 表示沿用 min_time/max_time 随机"""
        return self._question_seconds

    @property
    def question_jitter(self) -> float:
        """目标用时的抖动比例（0.12 = ±12%），避免每题的耗时完全一致"""
        return self._question_jitter

    def set_question_seconds(self, seconds, jitter=None):
        """实时调整每题用时，并写回 config.json（下一题立即生效）"""
        value = max(0.1, min(600.0, float(seconds)))
        self._question_seconds = value
        if jitter is not None:
            self._question_jitter = max(0.0, min(0.5, float(jitter)))
        config_file = os.path.join(self.path, "config", "config.json")
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            data['question_seconds'] = round(self._question_seconds, 2)
            data['question_jitter'] = round(self._question_jitter, 3)
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return self._question_seconds

    @property
    def question_seconds_min(self) -> float:
        """每题用时下限（秒）"""
        return self._question_seconds_min

    @property
    def question_seconds_max(self) -> float:
        """每题用时上限（秒）"""
        return self._question_seconds_max

    def set_question_range(self, low, high):
        """
        设置每题用时区间 [low, high]（秒），每题在其间随机；两者相等即固定用时。
        写回 config.json，下一题立即生效。
        """
        low = max(0.1, min(600.0, float(low)))
        high = max(0.1, min(600.0, float(high)))
        if low > high:
            low, high = high, low
        self._question_seconds_min = round(low, 2)
        self._question_seconds_max = round(high, 2)
        # 中间值写回 question_seconds 便于兼容老逻辑与日志展示；区间已显式，抖动置 0
        self._question_seconds = round((low + high) / 2, 2)
        self._question_jitter = 0.0
        config_file = os.path.join(self.path, "config", "config.json")
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            data['question_seconds'] = self._question_seconds
            data['question_seconds_min'] = self._question_seconds_min
            data['question_seconds_max'] = self._question_seconds_max
            data['question_jitter'] = 0.0
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return self._question_seconds_min, self._question_seconds_max

    @property
    def spend_min_time(self) -> int:
        return self._spend_min_time

    @property
    def spend_max_time(self) -> int:
        return self._spend_max_time

    @property
    def accept_encoding(self) -> str:
        return self._headers_accept_encoding

    @property
    def br_choices(self) -> bool:
        return self._br_choices

    @property
    def play_music(self) -> bool:
        return self._play_music

    @property
    def music_path(self) -> str:
        return self._music_path

    @property
    def version(self) -> str:
        return self._version

    @property
    def know_version(self) -> str:
        return self._know_version

    @property
    def read(self) -> bool:
        return self._read

    @property
    def task_name(self) -> str:
        return self._task_name

    def read_seen(self):
        with open(os.path.join(self.path, "config", "config.json"), 'r', encoding="utf-8") as f:
            data = json.load(f)
            data['read'] = True
            self._read = True
        with open(os.path.join(self.path, "config", "config.json"), 'w', encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def input_info(self, min_time, max_time, min_time_2, max_time_2, br_choices, accept_encoding, play_music=None, music_path=None):
        self._min_time = min_time
        self._max_time = max_time
        self._spend_min_time = min_time_2
        self._spend_max_time = max_time_2
        self._br_choices = br_choices
        self._headers_accept_encoding = accept_encoding
        if play_music is not None:
            self._play_music = play_music
        if music_path is not None:
            self._music_path = music_path

        with open(os.path.join(self.path, "config", "config.json"), 'r', encoding="utf-8") as f:
            data = json.load(f)
            data['min_time'] = self._min_time
            data['max_time'] = self._max_time
            data['spend_min_time'] = self._spend_min_time
            data['spend_max_time'] = self._spend_max_time
            data['br_choices'] = self._br_choices
            data['accept_encoding'] = self._headers_accept_encoding
            if play_music is not None:
                data['play_music'] = self._play_music
            if music_path is not None:
                data['music_path'] = self._music_path
        data_str = json.dumps(data, indent=2)
        with open(os.path.join(self.path, "config", "config.json"), 'w', encoding="utf-8") as f:
            f.write(data_str)

    def ignore_version(self, version):
        with open(os.path.join(self.path, "config", "config.json"), 'r', encoding="utf-8") as f:
            data = json.load(f)
            data['know_version'] = version
            self._know_version = version
        with open(os.path.join(self.path, "config", "config.json"), 'w', encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)