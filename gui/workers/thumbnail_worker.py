import os
import tempfile
from PyQt6.QtCore import QThread, pyqtSignal

from core.paths import tmp_dir


class ThumbnailWorker(QThread):
    thumb_ready = pyqtSignal(str)

    def __init__(self, converter, input_file):
        super().__init__()
        self.converter = converter
        self.input_file = input_file

    def run(self):
        tmp = None
        try:
            if self.isInterruptionRequested():
                return
            tmp = tempfile.NamedTemporaryFile(
                suffix='.jpg', delete=False, dir=str(tmp_dir()))
            tmp.close()
            ok = self.converter.extract_thumbnail(self.input_file, tmp.name, 1.0)
            if ok and not self.isInterruptionRequested():
                self.thumb_ready.emit(tmp.name)
                tmp = None
            else:
                self._unlink(tmp.name)
                tmp = None
        except Exception:
            if tmp and os.path.exists(tmp.name):
                self._unlink(tmp.name)

    @staticmethod
    def _unlink(path: str):
        try:
            os.unlink(path)
        except OSError:
            pass
