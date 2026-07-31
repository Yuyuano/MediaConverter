import os
import json
import re
import subprocess
import logging
from collections import OrderedDict
from pathlib import Path
from typing import Optional, Dict

from .options import ConvertOptions
from .constants import FFMPEG_SUBPROCESS_TIMEOUT

logger = logging.getLogger('MediaConverter')

_CROP_DETECT_RE = re.compile(r'crop=(\d+):(\d+):(\d+):(\d+)')

_INFO_CACHE_MAX = 200


class MediaProbe:
    """ffprobe 信息探测、缩略图提取、裁剪检测（带 filepath LRU 缓存）"""

    def __init__(self, ffmpeg_mgr):
        self._mgr = ffmpeg_mgr
        self._info_cache: OrderedDict[str, dict] = OrderedDict()

    @property
    def _ffmpeg_path(self) -> Optional[str]:
        return self._mgr.ffmpeg_path

    @property
    def _ffprobe_path(self) -> Optional[str]:
        return self._mgr.ffprobe_path

    def _cache_get(self, filepath: str) -> Optional[dict]:
        info = self._info_cache.get(filepath)
        if info is not None:
            self._info_cache.move_to_end(filepath)
        return info

    def _cache_put(self, filepath: str, info: dict):
        self._info_cache[filepath] = info
        self._info_cache.move_to_end(filepath)
        while len(self._info_cache) > _INFO_CACHE_MAX:
            self._info_cache.popitem(last=False)

    def get_info(self, filepath: str) -> dict:
        cached = self._cache_get(filepath)
        if cached is not None:
            return cached
        info = self._probe_raw(filepath)
        if info:
            self._cache_put(filepath, info)
        return info

    def _probe_raw(self, filepath: str) -> dict:
        if not self._ffprobe_path:
            return {}
        filepath = os.path.abspath(filepath)
        cmd = [
            self._ffprobe_path, '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,duration,r_frame_rate,codec_name,bit_rate',
            '-show_entries', 'format=duration,size,bit_rate,format_name',
            '-of', 'json',
            filepath
        ]
        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding='utf-8', errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=FFMPEG_SUBPROCESS_TIMEOUT
            )
            if r.returncode != 0 or not r.stdout.strip():
                return {}
            data = json.loads(r.stdout)
            return self._flatten_info(data)
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError, ValueError):
            return {}

    def _flatten_info(self, data: dict) -> dict:
        info = {}
        streams = data.get('streams') or []
        if streams:
            s = streams[0]
            for k in ('width', 'height', 'duration', 'r_frame_rate', 'codec_name', 'bit_rate'):
                if k in s and s[k] is not None:
                    info[k] = str(s[k])
        fmt = data.get('format') or {}
        for k in ('duration', 'size', 'bit_rate', 'format_name'):
            if k in fmt and fmt[k] is not None:
                info[k] = str(fmt[k])
        return info

    def get_duration(self, filepath: str) -> float:
        info = self.get_info(filepath)
        if info:
            try:
                return float(info.get('duration', 0) or 0)
            except (ValueError, TypeError):
                return 0.0
        if not self._ffprobe_path:
            return 0.0
        filepath = os.path.abspath(filepath)
        cmd = [
            self._ffprobe_path, '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            filepath
        ]
        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding='utf-8', errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=FFMPEG_SUBPROCESS_TIMEOUT
            )
            return float(r.stdout.strip()) if r.stdout.strip() else 0.0
        except (OSError, subprocess.SubprocessError, ValueError):
            return 0.0

    def get_file_summary(self, filepath: str) -> Dict:
        info = self.get_info(filepath)
        if not info:
            return {'valid': False}
        try:
            codec = info.get('codec_name', 'unknown').upper()
            width = int(info.get('width', 0) or 0)
            height = int(info.get('height', 0) or 0)
            duration_sec = float(info.get('duration', 0) or 0)
            size_bytes = int(info.get('size', 0) or 0)
            bitrate = int(info.get('bit_rate', 0) or 0)
            fps = 0.0
            r_frame_rate = info.get('r_frame_rate', '')
            if r_frame_rate and '/' in r_frame_rate:
                num, den = r_frame_rate.split('/', 1)
                if float(den) != 0:
                    fps = round(float(num) / float(den), 2)
            elif r_frame_rate:
                try:
                    fps = round(float(r_frame_rate), 2)
                except ValueError:
                    fps = 0.0
        except (ValueError, TypeError):
            codec = 'unknown'
            width = height = duration_sec = size_bytes = bitrate = fps = 0

        size_mb = size_bytes / (1024 * 1024)
        return {
            'valid': True,
            'codec': codec,
            'format_name': info.get('format_name', 'unknown'),
            'width': width,
            'height': height,
            'duration': duration_sec,
            'size_bytes': size_bytes,
            'size_mb': size_mb,
            'bitrate': bitrate,
            'fps': fps,
        }

    def estimate_output_size(self, input_file: str, opts: ConvertOptions) -> Optional[float]:
        info = self.get_info(input_file)
        if not info:
            return None
        try:
            duration = float(info.get('duration', 0) or 0)
            if duration == 0:
                return None
            if opts.bitrate:
                bitrate_str = opts.bitrate.lower()
                if bitrate_str.endswith('m'):
                    bitrate = float(bitrate_str[:-1]) * 1000000
                elif bitrate_str.endswith('k'):
                    bitrate = float(bitrate_str[:-1]) * 1000
                else:
                    bitrate = float(bitrate_str)
                total_bits = bitrate * duration
                size_mb = (total_bits / 8) / (1024 * 1024)
                audio_bitrate = 128000
                if opts.audio_bitrate:
                    ab_str = opts.audio_bitrate.lower()
                    if ab_str.endswith('k'):
                        audio_bitrate = float(ab_str[:-1]) * 1000
                    elif ab_str.endswith('m'):
                        audio_bitrate = float(ab_str[:-1]) * 1000000
                audio_size_mb = (audio_bitrate * duration / 8) / (1024 * 1024)
                return size_mb + audio_size_mb
            if opts.quality is not None:
                input_size_mb = int(info.get('size', 0) or 0) / (1024 * 1024)
                quality_factor = (23 - opts.quality) / 6
                return input_size_mb * (2 ** quality_factor)
        except (ValueError, ZeroDivisionError, TypeError) as e:
            logger.debug(f"无法估算输出大小: {e}")
        return None

    def detect_crop(self, filepath: str) -> Optional[Dict]:
        if not self._ffmpeg_path:
            return None
        cmd = [self._ffmpeg_path, '-i', os.path.abspath(filepath), '-vf', 'cropdetect=24:2',
               '-f', 'null', '-']
        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding='utf-8', errors='replace',
                timeout=FFMPEG_SUBPROCESS_TIMEOUT, creationflags=subprocess.CREATE_NO_WINDOW
            )
            for line in reversed(r.stderr.split('\n')):
                m = _CROP_DETECT_RE.search(line)
                if m:
                    return {'w': int(m.group(1)), 'h': int(m.group(2)),
                            'x': int(m.group(3)), 'y': int(m.group(4))}
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
        return None

    def extract_thumbnail(self, input_file: str, output_image: str, time_sec: float = 1.0) -> bool:
        if not self._ffmpeg_path:
            return False
        cmd = [self._ffmpeg_path, '-y', '-ss', str(time_sec),
               '-i', os.path.abspath(input_file), '-vframes', '1', '-q:v', '2', output_image]
        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding='utf-8', errors='replace',
                timeout=FFMPEG_SUBPROCESS_TIMEOUT, creationflags=subprocess.CREATE_NO_WINDOW
            )
            return r.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def export_file_info(self, input_file: str, output_path: str, format: str = 'txt') -> bool:
        info = self.get_file_summary(input_file)
        if not info or not info.get('valid'):
            return False
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                if format == 'json':
                    json.dump(info, f, ensure_ascii=False, indent=2)
                else:
                    path = Path(input_file)
                    f.write(f"文件: {path.name}\n")
                    f.write(f"路径: {input_file}\n")
                    f.write(f"大小: {info.get('size_mb', 0):.2f} MB\n")
                    f.write(f"格式: {info.get('format_name', 'unknown')}\n")
                    f.write(f"编码: {info.get('codec', 'unknown')}\n")
                    f.write(f"分辨率: {info.get('width', 0)}x{info.get('height', 0)}\n")
                    if info.get('fps'):
                        f.write(f"帧率: {info['fps']:.2f} fps\n")
                    dur = info.get('duration', 0)
                    if dur:
                        hrs, rem = divmod(int(dur), 3600)
                        mins, secs = divmod(rem, 60)
                        f.write(f"时长: {hrs}:{mins:02d}:{secs:02d}\n")
                    br = info.get('bitrate', 0)
                    if br:
                        f.write(f"比特率: {br/1000:.0f} kbps\n")
            return True
        except (OSError, ValueError) as e:
            logger.error(f"导出文件信息失败: {e}")
            return False
