import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, PropertyMock

from core.history import HistoryManager
from core.options import ConvertOptions


class TestHistoryManager(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.history_dir = Path(self.tmp.name) / "FFmpegConverter"
        self.history_mgr = HistoryManager()
        self.history_mgr.history_dir = self.history_dir
        self.history_mgr.history_file = self.history_dir / "history.json"
        self.history_mgr.max_history = 5

    def tearDown(self):
        self.tmp.cleanup()

    def test_load_empty(self):
        history = self.history_mgr.load_history()
        self.assertEqual(history, [])

    def test_add_and_load(self):
        opts = ConvertOptions(width=1920, height=1080, quality=23)
        self.history_mgr.add_record("test.mp4", "avi", opts)
        history = self.history_mgr.load_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['file'], 'test.mp4')
        self.assertEqual(history[0]['format'], 'avi')
        self.assertIn('width', history[0]['options'])
        self.assertIn('time', history[0])

    def test_deduplicate_same_file_same_format(self):
        opts1 = ConvertOptions(quality=23)
        opts2 = ConvertOptions(quality=15)
        self.history_mgr.add_record("test.mp4", "mp4", opts1)
        self.history_mgr.add_record("test.mp4", "mp4", opts2)
        history = self.history_mgr.load_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['format'], 'mp4')

    def test_keep_different_formats(self):
        opts1 = ConvertOptions(quality=23)
        opts2 = ConvertOptions(quality=15)
        self.history_mgr.add_record("test.mp4", "mp4", opts1)
        self.history_mgr.add_record("test.mp4", "avi", opts2)
        history = self.history_mgr.load_history()
        self.assertEqual(len(history), 2)

    def test_max_history(self):
        for i in range(10):
            opts = ConvertOptions(quality=i)
            self.history_mgr.add_record(f"file_{i}.mp4", "mp4", opts)
        history = self.history_mgr.load_history()
        self.assertEqual(len(history), 5)

    def test_get_recent(self):
        for i in range(5):
            opts = ConvertOptions(quality=i)
            self.history_mgr.add_record(f"file_{i}.mp4", "mp4", opts)
        recent = self.history_mgr.get_recent(3)
        self.assertEqual(len(recent), 3)

    def test_save_load_corrupted_json(self):
        self.history_dir.mkdir(parents=True, exist_ok=True)
        with open(self.history_mgr.history_file, 'w', encoding='utf-8') as f:
            f.write("not valid json")
        history = self.history_mgr.load_history()
        self.assertEqual(history, [])

    def test_options_none_values_excluded(self):
        opts = ConvertOptions(width=1920)
        self.history_mgr.add_record("test.mp4", "mp4", opts)
        history = self.history_mgr.load_history()
        self.assertIn('width', history[0]['options'])
        self.assertNotIn('height', history[0]['options'])


    def test_delete_record(self):
        opts = ConvertOptions()
        self.history_mgr.add_record("a.mp4", "mp4", opts)
        self.history_mgr.add_record("b.mp4", "mp4", opts)
        self.assertTrue(self.history_mgr.delete_record(0))
        history = self.history_mgr.load_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['file'], 'a.mp4')

    def test_delete_record_out_of_bounds(self):
        opts = ConvertOptions()
        self.history_mgr.add_record("a.mp4", "mp4", opts)
        self.assertFalse(self.history_mgr.delete_record(5))
        self.assertFalse(self.history_mgr.delete_record(-1))

    def test_clear_history(self):
        opts = ConvertOptions()
        self.history_mgr.add_record("a.mp4", "mp4", opts)
        self.history_mgr.clear_history()
        history = self.history_mgr.load_history()
        self.assertEqual(history, [])

    def test_concurrent_add_record(self):
        import threading
        self.history_mgr.max_history = 100
        errors = []

        def add_records(thread_id):
            try:
                for i in range(10):
                    opts = ConvertOptions(quality=i)
                    self.history_mgr.add_record(f"thread{thread_id}_file{i}.mp4", "mp4", opts)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_records, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Concurrent errors: {errors}")
        history = self.history_mgr.load_history()
        self.assertEqual(len(history), 50)


if __name__ == '__main__':
    unittest.main()
