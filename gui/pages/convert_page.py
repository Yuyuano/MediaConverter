import os
import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QMessageBox, QFileDialog, QComboBox, QFrame, QApplication,
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import QApplication

from core.options import ConvertOptions
from gui.widgets.file_drop import FileDropWidget
from gui.widgets.format_selector import FormatSelector
from gui.widgets.param_panel import ParamPanel
from gui.widgets.progress_panel import ProgressPanel
from gui.workers.convert_worker import ConvertWorker, BatchWorker

logger = logging.getLogger('MediaConverter')


class ConvertPage(QWidget):
    status_message = pyqtSignal(str)
    conversion_done = pyqtSignal()

    def __init__(self, converter, media_type: str):
        super().__init__()
        self._converter = converter
        self._media_type = media_type
        self._current_file = None
        self._file_info = {}
        self._worker = None
        self._batch_worker = None
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        self.file_drop = FileDropWidget()
        card1 = QFrame(objectName="card")
        card1.setLayout(QVBoxLayout())
        card1.layout().setContentsMargins(12, 12, 12, 12)
        card1.layout().addWidget(self.file_drop)
        layout.addWidget(card1)

        self.format_selector = FormatSelector(self._media_type)
        card2 = QFrame(objectName="card")
        card2.setLayout(QVBoxLayout())
        card2.layout().setContentsMargins(12, 12, 12, 12)
        card2.layout().addWidget(self.format_selector)
        layout.addWidget(card2)

        self.param_panel = ParamPanel()
        self.param_panel.set_media_type(self._media_type)

        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel("输出目录:"))
        self.combo_output = QComboBox()
        self.combo_output.addItem("与源文件同目录")
        self.combo_output.setEditable(True)
        self.combo_output.setMinimumHeight(30)
        self.btn_browse = QPushButton("浏览...")
        self.btn_browse.setMinimumHeight(30)
        self.btn_browse.clicked.connect(self._browse_dir)
        dir_row.addWidget(self.combo_output, 1)
        dir_row.addWidget(self.btn_browse)

        btn_row = QHBoxLayout()
        self.btn_batch = QPushButton("批量转换")
        self.btn_batch.setFixedHeight(40)
        self.btn_batch.setMinimumWidth(100)
        self.btn_batch.clicked.connect(self._open_batch)
        self.btn_concat = QPushButton("视频拼接")
        self.btn_concat.setFixedHeight(40)
        self.btn_concat.setMinimumWidth(100)
        self.btn_concat.clicked.connect(self._open_concat)
        if self._media_type != 'video':
            self.btn_concat.setVisible(False)
        self.btn_convert = QPushButton("开始转换")
        self.btn_convert.setObjectName("convertBtn")
        self.btn_convert.setFixedHeight(44)
        self.btn_convert.clicked.connect(self._on_convert)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_batch)
        btn_row.addWidget(self.btn_concat)
        btn_row.addWidget(self.btn_convert)
        btn_row.addStretch()

        card3 = QFrame(objectName="card")
        card3.setLayout(QVBoxLayout())
        card3.layout().setContentsMargins(12, 12, 12, 12)
        card3.layout().setSpacing(8)
        card3.layout().addWidget(self.param_panel)
        card3.layout().addLayout(dir_row)
        card3.layout().addLayout(btn_row)
        layout.addWidget(card3)

        self.progress_panel = ProgressPanel()
        card4 = QFrame(objectName="card")
        card4.setLayout(QVBoxLayout())
        card4.layout().setContentsMargins(12, 12, 12, 12)
        card4.layout().addWidget(self.progress_panel)
        layout.addWidget(card4)

    def _connect_signals(self):
        self.file_drop.file_selected.connect(self._on_file_selected)
        self.file_drop.info_requested.connect(self._on_info_requested)
        self.format_selector.format_changed.connect(self._on_format_changed)
        self.progress_panel.cancel_requested.connect(self._on_cancel)
        self.param_panel.crop_detect_requested.connect(self._on_crop_detect)

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if d:
            self.combo_output.setCurrentText(d)

    def _get_output_path(self, input_file: str, suffix: str, ext: str) -> str:
        opts = self._get_options()
        input_path = Path(input_file)
        out_text = self.combo_output.currentText().strip()
        if out_text and out_text != "与源文件同目录":
            output_dir = Path(out_text)
            output_dir.mkdir(parents=True, exist_ok=True)
        else:
            output_dir = input_path.parent
        return str(output_dir / f"{input_path.stem}_{suffix}.{ext}")

    def _on_file_selected(self, filepath: str):
        if not filepath:
            self._current_file = None
            self._file_info = {}
            self.status_message.emit("已清除选择")
            return
        self._current_file = filepath
        self._file_info = self._converter.get_file_summary(filepath)
        self.file_drop.set_file_info(self._file_info)
        self.status_message.emit(f"已选择: {Path(filepath).name}")

    def _on_info_requested(self, filepath: str):
        from gui.dialogs.info_dialog import InfoDialog
        dlg = InfoDialog(self._converter, filepath, self)
        dlg.exec()

    def _on_format_changed(self, fmt: str, media_type: str):
        if fmt:
            self.status_message.emit(f"输出格式: {fmt.upper()} ({media_type})")
        else:
            self.status_message.emit("未选择输出格式")

    def _on_crop_detect(self, _media_type: str):
        if not self._current_file:
            QMessageBox.warning(self, "提示", "请先选择文件")
            self.param_panel.set_crop_error()
            return
        QApplication.processEvents()
        result = self._converter.detect_crop(self._current_file)
        if result:
            self.param_panel.set_crop_result(result['w'], result['h'], result['x'], result['y'])
            self.status_message.emit(f"检测到裁剪: {result['w']}×{result['h']}+{result['x']}+{result['y']}")
        else:
            self.param_panel.set_crop_error()
            self.status_message.emit("未检测到黑边或检测失败")

    def _get_options(self) -> ConvertOptions:
        opts = self.param_panel.get_options()
        out_text = self.combo_output.currentText().strip()
        if out_text and out_text != "与源文件同目录":
            opts.output_dir = out_text
        return opts

    def _on_convert(self):
        if not self._current_file:
            QMessageBox.warning(self, "提示", "请先选择文件")
            return

        opts = self._get_options()

        if self.param_panel.is_compress_enabled():
            self._run_compress(opts)
            return

        sel = self.format_selector.selected_format
        if not sel:
            QMessageBox.warning(self, "提示", "请选择输出格式")
            return
        fmt, media_type = sel
        suffix = "converted"
        output = self._get_output_path(self._current_file, suffix, fmt)
        self._start_convert(self._current_file, output, opts)

    def _run_compress(self, opts: ConvertOptions):
        sel = self.format_selector.selected_format
        out_ext = sel[0] if sel else 'mp4'
        target_mb = self.param_panel.get_compress_target_mb()
        output = self._get_output_path(self._current_file, "compressed", out_ext)

        info = self._converter.get_info(self._current_file)
        try:
            duration = float(info.get('duration', 0) or 0)
        except (ValueError, TypeError):
            duration = 0
        if duration == 0:
            QMessageBox.warning(self, "提示", "无法获取视频时长")
            return
        target_bits = int((target_mb * 8 * 1024 * 1024) / duration * 0.9)
        opts.bitrate = f"{target_bits // 1024}k"
        opts.audio_bitrate = "128k"
        opts.preset = 'slow'
        self._start_convert(self._current_file, output, opts)

    def _start_convert(self, input_file: str, output_file: str, opts: ConvertOptions):
        if self._worker and self._worker.isRunning():
            try:
                self._worker.finished.disconnect()
            except TypeError:
                pass
            self._converter.cleanup()
            self._worker.wait(5000)
            self._worker = None
        self.progress_panel.clear()
        self.progress_panel.set_converting(True)
        self.btn_convert.setEnabled(False)

        self._worker = ConvertWorker(self._converter, input_file, output_file, opts)
        self._worker.log.connect(self.progress_panel.append_log)
        self._worker.progress.connect(self.progress_panel.append_progress)
        self._worker.progress_pct.connect(self.progress_panel.set_progress_pct)
        self._worker.eta.connect(self.progress_panel.set_eta)
        self._worker.finished.connect(self._on_convert_done)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()

    def _on_convert_done(self, success: bool, output_path: str):
        self._worker = None
        self.progress_panel.set_converting(False)
        self.progress_panel.set_eta('')
        self.btn_convert.setEnabled(True)
        if success:
            self.progress_panel.set_progress(100)
            self.progress_panel.append_log('info', f'完成! 输出: {output_path}')
            self.status_message.emit("转换完成")
            self.conversion_done.emit()
            self.window().alert(self.window(), f"转换完成: {Path(output_path).name}")
        else:
            self.progress_panel.append_log('error', '转换失败')
            self.status_message.emit("转换失败")

    def _on_cancel(self):
        if self._worker and self._worker.isRunning():
            try:
                self._worker.finished.disconnect()
            except TypeError:
                pass
            self._converter.cleanup()
            self._worker.wait(3000)
            self._worker = None
            self.progress_panel.append_log('warning', '已取消')
            self.progress_panel.set_converting(False)
            self.btn_convert.setEnabled(True)
        if self._batch_worker and self._batch_worker.isRunning():
            self._batch_worker.cancel()
            self._batch_worker.wait(3000)
            self._batch_worker = None
            self.progress_panel.append_log('warning', '已取消批量转换')
            self.progress_panel.set_converting(False)
            self.btn_convert.setEnabled(True)

    def _open_batch(self):
        if self.is_converting():
            QMessageBox.warning(self, "提示", "当前有转换任务正在进行，请等待完成或取消后再进行批量转换")
            return
        from gui.dialogs.batch_dialog import BatchDialog
        dlg = BatchDialog(self._converter, self)
        dlg.exec()

    def _open_concat(self):
        if self.is_converting():
            QMessageBox.warning(self, "提示", "当前有转换任务正在进行，请等待完成或取消后再进行拼接")
            return
        from gui.dialogs.concat_dialog import ConcatDialog
        dlg = ConcatDialog(self)
        dlg.exec()

    def set_gpu_available(self, available: bool, gpu_name: str = '', gpu_type: str = ''):
        self.param_panel.set_gpu_available(available, gpu_name, gpu_type)

    def load_file(self, filepath: str):
        self.file_drop.set_file(filepath)

    def select_format(self, fmt: str):
        self.format_selector.select_format(fmt)

    def clear(self):
        self._current_file = None
        self._file_info = {}
        self.file_drop.clear()
        self.format_selector.clear_selection()
        self.progress_panel.clear()

    def is_converting(self) -> bool:
        if self._worker and self._worker.isRunning():
            return True
        if self._batch_worker and self._batch_worker.isRunning():
            return True
        return False

    def cleanup(self):
        if self._worker and self._worker.isRunning():
            self._converter.cleanup()
            self._worker.wait(5000)
            self._worker = None
        if self._batch_worker and self._batch_worker.isRunning():
            self._batch_worker.cancel()
            self._batch_worker.wait(3000)
            self._batch_worker = None
