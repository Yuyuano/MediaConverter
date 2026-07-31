import sys
import logging
from pathlib import Path

from core.constants import APP_VERSION


def main():
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QIcon
    from gui.theme import ThemeManager, set_theme

    ROOT = Path(__file__).parent
    sys.path.insert(0, str(ROOT))

    LOG_DIR = ROOT / "history"
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(LOG_DIR / 'converter.log'),
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        encoding='utf-8'
    )
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
