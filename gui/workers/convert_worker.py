from PyQt6.QtCore import pyqtSignal

from core.options import ConvertOptions
from core.queue import ConversionQueue
from gui.workers.base import MediaWorker


class ConvertWorker(MediaWorker):

    def __init__(self, converter, input_file: str, output_file: str, opts: ConvertOptions):
        super().__init__(converter)
        self.input_file = input_file
        self.output_file = output_file
        self.opts = opts

    def run(self):
        try:
            if not self.converter.ffmpeg_path:
                if not self.converter.init():
                    self.log.emit('error', 'FFmpeg 未找到或初始化失败')
                    self.finished.emit(False, '')
                    return

            self.converter.reset_cancellation()
            self._bridge_callbacks()
            success = self.converter.convert(self.input_file, self.output_file, self.opts)
            self.finished.emit(success, self.output_file if success else '')
        except Exception as e:
            import logging
            logging.getLogger('MediaConverter').error(f"转换工作线程异常: {e}", exc_info=True)
            self.finished.emit(False, '')
        finally:
            self.converter.reset_callbacks()


class BatchWorker(MediaWorker):
    task_done = pyqtSignal(int, str, bool)
    all_done = pyqtSignal(int, int)

    def __init__(self, converter, tasks, max_workers: int = 2):
        super().__init__(converter)
        self.tasks = tasks
        self.max_workers = max_workers
        self._queue = None

    def run(self):
        try:
            self.converter.reset_cancellation()
            self._bridge_callbacks()

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
        finally:
            self.converter.reset_callbacks()

    def cancel(self):
        if self._queue:
            self._queue.cancel()
