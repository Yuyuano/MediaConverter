import os
import copy
import re
from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QComboBox, QSpinBox, QGroupBox, QMessageBox, QProgressBar,
    QAbstractItemView, QCheckBox, QTextEdit, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QDragEnterEvent, QDropEvent

from core.options import ConvertOptions
from core.converter import MediaConverter
from core.constants import ALL_MEDIA_EXTS, VIDEO_EXTS, IMAGE_EXTS, AUDIO_EXTS
from core.validators import validate_output_dir
from gui.theme import format_log_html
from gui.workers.convert_worker import BatchWorker


_VIDEO_FORMATS = ["mp4", "avi", "mkv", "mov", "webm", "wmv", "gif"]
_IMAGE_FORMATS = ["jpg", "png", "webp", "bmp"]
_AUDIO_FORMATS = ["mp3", "wav", "aac", "flac", "ogg", "m4a"]
_FORMATS_BY_TYPE = {'video': _VIDEO_FORMATS, 'image': _IMAGE_FORMATS, 'audio': _AUDIO_FORMATS}

_INVALID_FILENAME_RE = re.compile(r'[<>:"/\\|?*]')


def _input_media_type(ext: str) -> str:
    if ext in VIDEO_EXTS or ext == '.gif':
        return 'video'
    if ext in IMAGE_EXTS:
        return 'image'
    return 'audio'


def _safe_name_part(s: str) -> str:
    """把路径/名称片段清洗为合法、无穿越风险的文件名组件。"""
    s = _INVALID_FILENAME_RE.sub('_', s)
    s = s.replace('..', '_')
    s = s.strip(' ._')
    return s or 'file'


def _unique_path(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return str(p)
    stem, ext = p.stem, p.suffix
    for i in range(1, 10000):
        cand = p.with_name(f"{stem}_{i}{ext}")
        if not cand.exists():
            return str(cand)
    return str(p)


class BatchDialog(QDialog):

    def __init__(self, converter: MediaConverter, parent=None):
        super().__init__(parent)
        self._converter = converter
        self._files = []
        self._worker = None
        self._pending_worker = None
        self._is_running = False
        self._format_combos = []
        self.setWindowTitle("批量转换")
        self.setMinimumSize(720, 520)
        self.resize(800, 620)
        self.setAcceptDrops(True)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        file_group = QGroupBox("文件列表 (拖入文件或点击添加)")
        file_layout = QVBoxLayout(file_group)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["格式", "文件名", "路径", "状态"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 90)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setDefaultSectionSize(36)
        file_layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("+ 添加文件")
        self.btn_add.setFixedHeight(30)
        self.btn_add.clicked.connect(self._add_files)
        self.btn_add_folder = QPushButton("+ 添加文件夹")
        self.btn_add_folder.setFixedHeight(30)
        self.btn_add_folder.clicked.connect(self._add_folder)
        self.btn_remove = QPushButton("移除选中")
        self.btn_remove.setFixedHeight(30)
        self.btn_remove.clicked.connect(self._remove_selected)
        self.btn_clear = QPushButton("清空")
        self.btn_clear.setFixedHeight(30)
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

        settings_group = QGroupBox("转换设置")
        settings_layout = QVBoxLayout(settings_group)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("并发数:"))
        self.spin_workers = QSpinBox()
        self.spin_workers.setRange(1, 4)
        self.spin_workers.setValue(2)
        row1.addWidget(self.spin_workers)

        self.check_gpu = QCheckBox("GPU 加速")
        self.check_gpu.setEnabled(bool(self._converter.gpu_type))
        self._converter_gpu_type = self._converter.gpu_type
        row1.addWidget(self.check_gpu)
        row1.addStretch()
        settings_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("文件名模板:"))
        self.input_template = QLineEdit("{原名}_converted")
        self.input_template.setToolTip(
            "可用变量: {原名} {格式} {序号} {日期} {原路径}"
        )
        self.input_template.setMinimumHeight(30)
        row2.addWidget(self.input_template, 1)

        self.btn_batch_output = QPushButton("输出目录...")
        self.btn_batch_output.setFixedHeight(30)
        self.btn_batch_output.clicked.connect(self._select_batch_output)
        row2.addWidget(self.btn_batch_output)

        self.label_batch_output = QLabel("与源文件同目录")
        self.label_batch_output.setObjectName("dialogHint")
        row2.addWidget(self.label_batch_output, 1)
        settings_layout.addLayout(row2)

        template_btns = QHBoxLayout()
        template_btns.setSpacing(4)
        template_btns.addWidget(QLabel("插入变量:"))
        for var in ["{原名}", "{格式}", "{序号}", "{日期}", "{原路径}"]:
            btn = QPushButton(var)
            btn.setFixedHeight(24)
            btn.setObjectName("varBtn")
            btn.clicked.connect(lambda checked, v=var: self._insert_template_var(v))
            template_btns.addWidget(btn)
        template_btns.addStretch()
        settings_layout.addLayout(template_btns)

        layout.addWidget(settings_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(120)
        self.log_view.setPlaceholderText("转换日志将显示在这里...")
        layout.addWidget(self.log_view)

        self.label_status = QLabel("就绪")
        self.label_status.setObjectName("dialogHint")
        layout.addWidget(self.label_status)

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

    def _insert_template_var(self, var: str):
        cursor = self.input_template.cursorPosition()
        text = self.input_template.text()
        new_text = text[:cursor] + var + text[cursor:]
        self.input_template.setText(new_text)
        self.input_template.setCursorPosition(cursor + len(var))

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择文件")
        if files:
            self._add_paths(files)

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder:
            paths = []
            for f in Path(folder).iterdir():
                if f.is_file() and f.suffix.lower() in ALL_MEDIA_EXTS:
                    paths.append(str(f))
            self._add_paths(paths)

    def _guess_default_format(self, ext: str) -> str:
        if ext in IMAGE_EXTS:
            return "jpg"
        elif ext in AUDIO_EXTS:
            return "mp3"
        return "mp4"

    def _add_paths(self, paths):
        for p in paths:
            if not os.path.isfile(p):
                continue
            ext = Path(p).suffix.lower()
            if ext not in ALL_MEDIA_EXTS:
                continue
            if p in self._files:
                continue
            self._files.append(p)
            row = self.table.rowCount()
            self.table.insertRow(row)

            fmt_combo = QComboBox()
            fmt_combo.addItems(_FORMATS_BY_TYPE[_input_media_type(ext)])
            fmt_combo.setCurrentText(self._guess_default_format(ext))
            fmt_combo.setMinimumHeight(26)
            self.table.setCellWidget(row, 0, fmt_combo)
            self._format_combos.append(fmt_combo)

            self.table.setItem(row, 1, QTableWidgetItem(Path(p).name))
            self.table.setItem(row, 2, QTableWidgetItem(p))
            self.table.setItem(row, 3, QTableWidgetItem("等待中"))
        self.label_count.setText(f"{len(self._files)} 个文件")

    def _remove_selected(self):
        if self._is_running:
            return
        rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()), reverse=True)
        for row in rows:
            self.table.removeRow(row)
            if row < len(self._files):
                self._files.pop(row)
            if row < len(self._format_combos):
                self._format_combos.pop(row)
        self.label_count.setText(f"{len(self._files)} 个文件")

    def _clear_all(self):
        if self._is_running:
            return
        self.table.setRowCount(0)
        self._files.clear()
        self._format_combos.clear()
        self.label_count.setText("0 个文件")

    def _start_batch(self):
        if not self._files:
            QMessageBox.warning(self, "提示", "请先添加文件")
            return
        if len(self._format_combos) != len(self._files):
            QMessageBox.warning(self, "提示", "文件列表不完整，请重新添加")
            return

        template = self.input_template.text().strip() or "{原名}_converted"
        output_dir_override = getattr(self, '_batch_output_dir', '')

        tasks = []
        seen_outputs = set()
        for i, f in enumerate(self._files):
            p = Path(f)
            fmt = self._format_combos[i].currentText()
            ext = f'.{fmt}'
            if ext in VIDEO_EXTS or fmt == 'gif':
                media_type = 'video'
            elif ext in IMAGE_EXTS:
                media_type = 'image'
            else:
                media_type = 'audio'
            if media_type != _input_media_type(p.suffix.lower()):
                self._append_log('warning', f"跳过 {p.name}: 输出格式 {fmt} 与输入类型不匹配")
                continue
            base_opts = self._converter.get_default_opts(fmt, media_type)
            base_opts.use_gpu = self.check_gpu.isChecked() and bool(self._converter_gpu_type)

            stem = self._render_template(template, p.stem, fmt, i + 1, str(p.parent))
            if output_dir_override:
                validated = validate_output_dir(output_dir_override)
                if validated is None:
                    QMessageBox.warning(self, "提示", f"无效输出目录: {output_dir_override}")
                    return
                out_dir = Path(validated)
                try:
                    out_dir.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    QMessageBox.warning(self, "提示", f"无法创建输出目录: {output_dir_override}\n{e}")
                    return
                output = str(out_dir / f"{stem}.{fmt}")
            else:
                output = str(p.parent / f"{stem}.{fmt}")
            if output in seen_outputs:
                output = str(Path(output).parent / f"{stem}_{i + 1}.{fmt}")
            output = _unique_path(output)
            seen_outputs.add(output)
            tasks.append((f, output, copy.deepcopy(base_opts)))

        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.btn_add.setEnabled(False)
        self.btn_add_folder.setEnabled(False)
        self.btn_remove.setEnabled(False)
        self.btn_clear.setEnabled(False)
        self.label_status.setText("转换中...")
        self.progress_bar.setRange(0, len(tasks))
        self.progress_bar.setValue(0)
        self.log_view.clear()
        self._is_running = True

        self._worker = BatchWorker(
            self._converter, tasks, self.spin_workers.value()
        )
        self._worker.task_done.connect(self._on_task_done)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.progress_pct.connect(self._on_progress_pct)
        self._worker.log.connect(self._append_log)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()

    def _select_batch_output(self):
        d = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if d:
            self._batch_output_dir = d
            self.label_batch_output.setText(d)
        else:
            self._batch_output_dir = ''
            self.label_batch_output.setText("与源文件同目录")

    def _render_template(self, template: str, stem: str, fmt: str,
                         index: int, source_dir: str) -> str:
        # 先清洗模板字面量（防穿越），再替换变量；变量值各自单独清洗，
        # 避免变量展开后再次被全局替换破坏（如 {原路径} 中的反斜杠）。
        result = template.replace('..', '_').replace('/', '_').replace('\\', '_')
        result = result.replace("{原名}", _safe_name_part(stem))
        result = result.replace("{格式}", _safe_name_part(fmt))
        result = result.replace("{序号}", f"{index:03d}")
        result = result.replace("{日期}", datetime.now().strftime("%Y%m%d"))
        result = result.replace("{原路径}", _safe_name_part(source_dir))
        return result

    def _on_task_done(self, task_id, input_file, success):
        row = task_id - 1
        if 0 <= row < self.table.rowCount():
            status = "成功" if success else "失败"
            self.table.setItem(row, 3, QTableWidgetItem(status))
        done = sum(1 for i in range(self.table.rowCount())
                   if self.table.item(i, 3) and self.table.item(i, 3).text() in ("成功", "失败"))
        total = self.table.rowCount()
        if total > 0:
            overall_pct = int(done * 100 / total)
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(overall_pct)
        self.label_status.setText(f"进度: {done}/{total}")

    def _on_progress_pct(self, pct: int):
        pass

    def _append_log(self, lvl: str, msg: str):
        cursor = self.log_view.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertHtml(format_log_html(lvl, msg))
        cursor.insertBlock()
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_all_done(self, success_count, total):
        if not self._is_running:
            return
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self._set_idle()
        self.label_status.setText(f"完成: {success_count}/{total} 成功")

    def _set_idle(self):
        self._is_running = False
        self._worker = None
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.btn_add.setEnabled(True)
        self.btn_add_folder.setEnabled(True)
        self.btn_remove.setEnabled(True)
        self.btn_clear.setEnabled(True)

    def _cancel_batch(self):
        if self._worker and self._worker.isRunning():
            self._is_running = False
            self._worker.requestInterruption()
            self._worker.cancel()
            if not self._worker.wait(10000):
                self.label_status.setText("正在停止后台任务，请稍候...")
                return
            self._worker = None
            self._set_idle()
            self.label_status.setText("已取消")

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._is_running = False
            try:
                self._worker.log.disconnect()
                self._worker.progress.disconnect()
                self._worker.progress_pct.disconnect()
                self._worker.eta.disconnect()
                self._worker.task_done.disconnect()
                self._worker.all_done.disconnect()
            except (TypeError, RuntimeError):
                pass
            self._worker.requestInterruption()
            self._worker.cancel()
            if not self._worker.wait(10000):
                self._pending_worker = self._worker
                self._worker.finished.connect(self._pending_worker.deleteLater)
        self._worker = None
        event.accept()
