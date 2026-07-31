import os
from pathlib import Path
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget, QFileDialog, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QFont

from core.constants import ALL_MEDIA_EXTS, VIDEO_EXTS, IMAGE_EXTS, AUDIO_EXTS


class FileDropWidget(QWidget):
    file_selected = pyqtSignal(str)
    info_requested = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self._filepath = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.drop_label = QLabel("▽ 拖入文件到此处\n或点击下方按钮选择")
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_label.setObjectName("dropLabel")
        self.drop_label.setMinimumHeight(90)

        btn_layout = QHBoxLayout()
        self.btn_file = QPushButton("+ 选择文件")
        self.btn_file.setFixedHeight(30)
        self.btn_file.clicked.connect(self._select_file)
        self.btn_info = QPushButton("i")
        self.btn_info.setFixedSize(30, 30)
        self.btn_info.setToolTip("查看媒体信息")
        self.btn_info.clicked.connect(self._request_info)
        self.btn_info.hide()
        self.btn_clear = QPushButton("✕")
        self.btn_clear.setFixedSize(30, 30)
        self.btn_clear.setToolTip("清除")
        self.btn_clear.clicked.connect(self.clear)
        self.btn_clear.hide()
        btn_layout.addWidget(self.btn_file)
        btn_layout.addSpacing(6)
        btn_layout.addWidget(self.btn_info)
        btn_layout.addWidget(self.btn_clear)
        btn_layout.addStretch()

        self.file_info_label = QLabel("")
        self.file_info_label.setObjectName("fileInfo")
        self.file_info_label.setWordWrap(True)

        self._type_icon = QLabel("")
        self._type_icon.setObjectName("typeIcon")
        self._type_icon.setFixedSize(32, 32)
        self._type_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._type_icon.hide()

        file_row = QHBoxLayout()
        file_row.addWidget(self._type_icon)
        file_row.addWidget(self.file_info_label, 1)

        layout.addWidget(self.drop_label)
        layout.addLayout(btn_layout)
        layout.addLayout(file_row)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                path = url.toLocalFile()
                if path and Path(path).suffix.lower() in ALL_MEDIA_EXTS:
                    self._set_drop_state("drag")
                    self.drop_label.setText("⊕ 松开以添加文件")
                    event.acceptProposedAction()
                    return
            event.ignore()

    def dragLeaveEvent(self, event):
        self._reset_drop_style()

    def dropEvent(self, event: QDropEvent):
        self._reset_drop_style()
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            self.set_file(path)

    def _set_drop_state(self, state: str):
        """Switch drop-label visual state via dynamic property (styled in QSS)."""
        self.drop_label.setProperty("state", state)
        self.drop_label.style().unpolish(self.drop_label)
        self.drop_label.style().polish(self.drop_label)

    def _reset_drop_style(self):
        self._set_drop_state("")

    def _select_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择媒体文件",
            filter="媒体文件 (*.mp4 *.avi *.mkv *.mov *.webm *.wmv *.flv *.m4v "
                   "*.jpg *.jpeg *.png *.bmp *.webp *.gif *.tiff "
                   "*.mp3 *.wav *.aac *.flac *.ogg *.m4a *.wma);;所有文件 (*.*)"
        )
        if path:
            self.set_file(path)

    def _request_info(self):
        if self._filepath:
            self.info_requested.emit(self._filepath)

    def _get_type_icon(self, ext: str) -> str:
        if ext in VIDEO_EXTS or ext == '.gif':
            return "▶"
        if ext in IMAGE_EXTS:
            return "◆"
        if ext in AUDIO_EXTS:
            return "♪"
        return "?"

    def set_file(self, path: str):
        if not os.path.isfile(path):
            return
        ext = Path(path).suffix.lower()
        if ext not in ALL_MEDIA_EXTS:
            self.file_info_label.setText(f"不支持的格式: {ext}")
            return
        self._filepath = path
        name = Path(path).name
        try:
            size_mb = os.path.getsize(path) / (1024 * 1024)
        except OSError:
            size_mb = 0
        icon = self._get_type_icon(ext)
        self._type_icon.setText(icon)
        self._type_icon.show()
        self.drop_label.setText(f"已选择: {name}")
        self._set_drop_state("selected")
        self.file_info_label.setText(f"大小: {size_mb:.1f} MB")
        self.btn_info.show()
        self.btn_clear.show()
        self.file_selected.emit(path)

    @property
    def filepath(self) -> str:
        return self._filepath

    def clear(self):
        if not self._filepath:
            return
        self._filepath = None
        self._type_icon.hide()
        self._reset_drop_style()
        self.drop_label.setText("▽ 拖入文件到此处\n或点击下方按钮选择")
        self.file_info_label.setText("")
        self.btn_info.hide()
        self.btn_clear.hide()
        self.file_selected.emit('')

    def set_file_info(self, info: dict):
        if not info.get('valid'):
            return
        parts = []
        if info.get('codec'):
            parts.append(f"编码: {info['codec']}")
        w, h = info.get('width', 0), info.get('height', 0)
        if w and h:
            res_desc = ''
            if w >= 3840: res_desc = ' (4K)'
            elif w >= 1920: res_desc = ' (1080p)'
            elif w >= 1280: res_desc = ' (720p)'
            parts.append(f"分辨率: {w}×{h}{res_desc}")
        fps = info.get('fps', 0)
        if fps:
            parts.append(f"帧率: {fps} FPS")
        dur = info.get('duration', 0)
        if dur:
            if dur < 60:
                parts.append(f"时长: {int(dur)}秒")
            elif dur < 3600:
                parts.append(f"时长: {int(dur//60)}:{int(dur%60):02d}")
            else:
                parts.append(f"时长: {int(dur//3600)}:{int((dur%3600)//60):02d}:{int(dur%60):02d}")
        size_mb = info.get('size_mb', 0)
        if size_mb:
            if size_mb < 1024:
                parts.append(f"大小: {size_mb:.1f} MB")
            else:
                parts.append(f"大小: {size_mb/1024:.2f} GB")
        self.file_info_label.setText("  |  ".join(parts))
