"""运行时路径工具 — 所有产物必须留在程序目录内（硬约束）。"""
import os
import sys
from pathlib import Path


def program_dir() -> Path:
    """程序所在目录（frozen 打包时为 exe 所在目录）。"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def history_dir() -> Path:
    return program_dir() / "history"


def tmp_dir() -> Path:
    """项目内临时目录（创建于首次调用），替代系统 %TEMP%。"""
    d = program_dir() / "tmp"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        d = history_dir()
        try:
            d.mkdir(parents=True, exist_ok=True)
        except OSError:
            d = Path(os.environ.get('TEMP', str(Path.home() / 'AppData/Local/Temp')))
    return d
