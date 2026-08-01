import sys
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler

from core.constants import APP_VERSION


def main():
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QIcon
    from gui.theme import ThemeManager, set_theme

    ROOT = Path(__file__).parent
    sys.path.insert(0, str(ROOT))

    LOG_DIR = ROOT / "history"
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    _handler = RotatingFileHandler(
        str(LOG_DIR / 'converter.log'),
        maxBytes=1024 * 1024, backupCount=2, encoding='utf-8'
    )
    _handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(_handler)
    app = QApplication(sys.argv)
    app.setApplicationName("MediaConverter")
    app.setApplicationVersion(APP_VERSION)

    icon_path = ROOT / "ico" / "Miku.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    theme_mgr = ThemeManager(app, ROOT)
    set_theme(theme_mgr)
    theme_mgr.load_theme(theme_mgr.current)

    from gui.main_window import MainWindow
    window = MainWindow(theme_mgr)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
