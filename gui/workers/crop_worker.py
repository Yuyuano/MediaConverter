from PyQt6.QtCore import QThread, pyqtSignal


class CropWorker(QThread):
    crop_ready = pyqtSignal(dict)

    def __init__(self, converter, filepath: str):
        super().__init__()
        self.converter = converter
        self.filepath = filepath

    def run(self):
        try:
            if self.isInterruptionRequested():
                self.crop_ready.emit({})
                return
            result = self.converter.detect_crop(self.filepath)
            self.crop_ready.emit(result if result else {})
        except Exception:
            self.crop_ready.emit({})
