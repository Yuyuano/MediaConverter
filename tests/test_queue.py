import unittest
import threading
from unittest.mock import MagicMock

from core.queue import ConversionQueue, ConversionTask
from core.options import ConvertOptions


class TestConversionTask(unittest.TestCase):

    def test_task_initial_state(self):
        opts = ConvertOptions(quality=23)
        task = ConversionTask(1, "input.mp4", "output.mp4", opts)
        self.assertEqual(task.id, 1)
        self.assertEqual(task.input_file, "input.mp4")
        self.assertEqual(task.output_file, "output.mp4")
        self.assertEqual(task.status, 'waiting')
        self.assertIsNone(task.result)


class TestConversionQueue(unittest.TestCase):

    def setUp(self):
        self.converter = MagicMock()
        self.converter.convert.return_value = True

    def test_add_task(self):
        q = ConversionQueue(self.converter)
        tid = q.add_task("in.mp4", "out.mp4", ConvertOptions())
        self.assertEqual(tid, 1)
        self.assertEqual(len(q.tasks), 1)

    def test_add_multiple_tasks(self):
        q = ConversionQueue(self.converter)
        for i in range(5):
            tid = q.add_task(f"in_{i}.mp4", f"out_{i}.mp4", ConvertOptions())
        self.assertEqual(len(q.tasks), 5)

    def test_reset(self):
        q = ConversionQueue(self.converter)
        q.add_task("in.mp4", "out.mp4", ConvertOptions())
        q.reset()
        self.assertEqual(len(q.tasks), 0)

    def test_process_empty(self):
        q = ConversionQueue(self.converter)
        results = q.process()
        self.assertEqual(results, [])

    def test_process_single_success(self):
        q = ConversionQueue(self.converter)
        q.add_task("in.mp4", "out.mp4", ConvertOptions())
        results = q.process()
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0])
        self.converter.convert.assert_called_once()

    def test_process_task_status(self):
        q = ConversionQueue(self.converter)
        q.add_task("in.mp4", "out.mp4", ConvertOptions())
        q.process()
        self.assertEqual(q.tasks[0].status, 'completed')

    def test_process_callback(self):
        task_done_calls = []
        all_done_calls = []

        def on_done(task, success):
            task_done_calls.append((task.id, success))

        def on_all(success_count, total):
            all_done_calls.append((success_count, total))

        q = ConversionQueue(self.converter,
                           on_task_done=on_done, on_all_done=on_all)
        q.add_task("in.mp4", "out.mp4", ConvertOptions())
        q.process()
        self.assertEqual(len(task_done_calls), 1)
        self.assertEqual(task_done_calls[0], (1, True))
        self.assertEqual(all_done_calls[0], (1, 1))

    def test_cancel(self):
        q = ConversionQueue(self.converter)
        q.add_task("in.mp4", "out.mp4", ConvertOptions())
        q.cancel()
        self.assertTrue(q._cancel_event.is_set())
        self.converter.cleanup.assert_called_once()

    def test_cancel_mid_process(self):
        import time

        def slow_convert(*a, **kw):
            time.sleep(0.3)
            return True

        self.converter.convert.side_effect = slow_convert
        q = ConversionQueue(self.converter, max_workers=1)
        for i in range(5):
            q.add_task(f"in_{i}.mp4", f"out_{i}.mp4", ConvertOptions())

        import threading
        timer = threading.Timer(0.05, q.cancel)
        timer.start()
        results = q.process()
        timer.cancel()
        self.assertEqual(sum(1 for r in results if not r), 4)
        self.assertTrue(self.converter.cleanup.called)

    def test_process_converter_exception(self):
        self.converter.convert.side_effect = OSError("disk full")
        q = ConversionQueue(self.converter)
        q.add_task("in.mp4", "out.mp4", ConvertOptions())
        results = q.process()
        self.assertFalse(results[0])
        self.assertEqual(q.tasks[0].status, 'failed')


if __name__ == '__main__':
    unittest.main()
