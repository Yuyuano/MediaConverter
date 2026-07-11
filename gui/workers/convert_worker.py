from PyQt6.QtCore import QThread, pyqtSignal

from core.options import ConvertOptions
from core.queue import ConversionQueue


class ConvertWorker(QThread):
    progress = pyqtSignal(str)
    progress_pct = pyqtSignal(int)
    eta = pyqtSignal(str)
    log = pyqtSignal(str, str)
    finished = pyqtSignal(bool, str)

    def __init__(self, converter, input_file: str, output_file: str, opts: ConvertOptions):
        super().__init__()
        self.converter = converter
        self.input_file = input_file
        self.output_file = output_file
        self.opts = opts

    def run(self):
        try:
            self.converter.set_callbacks(
                on_log=lambda lvl, msg: self.log.emit(lvl, msg),
                on_progress=lambda msg: self.progress.emit(msg),
                on_progress_pct=lambda pct: self.progress_pct.emit(pct),
                on_eta=lambda eta: self.eta.emit(eta)
            )
            success = self.converter.convert(self.input_file, self.output_file, self.opts)
            self.finished.emit(success, self.output_file if success else '')
        except Exception as e:
            import logging
            logging.getLogger('MediaConverter').error(f"转换工作线程异常: {e}", exc_info=True)
            self.finished.emit(False, '')


class BatchWorker(QThread):
    task_done = pyqtSignal(int, str, bool)
    all_done = pyqtSignal(int, int)
    log = pyqtSignal(str, str)
    progress = pyqtSignal(str)
    progress_pct = pyqtSignal(int)
    eta = pyqtSignal(str)

    def __init__(self, converter, tasks, max_workers: int = 2):
        super().__init__()
        self.converter = converter
        self.tasks = tasks
        self.max_workers = max_workers
        self._queue = None

    def run(self):
        try:
            self.converter.set_callbacks(
                on_log=lambda lvl, msg: self.log.emit(lvl, msg),
                on_progress=lambda msg: self.progress.emit(msg),
                on_progress_pct=lambda pct: self.progress_pct.emit(pct),
                on_eta=lambda eta: self.eta.emit(eta)
            )

            self._queue = ConversionQueue(
                self.converter, self.max_workers,
                on_task_done=lambda task, success: self.task_done.emit(task.id, task.input_file, success),
                on_all_done=lambda sc, t: self.all_done.emit(sc, t)
            )
            for i, (inp, out, opts) in enumerate(self.tasks, 1):
                self._queue.add_task(inp, out, opts)
            self._queue.process()
        except Exception as e:
            import logging
            logging.getLogger('MediaConverter').error(f"批量工作线程异常: {e}", exc_info=True)
            self.all_done.emit(0, len(self.tasks))

    def cancel(self):
        if self._queue:
            self._queue.cancel()
