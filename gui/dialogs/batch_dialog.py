import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QComboBox, QSpinBox, QGroupBox, QMessageBox, QProgressBar,
    QAbstractItemView, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QDragEnterEvent, QDropEvent

from core.options import ConvertOptions
from core.converter import MediaConverter
from core.queue import ConversionQueue


class _BatchWorker(QThread):
    task_done = pyqtSignal(int, bool)
    all_done = pyqtSignal(int, int)
    log = pyqtSignal(str)

    def __init__(self, converter, tasks, max_workers):
        super().__init__()
        self.converter = converter
        self.tasks = tasks
        self.max_workers = max_workers
        self._queue = None

    def run(self):
        self.converter._on_log = lambda lvl, msg: self.log.emit(msg)
        self.converter._on_progress = lambda msg: None

        self._queue = ConversionQueue(
            self.converter, self.max_workers,
            on_task_done=lambda task, success: self.task_done.emit(task.id, success),
            on_all_done=lambda sc, t: self.all_done.emit(sc, t)
        )
        for inp, out, opts in self.tasks:
            self._queue.add_task(inp, out, opts)
        self._queue.process()

    def cancel(self):
        if self._queue:
            self._queue.cancel()


class BatchDialog(QDialog):
    """批量转换对话框"""

    VIDEO_EXTS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.ts', '.m2ts'}
    IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.tiff', '.tif', '.ico'}
    AUDIO_EXTS = {'.mp3', '.wav', '.aac', '.flac', '.ogg', '.m4a', '.wma'}
    ALL_EXTS = VIDEO_EXTS | IMAGE_EXTS | AUDIO_EXTS

    def __init__(self, converter: MediaConverter, parent=None):
        super().__init__(parent)
        self._converter = converter
        self._files = []
        self._worker = None
        self.setWindowTitle("批量转换")
        self.setMinimumSize(700, 500)
        self.resize(800, 600)
        self.setAcceptDrops(True)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # ── 文件列表 ──
        file_group = QGroupBox("文件列表 (拖入文件或点击添加)")
        file_layout = QVBoxLayout(file_group)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["文件名", "路径", "状态"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        file_layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("添加文件")
        self.btn_add.clicked.connect(self._add_files)
        self.btn_add_folder = QPushButton("添加文件夹")
        self.btn_add_folder.clicked.connect(self._add_folder)
        self.btn_remove = QPushButton("移除选中")
        self.btn_remove.clicked.connect(self._remove_selected)
        self.btn_clear = QPushButton("清空")
        self.btn_clear.clicked.connect(self._clear_all)
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_add_folder)
        btn_row.addWidget(self.btn_remove)
        btn_row.addWidget(self.btn_clear)
        btn_row.addStretch()
        self.label_count = QLabel("0 个文件")
        btn_row.addWidget(self.label_count)
        file_layout.addLayout(btn_row)
        layout.addWidget(file_group)

        # ── 转换设置 ──
        settings_group = QGroupBox("转换设置")
        settings_layout = QHBoxLayout(settings_group)

        settings_layout.addWidget(QLabel("输出格式:"))
        self.combo_format = QComboBox()
        self.combo_format.addItems(["mp4", "avi", "mkv", "mov", "webm", "jpg", "png", "webp", "mp3"])
        settings_layout.addWidget(self.combo_format)

        settings_layout.addWidget(QLabel("并发数:"))
        self.spin_workers = QSpinBox()
        self.spin_workers.setRange(1, 4)
        self.spin_workers.setValue(2)
        settings_layout.addWidget(self.spin_workers)

        self.check_gpu = QCheckBox("GPU 加速")
        self.check_gpu.setEnabled(bool(self._converter.gpu_type))
        settings_layout.addWidget(self.check_gpu)
        settings_layout.addStretch()

        layout.addWidget(settings_group)

        # ── 进度 ──
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.label_status = QLabel("就绪")
        layout.addWidget(self.label_status)

        # ── 操作按钮 ──
        action_row = QHBoxLayout()
        self.btn_start = QPushButton("开始批量转换")
        self.btn_start.setObjectName("convertBtn")
        self.btn_start.setFixedHeight(36)
        self.btn_start.clicked.connect(self._start_batch)
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setFixedHeight(36)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel_batch)
        self.btn_close = QPushButton("关闭")
        self.btn_close.setFixedHeight(36)
        self.btn_close.clicked.connect(self.close)
        action_row.addStretch()
        action_row.addWidget(self.btn_start)
        action_row.addWidget(self.btn_cancel)
        action_row.addWidget(self.btn_close)
        layout.addLayout(action_row)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        paths = [u.toLocalFile() for u in event.mimeData().urls()]
        self._add_paths(paths)

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择文件")
        if files:
            self._add_paths(files)

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder:
            paths = []
            for f in Path(folder).iterdir():
                if f.is_file() and f.suffix.lower() in self.ALL_EXTS:
                    paths.append(str(f))
            self._add_paths(paths)

    def _add_paths(self, paths):
        for p in paths:
            if not os.path.isfile(p):
                continue
            ext = Path(p).suffix.lower()
            if ext not in self.ALL_EXTS:
                continue
            if p in self._files:
                continue
            self._files.append(p)
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(Path(p).name))
            self.table.setItem(row, 1, QTableWidgetItem(p))
            self.table.setItem(row, 2, QTableWidgetItem("等待中"))
        self.label_count.setText(f"{len(self._files)} 个文件")

    def _remove_selected(self):
        rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()), reverse=True)
        for row in rows:
            self.table.removeRow(row)
            if row < len(self._files):
                self._files.pop(row)
        self.label_count.setText(f"{len(self._files)} 个文件")

    def _clear_all(self):
        self.table.setRowCount(0)
        self._files.clear()
        self.label_count.setText("0 个文件")

    def _start_batch(self):
        if not self._files:
            QMessageBox.warning(self, "提示", "请先添加文件")
            return
        fmt = self.combo_format.currentText()
        media_type = 'video' if fmt in ['mp4', 'avi', 'mkv', 'mov', 'webm'] else \
                     'image' if fmt in ['jpg', 'png', 'webp'] else 'audio'
        default_opts = self._converter.get_default_opts(fmt, media_type)
        default_opts.use_gpu = self.check_gpu.isChecked() and bool(self._converter.gpu_type)

        tasks = []
        for f in self._files:
            p = Path(f)
            output = str(p.parent / f"{p.stem}_converted.{fmt}")
            tasks.append((f, output, default_opts))

        self.progress_bar.setRange(0, 0)
        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.label_status.setText("转换中...")

        self._worker = _BatchWorker(
            self._converter, tasks, self.spin_workers.value()
        )
        self._worker.task_done.connect(self._on_task_done)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.log.connect(lambda msg: None)
        self._worker.start()

    def _on_task_done(self, task_id, success):
        row = task_id - 1
        if 0 <= row < self.table.rowCount():
            status = "成功" if success else "失败"
            self.table.setItem(row, 2, QTableWidgetItem(status))
        done = sum(1 for i in range(self.table.rowCount())
                   if self.table.item(i, 2) and self.table.item(i, 2).text() in ("成功", "失败"))
        total = self.table.rowCount()
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(done)
        self.label_status.setText(f"进度: {done}/{total}")

    def _on_all_done(self, success_count, total):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.label_status.setText(f"完成: {success_count}/{total} 成功")

    def _cancel_batch(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self.label_status.setText("已取消")
            self.btn_start.setEnabled(True)
            self.btn_cancel.setEnabled(False)

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(2000)
        event.accept()
