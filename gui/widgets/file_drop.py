import os
from pathlib import Path
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget, QFileDialog, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent


class FileDropWidget(QWidget):
    """文件拖拽区域"""
    file_selected = pyqtSignal(str)  # 文件路径

    VIDEO_EXTS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.ts', '.m2ts'}
    IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.tiff', '.tif', '.ico'}
    AUDIO_EXTS = {'.mp3', '.wav', '.aac', '.flac', '.ogg', '.m4a', '.wma'}
    ALL_EXTS = VIDEO_EXTS | IMAGE_EXTS | AUDIO_EXTS

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
        btn_layout.addWidget(self.btn_file)

        self.file_info_label = QLabel("")
        self.file_info_label.setObjectName("fileInfo")
        self.file_info_label.setWordWrap(True)

        layout.addWidget(self.drop_label)
        layout.addLayout(btn_layout)
        layout.addWidget(self.file_info_label)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            self._set_file(path)

    def _select_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择媒体文件")
        if path:
            self._set_file(path)

    def _set_file(self, path: str):
        if not os.path.isfile(path):
            return
        ext = Path(path).suffix.lower()
        if ext not in self.ALL_EXTS:
            self.file_info_label.setText(f"不支持的格式: {ext}")
            return
        self._filepath = path
        name = Path(path).name
        size_mb = os.path.getsize(path) / (1024 * 1024)
        self.drop_label.setText(f"已选择: {name}")
        self.file_info_label.setText(f"大小: {size_mb:.1f} MB")
        self.file_selected.emit(path)

    @property
    def filepath(self) -> str:
        return self._filepath

    def clear(self):
        self._filepath = None
        self.drop_label.setText("拖入文件到此处，或点击下方按钮选择")
        self.file_info_label.setText("")

    def set_file_info(self, info: dict):
        """更新文件详细信息（由主窗口调用）"""
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
