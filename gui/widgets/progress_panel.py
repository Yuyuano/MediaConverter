from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QProgressBar, QPlainTextEdit, QPushButton, QLabel
from PyQt6.QtCore import pyqtSignal, Qt


class ProgressPanel(QWidget):
    cancel_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        progress_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.label_eta = QLabel("")
        self.label_eta.setStyleSheet("color: #a6e3a1; font-size: 12px;")
        self.label_eta.setMinimumWidth(120)
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_requested.emit)
        self.btn_cancel.setFixedWidth(60)
        progress_row.addWidget(self.progress_bar, 1)
        progress_row.addWidget(self.label_eta)
        progress_row.addWidget(self.btn_cancel)
        layout.addLayout(progress_row)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(150)
        self.log_view.setPlaceholderText("转换日志将显示在这里...")
        layout.addWidget(self.log_view)

    def set_converting(self, converting: bool):
        self.btn_cancel.setEnabled(converting)
        if converting:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 100)

    def set_progress(self, value: int):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(value)

    def set_progress_pct(self, pct: int):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(pct)

    def append_log(self, level: str, message: str):
        prefix = {'info': '[+]', 'error': '[!]', 'warning': '[*]'}.get(level, '[*]')
        self.log_view.appendPlainText(f"{prefix} {message}")
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def append_progress(self, message: str):
        doc = self.log_view.document()
        block = doc.lastBlock()
        text = block.text()
        if text.startswith("  frame=") or text.startswith("  [进度]"):
            cursor = self.log_view.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            cursor.select(cursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.insertText(f"  [进度] {message}")
        else:
            self.log_view.appendPlainText(f"  [进度] {message}")
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def set_eta(self, eta_text: str):
        self.label_eta.setText(eta_text)

    def clear(self):
        self.progress_bar.setValue(0)
        self.log_view.clear()
        self.label_eta.setText('')
