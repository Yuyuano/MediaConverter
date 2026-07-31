import unittest
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import QCoreApplication
import sys

from core.options import ConvertOptions
from core.converter import MediaConverter
from gui.workers.convert_worker import ConvertWorker, BatchWorker
from gui.workers.crop_worker import CropWorker
from gui.workers.detect_worker import DetectWorker


class TestConvertWorker(unittest.TestCase):

    def setUp(self):
        self.converter = MagicMock()
        self.converter.convert.return_value = True
        self.opts = ConvertOptions()

    def test_convert_worker_emits_finished(self):
        worker = ConvertWorker(self.converter, 'in.mp4', 'out.mp4', self.opts)
        results = []
        worker.finished.connect(lambda ok, path: results.append((ok, path)))
        worker.run()
        self.assertEqual(results, [(True, 'out.mp4')])
        self.converter.set_callbacks.assert_called_once()

    def test_convert_worker_exception(self):
        self.converter.convert.side_effect = RuntimeError("boom")
        worker = ConvertWorker(self.converter, 'in.mp4', 'out.mp4', self.opts)
        results = []
        worker.finished.connect(lambda ok, path: results.append((ok, path)))
        worker.run()
        self.assertEqual(results, [(False, '')])

    def test_convert_worker_progress_signal(self):
        progress_calls = []
        self.converter.convert.side_effect = lambda *a, **kw: True
        worker = ConvertWorker(self.converter, 'in.mp4', 'out.mp4', self.opts)
        worker.progress.connect(lambda msg: progress_calls.append(msg))
        worker.run()
        self.converter.convert.assert_called_once()


class TestBatchWorker(unittest.TestCase):

    def setUp(self):
        self.converter = MagicMock()
        self.converter.convert.return_value = True

    def test_batch_worker_cancel(self):
        worker = BatchWorker(self.converter, [('a.mp4', 'b.mp4', ConvertOptions())])
        worker._queue = MagicMock()
        worker.cancel()
        worker._queue.cancel.assert_called_once()

    def test_batch_worker_emits_all_done(self):
        worker = BatchWorker(self.converter, [('a.mp4', 'b.mp4', ConvertOptions())])
        all_done_calls = []
        worker.all_done.connect(lambda sc, t: all_done_calls.append((sc, t)))
        worker.run()
        self.assertTrue(len(all_done_calls) > 0)


class TestCropWorker(unittest.TestCase):

    def test_crop_worker_emits_result(self):
        converter = MagicMock()
        converter.detect_crop.return_value = {'w': 1280, 'h': 720, 'x': 0, 'y': 0}
        worker = CropWorker(converter, 'input.mp4')
        results = []
        worker.crop_ready.connect(lambda d: results.append(d))
        worker.run()
        self.assertEqual(results, [{'w': 1280, 'h': 720, 'x': 0, 'y': 0}])

    def test_crop_worker_exception_emits_empty(self):
        converter = MagicMock()
        converter.detect_crop.side_effect = RuntimeError("fail")
        worker = CropWorker(converter, 'input.mp4')
        results = []
        worker.crop_ready.connect(lambda d: results.append(d))
        worker.run()
        self.assertEqual(results, [{}])

    def test_crop_worker_none_result(self):
        converter = MagicMock()
        converter.detect_crop.return_value = None
        worker = CropWorker(converter, 'input.mp4')
        results = []
        worker.crop_ready.connect(lambda d: results.append(d))
        worker.run()
        self.assertEqual(results, [{}])


class TestDetectWorker(unittest.TestCase):

    def test_detect_worker_emits_detected(self):
        converter = MagicMock()
        converter.init.return_value = True
        converter.gpu_type = 'nvidia'
        converter.gpu_name = 'NVIDIA (NVENC)'
        worker = DetectWorker(converter)
        results = []
        worker.detected.connect(lambda gt, gn: results.append((gt, gn)))
        worker.run()
        self.assertEqual(results, [('nvidia', 'NVIDIA (NVENC)')])
        converter.init.assert_called_once()

    def test_detect_worker_exception(self):
        converter = MagicMock()
        converter.init.side_effect = RuntimeError("fail")
        worker = DetectWorker(converter)
        results = []
        worker.detected.connect(lambda gt, gn: results.append((gt, gn)))
        worker.run()
        self.assertEqual(results, [('', '')])

    def test_detect_worker_no_gpu(self):
        converter = MagicMock()
        converter.init.return_value = True
        converter.gpu_type = None
        converter.gpu_name = ''
        worker = DetectWorker(converter)
        results = []
        worker.detected.connect(lambda gt, gn: results.append((gt, gn)))
        worker.run()
        self.assertEqual(results, [('', '')])


if __name__ == '__main__':
    unittest.main()
