from PyQt6.QtCore import QThread, pyqtSignal


class DetectWorker(QThread):
    """GPU 检测后台线程"""
    detected = pyqtSignal(str, str)   # gpu_type, gpu_name

    def __init__(self, converter):
        super().__init__()
        self.converter = converter

    def run(self):
        try:
            if self.isInterruptionRequested():
                self.detected.emit('', '')
                return
            self.converter.init()
            if self.isInterruptionRequested():
                self.detected.emit('', '')
                return
            gpu = self.converter.gpu_type or ''
            name = self.converter.gpu_name
            self.detected.emit(gpu, name)
        except Exception as e:
            import logging
            logging.getLogger('MediaConverter').error(f"GPU检测异常: {e}", exc_info=True)
            self.detected.emit('', '')
