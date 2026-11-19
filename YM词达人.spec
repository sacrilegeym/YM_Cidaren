# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：把 YM词达人 打成单文件 exe。

包含内容：
  · 代码（main.py 及其所有依赖包）
  · en_core_web_sm（spaCy 模型，约 14MB）
  · assets / config / get token（图标、默认配置、内置 token 对话框占位目录）
  · mitmproxy + mitmproxy_rs（进程内抓包，替代外部 mitmdump.exe）
"""
import os

ROOT = r"E:\ShuaKe"

datas = [
    (os.path.join(ROOT, "en_core_web_sm"), "en_core_web_sm"),
    (os.path.join(ROOT, "assets"), "assets"),
    (os.path.join(ROOT, "config"), "config"),
    (os.path.join(ROOT, "get token"), "get token"),
]
binaries = []
hiddenimports = [
    "brotli",
    "playsound",
    "mitmproxy.tools.dump",
    "mitmproxy.options",
    "mitmproxy.http",
]

# 把几个"运行时动态导入"的包完整收进来
from PyInstaller.utils.hooks import collect_all, collect_submodules

for pkg in ("spacy", "thinc", "mitmproxy", "mitmproxy_rs", "srsly", "blis", "weasel"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception as exc:  # 某个包收不全也不至于让构建直接失败
        print(f"[spec] collect_all({pkg}) failed: {exc}")

try:
    hiddenimports += collect_submodules("mitmproxy")
except Exception as exc:
    print(f"[spec] collect_submodules(mitmproxy) failed: {exc}")

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "IPython", "pytest", "pandas", "notebook"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="YM词达人",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,          # 无 cmd 窗口
    disable_windowed_traceback=False,
    icon=os.path.join(ROOT, "assets", "icon.ico"),
)
