import os
import re
import sys
import hashlib
import subprocess
import logging
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger('MediaConverter')

_VERSION_RE = re.compile(r'ffmpeg version (\S+)')


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
        if self.ffmpeg_path and Path(self.ffmpeg_path).exists():
            return self.ffmpeg_path
        paths = [
            self.base_dir / "ffmpeg.exe",
            self.base_dir / "ffmpeg" / "ffmpeg.exe",
            self.app_dir / "ffmpeg.exe",
            self.app_dir / "ffmpeg" / "ffmpeg.exe",
        ]
        ffmpeg_env = os.environ.get('FFMPEG_PATH', '')
        if ffmpeg_env:
            p = Path(ffmpeg_env) / "ffmpeg.exe"
            if not p.exists():
                p = Path(ffmpeg_env)
            if p.exists():
                paths.insert(0, p)
        for p in paths:
            if p.exists() and self._verify(str(p)):
                self.ffmpeg_path = str(p)
                self._find_ffprobe()
                self._verify_ffmpeg_hash()
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
                    self._verify_ffmpeg_hash()
                    return self.ffmpeg_path
        except (OSError, subprocess.SubprocessError):
            pass
        return None

    def _verify_ffmpeg_hash(self):
        if not self.ffmpeg_path:
            return
        try:
            hash_file = self.app_dir / "ffmpeg.sha256"
            if not hash_file.exists():
                hash_file.write_text(self._file_sha256(self.ffmpeg_path), encoding='utf-8')
                return
            try:
                st = os.stat(self.ffmpeg_path)
                fast_fingerprint = f"{st.st_mtime_ns}-{st.st_size}"
            except OSError:
                fast_fingerprint = None
            lines = hash_file.read_text(encoding='utf-8').strip().splitlines()
            stored_hash = lines[0] if lines else ''
            if fast_fingerprint is not None and len(lines) == 2 and lines[1] == fast_fingerprint:
                return
            current_hash = self._file_sha256(self.ffmpeg_path)
            if stored_hash != current_hash:
                logger.warning(
                    f"FFmpeg 二进制指纹已变更!\n"
                    f"  文件: {self.ffmpeg_path}\n"
                    f"  记录: {stored_hash}\n"
                    f"  当前: {current_hash}"
                )
            if fast_fingerprint is not None:
                hash_file.write_text(f"{current_hash}\n{fast_fingerprint}", encoding='utf-8')
        except OSError as e:
            logger.debug(f"FFmpeg 哈希校验失败: {e}")

    def _file_sha256(self, filepath: str) -> str:
        h = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                h.update(chunk)
        return h.hexdigest()

    def _find_ffprobe(self):
        if not self.ffmpeg_path:
            return
        base = Path(self.ffmpeg_path).parent
        probe = base / 'ffprobe.exe'
        if probe.exists():
            if self._verify_ffprobe(str(probe)):
                self.ffprobe_path = str(probe)
                return
        try:
            result = subprocess.run(
                ['where', 'ffprobe'], capture_output=True, text=True,
                encoding='utf-8', errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0:
                path = result.stdout.strip().split('\n')[0]
                if self._verify_ffprobe(path):
                    self.ffprobe_path = path
                    return
        except (OSError, subprocess.SubprocessError):
            pass
        self.ffprobe_path = None

    def _verify_ffprobe(self, path: str) -> bool:
        try:
            r = subprocess.run(
                [path, '-version'], capture_output=True,
                text=True, encoding='utf-8', errors='replace',
                timeout=5, creationflags=subprocess.CREATE_NO_WINDOW
            )
            return r.returncode == 0 and 'version' in r.stdout
        except (OSError, subprocess.SubprocessError):
            return False

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
            m = _VERSION_RE.search(r.stdout)
            return m.group(1) if m else 'unknown'
        except (OSError, subprocess.SubprocessError):
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
            candidates = [
                ('nvidia', ['h264_nvenc', 'hevc_nvenc', 'av1_nvenc'], 'cuda'),
                ('amd', ['h264_amf', 'hevc_amf', 'av1_amf'], 'd3d11va'),
                ('intel', ['h264_qsv', 'hevc_qsv', 'av1_qsv'], 'qsv'),
            ]
            for gpu_type, encoders, hwaccel in candidates:
                encoder = next((e for e in encoders if e in output), None)
                if encoder and self._verify_gpu_encoder(encoder):
                    self.gpu_type, self._hwaccel = gpu_type, hwaccel
                    break
        except (OSError, subprocess.SubprocessError):
            pass
        return self.gpu_type, self._hwaccel

    def _verify_gpu_encoder(self, encoder: str) -> bool:
        """用 1 帧实测确认编码器真正可用（无显卡时 nvenc/amf/qsv 会加载失败）。

        测试帧必须 >= 128x128：NVENC 对 H.264/HEVC/AV1 有最小帧尺寸下限，
        64x64 会报 "Frame Dimension less than the minimum supported value"。
        """
        try:
            r = subprocess.run(
                [self.ffmpeg_path, '-hide_banner', '-loglevel', 'error',
                 '-f', 'lavfi', '-i', 'color=size=256x256:rate=1:duration=1',
                 '-frames:v', '1', '-c:v', encoder, '-f', 'null', '-'],
                capture_output=True, text=True, encoding='utf-8', errors='replace',
                timeout=10, creationflags=subprocess.CREATE_NO_WINDOW
            )
            if r.returncode != 0:
                err = '\n'.join((r.stderr or '').strip().splitlines()[:3])
                logger.debug(f"GPU 编码器实测失败 {encoder}: {err}")
            return r.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    @property
    def hwaccel(self) -> Optional[str]:
        return self._hwaccel

    @property
    def gpu_name(self) -> str:
        names = {'nvidia': 'NVIDIA (NVENC)', 'amd': 'AMD (AMF)', 'intel': 'Intel (QSV)'}
        return names.get(self.gpu_type, '')
