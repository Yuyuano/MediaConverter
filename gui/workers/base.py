from PyQt6.QtCore import QThread, pyqtSignal


class MediaWorker(QThread):
    """转换类 worker 共享基类：统一信号定义与回调桥接。

    子类覆写 `run()`，开始时调用 `_bridge_callbacks()` 将 converter 回调
    桥接到 Qt 信号（跨线程安全），结束前记得 `reset_callbacks()`。
    """
    progress = pyqtSignal(str)
    progress_pct = pyqtSignal(int)
    eta = pyqtSignal(str)
    log = pyqtSignal(str, str)
    finished = pyqtSignal(bool, str)

    def __init__(self, converter, parent=None):
        super().__init__(parent)
        self.converter = converter

    def _bridge_callbacks(self):
        self.converter.set_callbacks(
            on_log=lambda lvl, msg: self.log.emit(lvl, msg),
            on_progress=lambda msg: self.progress.emit(msg),
            on_progress_pct=lambda pct: self.progress_pct.emit(pct),
            on_eta=lambda eta: self.eta.emit(eta)
        )
