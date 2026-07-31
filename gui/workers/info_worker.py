from PyQt6.QtCore import QThread, pyqtSignal


class InfoWorker(QThread):
    info_ready = pyqtSignal(str, dict)

    def __init__(self, converter, filepath: str):
        super().__init__()
        self.converter = converter
        self.filepath = filepath

    def run(self):
        try:
            if self.isInterruptionRequested():
                self.info_ready.emit(self.filepath, {})
                return
            result = self.converter.get_file_summary(self.filepath)
            self.info_ready.emit(self.filepath, result if result and result.get('valid') else {})
        except Exception:
            self.info_ready.emit(self.filepath, {})