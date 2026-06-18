import os
import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTabWidget, QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog, QSpinBox, QGroupBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from core.converter import MediaConverter
from core.options import ConvertOptions
from gui.widgets.file_drop import FileDropWidget
from gui.widgets.format_selector import FormatSelector
from gui.widgets.param_panel import ParamPanel
from gui.widgets.progress_panel import ProgressPanel
from gui.widgets.history_table import HistoryTable
from gui.workers.convert_worker import ConvertWorker, BatchWorker
from gui.workers.detect_worker import DetectWorker

logger = logging.getLogger('MediaConverter')


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MediaConverter v3.0 - 媒体格式转换工具")
        self.setMinimumSize(700, 500)
        self.resize(900, 800)

        # 图标
        icon_path = Path(__file__).parent.parent / "ico" / "Miku.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self._converter = MediaConverter()
        self._worker = None
        self._batch_worker = None
        self._current_file = None
        self._file_info = {}

        self._init_ui()
        self._connect_signals()
        self._start_gpu_detect()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(8)

        # 顶部：文件拖拽
        self.file_drop = FileDropWidget()
        main_layout.addWidget(self.file_drop)

        # 格式选择
        self.format_selector = FormatSelector()
        main_layout.addWidget(self.format_selector)

        # 参数面板（含裁剪、智能压缩）
        self.param_panel = ParamPanel()
        main_layout.addWidget(self.param_panel)

        # 操作按钮
        btn_row = QHBoxLayout()
        self.btn_batch = QPushButton("批量转换")
        self.btn_batch.setFixedHeight(40)
        self.btn_batch.setMinimumWidth(100)
        self.btn_batch.clicked.connect(self._open_batch)
        self.btn_convert = QPushButton("开始转换")
        self.btn_convert.setObjectName("convertBtn")
        self.btn_convert.setFixedHeight(40)
        self.btn_convert.clicked.connect(self._on_convert)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_batch)
        btn_row.addWidget(self.btn_convert)
        btn_row.addStretch()
        main_layout.addLayout(btn_row)

        # Tab：进度 / 历史
        self.tabs = QTabWidget()
        self.progress_panel = ProgressPanel()
        self.history_table = HistoryTable(self._converter.history)
        self.tabs.addTab(self.progress_panel, "转换进度")
        self.tabs.addTab(self.history_table, "历史记录")
        main_layout.addWidget(self.tabs)

        # 状态栏
        self.statusBar().showMessage("就绪")

    def _connect_signals(self):
        self.file_drop.file_selected.connect(self._on_file_selected)
        self.format_selector.format_changed.connect(self._on_format_changed)
        self.progress_panel.cancel_requested.connect(self._on_cancel)
        self.history_table.replay_requested.connect(self._on_replay)

    def _start_gpu_detect(self):
        self._detect_worker = DetectWorker(self._converter)
        self._detect_worker.detected.connect(self._on_gpu_detected)
        self._detect_worker.start()

    def _on_gpu_detected(self, gpu_type, gpu_name):
        self.param_panel.set_gpu_available(bool(gpu_type), gpu_name)
        if gpu_type:
            self.statusBar().showMessage(f"GPU: {gpu_name}")
        else:
            self.statusBar().showMessage("就绪 (CPU 模式)")

    def _on_file_selected(self, filepath: str):
        self._current_file = filepath
        self._file_info = self._converter.get_file_summary(filepath)
        self.file_drop.set_file_info(self._file_info)
        self.statusBar().showMessage(f"已选择: {Path(filepath).name}")

    def _on_format_changed(self, fmt: str, media_type: str):
        self.statusBar().showMessage(f"输出格式: {fmt.upper()} ({media_type})")

    def _get_output_path(self, input_file: str, suffix: str, ext: str, opts: ConvertOptions) -> str:
        input_path = Path(input_file)
        if opts.output_dir:
            output_dir = Path(opts.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
        else:
            output_dir = input_path.parent
        return str(output_dir / f"{input_path.stem}_{suffix}.{ext}")

    def _on_convert(self):
        if not self._current_file:
            QMessageBox.warning(self, "提示", "请先选择文件")
            return

        opts = self.param_panel.get_options()

        # 智能压缩模式
        if self.param_panel.is_compress_enabled():
            self._run_compress(opts)
            return

        sel = self.format_selector.selected_format
        if not sel:
            QMessageBox.warning(self, "提示", "请选择输出格式")
            return
        fmt, media_type = sel
        suffix = "converted"
        output = self._get_output_path(self._current_file, suffix, fmt, opts)

        self._start_convert(self._current_file, output, opts)

    def _run_compress(self, opts: ConvertOptions):
        target_mb = self.param_panel.get_compress_target_mb()
        output = self._get_output_path(self._current_file, "compressed", "mp4", opts)

        info = self._converter.get_info(self._current_file)
        try:
            duration = float(info.get('duration', 0) or info.get('format.duration', 0) or 0)
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
        self.progress_panel.clear()
        self.progress_panel.set_converting(True)
        self.tabs.setCurrentWidget(self.progress_panel)
        self.btn_convert.setEnabled(False)

        self._worker = ConvertWorker(self._converter, input_file, output_file, opts)
        self._worker.log.connect(self.progress_panel.append_log)
        self._worker.progress.connect(self.progress_panel.append_progress)
        self._worker.finished.connect(self._on_convert_done)
        self._worker.start()

    def _on_convert_done(self, success: bool, output_path: str):
        self.progress_panel.set_converting(False)
        self.btn_convert.setEnabled(True)
        if success:
            self.progress_panel.set_progress(100)
            self.progress_panel.append_log('info', f'完成! 输出: {output_path}')
            self.statusBar().showMessage("转换完成")
            self.history_table.refresh()
        else:
            self.progress_panel.append_log('error', '转换失败')
            self.statusBar().showMessage("转换失败")

    def _on_cancel(self):
        if self._worker and self._worker.isRunning():
            self._converter.cleanup()
            self.progress_panel.append_log('warning', '已取消')
            self.progress_panel.set_converting(False)
            self.btn_convert.setEnabled(True)
        if self._batch_worker and self._batch_worker.isRunning():
            self._batch_worker.cancel()

    def _on_replay(self, record: dict):
        filepath = record.get('file', '')
        if not os.path.isfile(filepath):
            QMessageBox.warning(self, "提示", f"原文件已不存在:\n{filepath}")
            return
        self._current_file = filepath
        self.file_drop._set_file(filepath)
        self._file_info = self._converter.get_file_summary(filepath)
        self.file_drop.set_file_info(self._file_info)
        self.tabs.setCurrentWidget(self.progress_panel)
        self.statusBar().showMessage(f"已加载历史文件: {Path(filepath).name}")

    def _open_batch(self):
        from gui.dialogs.batch_dialog import BatchDialog
        dlg = BatchDialog(self._converter, self)
        dlg.exec()

    def closeEvent(self, event):
        self._converter.cleanup()
        event.accept()
