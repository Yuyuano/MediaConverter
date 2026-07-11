import sys
import os
import logging
from pathlib import Path

# 确保项目根目录在 sys.path 中
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from core.constants import APP_VERSION
from core.history import HISTORY_DIR


# 日志配置 — 复用 history 模块的目录
LOG_DIR = HISTORY_DIR
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(LOG_DIR / 'converter.log'),
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    encoding='utf-8'
)


def load_stylesheet() -> str:
    qss_path = ROOT / "gui" / "styles" / "dark.qss"
    if qss_path.exists():
        with open(qss_path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MediaConverter")
    app.setApplicationVersion(APP_VERSION)

    # 应用图标
    icon_path = ROOT / "ico" / "Miku.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # 加载暗色主题
    stylesheet = load_stylesheet()
    if stylesheet:
        app.setStyleSheet(stylesheet)

    from gui.main_window import MainWindow
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
