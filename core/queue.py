import logging
import subprocess
import threading
from typing import List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from .options import ConvertOptions

logger = logging.getLogger('MediaConverter')


class ConversionTask:
    def __init__(self, task_id: int, input_file: str, output_file: str, opts: ConvertOptions):
        self.id = task_id
        self.input_file = input_file
        self.output_file = output_file
        self.opts = opts
        self.status: str = 'waiting'
        self.result: Optional[bool] = None


class ConversionQueue:

    def __init__(self, converter, max_workers: int = 2,
                 on_task_done: Optional[Callable] = None,
                 on_all_done: Optional[Callable] = None):
        self.converter = converter
        self.max_workers = max_workers
        self.tasks: List[ConversionTask] = []
        self._tasks_lock = threading.Lock()
        self._cancel_event = threading.Event()
        self._on_task_done = on_task_done
        self._on_all_done = on_all_done

    def add_task(self, input_file: str, output_file: str, opts: ConvertOptions) -> int:
        with self._tasks_lock:
            task_id = len(self.tasks) + 1
            task = ConversionTask(task_id, input_file, output_file, opts)
            self.tasks.append(task)
            return task_id

    def cancel(self):
        self._cancel_event.set()
        self.converter.cleanup()

    def reset(self):
        with self._tasks_lock:
            self.tasks.clear()
        self._cancel_event.clear()
        self.converter.reset_cancellation()

    def process(self) -> List[bool]:
        with self._tasks_lock:
            tasks = list(self.tasks)
        total = len(tasks)
        if total == 0:
            return []
        if not self.converter.ffmpeg_path:
            self.converter.init()

        def _do_convert(task: ConversionTask) -> bool:
            if self._cancel_event.is_set():
                task.status = 'cancelled'
                return False
            task.status = 'running'
            try:
                success = self.converter.convert(
                    task.input_file, task.output_file, task.opts
                )
                task.status = 'completed' if success else 'failed'
                task.result = success
                return success
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, TypeError, AttributeError) as e:
                task.status = 'failed'
                task.result = False
                logger.error(f"任务 {task.id} 异常: {e}", exc_info=True)
                return False

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {}
            for task in tasks:
                if self._cancel_event.is_set():
                    task.status = 'cancelled'
                    continue
                future = executor.submit(_do_convert, task)
                future_to_task[future] = task

            results_map = {}
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    success = future.result()
                    results_map[task.id] = success
                    if self._on_task_done:
                        self._on_task_done(task, success)
                except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, TypeError, AttributeError) as e:
                    results_map[task.id] = False
                    logger.error(f"任务 {task.id} 异常: {e}")
                    if self._on_task_done:
                        self._on_task_done(task, False)

        results = [results_map.get(t.id, False) for t in tasks]
        success_count = sum(1 for r in results if r)
        if self._on_all_done:
            self._on_all_done(success_count, total)
        return results
