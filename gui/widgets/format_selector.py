from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QButtonGroup, QLabel, QVBoxLayout
from PyQt6.QtCore import pyqtSignal, Qt


class FormatSelector(QWidget):
    """格式选择卡片"""
    format_changed = pyqtSignal(str, str)  # format_name, media_type

    VIDEO_FORMATS = ['MP4', 'AVI', 'MKV', 'MOV', 'WEBM', 'GIF']
    IMAGE_FORMATS = ['JPG', 'PNG', 'WEBP', 'BMP']
    AUDIO_FORMATS = ['MP3']

    def __init__(self):
        super().__init__()
        self._selected = None
        self._buttons = {}
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # 视频格式
        video_label = QLabel("视频格式")
        video_label.setObjectName("sectionLabel")
        video_row = QHBoxLayout()
        video_row.setSpacing(6)
        self._video_group = QButtonGroup(self)
        self._video_group.setExclusive(True)
        for fmt in self.VIDEO_FORMATS:
            btn = QPushButton(fmt)
            btn.setCheckable(True)
            btn.setFixedHeight(32)
            btn.setMinimumWidth(60)
            btn.setObjectName("formatBtn")
            btn.clicked.connect(lambda checked, f=fmt: self._on_click(f, 'video'))
            self._video_group.addButton(btn)
            self._buttons[f'video_{fmt}'] = btn
            video_row.addWidget(btn)
        video_row.addStretch()

        # 图片格式
        image_label = QLabel("图片格式")
        image_label.setObjectName("sectionLabel")
        image_row = QHBoxLayout()
        image_row.setSpacing(6)
        self._image_group = QButtonGroup(self)
        self._image_group.setExclusive(True)
        for fmt in self.IMAGE_FORMATS:
            btn = QPushButton(fmt)
            btn.setCheckable(True)
            btn.setFixedHeight(32)
            btn.setMinimumWidth(60)
            btn.setObjectName("formatBtn")
            btn.clicked.connect(lambda checked, f=fmt: self._on_click(f, 'image'))
            self._image_group.addButton(btn)
            self._buttons[f'image_{fmt}'] = btn
            image_row.addWidget(btn)
        image_row.addStretch()

        # 音频格式
        audio_label = QLabel("音频格式")
        audio_label.setObjectName("sectionLabel")
        audio_row = QHBoxLayout()
        audio_row.setSpacing(6)
        self._audio_group = QButtonGroup(self)
        self._audio_group.setExclusive(True)
        for fmt in self.AUDIO_FORMATS:
            btn = QPushButton(fmt)
            btn.setCheckable(True)
            btn.setFixedHeight(32)
            btn.setMinimumWidth(60)
            btn.setObjectName("formatBtn")
            btn.clicked.connect(lambda checked, f=fmt: self._on_click(f, 'audio'))
            self._audio_group.addButton(btn)
            self._buttons[f'audio_{fmt}'] = btn
            audio_row.addWidget(btn)
        audio_row.addStretch()

        main_layout.addWidget(video_label)
        main_layout.addLayout(video_row)
        main_layout.addWidget(image_label)
        main_layout.addLayout(image_row)
        main_layout.addWidget(audio_label)
        main_layout.addLayout(audio_row)

    def _on_click(self, fmt: str, media_type: str):
        self._selected = (fmt, media_type)
        # 取消其他组的选中
        for key, btn in self._buttons.items():
            if not key.startswith(f'{media_type}_'):
                btn.setChecked(False)
        self.format_changed.emit(fmt.lower(), media_type)

    @property
    def selected_format(self):
        return self._selected

    def clear_selection(self):
        self._selected = None
        for btn in self._buttons.values():
            btn.setChecked(False)
