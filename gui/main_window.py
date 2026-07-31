import os
import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QMessageBox, QLabel, QPushButton,
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
    def __init__(self, theme_mgr=None):
        super().__init__()
        self._theme_mgr = theme_mgr
        self.setWindowTitle(f"MediaConverter v{APP_VERSION} - 媒体格式转换工具")
        self.setMinimumSize(800, 600)
        self.resize(1000, 800)

        icon_path = Path(__file__).parent.parent / "ico" / "Miku.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self._converters = {}
        self._init_ui()
        self._connect_signals()
        self._start_gpu_detect()

    def _init_ui(self):
        central = QWidget()
        central.setObjectName("centralWidget")
        central.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.sidebar = Sidebar()
        self.stack = QStackedWidget()

        self.pages = {}
        for mt in _PAGE_ORDER:
            conv = MediaConverter()
            self._converters[mt] = conv
            page = ConvertPage(conv, mt)
            self.pages[mt] = page
            self.stack.addWidget(page)

        self.history_table = HistoryTable(self._converters['video'].history)
        self.stack.addWidget(self.history_table)

        main_layout.addWidget(self.sidebar, 0)
        main_layout.addWidget(self.stack, 1)

        self._status_label = QLabel("就绪")
        if self._theme_mgr:
            t = self._theme_mgr.tokens
            self._status_label.setStyleSheet(f"color: {t.get('on_surface_variant')}; font-size: 12px;")
        else:
            self._status_label.setStyleSheet("color: #a6adc8; font-size: 12px;")
        self.statusBar().addWidget(self._status_label, 1)

        self._theme_btn = QPushButton("☾" if self._theme_mgr and self._theme_mgr.current == 'dark' else "☀")
        self._theme_btn.setObjectName("themeBtn")
        self._theme_btn.setFixedSize(28, 28)
        self._theme_btn.setFlat(True)
        self._theme_btn.setToolTip("切换主题")
        self._theme_btn.clicked.connect(self._toggle_theme)
        self.statusBar().addPermanentWidget(self._theme_btn)

        self._ver_label = QLabel(f"v{APP_VERSION}")
        if self._theme_mgr:
            t = self._theme_mgr.tokens
            self._ver_label.setStyleSheet(f"color: {t.get('on_surface_dim')}; font-size: 11px; padding: 0 8px;")
        else:
            self._ver_label.setStyleSheet("color: #585b70; font-size: 11px; padding: 0 8px;")
        self.statusBar().addPermanentWidget(self._ver_label)

    def _connect_signals(self):
        self.sidebar.page_changed.connect(self._on_page_changed)
        for mt, page in self.pages.items():
            page.status_message.connect(self._set_status)
            page.conversion_done.connect(self.history_table.refresh)
        self.history_table.replay_requested.connect(self._on_replay)

    def _set_status(self, msg: str):
        if self._theme_mgr:
            t = self._theme_mgr.tokens
            colors = {
                '完成': t.get('success', '#a6e3a1'),
                '失败': t.get('error', '#f38ba8'),
                '错误': t.get('error', '#f38ba8'),
                '取消': t.get('warning', '#f9e2af'),
            }
            default = t.get('on_surface_variant', '#a6adc8')
        else:
            colors = {}
            default = '#a6adc8'
        color = default
        for key, c in colors.items():
            if key in msg:
                color = c
                break
        self._status_label.setStyleSheet(f"color: {color}; font-size: 12px;")
        self._status_label.setText(msg)

    def _toggle_theme(self):
        if self._theme_mgr:
            self._theme_mgr.toggle()
            self._theme_btn.setText("☾" if self._theme_mgr.current == 'dark' else "☀")
            # Refresh status bar inline styles with new tokens
            t = self._theme_mgr.tokens
            self._status_label.setStyleSheet(
                f"color: {t.get('on_surface_variant', '#a6adc8')}; font-size: 12px;"
            )
            self._ver_label.setStyleSheet(
                f"color: {t.get('on_surface_dim', '#585b70')}; font-size: 11px; padding: 0 8px;"
            )

    def _start_gpu_detect(self):
        self._detect_worker = DetectWorker(self._converters['video'])
        self._detect_worker.detected.connect(self._on_gpu_detected)
        self._detect_worker.finished.connect(self._detect_worker.deleteLater)
        self._detect_worker.start()

    def _on_gpu_detected(self, gpu_type, gpu_name):
        for page in self.pages.values():
            page.set_gpu_available(bool(gpu_type), gpu_name, gpu_type)
        if gpu_type:
            self._set_status(f"GPU: {gpu_name}")
        else:
            self._set_status("就绪 (CPU 模式)")

    def _on_page_changed(self, idx: int):
        self.stack.setCurrentIndex(idx)
        if idx < 3:
            names = ['视频转换', '图片转换', '音频转换']
            self._set_status(f"当前: {names[idx]}")
        else:
            self.history_table.refresh()
            self._set_status("历史记录")

    def _on_replay(self, record: dict):
        filepath = record.get('file', '')
        if not filepath or not os.path.isfile(filepath):
            QMessageBox.warning(self, "提示", f"原文件已不存在:\n{filepath}")
            return
        fmt = record.get('format', '')
        mt = _fmt_to_media_type(fmt) if fmt else 'video'
        page_idx = _PAGE_ORDER.index(mt)
        self.sidebar.set_active(page_idx)
        page = self.pages[mt]
        page.load_file(filepath)
        if fmt:
            page.select_format(fmt)
        opts = record.get('options', {})
        if opts:
            page.param_panel.apply_options(opts)
        self._set_status(f"已加载历史文件: {Path(filepath).name}")

    def closeEvent(self, event):
        for conv in self._converters.values():
            conv.cleanup()
        try:
            if self._detect_worker and self._detect_worker.isRunning():
                self._detect_worker.requestInterruption()
                if not self._detect_worker.wait(11000):
                    self._detect_worker.finished.connect(self._detect_worker.deleteLater)
                    self._detect_worker = None
        except RuntimeError:
            pass
        for page in self.pages.values():
            page.cleanup()
        event.accept()
