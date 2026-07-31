from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QProgressBar, QTextEdit, QPushButton, QLabel
from PyQt6.QtCore import pyqtSignal, Qt, QPropertyAnimation, QEasingCurve

from gui.theme import format_log_html


class ProgressPanel(QWidget):
    cancel_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        progress_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.label_eta = QLabel("")
        self.label_eta.setObjectName("etaLabel")
        self.label_eta.setMinimumWidth(120)
        self.label_eta.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.btn_cancel = QPushButton("✕ 取消")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setFixedSize(70, 28)
        self.btn_cancel.clicked.connect(self.cancel_requested.emit)
        progress_row.addWidget(self.progress_bar, 1)
        progress_row.addWidget(self.label_eta)
        progress_row.addSpacing(4)
        progress_row.addWidget(self.btn_cancel)
        layout.addLayout(progress_row)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(200)
        self.log_view.setPlaceholderText("选择文件并开始转换，日志将显示在这里...")
        layout.addWidget(self.log_view)

        self._anim = None

    def set_converting(self, converting: bool):
        self.btn_cancel.setEnabled(converting)
        if converting:
            self.progress_bar.setValue(0)
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 100)

    def set_progress(self, value: int):
        self._animate_progress(value)

    def set_progress_pct(self, pct: int):
        self._animate_progress(pct)

    def _animate_progress(self, target: int):
        if self._anim:
            try:
                if self._anim.state() == QPropertyAnimation.State.Running:
                    self._anim.stop()
            except RuntimeError:
                pass
            try:
                self._anim.deleteLater()
            except RuntimeError:
                pass
            self._anim = None
        anim = QPropertyAnimation(self.progress_bar, b"value")
        anim.setDuration(300)
        anim.setStartValue(self.progress_bar.value())
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.progress_bar.setRange(0, 100)
        anim.finished.connect(lambda a=anim: self._on_anim_finished(a))
        anim.start()
        self._anim = anim

    def _on_anim_finished(self, anim):
        try:
            anim.deleteLater()
        except RuntimeError:
            pass
        if self._anim is anim:
            self._anim = None

    def _append_html(self, html: str):
        cursor = self.log_view.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertHtml(html)
        cursor.insertBlock()
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def append_log(self, level: str, message: str):
        self._append_html(format_log_html(level, message))

    def append_progress(self, message: str):
        doc = self.log_view.document()
        block = doc.lastBlock()
        text = block.text()
        if text.startswith("  frame=") or "  ●" in text or "  [进度]" in text:
            cursor = self.log_view.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            cursor.select(cursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.insertHtml(f'  <span style="color:#a6adc8">{message}</span>')
        else:
            self._append_html(f'  <span style="color:#a6adc8">{message}</span>')

    def set_eta(self, eta_text: str):
        self.label_eta.setText(eta_text)

    def clear(self):
        if self._anim:
            try:
                if self._anim.state() == QPropertyAnimation.State.Running:
                    self._anim.stop()
            except RuntimeError:
                pass
            try:
                self._anim.deleteLater()
            except RuntimeError:
                pass
            self._anim = None
        self.progress_bar.setValue(0)
        self.log_view.clear()
        self.label_eta.setText('')
