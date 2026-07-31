import re
from typing import Optional

_PROGRESS_TIME_RE = re.compile(r'time=(\d+):(\d+):(\d+)\.(\d+)')
_PROGRESS_SPEED_RE = re.compile(r'speed=([\d.]+)x')


class ProgressParser:
    """FFmpeg 进度行解析与 ETA 计算（纯逻辑，无副作用）"""

    def parse_progress(self, line: str, total_duration: float) -> Optional[int]:
        match = _PROGRESS_TIME_RE.search(line)
        if match and total_duration > 0:
            current = self._match_to_seconds(match)
            return min(100, int(current / total_duration * 100))
        return None

    def parse_time_to_seconds(self, time_str: str) -> float:
        try:
            time_str = time_str.strip()
            if ':' in time_str:
                parts = time_str.split(':')
                if len(parts) == 3:
                    return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
                elif len(parts) == 2:
                    return int(parts[0]) * 60 + float(parts[1])
            return float(time_str)
        except (ValueError, TypeError):
            return 0.0

    def compute_eta(self, line: str, total_duration: float) -> Optional[str]:
        time_match = _PROGRESS_TIME_RE.search(line)
        speed_match = _PROGRESS_SPEED_RE.search(line)
        if time_match and speed_match and total_duration > 0:
            try:
                speed = float(speed_match.group(1))
            except ValueError:
                return None
            if speed > 0:
                current = self._match_to_seconds(time_match)
                remaining = max(0, total_duration - current) / speed
                hrs, rem = divmod(int(remaining), 3600)
                mins, secs = divmod(rem, 60)
                if hrs > 0:
                    return f"ETA {hrs}:{mins:02d}:{secs:02d}"
                return f"ETA {mins}:{secs:02d}"
        return None

    def _match_to_seconds(self, match) -> float:
        h, m, s, us_str = match.groups()
        return int(h) * 3600 + int(m) * 60 + int(s) + int(us_str.rjust(6, '0')) / 1000000
