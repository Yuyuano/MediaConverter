from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QProgressBar, QPlainTextEdit, QPushButton
from PyQt6.QtCore import pyqtSignal, Qt


class ProgressPanel(QWidget):
    """进度条 + 日志面板"""
    cancel_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 进度条
        progress_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_requested.emit)
        self.btn_cancel.setFixedWidth(60)
        progress_row.addWidget(self.progress_bar, 1)
        progress_row.addWidget(self.btn_cancel)
        layout.addLayout(progress_row)

        # 日志
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(150)
        self.log_view.setPlaceholderText("转换日志将显示在这里...")
        layout.addWidget(self.log_view)

    def set_converting(self, converting: bool):
        self.btn_cancel.setEnabled(converting)
        if converting:
            self.progress_bar.setRange(0, 0)  # 不确定进度模式
        else:
            self.progress_bar.setRange(0, 100)

    def set_progress(self, value: int):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(value)

    def append_log(self, level: str, message: str):
        prefix = {'info': '[+]', 'error': '[!]', 'warning': '[*]'}.get(level, '[*]')
        self.log_view.appendPlainText(f"{prefix} {message}")
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def append_progress(self, message: str):
        """显示 ffmpeg 实时进度（不换行，覆盖当前行）"""
        # 简化：直接追加
        self.log_view.appendPlainText(f"  {message}")
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def clear(self):
        self.progress_bar.setValue(0)
        self.log_view.clear()
