import os
import random
import re
import sys
import time

from PyQt6.QtCore import QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication

from answer_questions.answer_questions import *
from api.basic_api import get_all_unit, get_unit_words, get_book_all_words
from api.main_api import get_exam, select_all_word, skip_exam, get_task_score, SecurityVerifyError
from log.log import Log
from publicInfo.publicInfo import PublicInfo
from util.basic_util import extract_book_word, query_word_unit
from util.handle_word_list import handle_word_result
from api.update import get_update
from decryptencrypt.debase64 import debase64
from view.main_window import UiMainWindow

# 题型名称（用于界面"题目详情"面板）
MODE_NAMES = {
    0: "阅读卡片",
    11: "英译汉 · 句子填空",
    13: "判断题",
    15: "看词选义",
    16: "看词选义（二星）",
    17: "看义选词",
    18: "看义选词（二星）",
    21: "英译汉",
    22: "英译汉（二星）",
    31: "词义连线",
    32: "汉译英填空",
    41: "补全句子",
    42: "补全句子",
    43: "补全句子",
    44: "补全句子",
    51: "补全单词",
    52: "补全单词",
    53: "补全单词",
    54: "补全单词",
    73: "补全拼写",
}


def _clean(text):
    """合并接口里的多余空格（词达人题干常是双空格排版）"""
    return re.sub(r"\s{2,}", " ", str(text or "")).strip()


def format_exam_detail(exam):
    """把一道题渲染成纯文本，供界面"题目详情"面板显示"""
    if not isinstance(exam, dict):
        return "（当前不是可作答的题目）"
    mode = exam.get("topic_mode")
    stem = exam.get("stem") or {}
    content = _clean(stem.get("content"))
    remark = _clean(stem.get("remark"))
    options = [
        _clean(o.get("content"))
        for o in (exam.get("options") or [])
        if isinstance(o, dict) and o.get("content")
    ]
    done = exam.get("topic_done_num")
    total = exam.get("topic_total")

    lines = []
    if done is not None and total:
        lines.append(f"第 {done}/{total} 题    ·    题型 {mode}（{MODE_NAMES.get(mode, '未知')}）")
    else:
        lines.append(f"题型 {mode}（{MODE_NAMES.get(mode, '未知')}）")
    lines.append("─" * 34)
    if content:
        lines.append(f"题干：{content}")
    if remark:
        lines.append(f"译文：{remark}")
    w_tip = exam.get("w_tip")
    w_lens = exam.get("w_lens")
    if w_tip or w_lens:
        lines.append(f"提示：首字母「{w_tip}」 词长 {w_lens}")
    if options:
        lines.append("")
        lines.append("选项：")
        for index, option in enumerate(options):
            letter = "ABCD"[index] if index < 4 else str(index + 1)
            lines.append(f"  {letter}. {option}")
    return "\n".join(lines)


def describe_choice(exam, option):
    """把"提交了什么"渲染成一行，追加在题目详情后面"""
    options = []
    if isinstance(exam, dict):
        options = [
            _clean(o.get("content"))
            for o in (exam.get("options") or [])
            if isinstance(o, dict) and o.get("content")
        ]
    if isinstance(option, int) and 0 <= option < len(options):
        letter = "ABCD"[option] if option < 4 else str(option + 1)
        return f"\n✔ 已提交 {letter}. {options[option]}"
    if isinstance(option, dict):
        return f"\n✔ 已提交 {option}"
    if option is None:
        return "\n✘ 未匹配到答案，已跳过"
    return f"\n✔ 已提交 {option}"


class TaskWorker(QThread):
    task_finished = pyqtSignal(str)
    task_error = pyqtSignal(str)
    task_progress = pyqtSignal(str)
    task_notice = pyqtSignal(str)     # 重试/跳过等提示
    batch_finished = pyqtSignal(str)  # 批量模式全部执行结束
    task_detail = pyqtSignal(str)     # 当前题目详情（整题刷新）
    task_choice = pyqtSignal(str)     # 本题提交结果（追加一行）

    def __init__(self, task_infos, batch_mode=False):
        super().__init__()
        self.task_infos = task_infos
        self.batch_mode = batch_mode
        self._is_running = True
        self.start_time = None
        self.current_task_name = ''
        self.current_index = 0
        self.current_total = 0

    def run(self):
        total = len(self.task_infos)
        success_count = 0
        failed_tasks = []
        for index, task_info in enumerate(self.task_infos, start=1):
            if not self._is_running:
                break
            task_name = task_info['task_name']
            self.current_task_name = task_name
            self.current_index = index
            self.current_total = total
            main.logger.info(f"开始执行任务[{index}/{total}]：{task_name}")
            attempts = 0
            while self._is_running:
                attempts += 1
                try:
                    self.start_time = time.time()
                    self.complete_test(task_info)
                    if self._is_running:
                        elapsed_time = time.time() - self.start_time
                        message = f"[{index}/{total}] {task_name} 已完成，用时 {elapsed_time:.2f} 秒"
                        self.task_finished.emit(message)
                        get_task_score(public_info)
                        success_count += 1
                    break
                except SecurityVerifyError as e:
                    # 服务端风控(11003): 重试无意义(2秒内不可能解除验证), 立即停止当前任务
                    main.logger.error(f"任务 {task_name} 需安全验证: {e}")
                    if self.batch_mode:
                        failed_tasks.append(task_name)
                        self.task_notice.emit(f"[{index}/{total}] 任务 {task_name} 需安全验证已跳过：{e}，请完成验证后重试")
                    else:
                        self.task_error.emit(f"任务 {task_name} 需安全验证：{e}")
                        return
                    break
                except Exception as e:
                    main.logger.error(f"任务 {task_name} 执行出错（第{attempts}次）: {e}", exc_info=True)
                    if attempts >= 3:
                        if self.batch_mode:
                            failed_tasks.append(task_name)
                            self.task_notice.emit(f"[{index}/{total}] 任务 {task_name} 连续失败3次，已跳过，继续下一个")
                        else:
                            self.task_error.emit(f"任务 {task_name} 连续失败3次：{e}")
                            return
                        break
                    if not self._is_running:
                        break
                    self.task_notice.emit(f"[{index}/{total}] 任务 {task_name} 第{attempts}次出错：{e}，2秒后自动重试")
                    time.sleep(2)

        if self._is_running and self.batch_mode:
            summary = f"一键刷题完成：成功 {success_count} 个，失败 {len(failed_tasks)} 个"
            if failed_tasks:
                summary += f"\n失败任务：{', '.join(failed_tasks)}"
            self.batch_finished.emit(summary)

    def stop(self):
        self._is_running = False

    def complete_test(self, task_info: dict):
        task_name = task_info['task_name']
        public_info.course_id = task_info['course_id']
        main.logger.info(f'开始执行任务：{task_name}')
        main.logger.info('用课程course_id获取单元list_id')
        main.logger.info('获取该课程的所有单元')
        get_all_unit(public_info)
        public_info.release_id = task_info['release_id']
        all_unit_name = []
        for unit in public_info.all_unit['task_list']:
            if not self._is_running:
                return
            unit_name = unit['task_name']
            all_unit_name.append(unit_name)
            public_info.all_unit_name.append(unit['list_id'])
            if unit_name == task_name:
                public_info.now_unit = unit['list_id']
                public_info.task_id = unit['task_id']
                break
        unit_progress = task_info['progress']
        if task_name not in all_unit_name:
            public_info.is_self_built = True
            main.logger.info(f"{task_name}为自建任务")
            if task_info['task_type'] == 1:
                main.logger.info("完成学习任务的自建任务")
                main.logger.info('获取该自建任务的单词')
                public_info.task_id = task_info['task_id']
                get_unit_words(public_info)
                main.logger.info("获取提交单词")
                query_word_unit(public_info)
                main.logger.info(f"获取成功：{public_info.word_list}")
                if (unit_progress < 2 and public_info.get_word_list_result['exist_little_task'] != 1) or \
                        public_info.get_word_list_result['exist_little_task'] == 2:
                    select_all_word(public_info.word_list, public_info.task_id)
            else:
                main.logger.info("开始测试任务的自建任务")
            get_book_all_words(public_info)
            extract_book_word(public_info)
            self.class_task_answer()
        else:
            if task_info['task_type'] == 1:
                main.logger.info(f'开始班级学习任务{public_info.now_unit}')
                self.complete_practice(public_info.now_unit, unit_progress, task_info['task_id'])
            else:
                main.logger.info(f'开始班级测试任务{public_info.now_unit}')
                get_unit_words(public_info)
                handle_word_result(public_info)
                main.logger.info(f"获取单元所有单词{public_info.word_list}")
                public_info.task_id = task_info['task_id']
                self.class_task_answer()

    def emit_progress(self):
        """
        发送答题进度
        :return:
        """
        if isinstance(public_info.exam, dict):
            done = public_info.exam.get('topic_done_num', 0)
            total = public_info.exam.get('topic_total', 0)
            if total:
                self.task_progress.emit(f"{done}/{total}|{public_info.right_count}|{public_info.wrong_count}|{public_info.skip_count}|{self.current_index}/{self.current_total}|{self.current_task_name}")

    def question_target_seconds(self):
        """
        当前每题目标用时（秒）。

        优先用显式区间 [question_seconds_min, question_seconds_max] 内均匀随机；
        区间退化（min == max）即固定用时。老配置没有区间时回退"单值 ± 抖动"，
        再没有就用 min_time/max_time。
        """
        low = float(getattr(public_info, 'question_seconds_min', 0) or 0)
        high = float(getattr(public_info, 'question_seconds_max', 0) or 0)
        if low > 0 and high > 0:
            if high < low:
                low, high = high, low
            if high - low < 0.005:
                return max(0.1, low)
            return max(0.1, random.uniform(low, high))
        target = getattr(public_info, 'question_seconds', 0) or 0
        if target <= 0:
            low_t = max(1, int(getattr(public_info, 'min_time', 2) or 2))
            high_t = max(low_t, int(getattr(public_info, 'max_time', low_t) or low_t))
            target = random.randint(low_t, high_t)
        jitter = getattr(public_info, 'question_jitter', 0) or 0
        if jitter > 0:
            target *= random.uniform(1 - jitter, 1 + jitter)
        return max(0.1, target)

    def wait_question_time(self, started_at):
        """
        按目标用时补足等待，返回本题实际毫秒数（用于上报 time_spent）。
        分段睡眠，保证「中止任务」能及时打断。
        """
        goal = self.question_target_seconds()
        while self._is_running:
            remain = goal - (time.time() - started_at)
            if remain <= 0:
                break
            time.sleep(min(0.05, remain))
        return int((time.time() - started_at) * 1000)

    def emit_detail(self, exam=None):
        """把当前题目推给界面右侧"题目详情"面板"""
        try:
            target = exam if exam is not None else public_info.exam
            if not isinstance(target, dict):
                return
            self.task_detail.emit(format_exam_detail(target))
        except Exception as e:
            main.logger.error(f"生成题目详情失败: {e}", exc_info=True)

    def emit_choice(self, exam, submitted):
        """把本题提交结果追加到题目详情面板"""
        try:
            self.task_choice.emit(describe_choice(exam, submitted))
        except Exception as e:
            main.logger.error(f"生成提交详情失败: {e}")

    def class_task_answer(self):
        token = PublicInfo.token
        # 确保单元词表已加载(汉译英术语题依赖词表的 word_zh)
        if not public_info.word_list:
            try:
                get_unit_words(public_info)
                handle_word_result(public_info)
            except Exception as e:
                main.logger.error(f"加载词表失败: {e}", exc_info=True)
        get_exam(public_info)
        if public_info.exam == 'complete':
            main.logger.info('该任务已完成，无法重复作答')
            return
        public_info.topic_code = public_info.exam['topic_code']
        self.emit_progress()
        main.logger.info("开始答题")
        while self._is_running:
            main.logger.info("获取题目类型")
            if public_info.exam == 'complete':
                break
            mode = public_info.exam['topic_mode']
            main.logger.info(f'题目类型{mode}')
            if mode == 0:
                jump_read(public_info)
                self.emit_progress()
                continue
            question_started = time.time()
            exam_snapshot = public_info.exam if isinstance(public_info.exam, dict) else None
            self.emit_detail(exam_snapshot)
            submitted = None
            option = answer(public_info, mode)
            if option is None:
                # 兜底：宁可猜一个提交（判分响应会带回标准答案并写入本地答案库），
                # 也不要直接跳过——SkipAnswer 不返回正确答案，跳过等于永久放弃该题
                guess = guess_answer(public_info, mode)
                if guess is not None:
                    main.logger.info(f"未匹配到答案，提交兜底猜测：{guess}")
                    submitted = guess
                    elapsed_ms = self.wait_question_time(question_started)
                    submit(public_info, guess, time_spent_ms=elapsed_ms)
                else:
                    public_info.topic_code = public_info.exam['topic_code']
                    public_info.skip_count += 1
                    skip_exam(public_info)
            else:
                submitted = option
                elapsed_ms = self.wait_question_time(question_started)
                submit(public_info, option, time_spent_ms=elapsed_ms)
            self.emit_choice(exam_snapshot, submitted)
            self.emit_progress()

    def complete_practice(self, unit: str, progress: int, task_id=None):
        main.logger.info(f"获取该{unit}单元的单词")
        public_info.now_unit = unit
        public_info.task_id = task_id
        get_unit_words(public_info)
        main.logger.info("处理words")
        handle_word_result(public_info)
        main.logger.info("选择该单元所有单词")
        exist_little_task = None
        gwlr = public_info.get_word_list_result
        if isinstance(gwlr, dict) and 'data' in gwlr:
            data_field = gwlr['data']
            if isinstance(data_field, dict):
                exist_little_task = data_field.get('exist_little_task')
            else:
                try:
                    if 'jv' in gwlr:
                        decoded = debase64(data_field, gwlr.get('jv'))
                        if isinstance(decoded, dict):
                            exist_little_task = decoded.get('exist_little_task')
                            public_info.get_word_list_result = decoded
                except Exception as e:
                    main.logger.error(f"解析 get_word_list_result 失败: {e}", exc_info=True)
        if (progress < 2 and exist_little_task != 1) or exist_little_task == 2:
            try:
                select_all_word({f"{public_info.course_id}:{unit}": public_info.word_list}, public_info.task_id)
            except Exception as e:
                main.logger.info("任务已经开启")
        get_exam(public_info)
        if public_info.exam == 'complete':
            main.logger.info('该任务已完成，无法重复作答')
            return
        public_info.topic_code = public_info.exam['topic_code']
        self.emit_progress()
        main.logger.info("开始答题")
        while self._is_running:
            main.logger.info("获取题目类型")
            if public_info.exam == 'complete':
                main.logger.info('该单元已完成')
                break
            mode = public_info.exam['topic_mode']
            if mode == 0:
                jump_read(public_info)
                self.emit_progress()
                continue
            question_started = time.time()
            exam_snapshot = public_info.exam if isinstance(public_info.exam, dict) else None
            self.emit_detail(exam_snapshot)
            submitted = None
            option = answer(public_info, mode)
            if option is None:
                # 兜底：宁可猜一个提交（判分响应会带回标准答案并写入本地答案库），
                # 也不要直接跳过——SkipAnswer 不返回正确答案，跳过等于永久放弃该题
                guess = guess_answer(public_info, mode)
                if guess is not None:
                    main.logger.info(f"未匹配到答案，提交兜底猜测：{guess}")
                    submitted = guess
                    elapsed_ms = self.wait_question_time(question_started)
                    submit(public_info, guess, time_spent_ms=elapsed_ms)
                else:
                    public_info.topic_code = public_info.exam['topic_code']
                    public_info.skip_count += 1
                    skip_exam(public_info)
            else:
                submitted = option
                elapsed_ms = self.wait_question_time(question_started)
                submit(public_info, option, time_spent_ms=elapsed_ms)
            self.emit_choice(exam_snapshot, submitted)
            self.emit_progress()


def run_selftest(report_path=None):
    """
    打包自检：不启动界面，只验证 exe 内最关键的三条链路是否可用。
    用法：YM词达人.exe --selftest
    """
    import traceback

    checks = []

    def check(name, func):
        try:
            detail = func()
            checks.append((name, True, detail))
        except Exception as e:
            checks.append((name, False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}"))

    def _paths():
        from util.runtime_paths import DATA_DIR, FROZEN, RESOURCE_DIR

        return f"frozen={FROZEN} resource={RESOURCE_DIR} data={DATA_DIR}"

    def _spacy_pos():
        from util.select_mean import stem_word_pos

        pos = stem_word_pos({"stem": {"content": "Jack {sacrificed} his life to save the child."}})
        assert pos == "verb", f"词性标注错误: {pos}"
        return f"sacrificed -> {pos}"

    def _sense():
        from util.select_mean import sense_score, stem_word_pos
        from util.text_norm import norm_cn

        exam = {
            "topic_mode": 11,
            "stem": {
                "content": "The workers expected to share out a year-end {bonus}.",
                "remark": "工人们期望年终分红。",
            },
            "options": [{"content": c} for c in
                        ["noun 额外的好处，意外收获", "noun 奖金；红利"]],
        }
        s_hit = sense_score("noun 奖金；红利", norm_cn(exam["stem"]["remark"]))
        s_miss = sense_score("noun 额外的好处，意外收获", norm_cn(exam["stem"]["remark"]))
        assert s_hit > s_miss, f"译文消歧打分异常 hit={s_hit} miss={s_miss}"
        return f"bonus 译文得分 hit={s_hit} miss={s_miss}, 题干词性={stem_word_pos(exam)}"

    def _mitm():
        from api.mitm_inproc import InProcessProxy, TokenCatcher

        proxy = InProcessProxy(host="127.0.0.1", port=18888,
                               addons=[TokenCatcher(os.path.join("", "selftest_token.txt"))])
        proxy.start(timeout=60)
        try:
            alive = proxy.poll() is None
            assert alive, "mitmproxy 未存活"
            return "进程内 mitmproxy 可启动/可停止"
        finally:
            proxy.stop()

    def _config():
        from publicInfo.publicInfo import PublicInfo
        from util.runtime_paths import DATA_DIR

        info = PublicInfo(DATA_DIR)
        return f"version={info.version} min_time={info.min_time} max_time={info.max_time}"

    def _answer_lib():
        from util.answer_lib import load_lib

        lib = load_lib()
        return f"答案库条目={len([k for k in lib if k != '_word_answers'])}"

    check("路径解析", _paths)
    check("spaCy 模型 + 词性标注", _spacy_pos)
    check("译文消歧打分", _sense)
    check("进程内 mitmproxy", _mitm)
    check("配置读取", _config)
    check("答案库加载", _answer_lib)

    lines = ["=== YM词达人 自检 ==="]
    all_ok = True
    for name, ok, detail in checks:
        all_ok = all_ok and ok
        lines.append(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    lines.append(f"结果：{'全部通过' if all_ok else '存在失败项'}")

    try:
        from util.runtime_paths import data_path

        target = report_path or data_path("selftest.txt")
        with open(target, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except Exception:
        pass
    return all_ok, "\n".join(lines)


if __name__ == '__main__':
    # 打包自检模式：不启动界面，验证冻结环境下的关键链路
    if "--selftest" in sys.argv:
        from log.log import ensure_stdio_for_gui, install_exception_hook

        ensure_stdio_for_gui()
        install_exception_hook()
        ok, report = run_selftest()
        try:
            from log.log import Log as _Log
            _Log("selftest").logger.info(report.replace("\n", " | "))
        except Exception:
            pass
        sys.exit(0 if ok else 1)

    main = Log("main")
    main.logger.info("初始化主页面")
    # 无控制台启动（pythonw）时：接管 stdout/stderr、未捕获异常，并安装界面日志管道，
    # 这样 cmd 黑框里的内容全部转到主界面"输出信息"面板。
    from log.log import ensure_stdio_for_gui, install_ui_handler, install_exception_hook, has_console

    _console_mode = has_console()
    ensure_stdio_for_gui()
    install_ui_handler()
    install_exception_hook()
    main.logger.info(f"启动模式：{'控制台' if _console_mode else '界面（无 cmd 窗口）'}")
    # 自检：上次抓取 token 被强制中断时，mitmproxy 的 finally 没能执行，
    # 系统代理会残留指向 127.0.0.1:8888，导致本机断网/登录失败。
    # 仅在"代理指向该地址 且 该端口无人监听"时自动关闭。
    try:
        from api.token_capture_service import heal_stale_proxy

        heal_stale_proxy(main.logger)
    except Exception as e:
        main.logger.error(f"代理残留自检失败: {e}")
    from util.runtime_paths import DATA_DIR, RESOURCE_DIR, ensure_data_files

    ensure_data_files()
    # 统一工作目录到数据目录：packaged exe 被快捷方式/计划任务拉起时 cwd 可能不是程序目录，
    # 某些历史代码仍按相对路径找 config/log，切过来最稳
    try:
        os.chdir(DATA_DIR)
    except Exception:
        pass
    main.logger.info(f"资源目录：{RESOURCE_DIR}")
    main.logger.info(f"数据目录：{DATA_DIR}")
    main.logger.info("初始化公共组件")
    public_info = PublicInfo(DATA_DIR)
    main.logger.info(f"当前版本号：{public_info.version}")

    app = QApplication(sys.argv)
    if not public_info.read:
        main.logger.info("显示首次使用提示页面")
        import view.first_note

        note = view.first_note.Ui_Form(public_info)
        note.show()
        app.exec()

    try:
        ui = UiMainWindow(public_info, RESOURCE_DIR, main, TaskWorker)
        ui.show()
        # 启动后询问是否自动捕获 token
        QTimer.singleShot(400, ui.ask_capture_token)


        class UpdateCheckThread(QThread):
            version_ready = pyqtSignal(str)

            def run(self):
                self.version_ready.emit(get_update())


        update_thread = UpdateCheckThread()


        def on_version_checked(latest_version):
            if public_info.version < latest_version and public_info.know_version < latest_version:
                import view.update
                update = view.update.Ui_Form(public_info)
                update.exec()


        update_thread.version_ready.connect(on_version_checked)
        update_thread.start()

        app.exec()
    except Exception as e:
        main.logger.error(e)
        main.logger.error("程序异常")
        import view.error

        ui = view.error.Ui_Form()
        ui.show()
        app.exec()
