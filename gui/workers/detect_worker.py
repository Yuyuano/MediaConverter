from PyQt6.QtCore import QThread, pyqtSignal


class DetectWorker(QThread):
    """GPU 检测后台线程"""
    detected = pyqtSignal(str, str)   # gpu_type, gpu_name
    finished_detect = pyqtSignal()

    def __init__(self, converter):
        super().__init__()
        self.converter = converter

    def run(self):
        self.converter.init()
        gpu = self.converter.gpu_type or ''
        name = self.converter.gpu_name
        self.detected.emit(gpu, name)
        self.finished_detect.emit()
