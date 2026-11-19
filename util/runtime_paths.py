"""运行时路径管理：区分「资源目录」和「数据目录」。

· 开发运行（python main.py）：两者都是项目根目录，行为与原来完全一致。
· 单文件 exe（PyInstaller onefile）：代码/模型/默认配置被打进 exe，
  运行时解包到临时目录（sys._MEIPASS，只读性质、退出即删）；
  而 config / log / token 这类**要写**的东西必须放在 exe 旁边，
  否则每次重启都丢配置、日志也找不到。

对外提供：
    RESOURCE_DIR  只读资源（en_core_web_sm、assets、get token/addon.py）
    DATA_DIR      可写数据（config、log、token.txt）
    ensure_data_files()  首次运行把默认配置从资源目录复制到数据目录
"""
import os
import shutil
import sys

FROZEN = bool(getattr(sys, "frozen", False))

if FROZEN:
    RESOURCE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
else:
    # 开发运行：本文件在 util/ 下，项目根目录是它的上一级
    RESOURCE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _is_writable(path):
    """真实写一个文件来判断可写（比 os.access 可靠）"""
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".write_probe")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("1")
        os.remove(probe)
        return True
    except Exception:
        return False


def _pick_data_dir():
    if not FROZEN:
        return RESOURCE_DIR
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    local_app = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    for candidate in (exe_dir, os.path.join(local_app, "YM_Cidaren")):
        if _is_writable(candidate):
            return candidate
    return os.path.expanduser("~")


DATA_DIR = _pick_data_dir()

# 需要随 exe 分发、但首次运行必须落到数据目录的默认配置
_DEFAULT_DATA_FILES = (
    os.path.join("config", "config.json"),
    os.path.join("config", "answer_lib.json"),
    os.path.join("config", "word_pool.json"),
)


def ensure_data_files():
    """把打包进来的默认配置复制到数据目录（已存在则不覆盖，保留用户积累的答案库）"""
    if os.path.abspath(RESOURCE_DIR) == os.path.abspath(DATA_DIR):
        return
    for rel in _DEFAULT_DATA_FILES:
        src = os.path.join(RESOURCE_DIR, rel)
        dst = os.path.join(DATA_DIR, rel)
        if not os.path.exists(src) or os.path.exists(dst):
            continue
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
        except Exception:
            pass


def resource_path(*parts):
    return os.path.join(RESOURCE_DIR, *parts)


def data_path(*parts):
    return os.path.join(DATA_DIR, *parts)
