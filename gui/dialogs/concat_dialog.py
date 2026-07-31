from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QListWidgetItem, QFileDialog, QLabel, QMessageBox,
    QCheckBox, QLineEdit
)
from PyQt6.QtCore import Qt
from pathlib import Path

from core.constants import VIDEO_EXTS
from gui.widgets.progress_panel import ProgressPanel
from gui.workers.concat_worker import ConcatWorker


class ConcatDialog(QDialog):
    def __init__(self, converter, parent=None):
        super().__init__(parent)
        self.setWindowTitle("视频拼接")
        self.setMinimumSize(640, 520)
        self._converter = converter
        self._worker = None
        self._pending_worker = None
        self._cancelled = False
        self._init_ui()
        self.progress_panel.cancel_requested.connect(self._cancel_concat)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        header = QLabel("添加视频文件并调整顺序（拖拽排序）:")
        header.setObjectName("dialogHeader")
        layout.addWidget(header)

        self.list_files = QListWidget()
        self.list_files.setAlternatingRowColors(True)
        self.list_files.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.list_files.setDefaultDropAction(Qt.DropAction.MoveAction)
        layout.addWidget(self.list_files, 1)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ 添加文件")
        btn_add.clicked.connect(self._add_files)
        btn_remove = QPushButton("移除选中")
        btn_remove.clicked.connect(self._remove_selected)
        btn_up = QPushButton("▲ 上移")
        btn_up.clicked.connect(self._move_up)
        btn_down = QPushButton("▼ 下移")
        btn_down.clicked.connect(self._move_down)
        btn_clear = QPushButton("清空")
        btn_clear.clicked.connect(self._clear_list)
        for b in (btn_add, btn_remove, btn_up, btn_down, btn_clear):
            b.setFixedHeight(30)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_remove)
        btn_row.addWidget(btn_up)
        btn_row.addWidget(btn_down)
        btn_row.addWidget(btn_clear)
        layout.addLayout(btn_row)

        output_row = QHBoxLayout()
        output_row.addWidget(QLabel("输出文件:"))
        self.edit_output = QLineEdit()
        self.edit_output.setPlaceholderText("选择输出路径...")
        self.edit_output.setReadOnly(True)
        self.edit_output.setMinimumHeight(30)
        output_row.addWidget(self.edit_output, 1)
        btn_output = QPushButton("浏览...")
        btn_output.setFixedHeight(30)
        btn_output.clicked.connect(self._browse_output)
        output_row.addWidget(btn_output)
        layout.addLayout(output_row)

        opts_row = QHBoxLayout()
        self.chk_stream_copy = QCheckBox("流复制（无损，推荐）")
        self.chk_stream_copy.setChecked(True)
        opts_row.addWidget(self.chk_stream_copy)
        opts_row.addStretch(1)

        self.btn_start = QPushButton("开始拼接")
        self.btn_start.setObjectName("convertBtn")
        self.btn_start.setFixedHeight(36)
        self.btn_start.clicked.connect(self._start_concat)
        self.btn_start.setEnabled(False)
        opts_row.addWidget(self.btn_start)

        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setFixedHeight(36)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel_concat)
        opts_row.addWidget(self.btn_cancel)
        layout.addLayout(opts_row)

        self.progress_panel = ProgressPanel()
        self.progress_panel.setMaximumHeight(180)
        self.progress_panel.hide()
        layout.addWidget(self.progress_panel)

        self.list_files.model().rowsInserted.connect(self._update_btn_state)
        self.list_files.model().rowsRemoved.connect(self._update_btn_state)

    def _clear_list(self):
        self.list_files.clear()

    def _update_btn_state(self):
        self.btn_start.setEnabled(
            self.list_files.count() >= 2 and bool(self.edit_output.text()) and not self._worker
        )

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择视频文件", "",
            f"视频文件 ({' '.join(f'*{e}' for e in sorted(VIDEO_EXTS))})"
        )
        seen = {self.list_files.item(i).toolTip() for i in range(self.list_files.count())}
        for f in files:
            if f not in seen:
                seen.add(f)
                item = QListWidgetItem(Path(f).name)
                item.setToolTip(f)
                self.list_files.addItem(item)

    def _remove_selected(self):
        for item in self.list_files.selectedItems():
            self.list_files.takeItem(self.list_files.row(item))

    def _move_up(self):
        row = self.list_files.currentRow()
        if row > 0:
            item = self.list_files.takeItem(row)
            self.list_files.insertItem(row - 1, item)
            self.list_files.setCurrentRow(row - 1)

    def _move_down(self):
        row = self.list_files.currentRow()
        if row >= 0 and row < self.list_files.count() - 1:
            item = self.list_files.takeItem(row)
            self.list_files.insertItem(row + 1, item)
            self.list_files.setCurrentRow(row + 1)

    def _browse_output(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "保存拼接视频", "", "视频文件 (*.mp4);;所有文件 (*.*)"
        )
        if path:
            self.edit_output.setText(path)
            self._update_btn_state()

    def _get_input_files(self):
        return [self.list_files.item(i).toolTip() for i in range(self.list_files.count())]

    def _start_concat(self):
        inputs = self._get_input_files()
        output = self.edit_output.text()
        if len(inputs) < 2:
            QMessageBox.warning(self, "提示", "请至少添加 2 个视频文件")
            return
        if not output:
            QMessageBox.warning(self, "提示", "请选择输出路径")
            return

        converter = self._converter
        self._worker = ConcatWorker(converter, inputs, output, self.chk_stream_copy.isChecked())
        self._worker.finished.connect(self._on_concat_done)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.log.connect(self.progress_panel.append_log)
        self._worker.progress.connect(self.progress_panel.append_progress)
        self._worker.progress_pct.connect(self.progress_panel.set_progress_pct)
        self._worker.eta.connect(self.progress_panel.set_eta)

        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.list_files.setEnabled(False)
        self.progress_panel.clear()
        self.progress_panel.set_converting(True)
        self.progress_panel.show()

        self._worker.start()

    def _cancel_concat(self):
        if self._worker:
            self._cancelled = True
            self._worker.requestInterruption()
            self._worker.cancel()
            if not self._worker.wait(10000):
                return
            self._worker = None
            self.btn_start.setEnabled(True)
            self.btn_cancel.setEnabled(False)
            self.list_files.setEnabled(True)
            self.progress_panel.set_converting(False)

    def _on_concat_done(self, success: bool, output_path: str):
        if getattr(self, '_cancelled', False):
            self._cancelled = False
            self._worker = None
            return
        if success:
            self.progress_panel.set_progress(100)
            QMessageBox.information(self, "完成", f"拼接完成!\n输出: {output_path}")
        else:
            QMessageBox.critical(self, "失败", "拼接失败，请检查日志")
        self._worker = None
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.list_files.setEnabled(True)
        self.progress_panel.set_converting(False)

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._cancelled = True
            try:
                self._worker.log.disconnect()
                self._worker.progress.disconnect()
                self._worker.progress_pct.disconnect()
                self._worker.eta.disconnect()
                self._worker.finished.disconnect()
            except (TypeError, RuntimeError):
                pass
            self._worker.requestInterruption()
            self._worker.cancel()
            if not self._worker.wait(10000):
                self._pending_worker = self._worker
                self._worker.finished.connect(self._pending_worker.deleteLater)
        self._worker = None
        event.accept()
