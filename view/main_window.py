import html
import logging
import os
import subprocess
import threading
import time

import winsound
from playsound import playsound

from PyQt6.QtGui import QAction, QIcon
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtWidgets import QMainWindow, QApplication, QMessageBox

import api.request_header as requests
import view.setting, view.introduce, view.error
from api.login import verify_token
from api.main_api import get_class_task
from util.basic_util import get_all_task
from publicInfo.publicInfo import PublicInfo
from api.geuuid import get_uuid


class UiMainWindow(QMainWindow):
    output = "软件初始化成功！"

    def __init__(self, public_info, root_path, main_logger, task_worker_class):
        super(UiMainWindow, self).__init__()
        self.public_info = public_info
        self.root_path = root_path
        self.main_logger = main_logger
        self.task_worker_class = task_worker_class
        self.token = ''
        self.task_worker = None
        self._batch_mode = False
        self.setupUi(self)
        self._setup_log_bridge()

    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.setFixedSize(1080, 470)
        icon_path = os.path.join(self.root_path, 'assets', 'icon.ico')
        if os.path.exists(icon_path):
            MainWindow.setWindowIcon(QIcon(icon_path))
        self.centralwidget = QtWidgets.QWidget(parent=MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.output_info = QtWidgets.QTextBrowser(parent=self.centralwidget)
        self.output_info.setGeometry(QtCore.QRect(460, 40, 280, 310))
        self.output_info.setObjectName("textBrowser")
        # 题目详情面板：实时显示当前题号/题干/译文/选项
        self.question_label = QtWidgets.QLabel(parent=self.centralwidget)
        self.question_label.setGeometry(QtCore.QRect(750, 20, 71, 16))
        self.question_label.setObjectName("question_label")
        self.question_info = QtWidgets.QTextBrowser(parent=self.centralwidget)
        self.question_info.setGeometry(QtCore.QRect(750, 40, 310, 310))
        self.question_info.setObjectName("question_info")
        self.question_info.setStyleSheet("QTextBrowser { background-color: #fbfbfb; }")
        self.label = QtWidgets.QLabel(parent=self.centralwidget)
        self.label.setGeometry(QtCore.QRect(20, 20, 71, 16))
        self.label.setObjectName("label")
        self.token_input = QtWidgets.QLineEdit(parent=self.centralwidget)
        self.token_input.setGeometry(QtCore.QRect(20, 40, 301, 20))
        self.token_input.setObjectName("token")
        self.login = QtWidgets.QPushButton(parent=self.centralwidget)
        self.login.setGeometry(QtCore.QRect(330, 40, 61, 24))
        self.login.setObjectName("login")
        self.login.clicked.connect(self.token_login)
        self.warn_info = QtWidgets.QLabel(parent=self.centralwidget)
        self.warn_info.setGeometry(QtCore.QRect(20, 60, 441, 16))
        self.warn_info.setStyleSheet("")
        self.warn_info.setObjectName("warn_info")
        self.label_3 = QtWidgets.QLabel(parent=self.centralwidget)
        self.label_3.setGeometry(QtCore.QRect(460, 20, 61, 16))
        self.label_3.setObjectName("label_3")
        self.label_4 = QtWidgets.QLabel(parent=self.centralwidget)
        self.label_4.setGeometry(QtCore.QRect(20, 90, 61, 16))
        self.label_4.setObjectName("label_4")
        self.user_info = QtWidgets.QLabel(parent=self.centralwidget)
        self.user_info.setGeometry(QtCore.QRect(20, 110, 441, 16))
        self.user_info.setObjectName("user_info")
        self.label_6 = QtWidgets.QLabel(parent=self.centralwidget)
        self.label_6.setGeometry(QtCore.QRect(20, 140, 71, 16))
        self.label_6.setObjectName("label_6")
        self.formLayoutWidget = QtWidgets.QWidget(parent=self.centralwidget)
        self.formLayoutWidget.setGeometry(QtCore.QRect(100, 140, 211, 22))
        self.formLayoutWidget.setObjectName("formLayoutWidget")
        self.formLayout = QtWidgets.QFormLayout(self.formLayoutWidget)
        self.formLayout.setContentsMargins(0, 0, 0, 0)
        self.formLayout.setObjectName("formLayout")
        self.learn_task = QtWidgets.QRadioButton(parent=self.formLayoutWidget)
        self.learn_task.setObjectName("learn_task")
        self.learn_task.setChecked(True)
        self.learn_task.clicked.connect(self.get_task_list)
        self.formLayout.setWidget(0, QtWidgets.QFormLayout.ItemRole.LabelRole, self.learn_task)
        self.test_task = QtWidgets.QRadioButton(parent=self.formLayoutWidget)
        self.test_task.setObjectName("test_task")
        self.test_task.clicked.connect(self.get_task_list)
        self.formLayout.setWidget(0, QtWidgets.QFormLayout.ItemRole.FieldRole, self.test_task)
        self.task_list = QtWidgets.QTableWidget(parent=self.centralwidget)
        self.task_list.setGeometry(QtCore.QRect(20, 170, 291, 80))
        self.task_list.setObjectName("task_list")
        # 四列：单选框 | 任务名 | 进度 | 得分，每列左对齐
        self.task_list.setColumnCount(4)
        self.task_list.verticalHeader().setVisible(False)
        self.task_list.horizontalHeader().setVisible(False)
        self.task_list.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.task_list.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.task_list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.task_list.setShowGrid(False)
        self.task_list.setWordWrap(False)
        self.task_list.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Fixed)
        self.task_list.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.task_list.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Fixed)
        self.task_list.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Fixed)
        self.task_list.setColumnWidth(0, 30)
        self.task_list.setColumnWidth(2, 55)
        self.task_list.setColumnWidth(3, 75)
        # 目标任务选择：互斥单选框，勾选时同步选中表格行
        self.task_radio_group = QtWidgets.QButtonGroup(self)
        self.task_radio_group.setExclusive(True)
        self.task_list.itemClicked.connect(self._on_task_item_clicked)
        self.start_task = QtWidgets.QPushButton(parent=self.centralwidget)
        self.start_task.setGeometry(QtCore.QRect(20, 340, 85, 24))
        self.start_task.setObjectName("start_task")
        self.start_task.clicked.connect(self.start)
        self.batch_start = QtWidgets.QPushButton(parent=self.centralwidget)
        self.batch_start.setGeometry(QtCore.QRect(115, 340, 85, 24))
        self.batch_start.setObjectName("batch_start")
        self.batch_start.setText("一键刷题")
        self.batch_start.clicked.connect(self.start_batch)
        self.stop_task = QtWidgets.QPushButton(parent=self.centralwidget)
        self.stop_task.setGeometry(QtCore.QRect(210, 340, 85, 24))
        self.stop_task.setObjectName("stop_task")
        self.stop_task.clicked.connect(self.stop_current_task)
        # 当前任务名(一键刷题时显示正在执行的任务, 如 [2/6] 第五部分)
        self.progress_task_label = QtWidgets.QLabel(parent=self.centralwidget)
        self.progress_task_label.setGeometry(QtCore.QRect(20, 392, 432, 18))
        self.progress_task_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.progress_task_label.setStyleSheet("color: #404040; font-weight: bold;")
        self.progress_task_label.setText("")
        # 答题进度条
        self.progress_bar = QtWidgets.QProgressBar(parent=self.centralwidget)
        self.progress_bar.setGeometry(QtCore.QRect(20, 370, 291, 20))
        self.progress_bar.setObjectName("progress_bar")
        self.progress_bar.setValue(0)
        # 进度文字（已完成数/总数）
        self.progress_label = QtWidgets.QLabel(parent=self.centralwidget)
        self.progress_label.setGeometry(QtCore.QRect(320, 370, 50, 20))
        self.progress_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        # 答题对错统计(正确/错误)
        self.progress_right_label = QtWidgets.QLabel(parent=self.centralwidget)
        self.progress_right_label.setGeometry(QtCore.QRect(372, 370, 62, 20))
        self.progress_right_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.progress_right_label.setStyleSheet("color: #2e9e44; font-weight: bold;")
        self.progress_right_label.setText("")
        self.progress_wrong_label = QtWidgets.QLabel(parent=self.centralwidget)
        self.progress_wrong_label.setGeometry(QtCore.QRect(434, 370, 62, 20))
        self.progress_wrong_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.progress_wrong_label.setStyleSheet("color: #d0342c; font-weight: bold;")
        self.progress_wrong_label.setText("")
        self.progress_skip_label = QtWidgets.QLabel(parent=self.centralwidget)
        self.progress_skip_label.setGeometry(QtCore.QRect(496, 370, 62, 20))
        self.progress_skip_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.progress_skip_label.setStyleSheet("color: #808080; font-weight: bold;")
        self.progress_skip_label.setText("")
        # 每题用时区间（限时题型用：如班级测试单选只有 10 秒）
        self.speed_label = QtWidgets.QLabel(parent=self.centralwidget)
        self.speed_label.setGeometry(QtCore.QRect(596, 366, 60, 20))
        self.speed_label.setObjectName("speed_label")

        def _make_spin(x, value):
            spin = QtWidgets.QDoubleSpinBox(parent=self.centralwidget)
            spin.setGeometry(QtCore.QRect(x, 364, 64, 24))
            spin.setRange(0.10, 600.00)
            spin.setDecimals(2)
            spin.setSingleStep(0.10)
            spin.setToolTip(
                "每题从取题到提交的用时区间，每题在上下限之间随机（两位小数）\n"
                "风险参考（班级测试多为 10 秒限时）：\n"
                "  ≤0.5 秒  极高风险：完全非人工节奏，极易触发风控/安全验证\n"
                "  0.6~2 秒 过快：仍明显快于人类作答\n"
                "  3~4 秒   偏快：能过但没余量\n"
                "  5~8 秒   安全：10 秒限时的推荐区间\n"
                "  9~10 秒  临界：网络抖动就会超时\n"
                "  >10 秒   超时风险：多数限时题会判错"
            )
            # 防误改：不跟随键盘逐字生效、不被 Tab 抢焦点、忽略鼠标滚轮
            spin.setKeyboardTracking(False)
            spin.setFocusPolicy(QtCore.Qt.FocusPolicy.ClickFocus)
            spin.installEventFilter(self)
            spin.setValue(max(0.1, float(value)))
            spin.valueChanged.connect(self.on_question_range_changed)
            return spin

        self.speed_spin_min = _make_spin(658, self.public_info.question_seconds_min)
        self.speed_range_sep = QtWidgets.QLabel(parent=self.centralwidget)
        self.speed_range_sep.setGeometry(QtCore.QRect(724, 366, 12, 20))
        self.speed_range_sep.setText("~")
        self.speed_range_sep.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.speed_spin_max = _make_spin(738, self.public_info.question_seconds_max)
        self.speed_up = QtWidgets.QPushButton(parent=self.centralwidget)
        self.speed_up.setGeometry(QtCore.QRect(810, 364, 54, 24))
        self.speed_up.setObjectName("speed_up")
        self.speed_up.setText("加速")
        self.speed_up.setToolTip("区间整体减半（×0.5），立即生效")
        self.speed_up.clicked.connect(lambda: self.speed_scale(0.5))
        self.speed_down = QtWidgets.QPushButton(parent=self.centralwidget)
        self.speed_down.setGeometry(QtCore.QRect(868, 364, 54, 24))
        self.speed_down.setObjectName("speed_down")
        self.speed_down.setText("减速")
        self.speed_down.setToolTip("区间整体加倍（×2），立即生效")
        self.speed_down.clicked.connect(lambda: self.speed_scale(2.0))
        self.speed_hint = QtWidgets.QLabel(parent=self.centralwidget)
        self.speed_hint.setGeometry(QtCore.QRect(800, 392, 260, 18))
        self.speed_hint.setStyleSheet("color: #808080;")
        self.speed_hint.setObjectName("speed_hint")
        # 安全阈值提醒：放在调速同一行，颜色区分风险等级
        self.speed_warn = QtWidgets.QLabel(parent=self.centralwidget)
        self.speed_warn.setGeometry(QtCore.QRect(928, 366, 150, 20))
        self.speed_warn.setObjectName("speed_warn")
        self._syncing_speed = False
        # 当前任务计时器：实时显示本任务已运行多久
        self.elapsed_label = QtWidgets.QLabel(parent=self.centralwidget)
        self.elapsed_label.setGeometry(QtCore.QRect(596, 392, 200, 18))
        self.elapsed_label.setStyleSheet("color: #1a6ee0; font-weight: bold;")
        self.elapsed_label.setObjectName("elapsed_label")
        self.elapsed_label.setText("⏱ 未开始")
        self._task_started_at = None
        self._elapsed_timer = QtCore.QTimer(self)
        self._elapsed_timer.setInterval(500)
        self._elapsed_timer.timeout.connect(self.tick_elapsed)
        self.follow_output = QtWidgets.QRadioButton(parent=self.centralwidget)
        self.follow_output.setGeometry(QtCore.QRect(530, 19, 101, 16))
        self.follow_output.setObjectName("follow_output")
        self.follow_output.setChecked(True)
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(parent=MainWindow)
        self.menubar.setEnabled(True)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 1080, 33))
        self.menubar.setObjectName("menubar")
        self.menubar.setStyleSheet("""
            QMenuBar {
                background-color: palette(menu);
                color: palette(text);
                border: none;
            }
            QMenuBar::item {
                background: transparent;
                color: palette(text);
            }
            QMenuBar::item:selected {
                background: palette(highlight);
            }
            QMenuBar::item:pressed {
                background: palette(highlight);
            }
            QMenu {
                background-color: palette(menu);
                color: palette(text);
            }
            QMenu::item {
                color: palette(text);
            }
            QMenu::item:selected {
                background-color: palette(highlight);
            }
        """)

        self.menu_separator = QtWidgets.QFrame(parent=MainWindow)
        self.menu_separator.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        self.menu_separator.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.menu_separator.setObjectName("menu_separator")

        self.menu = QtWidgets.QMenu(parent=self.menubar)
        self.menu.setObjectName("menu")
        self.menu_2 = QtWidgets.QMenu(parent=self.menubar)
        self.menu_2.setObjectName("menu_2")
        MainWindow.setMenuBar(self.menubar)

        self.menu_separator.setGeometry(QtCore.QRect(0, 33, 1080, 3))

        self.statusbar = QtWidgets.QStatusBar(parent=MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)
        self.action = QtGui.QAction(parent=MainWindow)
        self.action.setObjectName("action")
        self.action_3 = QtGui.QAction(parent=MainWindow)
        self.action_3.setObjectName("action_3")
        self.action_4 = QtGui.QAction(parent=MainWindow)
        self.action_4.setObjectName("action_4")
        self.action_6 = QtGui.QAction(parent=MainWindow)
        self.action_6.setObjectName("action_6")
        self.action_7 = QtGui.QAction(parent=MainWindow)
        self.action_7.setObjectName("action_7")
        self.menu_get_token = QtWidgets.QMenu(parent=self.menubar)
        self.menu_get_token.setObjectName("menu_get_token")
        self.action_builtin = QtGui.QAction(parent=MainWindow)
        self.action_builtin.setObjectName("action_builtin")
        self.action_third_party = QtGui.QAction(parent=MainWindow)
        self.action_third_party.setObjectName("action_third_party")
        self.action_8 = QtGui.QAction(parent=MainWindow)
        self.action_8.setObjectName("action_8")
        self.action_open_logs = QtGui.QAction(parent=MainWindow)
        self.action_open_logs.setObjectName("action_open_logs")
        self.action_about = QtGui.QAction(parent=MainWindow)
        self.action_about.setObjectName("action_about")
        self.menu.addAction(self.action)
        self.menu.triggered[QAction].connect((self.open_settings))
        self.menu_2.addAction(self.action_4)
        self.menu_2.addSeparator()
        self.menu_2.addAction(self.action_6)
        self.menu_2.addAction(self.action_7)
        self.menu_2.addAction(self.action_about)
        self.menu_2.addSeparator()
        self.menu_2.addMenu(self.menu_get_token)
        self.menu_get_token.addAction(self.action_builtin)
        self.menu_get_token.addAction(self.action_third_party)
        self.action_open_logs.setText("导出日志文件")
        self.menu_2.addAction(self.action_open_logs)
        self.menu_2.triggered[QAction].connect((self.open_helper))
        self.menubar.addAction(self.menu.menuAction())
        self.menubar.addAction(self.menu_2.menuAction())
        self.retranslate_ui(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)
        self.update_speed_warning()

    def retranslate_ui(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "YM词达人"))
        self.question_label.setText(_translate("MainWindow", "题目详情"))
        self.question_info.setHtml(_translate("MainWindow", "<pre style='white-space:pre-wrap;'>（等待开始答题…）</pre>"))
        self.output_info.setHtml(_translate("MainWindow", f"<pre>{UiMainWindow.output}</pre>"))
        self.label.setText(_translate("MainWindow", "用户token："))
        self.login.setText(_translate("MainWindow", "登录"))
        self.label_3.setText(_translate("MainWindow", "输出信息："))
        self.label_4.setText(_translate("MainWindow", "用户信息："))
        self.user_info.setText(_translate("MainWindow", "未获取"))
        self.label_6.setText(_translate("MainWindow", "待完成任务："))
        self.learn_task.setText(_translate("MainWindow", "班级自学任务"))
        self.test_task.setText(_translate("MainWindow", "班级测试任务"))
        self.start_task.setText(_translate("MainWindow", "开始任务"))
        self.stop_task.setText(_translate("MainWindow", "中止任务"))
        self.follow_output.setText(_translate("MainWindow", "随新消息滚动"))
        self.speed_label.setText(_translate("MainWindow", "用时范围"))
        low, high = self.public_info.question_seconds_min, self.public_info.question_seconds_max
        hint = f"上报用时≈{low:.2f}s" if abs(high - low) < 0.005 else f"上报用时≈{low:.2f}~{high:.2f}s"
        self.speed_hint.setText(_translate("MainWindow", hint))
        self.menu.setTitle(_translate("MainWindow", "设置"))
        self.menu_2.setTitle(_translate("MainWindow", "帮助"))
        self.action.setText(_translate("MainWindow", "首选项..."))
        self.action_4.setText(_translate("MainWindow", "使用教程"))
        self.action_6.setText(_translate("MainWindow", "项目首页"))
        self.action_7.setText(_translate("MainWindow", "作者首页"))
        self.menu_get_token.setTitle(_translate("MainWindow", "获取 token"))
        self.action_builtin.setText(_translate("MainWindow", "内置"))
        self.action_third_party.setText(_translate("MainWindow", "第三方"))
        self.action_open_logs.setText(_translate("MainWindow", "导出日志文件"))
        self.action_about.setText(_translate("MainWindow", "关于"))

    # ---------------- 任务计时器 ----------------
    def eventFilter(self, obj, event):
        """吞掉「每题用时」微调框上的滚轮事件，避免鼠标滚页面时误改设置"""
        if obj is getattr(self, "speed_spin", None) and event.type() == QtCore.QEvent.Type.Wheel:
            return True
        return super().eventFilter(obj, event)

    def start_elapsed(self):
        """任务开始时启动计时"""
        self._task_started_at = time.time()
        self.elapsed_label.setText("⏱ 已用时 00:00:00")
        self._elapsed_timer.start()

    def stop_elapsed(self, note=""):
        """任务结束/中止时停表，并把总用时写进输出信息"""
        self._elapsed_timer.stop()
        if self._task_started_at is None:
            return
        total = int(time.time() - self._task_started_at)
        text = f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"
        self.elapsed_label.setText(f"⏱ 用时 {text}{('（' + note + '）') if note else '（已结束）'}")
        self.update_output_info(f"本任务总用时 {text}{('（' + note + '）') if note else ''}")
        self._task_started_at = None

    def tick_elapsed(self):
        """每 0.5 秒刷新一次已用时"""
        if self._task_started_at is None:
            return
        total = int(time.time() - self._task_started_at)
        self.elapsed_label.setText(
            f"⏱ 已用时 {total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"
        )

    # ---------------- 每题用时区间 ----------------
    def eventFilter(self, obj, event):
        """吞掉用时输入框上的滚轮事件，避免鼠标滚页面时误改设置"""
        spins = (getattr(self, "speed_spin_min", None), getattr(self, "speed_spin_max", None))
        if obj in spins and event.type() == QtCore.QEvent.Type.Wheel:
            return True
        return super().eventFilter(obj, event)

    def speed_range(self):
        """取当前区间（自动保证 low <= high）"""
        try:
            low = float(self.speed_spin_min.value())
            high = float(self.speed_spin_max.value())
        except Exception:
            return 8.0, 8.0
        return (low, high) if low <= high else (high, low)

    def speed_warning(self, low=None, high=None):
        """
        按任务类型给出用时区间风险提示 -> (文案, 颜色)

        风险区（班级测试多为 10 秒限时）：
          ≤0.5s    极高风险：完全非人工节奏，最易触发风控/安全验证
          0.6~2s   过快：仍明显快于人类作答
          3~4s     偏快：能过但没余量
          5~8s     安全：10 秒限时下的推荐区间
          9~10s    临界：网络抖动就会超时
          >10s     超时风险：多数限时题直接判错
        """
        if low is None or high is None:
            low, high = self.speed_range()
        span = f"{low:.2f}" if abs(high - low) < 0.005 else f"{low:.2f}~{high:.2f}"
        if self.test_task.isChecked():
            if high > 10:
                return (f"⚠ 超时风险 {span}s", "#d0342c")
            if high > 8:
                return (f"⚠ 临界 {span}s", "#e08b00")
            if low <= 0.5:
                return (f"⚠ 极高风险 {span}s", "#b00020")
            if low <= 2:
                return (f"⚠ 过快 {span}s", "#d0342c")
            if low < 5:
                return (f"⚠ 偏快 {span}s", "#e08b00")
            return (f"✓ 安全 {span}s", "#2e9e44")
        if low <= 0.5:
            return (f"⚠ 极高风险 {span}s", "#b00020")
        if low < 2:
            return (f"⚠ 偏快 {span}s", "#e08b00")
        return (f"✓ 安全 {span}s", "#2e9e44")

    def update_speed_warning(self):
        try:
            text, color = self.speed_warning()
            self.speed_warn.setText(text)
            self.speed_warn.setStyleSheet(f"color: {color}; font-weight: bold;")
            low, high = self.speed_range()
            if abs(high - low) < 0.005:
                self.speed_hint.setText(f"上报用时≈{low:.2f}s")
            else:
                self.speed_hint.setText(f"上报用时≈{low:.2f}~{high:.2f}s")
        except Exception as e:
            self.main_logger.error(f"刷新用时提示失败: {e}")

    def on_question_range_changed(self, _value=None):
        """区间改动：写回配置，下一题立即生效"""
        if getattr(self, "_syncing_speed", False):
            return
        try:
            low, high = self.speed_range()
            self.public_info.set_question_range(low, high)
            self.update_speed_warning()
            warn_text, _ = self.speed_warning(low, high)
            detail = f"{low:.2f}s（固定）" if abs(high - low) < 0.005 else f"{low:.2f}~{high:.2f}s"
            self.update_output_info(f"每题用时改为 {detail}（下一题生效）{warn_text}")
            self.main_logger.info(f"每题用时区间设为 {detail} {warn_text}")
        except Exception as e:
            self.main_logger.error(f"设置用时区间失败: {e}")

    def speed_scale(self, factor):
        """加速/减速：区间上下限同时缩放（保留两位小数）"""
        try:
            low, high = self.speed_range()
            lo = max(0.1, min(600.0, round(low * factor, 2)))
            hi = max(0.1, min(600.0, round(high * factor, 2)))
            if lo > hi:
                lo, hi = hi, lo
            if abs(lo - low) < 0.005 and abs(hi - high) < 0.005:
                return
            self._syncing_speed = True
            try:
                self.speed_spin_min.setValue(lo)
                self.speed_spin_max.setValue(hi)
            finally:
                self._syncing_speed = False
            self.on_question_range_changed()
        except Exception as e:
            self.main_logger.error(f"调速失败: {e}")

    def update_output_info(self, info):
        """
        刷新前端输出信息
        :param info:
        :return:
        """
        self._append_output_lines([str(info)])

    def _append_output_lines(self, lines):
        """把若干行纯文本追加到输出信息面板（统一做 HTML 转义，避免日志里的尖括号破坏渲染）"""
        if not lines:
            return
        self.output = self.output + "".join(f"\n{line}" for line in lines)
        # 超长时截断，避免长时间刷题后 HTML 过大卡顿
        if len(self.output) > 120000:
            self.output = "……（历史输出已截断）\n" + self.output[-100000:]
        escaped = html.escape(self.output)
        self.output_info.setHtml(
            f"<pre style='white-space:pre-wrap;word-wrap:break-word;'>{escaped}</pre>"
        )
        if self.follow_output.isChecked():
            scrollbar = self.output_info.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    # ---------------- 控制台输出 -> 界面 ----------------
    def _setup_log_bridge(self):
        """把日志队列接到输出信息面板（替代 cmd 黑框里的日志输出）"""
        try:
            from log.log import install_ui_handler

            install_ui_handler()
        except Exception as e:
            self.main_logger.error(f"安装界面日志处理器失败: {e}")
        self._log_timer = QtCore.QTimer(self)
        self._log_timer.setInterval(250)
        self._log_timer.timeout.connect(self._drain_logs)
        self._log_timer.start()

    def _drain_logs(self):
        try:
            from log.log import drain_ui_records

            records = drain_ui_records()
            if not records:
                return
            lines = []
            for record in records:
                stamp = time.strftime("%H:%M:%S", time.localtime(record.created))
                if record.levelno >= logging.ERROR:
                    tag = "[错误] "
                elif record.levelno >= logging.WARNING:
                    tag = "[警告] "
                else:
                    tag = ""
                try:
                    message = record.getMessage()
                except Exception:
                    message = str(record.msg)
                lines.append(f"[{stamp}] {tag}{message}")
            self._append_output_lines(lines)
        except Exception:
            pass

    # ---------------- 题目详情面板 ----------------
    def on_task_detail(self, text):
        """整题刷新"""
        try:
            self.question_info.setHtml(
                f"<pre style='white-space:pre-wrap;word-wrap:break-word;'>{html.escape(text)}</pre>"
            )
            self.question_info.verticalScrollBar().setValue(0)
        except Exception as e:
            self.main_logger.error(f"显示题目详情失败: {e}")

    def on_task_choice(self, text):
        """在详情面板末尾追加「提交了哪个选项」这一行"""
        try:
            current = self.question_info.toPlainText()
            self.question_info.setHtml(
                f"<pre style='white-space:pre-wrap;word-wrap:break-word;'>{html.escape(current + chr(10) + text)}</pre>"
            )
            self.question_info.verticalScrollBar().setValue(
                self.question_info.verticalScrollBar().maximum()
            )
        except Exception as e:
            self.main_logger.error(f"显示提交结果失败: {e}")

    def token_login(self):
        """
        登录
        :return:
        """
        self.warn_info.setText("")
        input_text = self.token_input.text()
        if '\n' in input_text:
            self.token = input_text.split('\n')[0].strip()
        else:
            self.token = input_text.strip()
        if self.token == '':
            self.warn_info.setStyleSheet("color: red;")
            self.warn_info.setText("登录失败！请输入token！")
        else:
            result = verify_token(self.token)
            self.warn_info.setStyleSheet("color: red;")
            if result == 1:
                self.warn_info.setText("登录失败！token已过期，请重新获取！")
            elif result == 2:
                self.warn_info.setText("登录失败！HTTP请求错误！")
            elif result == 3:
                self.warn_info.setText("登录失败！请检查网络连接！")
            elif result == 4:
                self.warn_info.setText("登录失败！响应内容不是有效的JSON格式！")
            elif result == 5:
                self.warn_info.setText("登录失败！请检查token获取软件是否关闭！")
            elif result == 6:
                self.warn_info.setText("登录失败！请检查或关闭代理软件！")
            elif result == 7:
                self.warn_info.setText("登录失败！请检查网络连接！")
            else:
                self.warn_info.setStyleSheet("color: green;")
                self.warn_info.setText("登录成功！")
                self.update_output_info("登录成功！")
                student_name = result['data']['user_info']['student_name']
                student_code = result['data']['user_info']['student_code']
                school_name = result['data']['user_info']['school_name']
                class_name = result['data']['user_info']['class_name']
                self.user_info.setText(f"{student_name} {student_code} {school_name} {class_name}")
                self.update_output_info("用户信息获取成功！")
                requests.set_token(self.token)
                self.get_task_list()

    def get_task_list(self):
        """
        获取任务列表
        :return:
        """
        # 任务类型（学习/测试）会改变用时风险判定，先刷新一次提示
        try:
            self.update_speed_warning()
        except Exception:
            pass
        self.task_list.setRowCount(0)
        if not self.user_info.text() == "未获取":
            if self.learn_task.isChecked():
                self.public_info._task_choices = 1
                self.update_output_info("开始获取：班级学习任务")
                self.main_logger.info("开始获取：班级学习任务")
            elif self.test_task.isChecked():
                self.public_info._task_choices = 2
                self.update_output_info("开始获取：班级测试任务")
                self.main_logger.info("开始获取：班级测试任务")
            self.public_info.class_task = []
            PublicInfo.task_type = 'ClassTask'
            PublicInfo.task_type_int = 2
            try:
                now_page = 1
                get_class_task(self.public_info, now_page)
                while self.public_info.task_total_count > now_page * 10:
                    now_page += 1
                    get_class_task(self.public_info, now_page)
                get_all_task(self.public_info)
            except Exception as e:
                # 网络请求失败(如服务端 11003 风控)时提示而非崩溃闪退
                self.main_logger.error(f"获取任务列表失败: {e}")
                self.update_output_info(f"获取任务列表失败: {e}")
                QtWidgets.QMessageBox.warning(self, "获取任务列表失败", str(e))
                return
            if not self.public_info.task_list == []:
                task_names = [task['task_name'] for task in self.public_info.task_list]
                self.main_logger.info(f'{task_names}')
                for task in self.public_info.task_list:
                    task_name = task['task_name']
                    progress = task.get('progress', 0)
                    score = task.get('score') or 0
                    over_status = task.get('over_status', 2)
                    row = self.task_list.rowCount()
                    self.task_list.insertRow(row)
                    # 左侧目标任务单选框（容器+布局使其在格内居中）
                    radio = QtWidgets.QRadioButton(self.task_list)
                    radio.clicked.connect(lambda checked, r=row: self._select_task_row(r))
                    self.task_radio_group.addButton(radio)
                    radio_container = QtWidgets.QWidget(self.task_list)
                    radio_layout = QtWidgets.QHBoxLayout(radio_container)
                    radio_layout.setContentsMargins(0, 0, 0, 0)
                    radio_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                    radio_layout.addWidget(radio)
                    self.task_list.setCellWidget(row, 0, radio_container)
                    # 测试任务页面：已完成任务不可重试，禁用勾选、灰色实心圆点并悬浮提示
                    task_disabled = self.test_task.isChecked() and progress >= 100
                    if task_disabled:
                        self.task_radio_group.removeButton(radio)
                        radio.hide()
                        dot = QtWidgets.QLabel(radio_container)
                        dot.setFixedSize(20, 20)
                        dot_pixmap = QtGui.QPixmap(20, 20)
                        dot_pixmap.fill(QtCore.Qt.GlobalColor.transparent)
                        painter = QtGui.QPainter(dot_pixmap)
                        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
                        painter.setPen(QtCore.Qt.PenStyle.NoPen)
                        painter.setBrush(QtGui.QColor("#999999"))
                        painter.drawEllipse(1, 1, 17, 17)
                        painter.end()
                        dot.setPixmap(dot_pixmap)
                        radio_layout.addWidget(dot)
                        radio_container.setToolTip("已完成的测试任务不可重试")
                    score_text = str(score)
                    if over_status == 1:
                        score_text += " (未开始)"
                    # 任务数据存入三个数据列单元格，点任意列都能取到任务
                    for col, text in enumerate([task_name, f"{progress}%", score_text], start=1):
                        cell = QtWidgets.QTableWidgetItem(text)
                        cell.setData(QtCore.Qt.ItemDataRole.UserRole, task)
                        # 已完成的任务显示绿色
                        if progress >= 100:
                            cell.setForeground(QtGui.QColor("green"))
                        # 未开始的任务显示灰色
                        elif over_status == 1:
                            cell.setForeground(QtGui.QColor("gray"))
                        if task_disabled:
                            cell.setToolTip("已完成的测试任务不可重试")
                        self.task_list.setItem(row, col, cell)
                self.update_output_info("获取成功！")
            else:
                self.update_output_info("获取失败！没有任务！")

    def _select_task_row(self, row):
        """
        勾选单选框时同步选中表格行
        :param row:
        :return:
        """
        item = self.task_list.item(row, 1)
        if item:
            self.task_list.setCurrentItem(item)

    def _on_task_item_clicked(self, item):
        """
        点击任务行时自动勾选该行单选框
        :param item:
        :return:
        """
        try:
            task = item.data(QtCore.Qt.ItemDataRole.UserRole)
            if self.test_task.isChecked() and task and task.get('progress', 0) >= 100:
                return
            row = item.row()
            widget = self.task_list.cellWidget(row, 0)
            radio = widget.findChild(QtWidgets.QRadioButton) if widget else None
            if radio and not radio.isChecked():
                radio.setChecked(True)
        except Exception as e:
            self.main_logger.error(f"选择任务行失败: {e}")

    def start(self):
        try:
            current_item = self.task_list.currentItem()
            if not self.public_info.task_list == [] and not self.public_info.class_task == [] and current_item:
                if self.learn_task.isChecked():
                    self.main_logger.info("开始班级学习任务")
                else:
                    self.main_logger.info("开始班级测试任务")
                task_info = current_item.data(QtCore.Qt.ItemDataRole.UserRole)
                if self.test_task.isChecked() and task_info.get('progress', 0) >= 100:
                    self.update_output_info("已完成的测试任务不可重试")
                    QMessageBox.warning(self, "提示", "已完成的测试任务不可重试")
                    return
                task_name = task_info['task_name']
                self.public_info._task_name = task_name
                self.public_info.class_task = [task_info]
                self.update_output_info(f"开始任务{task_name}")
                reply = QMessageBox.question(self, f"开始任务{task_name}",
                                             f"确认开始任务{task_name}吗？\n任务开始后，主页面将无法操作，可点击“中止任务”按钮手动中止任务\n系统将在后台自动执行刷题\n运行期间请勿关闭程序窗口",
                                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                             QMessageBox.StandardButton.Yes)
                if reply == QMessageBox.StandardButton.Yes:
                    task_info = self.public_info.class_task[0]
                    self.public_info.is_self_built = False
                    self._batch_mode = False
                    # 开启新任务周期: 清空上一轮对错/跳过计数
                    self.public_info.right_count = 0
                    self.public_info.wrong_count = 0
                    self.public_info.skip_count = 0
                    self.set_ui_enabled(False)
                    self.task_worker = self.task_worker_class([task_info], batch_mode=False)
                    self.task_worker.task_finished.connect(self.on_task_finished)
                    self.task_worker.task_error.connect(self.on_task_error)
                    self.task_worker.task_progress.connect(self.update_progress)
                    self.task_worker.task_notice.connect(self.on_task_notice)
                    self.task_worker.task_detail.connect(self.on_task_detail)
                    self.task_worker.task_choice.connect(self.on_task_choice)
                    self.task_worker.start()
                    self.start_elapsed()
                    self.update_output_info("任务已在后台开始执行...")
            else:
                self.update_output_info("没有可执行的任务")
        except Exception as e:
            self.main_logger.error(f"运行出错，错误信息：{e}")
            self.update_output_info(f"运行出错，错误信息：{e}")

    def start_batch(self):
        """一键刷题：按顺序自动执行列表中所有未完成的任务"""
        try:
            if self.user_info.text() == "未获取":
                self.update_output_info("请先登录后再使用一键刷题")
                return
            tasks = [t for t in self.public_info.task_list if t.get('progress', 0) < 100]
            if not tasks:
                self.update_output_info("没有可执行的任务（已完成的任务已跳过）")
                return
            skipped = len(self.public_info.task_list) - len(tasks)
            reply = QMessageBox.question(
                self,
                "一键刷题",
                f"将按顺序自动执行 {len(tasks)} 个未完成任务"
                + (f"（已跳过 {skipped} 个已完成任务）" if skipped else "")
                + "\n任务开始后，主页面将无法操作，可点击“中止任务”按钮手动中止任务\n运行期间请勿关闭程序窗口",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            self.public_info.is_self_built = False
            self._batch_mode = True
            # 开启新一轮一键刷题: 清空上一轮对错/跳过计数
            self.public_info.right_count = 0
            self.public_info.wrong_count = 0
            self.public_info.skip_count = 0
            self.set_ui_enabled(False)
            self.task_worker = self.task_worker_class(tasks, batch_mode=True)
            self.task_worker.task_finished.connect(self.on_task_finished)
            self.task_worker.task_error.connect(self.on_task_error)
            self.task_worker.task_progress.connect(self.update_progress)
            self.task_worker.task_notice.connect(self.on_task_notice)
            self.task_worker.task_detail.connect(self.on_task_detail)
            self.task_worker.task_choice.connect(self.on_task_choice)
            self.task_worker.batch_finished.connect(self.on_batch_finished)
            self.task_worker.start()
            self.start_elapsed()
            self.update_output_info(f"开始一键刷题：共 {len(tasks)} 个任务")
        except Exception as e:
            self.main_logger.error(f"一键刷题启动失败: {e}")
            self.update_output_info(f"运行出错，错误信息：{e}")

    def update_progress(self, progress_text):
        """
        更新进度
        :param progress_text: 格式 "done/total|right|wrong|skip|index/total|task_name"
        :return:
        """
        # 先按 | 切分(避免 index/total 段中的 / 破坏 done/total 解析)
        segments = progress_text.split('|')
        dt = segments[0].split('/')
        if len(dt) == 2:
            try:
                done = int(dt[0])
                total = int(dt[1])
                self.progress_bar.setMaximum(total)
                self.progress_bar.setValue(done)
                self.progress_label.setText(f"{done}/{total}")
                if len(segments) > 2:
                    self.progress_right_label.setText(f"正确 {segments[1]}")
                    self.progress_wrong_label.setText(f"错误 {segments[2]}")
                    if len(segments) > 3:
                        self.progress_skip_label.setText(f"跳过 {segments[3]}")
                        if len(segments) > 5:
                            self.progress_task_label.setText(f"[{segments[4]}] {segments[5]}")
            except ValueError:
                pass

    def on_task_finished(self, message):
        """
        任务完成
        :param message:
        :return:
        """
        self.main_logger.info(f'{message}')
        if self._batch_mode:
            # 批量模式：不弹窗，输出信息并刷新任务列表，自动继续下一个任务
            self.update_output_info(message)
            self.progress_bar.setValue(0)
            self.progress_label.setText("")
            self.progress_task_label.setText("")
            self.progress_right_label.setText("")
            self.progress_wrong_label.setText("")
            self.progress_skip_label.setText("")
            self.get_task_list()
            return
        self.set_ui_enabled(True)
        self.stop_elapsed("任务完成")
        self.progress_bar.setValue(self.progress_bar.maximum())
        music_thread = threading.Thread(target=self.play_music)
        music_thread.start()
        QtWidgets.QMessageBox.information(self, "任务完成！", message)
        task_name = self.public_info.class_task[0]['task_name']
        self.update_output_info(f"{task_name}运行完成")
        self.update_output_info(message)
        # 自动刷新任务列表，显示最新进度和得分
        time.sleep(1)
        self.get_task_list()
        if self.task_worker:
            self.task_worker.deleteLater()
            self.task_worker = None

    def on_batch_finished(self, summary):
        """
        一键刷题全部任务执行结束
        :param summary:
        :return:
        """
        self._batch_mode = False
        self.set_ui_enabled(True)
        self.stop_elapsed("一键刷题完成")
        self.progress_bar.setValue(0)
        self.progress_label.setText("")
        self.progress_right_label.setText("")
        self.progress_wrong_label.setText("")
        self.progress_skip_label.setText("")
        self.main_logger.info(summary)
        self.update_output_info(summary)
        music_thread = threading.Thread(target=self.play_music)
        music_thread.start()
        QtWidgets.QMessageBox.information(self, "一键刷题完成", summary)
        # 等服务端进度落库后再刷新
        time.sleep(1)
        self.get_task_list()
        if self.task_worker:
            self.task_worker.deleteLater()
            self.task_worker = None

    def on_task_notice(self, message):
        """
        任务执行中的提示信息
        :param message:
        :return:
        """
        self.main_logger.info(message)
        self.update_output_info(message)

    def on_task_error(self, error_message):
        """
        任务出错
        :param error_message:
        :return:
        """
        self._batch_mode = False
        self.set_ui_enabled(True)
        self.stop_elapsed("异常中止")
        self.progress_bar.setValue(0)
        self.progress_label.setText("")
        self.progress_right_label.setText("")
        self.progress_wrong_label.setText("")
        self.progress_skip_label.setText("")
        self.main_logger.error(f"运行出错，错误信息：{error_message}")
        self.update_output_info(f"运行出错，错误信息：{error_message}")
        error = view.error.Ui_Form()
        error.exec()
        if self.task_worker:
            self.task_worker.deleteLater()
            self.task_worker = None

    def open_settings(self, m):
        """
        打开设置
        :param m:
        :return:
        """
        if m.text() == "首选项...":
            self.settings = view.setting.Ui_Form(self.public_info)
            self.settings.show()

    def open_helper(self, m):
        """
        打开帮助
        :param m:
        :return:
        """
        if m.text() == "使用教程":
            self.use_introduction = view.introduce.Ui_Form()
            self.use_introduction.show()
        elif m.text() == "关于Easy_Cidaren":
            QtGui.QDesktopServices.openUrl(QtCore.QUrl('https://github.com/ularch/Easy_Cidaren'))
        elif m.text() == "关于作者":
            QtGui.QDesktopServices.openUrl(QtCore.QUrl('https://github.com/ularch'))
        elif m.text() == "关于":
            uid = get_uuid()
            msg_box = QMessageBox()
            msg_box.setWindowTitle("关于")
            msg_box.setText(f"EasyCidaren\n版本: {self.public_info.version}\n作者: ularch\n开源地址: https://github.com/ularch/Easy_Cidaren\n唯一设备ID: {uid}")
            msg_box.setIcon(QMessageBox.Icon.Information)
            copy_button = msg_box.addButton("复制", QMessageBox.ButtonRole.ActionRole)
            close_button = msg_box.addButton("关闭", QMessageBox.ButtonRole.AcceptRole)
            msg_box.setDefaultButton(close_button)
            msg_box.exec()
            if msg_box.clickedButton() == copy_button:
                clipboard = QApplication.clipboard()
                info_text = f"EasyCidaren\n版本: {self.public_info.version}\n作者: ularch\n开源地址: https://github.com/ularch/Easy_Cidaren\n唯一设备ID: {uid}"
                clipboard.setText(info_text)
                QMessageBox.information(self, "复制成功", "已将相关信息复制到剪贴板")
        elif m.text() == "第三方":
            self.get_token()
        elif m.text() == "内置":
            self.open_builtin_token_dialog()
        elif m.text() == "导出日志文件":
            from log.log import export_logs
            export_logs(self)

    def play_music(self):
        """
        播放音乐
        :return:
        """
        if hasattr(self.public_info, 'music_path') and self.public_info.music_path:
            if os.path.exists(self.public_info.music_path):
                music_path = self.public_info.music_path
            else:
                music_path = self.root_path + "/assets/music.wav"
                self.main_logger.error("自定义音乐文件不存在，使用默认音乐")
        else:
            music_path = self.root_path + "/assets/music.wav"
        try:
            playsound(music_path)
        except Exception as e:
            self.main_logger.info(f"playsound播放失败，使用winsound播放: {e}")
            try:
                winsound.PlaySound(music_path, winsound.SND_FILENAME)
            except Exception as e2:
                self.main_logger.info(f"winsound播放失败: {e2}")

    def get_token(self):
        """
        打开获取 token 界面
        :return:
        """
        exe_path = self.root_path + "\\get token\\词达人token获取.exe"
        try:
            subprocess.Popen([exe_path], shell=True)
        except:
            self.main_logger.info("词达人token获取.exe打开失败")

    def ask_capture_token(self):
        """启动时询问是否自动捕获 token；选「是」直接进内置捕获流程"""
        try:
            box = QMessageBox(self)
            box.setWindowTitle("YM词达人")
            box.setIcon(QMessageBox.Icon.Question)
            box.setText("是否现在自动捕获 token？")
            box.setInformativeText(
                "选择「是」：自动配置系统代理并开始抓取微信里的 UserToken，"
                "抓取期间请不要在其它设备登录词达人。\n"
                "选择「否」：直接进入主界面，可手动粘贴 token，或稍后从"
                "「帮助 → 获取 token → 内置」再抓。"
            )
            yes_button = box.addButton("是，自动捕获", QMessageBox.ButtonRole.AcceptRole)
            box.addButton("否", QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(yes_button)
            box.exec()
            if box.clickedButton() is yes_button:
                self.main_logger.info("启动时选择自动捕获 token")
                self.update_output_info("开始自动捕获 token...")
                self.open_builtin_token_dialog(auto_start=True)
            else:
                self.main_logger.info("启动时跳过 token 捕获，等待手动输入")
                self.update_output_info("已跳过自动捕获，请手动输入 token")
        except Exception as e:
            self.main_logger.error(f"询问是否捕获 token 失败: {e}")

    def open_builtin_token_dialog(self, auto_start=False):
        """
        打开内置 token 获取功能
        :param auto_start: 是否自动点击「开始捕获」
        """
        try:
            from view.builtin_token import BuiltinTokenDialog
            fetch_token_path = os.path.join(self.root_path, "get token", "fetch_token")
            if not os.path.exists(fetch_token_path):
                QMessageBox.critical(self, "错误", f"fetch_token 目录不存在：{fetch_token_path}")
                return
            dialog = BuiltinTokenDialog(
                parent=self, fetch_token_path=fetch_token_path, auto_start=auto_start
            )
            dialog.captured.connect(self.on_builtin_token_captured)
            dialog.exec()
        except ImportError as e:
            QMessageBox.critical(self, "错误", f"无法导入 builtin_token 模块：{e}")
            self.main_logger.error(f"导入 builtin_token 模块失败: {e}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开内置 token 获取功能失败：{e}")
            self.main_logger.error(f"打开内置 token 获取功能失败: {e}", exc_info=True)

    def on_builtin_token_captured(self, token):
        """
        内置 token 获取功能捕获 token
        :param token:
        :return:
        """
        if token:
            self.token_input.setText(token)
            self.update_output_info("Token 已自动填充到输入框")
            self.main_logger.info("内置 token 捕获成功，已自动填充")
            reply = QMessageBox.question(
                self,
                "自动登录",
                "Token 已捕获成功！是否立即登录？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.token_login()

    def set_ui_enabled(self, enabled):
        self.token_input.setEnabled(enabled)
        self.login.setEnabled(enabled)
        self.learn_task.setEnabled(enabled)
        self.test_task.setEnabled(enabled)
        self.task_list.setEnabled(enabled)
        self.start_task.setEnabled(enabled)
        self.batch_start.setEnabled(enabled)
        self.menu.setEnabled(enabled)
        self.menu_2.setEnabled(enabled)
        if not enabled:
            self.stop_task.setEnabled(True)

    def stop_current_task(self):
        """
        停止当前任务
        :return:
        """
        if self.task_worker and self.task_worker.isRunning():
            reply = QMessageBox.question(
                self,
                "确认停止",
                "确定要停止当前任务吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.task_worker.stop()
                self.task_worker.quit()
                self.task_worker.wait()
                self._batch_mode = False
                self.set_ui_enabled(True)
                self.stop_elapsed("手动中止")
                self.progress_bar.setValue(0)
                self.progress_label.setText("")
                self.progress_right_label.setText("")
                self.progress_wrong_label.setText("")
                self.progress_skip_label.setText("")
                self.update_output_info("任务已手动停止")
                QMessageBox.information(self, "任务停止", "任务已安全停止")
                self.task_worker.deleteLater()
                self.task_worker = None
                self.main_logger.info("任务已手动停止")
        else:
            return
