import os
from pathlib import Path
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget, QFileDialog, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent

from core.constants import ALL_MEDIA_EXTS


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

        self.drop_label = QLabel("拖入文件到此处，或点击下方按钮选择")
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_label.setObjectName("dropLabel")
        self.drop_label.setMinimumHeight(80)

        btn_layout = QHBoxLayout()
        self.btn_file = QPushButton("选择文件")
        self.btn_file.clicked.connect(self._select_file)
        self.btn_info = QPushButton("信息")
        self.btn_info.clicked.connect(self._request_info)
        self.btn_info.hide()
        self.btn_clear = QPushButton("清除")
        self.btn_clear.clicked.connect(self.clear)
        self.btn_clear.hide()
        btn_layout.addWidget(self.btn_file)
        btn_layout.addWidget(self.btn_info)
        btn_layout.addWidget(self.btn_clear)
        btn_layout.addStretch()

        self.file_info_label = QLabel("")
        self.file_info_label.setObjectName("fileInfo")
        self.file_info_label.setWordWrap(True)

        layout.addWidget(self.drop_label)
        layout.addLayout(btn_layout)
        layout.addWidget(self.file_info_label)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                path = url.toLocalFile()
                if path and Path(path).suffix.lower() in ALL_MEDIA_EXTS:
                    event.acceptProposedAction()
                    return
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            self.set_file(path)

    def _select_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择媒体文件",
            filter="媒体文件 (*.mp4 *.avi *.mkv *.mov *.webm *.wmv *.flv *.m4v *.jpg *.jpeg *.png *.bmp *.webp *.gif *.tiff *.mp3 *.wav *.aac *.flac *.ogg *.m4a *.wma);;所有文件 (*.*)"
        )
        if path:
            self.set_file(path)

    def _request_info(self):
        if self._filepath:
            self.info_requested.emit(self._filepath)

    def set_file(self, path: str):
        if not os.path.isfile(path):
            return
        ext = Path(path).suffix.lower()
        if ext not in ALL_MEDIA_EXTS:
            self.file_info_label.setText(f"不支持的格式: {ext}")
            return
        self._filepath = path
        name = Path(path).name
        size_mb = os.path.getsize(path) / (1024 * 1024)
        self.drop_label.setText(f"已选择: {name}")
        self.file_info_label.setText(f"大小: {size_mb:.1f} MB")
        self.btn_info.show()
        self.btn_clear.show()
        self.file_selected.emit(path)

    @property
    def filepath(self) -> str:
        return self._filepath

    def clear(self):
        self._filepath = None
        self.drop_label.setText("拖入文件到此处，或点击下方按钮选择")
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
