from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel, QVBoxLayout
from PyQt6.QtCore import pyqtSignal, Qt


class FormatSelector(QWidget):
    format_changed = pyqtSignal(str, str)

    VIDEO_FORMATS = ['MP4', 'AVI', 'MKV', 'MOV', 'WEBM', 'GIF']
    IMAGE_FORMATS = ['JPG', 'PNG', 'WEBP', 'BMP']
    AUDIO_FORMATS = ['MP3', 'WAV', 'AAC', 'FLAC', 'OGG', 'WMA', 'M4A']

    def __init__(self, media_type: str = None):
        super().__init__()
        self._media_type = media_type
        self._selected = None
        self._selected_btn = None
        self._buttons = {}
        self._init_ui()

    def _build_section(self, label: str, formats: list, prefix: str):
        section_label = QLabel(label)
        section_label.setObjectName("sectionLabel")
        row = QHBoxLayout()
        row.setSpacing(8)
        for fmt in formats:
            btn = QPushButton(fmt)
            btn.setCheckable(True)
            btn.setFixedHeight(32)
            btn.setMinimumWidth(58)
            btn.setObjectName("formatChip")
            btn.clicked.connect(lambda checked, b=btn: self._on_click(b))
            self._buttons[f'{prefix}_{fmt}'] = btn
            row.addWidget(btn)
        row.addStretch()
        return section_label, row

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)

        mt = self._media_type
        if mt is None or mt == 'video':
            label, row = self._build_section("视频格式", self.VIDEO_FORMATS, 'video')
            main_layout.addWidget(label)
            main_layout.addLayout(row)
        if mt is None or mt == 'image':
            label, row = self._build_section("图片格式", self.IMAGE_FORMATS, 'image')
            main_layout.addWidget(label)
            main_layout.addLayout(row)
        if mt is None or mt == 'audio':
            label, row = self._build_section("音频格式", self.AUDIO_FORMATS, 'audio')
            main_layout.addWidget(label)
            main_layout.addLayout(row)

    def _on_click(self, btn):
        fmt, media_type = self._resolve_btn(btn)
        if fmt is None:
            return
        if btn is self._selected_btn:
            self._selected_btn = None
            self._selected = None
            btn.setChecked(False)
            self.format_changed.emit('', '')
            return
        self._selected_btn = btn
        self._selected = (fmt, media_type)
        for key, b in self._buttons.items():
            if b is not btn and b.isChecked():
                b.setChecked(False)
        self.format_changed.emit(fmt.lower(), media_type)

    def _resolve_btn(self, btn) -> tuple:
        for key, b in self._buttons.items():
            if b is btn:
                media_type, _, fmt = key.partition('_')
                return fmt, media_type
        return None, None

    @property
    def selected_format(self):
        return self._selected

    def select_format(self, fmt: str):
        fmt_upper = fmt.upper()
        prefixes = [('video', 'video'), ('image', 'image'), ('audio', 'audio')]
        if self._media_type:
            prefixes = [(self._media_type, self._media_type)]
        for key, media_type in prefixes:
            btn_key = f'{media_type}_{fmt_upper}'
            if btn_key in self._buttons:
                btn = self._buttons[btn_key]
                if btn is self._selected_btn:
                    return
                btn.click()
                return

    def clear_selection(self):
        if not self._selected_btn:
            return
        self._selected = None
        self._selected_btn = None
        for btn in self._buttons.values():
            btn.setChecked(False)
        self.format_changed.emit('', '')
