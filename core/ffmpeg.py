import os
import sys
import subprocess
import logging
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger('MediaConverter')


class FFmpegManager:
    """FFmpeg 路径查找与 GPU 检测"""

    def __init__(self):
        if getattr(sys, 'frozen', False):
            self.base_dir = Path(sys._MEIPASS)
            self.app_dir = Path(sys.executable).parent
        else:
            self.base_dir = Path(__file__).parent.parent
            self.app_dir = self.base_dir
        self.ffmpeg_path: Optional[str] = None
        self.ffprobe_path: Optional[str] = None
        self.gpu_type: Optional[str] = None
        self._hwaccel: Optional[str] = None

    def find_ffmpeg(self) -> Optional[str]:
        paths = [
            self.base_dir / "ffmpeg.exe",
            self.base_dir / "ffmpeg" / "ffmpeg.exe",
            self.app_dir / "ffmpeg.exe",
            self.app_dir / "ffmpeg" / "ffmpeg.exe",
        ]
        for p in paths:
            if p.exists() and self._verify(str(p)):
                self.ffmpeg_path = str(p)
                self._find_ffprobe()
                return self.ffmpeg_path
        try:
            result = subprocess.run(
                ['where', 'ffmpeg'], capture_output=True, text=True,
                encoding='utf-8', errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0:
                path = result.stdout.strip().split('\n')[0]
                if self._verify(path):
                    self.ffmpeg_path = path
                    self._find_ffprobe()
                    return self.ffmpeg_path
        except (OSError, subprocess.SubprocessError):
            pass
        return None

    def _find_ffprobe(self):
        if self.ffmpeg_path:
            base = Path(self.ffmpeg_path).parent
            probe = base / 'ffprobe.exe'
            if probe.exists():
                try:
                    r = subprocess.run(
                        [str(probe), '-version'], capture_output=True,
                        text=True, encoding='utf-8', errors='replace',
                        timeout=5, creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    if r.returncode == 0 and 'version' in r.stdout:
                        self.ffprobe_path = str(probe)
                        return
                except (OSError, subprocess.SubprocessError):
                    pass
            self.ffprobe_path = None

    def _verify(self, path: str) -> bool:
        try:
            r = subprocess.run(
                [path, '-version'], capture_output=True,
                text=True, encoding='utf-8', errors='replace',
                timeout=5, creationflags=subprocess.CREATE_NO_WINDOW
            )
            return r.returncode == 0 and 'version' in r.stdout
        except (OSError, subprocess.SubprocessError):
            return False

    def get_version(self) -> str:
        if not self.ffmpeg_path:
            return ""
        try:
            r = subprocess.run(
                [self.ffmpeg_path, '-version'], capture_output=True, text=True,
                encoding='utf-8', errors='replace',
                timeout=5, creationflags=subprocess.CREATE_NO_WINDOW
            )
            return r.stdout.split()[2] if r.stdout and len(r.stdout.split()) > 2 else 'unknown'
        except (OSError, subprocess.SubprocessError, IndexError):
            return 'unknown'

    def detect_gpu(self) -> Tuple[Optional[str], Optional[str]]:
        if not self.ffmpeg_path:
            return None, None
        try:
            r = subprocess.run(
                [self.ffmpeg_path, '-encoders'], capture_output=True,
                text=True, encoding='utf-8', errors='replace',
                timeout=10, creationflags=subprocess.CREATE_NO_WINDOW
            )
            output = r.stdout
            if 'h264_nvenc' in output or 'hevc_nvenc' in output or 'av1_nvenc' in output:
                self.gpu_type, self._hwaccel = 'nvidia', 'cuda'
            elif 'h264_amf' in output or 'hevc_amf' in output or 'av1_amf' in output:
                self.gpu_type, self._hwaccel = 'amd', 'd3d11va'
            elif 'h264_qsv' in output or 'hevc_qsv' in output or 'av1_qsv' in output:
                self.gpu_type, self._hwaccel = 'intel', 'qsv'
        except (OSError, subprocess.SubprocessError):
            pass
        return self.gpu_type, self._hwaccel

    @property
    def hwaccel(self) -> Optional[str]:
        return self._hwaccel

    @property
    def gpu_name(self) -> str:
        names = {'nvidia': 'NVIDIA (NVENC)', 'amd': 'AMD (AMF)', 'intel': 'Intel (QSV)'}
        return names.get(self.gpu_type, '')
