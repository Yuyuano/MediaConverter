from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap
from pathlib import Path


class ThumbnailWorker(QThread):
    thumb_ready = pyqtSignal(str)

    def __init__(self, converter, input_file):
        super().__init__()
        self.converter = converter
        self.input_file = input_file

    def run(self):
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
        tmp.close()
        ok = self.converter.extract_thumbnail(self.input_file, tmp.name, 1.0)
        if ok:
            self.thumb_ready.emit(tmp.name)


class InfoDialog(QDialog):
    def __init__(self, converter, filepath: str, parent=None):
        super().__init__(parent)
        self._converter = converter
        self._filepath = filepath
        self._info = {}
        self._thumb_worker = None
        self._init_ui()
        self._load_info()
        self._load_thumbnail()

    def _init_ui(self):
        self.setWindowTitle("媒体信息")
        self.setMinimumSize(500, 400)

        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(200, 120)
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setStyleSheet("background: #1e1e2e; border: 1px solid #313244;")
        top.addWidget(self.thumb_label)

        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("font-size: 13px;")
        top.addWidget(self.info_label, 1)
        layout.addLayout(top)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_export_txt = QPushButton("导出信息(TXT)")
        btn_export_txt.clicked.connect(lambda: self._export('txt'))
        btn_export_json = QPushButton("导出信息(JSON)")
        btn_export_json.clicked.connect(lambda: self._export('json'))
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_export_txt)
        btn_row.addWidget(btn_export_json)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    def _load_info(self):
        self._info = self._converter.get_file_summary(self._filepath)
        if not self._info or not self._info.get('valid'):
            self.info_label.setText("无法读取文件信息")
            return
        dur = self._info.get('duration', 0)
        dur_str = ''
        if dur:
            hrs, rem = divmod(int(dur), 3600)
            mins, secs = divmod(rem, 60)
            dur_str = f"{hrs}:{mins:02d}:{secs:02d}"
        lines = [
            f"<b>{Path(self._filepath).name}</b>",
            f"大小: {self._info.get('size_mb', 0):.2f} MB",
            f"格式: {self._info.get('format_name', 'unknown')}",
            f"编码: {self._info.get('codec', 'unknown')}",
            f"分辨率: {self._info.get('width', 0)}x{self._info.get('height', 0)}",
        ]
        if self._info.get('fps'):
            lines.append(f"帧率: {self._info['fps']:.2f} fps")
        if dur_str:
            lines.append(f"时长: {dur_str}")
        br = self._info.get('bitrate', 0)
        if br:
            lines.append(f"比特率: {br/1000:.0f} kbps")
        self.info_label.setText('<br>'.join(lines))

    def _load_thumbnail(self):
        self._thumb_worker = ThumbnailWorker(self._converter, self._filepath)
        self._thumb_worker.thumb_ready.connect(self._on_thumb_ready)
        self._thumb_worker.finished.connect(self._thumb_worker.deleteLater)
        self._thumb_worker.start()

    def _on_thumb_ready(self, thumb_path: str):
        pixmap = QPixmap(thumb_path)
        if not pixmap.isNull():
            self.thumb_label.setPixmap(pixmap.scaled(
                200, 120, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            ))
        try:
            Path(thumb_path).unlink(missing_ok=True)
        except OSError:
            pass

    def _export(self, fmt: str):
        exts = {'txt': '*.txt', 'json': '*.json'}
        path, _ = QFileDialog.getSaveFileName(
            self, f"导出文件信息 ({fmt.upper()})",
            Path(self._filepath).stem + f'_info.{fmt}',
            f"{fmt.upper()}文件 ({exts[fmt]})"
        )
        if path:
            if self._converter.export_file_info(self._filepath, path, fmt):
                QMessageBox.information(self, "完成", f"信息已导出到:\n{path}")
            else:
                QMessageBox.warning(self, "失败", "导出失败")
