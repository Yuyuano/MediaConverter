import os
from PyQt6.QtCore import QThread, pyqtSignal

from core.options import ConvertOptions
from core.queue import ConversionQueue


class ConvertWorker(QThread):
    """单文件转换后台线程"""
    progress = pyqtSignal(str)        # ffmpeg 进度信息
    log = pyqtSignal(str, str)        # level, message
    finished = pyqtSignal(bool, str)  # success, output_path

    def __init__(self, converter, input_file: str, output_file: str, opts: ConvertOptions):
        super().__init__()
        self.converter = converter
        self.input_file = input_file
        self.output_file = output_file
        self.opts = opts

    def run(self):
        self.converter._on_progress = lambda msg: self.progress.emit(msg)
        self.converter._on_log = lambda lvl, msg: self.log.emit(lvl, msg)
        success = self.converter.convert(self.input_file, self.output_file, self.opts)
        self.finished.emit(success, self.output_file if success else '')


class BatchWorker(QThread):
    """批量转换后台线程"""
    task_done = pyqtSignal(int, str, bool)  # task_id, input_file, success
    all_done = pyqtSignal(int, int)          # success_count, total
    log = pyqtSignal(str, str)               # level, message
    progress = pyqtSignal(str)               # 当前任务进度

    def __init__(self, converter, tasks, max_workers: int = 2):
        super().__init__()
        self.converter = converter
        self.tasks = tasks  # list of (input_file, output_file, opts)
        self.max_workers = max_workers
        self._queue = None

    def run(self):
        self.converter._on_progress = lambda msg: self.progress.emit(msg)
        self.converter._on_log = lambda lvl, msg: self.log.emit(lvl, msg)

        self._queue = ConversionQueue(
            self.converter, self.max_workers,
            on_task_done=lambda task, success: self.task_done.emit(task.id, task.input_file, success),
            on_all_done=lambda sc, t: self.all_done.emit(sc, t)
        )
        for i, (inp, out, opts) in enumerate(self.tasks, 1):
            self._queue.add_task(inp, out, opts)
        self._queue.process()

    def cancel(self):
        if self._queue:
            self._queue.cancel()
