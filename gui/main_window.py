import os
import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QMessageBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from core.converter import MediaConverter
from core.constants import APP_VERSION, VIDEO_EXTS, IMAGE_EXTS, AUDIO_EXTS
from gui.widgets.sidebar import Sidebar
from gui.widgets.history_table import HistoryTable
from gui.pages.convert_page import ConvertPage
from gui.workers.detect_worker import DetectWorker

logger = logging.getLogger('MediaConverter')


_PAGE_ORDER = ['video', 'image', 'audio']


def _fmt_to_media_type(fmt: str) -> str:
    ext = f".{fmt.lower()}"
    if ext in VIDEO_EXTS or fmt == 'gif':
        return 'video'
    if ext in IMAGE_EXTS:
        return 'image'
    if ext in AUDIO_EXTS:
        return 'audio'
    return 'video'


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"MediaConverter v{APP_VERSION} - 媒体格式转换工具")
        self.setMinimumSize(800, 600)
        self.resize(1000, 800)

        icon_path = Path(__file__).parent.parent / "ico" / "Miku.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self._converter = MediaConverter()
        self._init_ui()
        self._connect_signals()
        self._start_gpu_detect()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.sidebar = Sidebar()
        self.stack = QStackedWidget()

        self.pages = {}
        for mt in _PAGE_ORDER:
            page = ConvertPage(self._converter, mt)
            self.pages[mt] = page
            self.stack.addWidget(page)

        self.history_table = HistoryTable(self._converter.history)
        self.stack.addWidget(self.history_table)

        main_layout.addWidget(self.sidebar, 0)
        main_layout.addWidget(self.stack, 1)

        self.statusBar().showMessage("就绪")

    def _connect_signals(self):
        self.sidebar.page_changed.connect(self._on_page_changed)
        for mt, page in self.pages.items():
            page.status_message.connect(self.statusBar().showMessage)
            page.conversion_done.connect(self.history_table.refresh)
        self.history_table.replay_requested.connect(self._on_replay)

    def _start_gpu_detect(self):
        self._detect_worker = DetectWorker(self._converter)
        self._detect_worker.detected.connect(self._on_gpu_detected)
        self._detect_worker.start()

    def _on_gpu_detected(self, gpu_type, gpu_name):
        for page in self.pages.values():
            page.set_gpu_available(bool(gpu_type), gpu_name, gpu_type)
        if gpu_type:
            self.statusBar().showMessage(f"GPU: {gpu_name}")
        else:
            self.statusBar().showMessage("就绪 (CPU 模式)")

    def _on_page_changed(self, idx: int):
        self.stack.setCurrentIndex(idx)
        if idx < 3:
            names = ['视频转换', '图片转换', '音频转换']
            self.statusBar().showMessage(f"当前: {names[idx]}")
        else:
            self.history_table.refresh()
            self.statusBar().showMessage("历史记录")

    def _on_replay(self, record: dict):
        filepath = record.get('file', '')
        if not os.path.isfile(filepath):
            QMessageBox.warning(self, "提示", f"原文件已不存在:\n{filepath}")
            return
        fmt = record.get('format', '')
        mt = _fmt_to_media_type(fmt) if fmt else 'video'
        page_idx = _PAGE_ORDER.index(mt)
        self.sidebar.set_active(page_idx)
        self.stack.setCurrentIndex(page_idx)
        page = self.pages[mt]
        page.load_file(filepath)
        if fmt:
            page.select_format(fmt)
        self.statusBar().showMessage(f"已加载历史文件: {Path(filepath).name}")

    def closeEvent(self, event):
        self._converter.cleanup()
        for page in self.pages.values():
            page.cleanup()
        event.accept()
