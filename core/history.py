import os
import json
import sys
import threading
import tempfile
import logging
from pathlib import Path
from dataclasses import asdict
from datetime import datetime
from typing import Optional, List, Dict

from .options import ConvertOptions
from .constants import MAX_HISTORY_RECORDS

logger = logging.getLogger('MediaConverter')





class HistoryManager:
    """转换历史记录管理器"""

    def __init__(self):
        if getattr(sys, 'frozen', False):
            self.history_dir = Path(sys.executable).parent / "history"
        else:
            self.history_dir = Path(__file__).parent.parent / "history"
        self.history_file = self.history_dir / "history.json"
        self.max_history = MAX_HISTORY_RECORDS
        self._lock = threading.Lock()

    def _ensure_dir(self):
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def load_history(self) -> List[Dict]:
        if not self.history_file.exists():
            return []
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict) or not isinstance(data.get('recent'), list):
                logger.warning(f"历史记录结构异常，已重置: {self.history_file}")
                return []
            return data.get('recent', [])
        except (json.JSONDecodeError, OSError, KeyError, AttributeError) as e:
            logger.warning(f"加载历史记录失败: {e}")
            return []

    def save_history(self, history: List[Dict]):
        self._ensure_dir()
        tmp_fd = None
        tmp_path = None
        try:
            tmp_fd, tmp_path = tempfile.mkstemp(
                dir=str(self.history_dir), suffix='.tmp', prefix='history_'
            )
            os.close(tmp_fd)
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump({'recent': history}, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, str(self.history_file))
        except OSError as e:
            logger.error(f"保存历史记录失败: {e}")
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    def add_record(self, input_file: str, output_format: str, options: ConvertOptions, output_file: str = ''):
        with self._lock:
            history = self.load_history()
            record = {
                'file': str(input_file),
                'format': output_format,
                'output': str(output_file) if output_file else '',
                'options': {k: v for k, v in asdict(options).items() if v is not None},
                'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            history = [h for h in history if not (h.get('file') == str(input_file) and h.get('format') == output_format)]
            history.insert(0, record)
            history = history[:self.max_history]
            self.save_history(history)

    def get_recent(self, count: int = 10) -> List[Dict]:
        with self._lock:
            return self.load_history()[:count]

    def delete_record(self, index: int) -> bool:
        with self._lock:
            history = self.load_history()
            if 0 <= index < len(history):
                history.pop(index)
                self.save_history(history)
                return True
            return False

    def clear_history(self):
        with self._lock:
            self.save_history([])
