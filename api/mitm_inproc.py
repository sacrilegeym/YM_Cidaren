"""进程内 token 捕获（替代外部 mitmdump.exe）。

原实现靠 `mitmdump` 子进程抓包，需要机器上另有安装 mitmproxy 的 Python 环境。
打包成单文件 exe 后这种外部程序不存在，所以改成在应用进程里直接跑一个
mitmproxy `DumpMaster`（后台线程 + 独立 asyncio 事件循环）。

抓取逻辑与 `get token/fetch_token/addon.py` 完全一致：
命中 `app.vocabgo.com` 的请求 → 取 `UserToken` 请求头 → 写入 token.txt。
"""
import asyncio
import os
import threading

from log.log import Log

logger = Log("mitm_inproc").logger


class TokenCatcher:
    """mitmproxy addon：只关心 vocabgo 的 UserToken"""

    def __init__(self, token_file, on_captured=None):
        self.token_file = token_file
        self.on_captured = on_captured
        self.token = None

    def request(self, flow):
        try:
            if flow.request.host != "app.vocabgo.com":
                return
            token = flow.request.headers.get("UserToken")
            if not token:
                return
            self._save(token)
        except Exception as e:
            logger.error(f"解析请求失败: {e}")

    def response(self, flow):
        self.request(flow)

    def _save(self, token):
        if token == self.token:
            return
        self.token = token
        try:
            directory = os.path.dirname(self.token_file)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(self.token_file, "w", encoding="utf-8") as f:
                f.write(token)
            logger.info(f"捕获到 UserToken: {token[:8]}...")
        except Exception as e:
            logger.error(f"写入 token 文件失败: {e}")
            return
        if self.on_captured:
            try:
                self.on_captured(token)
            except Exception as e:
                logger.error(f"token 回调失败: {e}")


class InProcessProxy:
    """在后台线程里运行 mitmproxy，接口对齐原先 subprocess 的用法（start/poll/stop）"""

    def __init__(self, host="127.0.0.1", port=8888, addons=None):
        self.host = host
        self.port = port
        self._addons = list(addons or [])
        self._thread = None
        self._loop = None
        self._master = None
        self._ready = threading.Event()
        self._error = None

    def start(self, timeout=30):
        self._thread = threading.Thread(target=self._run, name="ym-mitmproxy", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout):
            raise RuntimeError("mitmproxy 启动超时（30 秒）")
        if self._error is not None:
            raise RuntimeError(f"mitmproxy 启动失败: {self._error}")
        logger.info(f"进程内 mitmproxy 已监听 {self.host}:{self.port}")

    def _run(self):
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._amain())
        except Exception as e:
            self._error = e
            logger.error(f"mitmproxy 运行异常: {e}", exc_info=True)
            self._ready.set()

    async def _amain(self):
        """DumpMaster 必须在**运行中的**事件循环里构造（内部会取 running loop）"""
        from mitmproxy import options as mitm_options
        from mitmproxy.tools.dump import DumpMaster

        opts = mitm_options.Options(listen_host=self.host, listen_port=self.port)
        self._master = DumpMaster(opts, with_termlog=False, with_dumper=False)
        for addon in self._addons:
            self._master.addons.add(addon)
        logger.info("mitmproxy 实例就绪")
        self._ready.set()
        await self._master.run()

    def poll(self):
        """与 subprocess.Popen.poll 语义一致：存活返回 None，已退出返回非 None"""
        if self._thread is None:
            return 1
        return None if self._thread.is_alive() else 1

    def stop(self, timeout=5):
        try:
            if self._master is not None and self._loop is not None:
                self._loop.call_soon_threadsafe(self._master.shutdown)
        except Exception as e:
            logger.error(f"停止 mitmproxy 失败: {e}")
        if self._thread is not None:
            self._thread.join(timeout)
            logger.info("mitmproxy 线程已结束")
