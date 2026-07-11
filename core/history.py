import os
import json
import threading
import logging
from pathlib import Path
from dataclasses import asdict
from datetime import datetime
from typing import Optional, List, Dict

from .options import ConvertOptions

logger = logging.getLogger('MediaConverter')

_local_app_data = os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local'))
HISTORY_DIR = Path(_local_app_data) / 'FFmpegConverter'


class HistoryManager:
    """转换历史记录管理器"""

    def __init__(self):
        self.history_dir = HISTORY_DIR
        self.history_file = self.history_dir / "history.json"
        self.max_history = 20
        self._lock = threading.Lock()

    def _ensure_dir(self):
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def load_history(self) -> List[Dict]:
        if not self.history_file.exists():
            return []
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('recent', [])
        except (json.JSONDecodeError, OSError, KeyError) as e:
            logger.warning(f"加载历史记录失败: {e}")
            return []

    def save_history(self, history: List[Dict]):
        self._ensure_dir()
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump({'recent': history}, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.error(f"保存历史记录失败: {e}")

    def add_record(self, input_file: str, output_format: str, options: ConvertOptions):
        with self._lock:
            history = self.load_history()
            record = {
                'file': str(input_file),
                'format': output_format,
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
