import os
import re
import sys
import subprocess
import logging
from pathlib import Path
from typing import Optional, List, Callable, Dict

from .options import ConvertOptions
from .ffmpeg import FFmpegManager
from .history import HistoryManager
from .validators import validate_extra_args, validate_output_dir

logger = logging.getLogger('MediaConverter')


class MediaConverter:
    """媒体转换核心引擎（UI 无关）"""

    VIDEO_EXTS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.ts', '.m2ts'}
    IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.tiff', '.tif', '.ico', '.raw', '.cr2', '.nef'}
    AUDIO_EXTS = {'.mp3', '.wav', '.aac', '.flac', '.ogg', '.m4a', '.wma'}

    # 回调类型：on_log(level, message), on_progress(message), on_complete(success, output_path)
    def __init__(self, on_log: Optional[Callable] = None, on_progress: Optional[Callable] = None):
        self._on_log = on_log or (lambda lvl, msg: None)
        self._on_progress = on_progress or (lambda msg: None)
        self._ffmpeg_mgr = FFmpegManager()
        self.history = HistoryManager()
        self._current_process: Optional[subprocess.Popen] = None

    @property
    def ffmpeg_path(self) -> Optional[str]:
        return self._ffmpeg_mgr.ffmpeg_path

    @property
    def ffprobe_path(self) -> Optional[str]:
        return self._ffmpeg_mgr.ffprobe_path

    @property
    def gpu_type(self) -> Optional[str]:
        return self._ffmpeg_mgr.gpu_type

    @property
    def hwaccel(self) -> Optional[str]:
        return self._ffmpeg_mgr.hwaccel

    @property
    def gpu_name(self) -> str:
        return self._ffmpeg_mgr.gpu_name

    def init(self) -> bool:
        """初始化：查找 FFmpeg 并检测 GPU"""
        path = self._ffmpeg_mgr.find_ffmpeg()
        if not path:
            self._on_log('error', '未找到 FFmpeg，请将 ffmpeg.exe 放在程序目录')
            return False
        ver = self._ffmpeg_mgr.get_version()
        self._on_log('info', f'FFmpeg: {ver}')
        self._ffmpeg_mgr.detect_gpu()
        if self.gpu_type:
            self._on_log('info', f'GPU 加速: {self.gpu_name}')
        else:
            self._on_log('info', '未检测到 GPU，使用 CPU 软解')
        return True

    def cleanup(self):
        """终止正在运行的子进程"""
        if self._current_process and self._current_process.poll() is None:
            try:
                self._current_process.terminate()
                self._current_process.wait(timeout=3)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    self._current_process.kill()
                except OSError:
                    pass

    def get_info(self, filepath: str) -> dict:
        """获取媒体信息"""
        if not self.ffprobe_path:
            return {}
        cmd = [
            self.ffprobe_path, '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,duration,r_frame_rate,codec_name,bit_rate',
            '-show_entries', 'format=duration,size,bit_rate,format_name',
            '-of', 'default=noprint_wrappers=1',
            filepath
        ]
        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding='utf-8', errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            info = {}
            for line in r.stdout.split('\n'):
                if '=' in line:
                    k, v = line.split('=', 1)
                    info[k] = v
            return info
        except (OSError, subprocess.SubprocessError):
            return {}

    def get_file_summary(self, filepath: str) -> Dict:
        """获取文件摘要信息（供 GUI 展示）"""
        info = self.get_info(filepath)
        if not info:
            return {'valid': False}
        try:
            codec = info.get('codec_name', 'unknown').upper()
            width = int(info.get('width', 0) or 0)
            height = int(info.get('height', 0) or 0)
            duration_sec = float(info.get('duration', info.get('format.duration', 0)) or 0)
            size_bytes = int(info.get('size', info.get('format.size', 0)) or 0)
            bitrate = int(info.get('bit_rate', info.get('format.bit_rate', 0)) or 0)
        except (ValueError, TypeError):
            codec = 'unknown'
            width = height = duration_sec = size_bytes = bitrate = 0

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
        }

    def estimate_output_size(self, input_file: str, opts: ConvertOptions) -> Optional[float]:
        """预估输出文件大小（MB）"""
        info = self.get_info(input_file)
        if not info:
            return None
        try:
            duration = float(info.get('duration', info.get('format.duration', 0)) or 0)
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
        except (ValueError, ZeroDivisionError, TypeError):
            pass
        return None

    def _build_filter(self, opts: ConvertOptions) -> List[str]:
        filters = []
        if opts.width or opts.height:
            w = opts.width or -1
            h = opts.height or -1
            if w == -1:
                filters.append(f"scale=-1:{h}")
            elif h == -1:
                filters.append(f"scale={w}:-1")
            else:
                filters.append(f"scale={w}:{h}")
        if opts.fps:
            filters.append(f"fps={opts.fps}")
        if filters:
            return ['-vf', ','.join(filters)]
        return []

    def _get_gpu_encoder(self, ext: str) -> Optional[str]:
        gpu_encoders = {'nvidia': 'h264_nvenc', 'amd': 'h264_amf', 'intel': 'h264_qsv'}
        gpu_codec = gpu_encoders.get(self.gpu_type)
        if gpu_codec and ext in ('.mp4', '.mov', '.mkv', '.m4v', '.flv', '.avi'):
            return gpu_codec
        return None

    def _get_gpu_quality_args(self, quality: int) -> List[str]:
        if self.gpu_type == 'nvidia':
            return ['-cq', str(quality)]
        elif self.gpu_type == 'amd':
            return ['-qp_i', str(quality), '-qp_p', str(quality)]
        elif self.gpu_type == 'intel':
            return ['-global_quality', str(quality)]
        return ['-crf', str(quality)]

    def _map_gpu_preset(self, preset: str) -> str:
        if self.gpu_type == 'nvidia':
            p_map = {
                'ultrafast': 'p1', 'superfast': 'p2', 'veryfast': 'p3',
                'faster': 'p4', 'fast': 'p4', 'medium': 'p5',
                'slow': 'p6', 'slower': 'p7', 'veryslow': 'p7'
            }
            return p_map.get(preset, 'p4')
        return preset

    def _build_video_opts(self, output_ext: str, opts: ConvertOptions) -> List[str]:
        args = []
        args.extend(self._build_filter(opts))
        ext = output_ext.lower()
        codec_map = {
            '.mp4': 'libx264', '.mov': 'libx264', '.m4v': 'libx264',
            '.avi': 'libxvid', '.mkv': 'libx264', '.webm': 'libvpx-vp9',
            '.wmv': 'wmv2', '.flv': 'libx264', '.gif': 'gif',
        }
        if opts.use_gpu and self.gpu_type:
            gpu_codec = self._get_gpu_encoder(ext)
            if gpu_codec:
                for k in list(codec_map.keys()):
                    if k not in ('.webm', '.wmv', '.gif'):
                        codec_map[k] = gpu_codec
        if opts.codec:
            args.extend(['-c:v', opts.codec])
        elif ext in codec_map:
            if ext == '.gif':
                quality = opts.quality if opts.quality is not None else 5
                max_colors = min(256, max(32, 32 + quality * 24))
                args.extend([
                    '-vf',
                    f"fps={opts.fps or 30},scale={opts.width or 480}:-1:flags=lanczos,"
                    f"split[s0][s1];[s0]palettegen=max_colors={max_colors}[p];[s1][p]paletteuse",
                    '-loop', '0'
                ])
                return args
            else:
                args.extend(['-c:v', codec_map[ext]])
        if opts.quality is not None:
            if opts.use_gpu and self.gpu_type and self._get_gpu_encoder(ext):
                args.extend(self._get_gpu_quality_args(opts.quality))
            else:
                args.extend(['-crf', str(opts.quality)])
        elif opts.bitrate:
            args.extend(['-b:v', opts.bitrate])
        if opts.preset:
            if opts.use_gpu and self.gpu_type and self._get_gpu_encoder(ext):
                args.extend(['-preset', self._map_gpu_preset(opts.preset)])
            else:
                args.extend(['-preset', opts.preset])
        if opts.audio_bitrate:
            args.extend(['-c:a', 'aac', '-b:a', opts.audio_bitrate])
        else:
            args.extend(['-c:a', 'aac', '-b:a', '192k'])
        if opts.extra_args:
            args.extend(validate_extra_args(opts.extra_args))
        return args

    def _build_image_opts(self, output_ext: str, opts: ConvertOptions) -> List[str]:
        args = []
        vf = []
        if opts.width or opts.height:
            w = opts.width or -1
            h = opts.height or -1
            vf.append(f"scale={w}:{h}:flags=lanczos")
        q = opts.quality if opts.quality is not None else 2
        ext = output_ext.lower()
        if ext in ['.jpg', '.jpeg']:
            vf.append("format=yuvj420p")
            args.extend(['-q:v', str(min(max(q, 2), 31))])
        elif ext == '.png':
            compression = min(max((q // 3), 0), 9)
            args.extend(['-compression_level', str(compression)])
        elif ext == '.webp':
            args.extend(['-q:v', str(min(max(q, 1), 100))])
        if vf:
            args.extend(['-vf', ','.join(vf)])
        args.append('-y')
        return args

    def _get_output_path(self, input_file: str, suffix: str, ext: str, opts: ConvertOptions) -> str:
        input_path = Path(input_file)
        if opts.output_dir:
            validated = validate_output_dir(opts.output_dir)
            if validated:
                output_dir = Path(validated)
                output_dir.mkdir(parents=True, exist_ok=True)
            else:
                output_dir = input_path.parent
        else:
            output_dir = input_path.parent
        output_name = f"{input_path.stem}_{suffix}.{ext}"
        return str(output_dir / output_name)

    def _build_img_to_video_cmd(self, input_file: str, opts: ConvertOptions) -> List[str]:
        duration = opts.trim_duration or "5"
        codec = opts.codec
        if not codec and opts.use_gpu:
            codec = self._get_gpu_encoder('.mp4')
        if not codec:
            codec = 'libx264'
        cmd = [
            self.ffmpeg_path, '-loop', '1',
            '-i', input_file, '-c:v', codec,
            '-t', str(duration), '-pix_fmt', 'yuv420p'
        ]
        cmd.extend(self._build_filter(opts))
        if opts.quality is not None:
            if opts.use_gpu and self.gpu_type:
                cmd.extend(self._get_gpu_quality_args(opts.quality))
            else:
                cmd.extend(['-crf', str(opts.quality)])
        return cmd

    def _run_ffmpeg(self, cmd: List[str], input_file: str, output_file: str,
                    output_ext: str, opts: ConvertOptions, add_to_history: bool = True) -> bool:
        process = None
        try:
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding='utf-8', errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            self._current_process = process
            for line in process.stdout:
                line = line.strip()
                if any(x in line for x in ['frame=', 'size=', 'time=', 'out_time_ms']):
                    self._on_progress(line)
            process.wait()
            if process.returncode == 0:
                size = os.path.getsize(output_file) / 1024 / 1024
                self._on_log('info', f'转换成功: {size:.2f} MB')
                logger.info(f"转换成功: {input_file} -> {output_file} ({size:.2f} MB)")
                if add_to_history:
                    target_format = output_ext.replace('.', '')
                    self.history.add_record(input_file, target_format, opts)
                return True
            self._on_log('error', '转换失败')
            logger.error(f"转换失败，返回码: {process.returncode}")
            return False
        except Exception as e:
            self._on_log('error', f'错误: {e}')
            logger.error(f"FFmpeg 执行错误: {e}", exc_info=True)
            return False
        finally:
            self._current_process = None

    def convert(self, input_file: str, output_file: str,
                opts: Optional[ConvertOptions] = None, add_to_history: bool = True) -> bool:
        """通用转换接口"""
        if not os.path.exists(input_file):
            self._on_log('error', f'文件不存在: {input_file}')
            return False
        opts = opts or ConvertOptions()
        input_path = Path(input_file)
        output_path = Path(output_file)
        input_ext = input_path.suffix.lower()
        output_ext = output_path.suffix.lower()
        is_video_input = input_ext in self.VIDEO_EXTS or input_ext in {'.gif'}
        is_image_input = input_ext in self.IMAGE_EXTS
        is_video_output = output_ext in self.VIDEO_EXTS or output_ext == '.gif'

        cmd = [self.ffmpeg_path]
        if is_video_input and is_video_output and opts.use_gpu and self.hwaccel:
            cmd.extend(['-hwaccel', self.hwaccel])
        if opts.start_time:
            cmd.extend(['-ss', opts.start_time])
        if opts.trim_duration:
            cmd.extend(['-t', opts.trim_duration])
        cmd.extend(['-i', input_file])

        if is_video_output:
            if is_image_input:
                self._on_log('info', '图片转视频模式')
                cmd = self._build_img_to_video_cmd(input_file, opts)
            else:
                cmd.extend(self._build_video_opts(output_ext, opts))
        else:
            if is_video_input:
                self._on_log('info', '视频转图片模式（提取第一帧）')
                if not opts.start_time:
                    cmd.extend(['-ss', '00:00:01'])
                cmd.extend(['-vframes', '1'])
            cmd.extend(self._build_image_opts(output_ext, opts))

        cmd.append(output_file)
        return self._run_ffmpeg(cmd, input_file, output_file, output_ext, opts, add_to_history)

    def get_default_opts(self, target_format: str, media_type: str = 'video') -> ConvertOptions:
        """获取格式的默认推荐参数"""
        if media_type == 'video':
            presets = {
                'mp4': ConvertOptions(quality=23, preset='medium'),
                'avi': ConvertOptions(codec='libxvid'),
                'mkv': ConvertOptions(),
                'mov': ConvertOptions(quality=23),
                'wmv': ConvertOptions(),
                'webm': ConvertOptions(quality=28),
                'gif': ConvertOptions(width=480, fps=15, quality=10),
            }
            return presets.get(target_format, ConvertOptions())
        else:
            quality_map = {
                'jpg': 2, 'jpeg': 2, 'png': 2,
                'webp': 85, 'bmp': None, 'gif': None,
            }
            return ConvertOptions(quality=quality_map.get(target_format, 2))
