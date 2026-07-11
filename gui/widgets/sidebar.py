from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel
from PyQt6.QtCore import pyqtSignal, Qt
from core.constants import APP_VERSION


class Sidebar(QWidget):
    page_changed = pyqtSignal(int)

    NAV_ITEMS = [
        (0, "video",   "📹  视频转换"),
        (1, "image",   "🖼️  图片转换"),
        (2, "audio",   "🎵  音频转换"),
        (3, "history", "📋  历史记录"),
    ]

    def __init__(self):
        super().__init__()
        self._buttons = {}
        self._current = 0
        self.setObjectName("sidebar")
        self.setFixedWidth(180)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title = QLabel("MediaConverter")
        title.setObjectName("sidebarTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFixedHeight(50)
        layout.addWidget(title)

        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #313244;")
        layout.addWidget(sep)

        for idx, key, text in self.NAV_ITEMS:
            btn = QPushButton(text)
            btn.setObjectName("sidebarBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, i=idx: self._on_click(i))
            self._buttons[key] = btn
            layout.addWidget(btn)

        layout.addStretch()

        ver = QLabel(f"v{APP_VERSION}")
        ver.setObjectName("sidebarVersion")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver.setFixedHeight(40)
        layout.addWidget(ver)

        self._update_highlight(0)

    def _on_click(self, idx: int):
        if idx == self._current:
            return
        self._current = idx
        self._update_highlight(idx)
        self.page_changed.emit(idx)

    def _update_highlight(self, idx: int):
        for key, btn in self._buttons.items():
            btn.setChecked(False)
        target_key = self.NAV_ITEMS[idx][1]
        self._buttons[target_key].setChecked(True)

    def set_active(self, idx: int):
        if idx != self._current:
            self._current = idx
            self._update_highlight(idx)
            self.page_changed.emit(idx)
