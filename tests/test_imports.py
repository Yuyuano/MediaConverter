import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


class TestImports(unittest.TestCase):
    """Smoke test: verify all modules are importable without errors."""

    def test_import_core_constants(self):
        from core.constants import APP_VERSION, VIDEO_EXTS, IMAGE_EXTS, AUDIO_EXTS, ALL_MEDIA_EXTS
        self.assertIsInstance(APP_VERSION, str)
        self.assertTrue(len(ALL_MEDIA_EXTS) > 0)

    def test_import_core_options(self):
        from core.options import ConvertOptions
        opts = ConvertOptions()
        self.assertIsNone(opts.width)

    def test_import_core_validators(self):
        from core.validators import validate_extra_args, validate_output_dir, parse_size, SIZE_PRESETS
        self.assertIn('1080p', SIZE_PRESETS)

    def test_import_core_ffmpeg(self):
        from core.ffmpeg import FFmpegManager
        mgr = FFmpegManager()
        self.assertIsNotNone(mgr)

    def test_import_core_history(self):
        from core.history import HistoryManager
        mgr = HistoryManager()
        self.assertIsNotNone(mgr.history_dir)

    def test_import_core_converter(self):
        from core.converter import MediaConverter
        conv = MediaConverter()
        self.assertIsNotNone(conv)

    def test_import_core_queue(self):
        from core.queue import ConversionQueue, ConversionTask
        self.assertIsNotNone(ConversionQueue)
        self.assertIsNotNone(ConversionTask)

    def test_import_core_probe_and_builder(self):
        from core.probe import MediaProbe
        from core.command_builder import CommandBuilder
        from core.progress_parser import ProgressParser
        self.assertIsNotNone(MediaProbe)
        self.assertIsNotNone(CommandBuilder)
        self.assertIsNotNone(ProgressParser)

    def test_import_gui_main_window(self):
        from gui.main_window import MainWindow
        self.assertIsNotNone(MainWindow)

    def test_import_gui_pages(self):
        from gui.pages.convert_page import ConvertPage
        self.assertIsNotNone(ConvertPage)

    def test_import_gui_widgets(self):
        from gui.widgets.sidebar import Sidebar
        from gui.widgets.progress_panel import ProgressPanel
        from gui.widgets.param_panel import ParamPanel
        from gui.widgets.history_table import HistoryTable
        from gui.widgets.format_selector import FormatSelector
        from gui.widgets.file_drop import FileDropWidget
        self.assertIsNotNone(Sidebar)
        self.assertIsNotNone(ProgressPanel)
        self.assertIsNotNone(ParamPanel)
        self.assertIsNotNone(HistoryTable)
        self.assertIsNotNone(FormatSelector)
        self.assertIsNotNone(FileDropWidget)

    def test_import_gui_dialogs(self):
        from gui.dialogs.batch_dialog import BatchDialog
        from gui.dialogs.concat_dialog import ConcatDialog
        from gui.dialogs.info_dialog import InfoDialog
        self.assertIsNotNone(BatchDialog)
        self.assertIsNotNone(ConcatDialog)
        self.assertIsNotNone(InfoDialog)

    def test_import_gui_theme(self):
        from gui.theme import ThemeManager, format_log_html, get_theme
        self.assertIsNotNone(ThemeManager)
        self.assertIsNotNone(format_log_html)
        self.assertIsNone(get_theme())

    def test_import_gui_workers(self):
        from gui.workers.convert_worker import ConvertWorker, BatchWorker
        from gui.workers.detect_worker import DetectWorker
        from gui.workers.crop_worker import CropWorker
        from gui.workers.info_worker import InfoWorker
        from gui.workers.concat_worker import ConcatWorker
        from gui.workers.thumbnail_worker import ThumbnailWorker
        self.assertIsNotNone(ConvertWorker)
        self.assertIsNotNone(BatchWorker)
        self.assertIsNotNone(DetectWorker)
        self.assertIsNotNone(CropWorker)
        self.assertIsNotNone(InfoWorker)
        self.assertIsNotNone(ConcatWorker)
        self.assertIsNotNone(ThumbnailWorker)


if __name__ == '__main__':
    unittest.main()
