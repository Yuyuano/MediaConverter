import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QMessageBox, QFrame, QFormLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from pathlib import Path

from gui.workers.thumbnail_worker import ThumbnailWorker
from gui.workers.info_worker import InfoWorker

logger = logging.getLogger('MediaConverter')


class InfoDialog(QDialog):
    def __init__(self, converter, filepath: str, parent=None):
        super().__init__(parent)
        self._converter = converter
        self._filepath = filepath
        self._info = {}
        self._info_worker = None
        self._thumb_worker = None
        self._init_ui()
        self._load_info()

    def _init_ui(self):
        self.setWindowTitle("媒体信息")
        self.setMinimumSize(520, 340)
        self.resize(560, 380)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        top = QHBoxLayout()
        top.setSpacing(16)

        thumb_card = QFrame()
        thumb_card.setObjectName("card")
        thumb_card.setFixedSize(220, 140)
        thumb_layout = QVBoxLayout(thumb_card)
        thumb_layout.setContentsMargins(4, 4, 4, 4)
        self.thumb_label = QLabel()
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb_layout.addWidget(self.thumb_label)
        top.addWidget(thumb_card)

        info_card = QFrame()
        info_card.setObjectName("card")
        info_card_layout = QVBoxLayout(info_card)
        info_card_layout.setContentsMargins(14, 12, 14, 12)
        self.form_layout = QFormLayout()
        self.form_layout.setSpacing(6)
        self.form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        info_card_layout.addLayout(self.form_layout)
        top.addWidget(info_card, 1)
        layout.addLayout(top)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_txt = QPushButton("导出 TXT")
        self.btn_txt.setFixedHeight(30)
        self.btn_txt.clicked.connect(lambda: self._export('txt'))
        self.btn_json = QPushButton("导出 JSON")
        self.btn_json.setFixedHeight(30)
        self.btn_json.clicked.connect(lambda: self._export('json'))
        btn_close = QPushButton("关闭")
        btn_close.setFixedHeight(30)
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_txt)
        btn_row.addWidget(self.btn_json)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    def _add_field(self, label: str, value: str):
        lbl = QLabel(label)
        lbl.setObjectName("dialogHint")
        val = QLabel(value)
        val.setObjectName("dialogValue")
        self.form_layout.addRow(lbl, val)

    def _load_info(self):
        self._info_worker = InfoWorker(self._converter, self._filepath)
        self._info_worker.info_ready.connect(self._on_info_ready)
        self._info_worker.finished.connect(self._info_worker.deleteLater)
        self._info_worker.start()

    def _on_info_ready(self, filepath: str, info: dict):
        self._info_worker = None
        self._info = info
        if not self._info or not self._info.get('valid'):
            self.form_layout.addRow(QLabel("无法读取文件信息"))
            self.btn_txt.setEnabled(False)
            self.btn_json.setEnabled(False)
            return

        self._add_field("文件名", Path(self._filepath).name)
        self._add_field("大小", f"{self._info.get('size_mb', 0):.2f} MB")
        self._add_field("格式", self._info.get('format_name', 'unknown'))
        self._add_field("编码", self._info.get('codec', 'unknown'))
        self._add_field("分辨率", f"{self._info.get('width', 0)}×{self._info.get('height', 0)}")

        fps = self._info.get('fps', 0)
        if fps:
            self._add_field("帧率", f"{fps:.2f} fps")

        dur = self._info.get('duration', 0)
        if dur:
            hrs, rem = divmod(int(dur), 3600)
            mins, secs = divmod(rem, 60)
            self._add_field("时长", f"{hrs}:{mins:02d}:{secs:02d}")

        br = self._info.get('bitrate', 0)
        if br:
            self._add_field("比特率", f"{br/1000:.0f} kbps")

        self._load_thumbnail()

    def _load_thumbnail(self):
        self._thumb_worker = ThumbnailWorker(self._converter, self._filepath)
        self._thumb_worker.thumb_ready.connect(self._on_thumb_ready)
        self._thumb_worker.finished.connect(self._thumb_worker.deleteLater)
        self._thumb_worker.start()

    def closeEvent(self, event):
        # 绝不 terminate()（可能残留锁/悬挂状态）：先断开信号再请求中断，
        # 超时未退出的 worker 保留引用转后台，等它自然跑完（ffprobe 自带超时）。
        for attr in ('_info_worker', '_thumb_worker'):
            worker = getattr(self, attr, None)
            self._shutdown_worker(worker, attr.lstrip('_'))
            setattr(self, attr, None)
        event.accept()

    def _shutdown_worker(self, worker, name: str):
        if worker is None:
            return
        try:
            for sig in ('info_ready', 'thumb_ready'):
                try:
                    getattr(worker, sig).disconnect()
                except (TypeError, RuntimeError):
                    pass
            if worker.isRunning():
                worker.requestInterruption()
                if not worker.wait(2000):
                    logger.warning(f"{name} 未在 2s 内退出，转后台等待完成")
                    worker.finished.connect(worker.deleteLater)
                else:
                    worker.deleteLater()
            else:
                worker.deleteLater()
        except RuntimeError:
            pass

    def _on_thumb_ready(self, thumb_path: str):
        pixmap = QPixmap(thumb_path)
        if not pixmap.isNull():
            self.thumb_label.setPixmap(pixmap.scaled(
                210, 130, Qt.AspectRatioMode.KeepAspectRatio,
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
