import logging
from typing import List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from .options import ConvertOptions

logger = logging.getLogger('MediaConverter')


class ConversionTask:
    """单个转换任务"""
    def __init__(self, task_id: int, input_file: str, output_file: str, opts: ConvertOptions):
        self.id = task_id
        self.input_file = input_file
        self.output_file = output_file
        self.opts = opts
        self.status: str = 'waiting'  # waiting, running, completed, failed, cancelled
        self.result: Optional[bool] = None


class ConversionQueue:
    """批量转换队列"""

    def __init__(self, converter, max_workers: int = 2,
                 on_task_done: Optional[Callable] = None,
                 on_all_done: Optional[Callable] = None):
        self.converter = converter
        self.max_workers = max_workers
        self.tasks: List[ConversionTask] = []
        self._cancel_all = False
        self._on_task_done = on_task_done      # (task: ConversionTask, success: bool)
        self._on_all_done = on_all_done        # (success_count, total)

    def add_task(self, input_file: str, output_file: str, opts: ConvertOptions) -> int:
        task_id = len(self.tasks) + 1
        task = ConversionTask(task_id, input_file, output_file, opts)
        self.tasks.append(task)
        return task_id

    def cancel(self):
        self._cancel_all = True
        self.converter.cleanup()

    def reset(self):
        self.tasks.clear()
        self._cancel_all = False

    def process(self) -> List[bool]:
        """处理所有任务，返回结果列表"""
        self._cancel_all = False
        results = []
        total = len(self.tasks)
        if total == 0:
            return results

        def _do_convert(task: ConversionTask) -> bool:
            if self._cancel_all:
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
            except Exception as e:
                task.status = 'failed'
                task.result = False
                logger.error(f"任务 {task.id} 异常: {e}", exc_info=True)
                return False

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {}
            for task in self.tasks:
                if self._cancel_all:
                    task.status = 'cancelled'
                    results.append(False)
                    continue
                future = executor.submit(_do_convert, task)
                future_to_task[future] = task

            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    success = future.result()
                    results.append(success)
                    if self._on_task_done:
                        self._on_task_done(task, success)
                except Exception as e:
                    results.append(False)
                    if self._on_task_done:
                        self._on_task_done(task, False)

        success_count = sum(1 for r in results if r)
        if self._on_all_done:
            self._on_all_done(success_count, total)
        return results
