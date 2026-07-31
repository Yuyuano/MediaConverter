import os
import tempfile
from PyQt6.QtCore import QThread, pyqtSignal


class ThumbnailWorker(QThread):
    thumb_ready = pyqtSignal(str)

    def __init__(self, converter, input_file):
        super().__init__()
        self.converter = converter
        self.input_file = input_file

    def run(self):
        tmp = None
        try:
            tmp = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
            tmp.close()
            ok = self.converter.extract_thumbnail(self.input_file, tmp.name, 1.0)
            if ok:
                self.thumb_ready.emit(tmp.name)
            else:
                os.unlink(tmp.name)
        except Exception:
            if tmp and os.path.exists(tmp.name):
                try:
                    os.unlink(tmp.name)
                except OSError:
                    pass
