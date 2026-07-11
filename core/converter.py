import os
import re
import sys
import subprocess
import logging
import threading
from pathlib import Path
from typing import Optional, List, Callable, Dict

from .options import ConvertOptions
from .ffmpeg import FFmpegManager
from .history import HistoryManager
from .validators import validate_extra_args, validate_output_dir
from .constants import VIDEO_EXTS, IMAGE_EXTS, AUDIO_EXTS

logger = logging.getLogger('MediaConverter')


class MediaConverter:

    def __init__(self, on_log: Optional[Callable] = None, on_progress: Optional[Callable] = None):
        self._on_log = on_log or (lambda lvl, msg: None)
        self._on_progress = on_progress or (lambda msg: None)
        self._on_progress_pct: Callable = lambda pct: None
        self._on_eta: Callable = lambda eta: None
        self._ffmpeg_mgr = FFmpegManager()
        self.history = HistoryManager()
        self._active_processes: set = set()
        self._process_lock = threading.Lock()

    def set_callbacks(self, on_log=None, on_progress=None, on_progress_pct=None, on_eta=None):
        if on_log is not None:
            self._on_log = on_log
        if on_progress is not None:
            self._on_progress = on_progress
        if on_progress_pct is not None:
            self._on_progress_pct = on_progress_pct
        if on_eta is not None:
            self._on_eta = on_eta

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
        with self._process_lock:
            procs = list(self._active_processes)
            self._active_processes.clear()
        for proc in procs:
            if proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=3)
                except (OSError, subprocess.TimeoutExpired):
                    try:
                        proc.kill()
                        proc.wait(timeout=2)
                    except (OSError, subprocess.TimeoutExpired):
                        pass

    def get_info(self, filepath: str) -> dict:
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

    def get_audio_duration(self, filepath: str) -> float:
        if not self.ffprobe_path:
            return 0.0
        cmd = [
            self.ffprobe_path, '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            filepath
        ]
        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding='utf-8', errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW
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
        if opts.crop_w and opts.crop_h:
            filters.append(f"crop={opts.crop_w}:{opts.crop_h}:{opts.crop_x}:{opts.crop_y}")
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
        elif self.gpu_type == 'amd':
            p_map = {
                'ultrafast': 'speed', 'superfast': 'speed', 'veryfast': 'speed',
                'faster': 'speed', 'fast': 'balanced',
                'medium': 'balanced',
                'slow': 'quality', 'slower': 'quality', 'veryslow': 'quality'
            }
            return p_map.get(preset, 'balanced')
        elif self.gpu_type == 'intel':
            p_map = {
                'ultrafast': 'veryfast', 'superfast': 'veryfast', 'veryfast': 'veryfast',
                'faster': 'faster', 'fast': 'medium',
                'medium': 'medium',
                'slow': 'slow', 'slower': 'very_slow', 'veryslow': 'very_slow'
            }
            return p_map.get(preset, 'medium')
        return preset

    def _build_video_opts(self, output_ext: str, opts: ConvertOptions) -> List[str]:
        args = []
        ext = output_ext.lower()

        if ext == '.gif':
            return self._build_gif_opts(opts)

        args.extend(self._build_filter(opts))
        codec_map = {
            '.mp4': 'libx264', '.mov': 'libx264', '.m4v': 'libx264',
            '.avi': 'libxvid', '.mkv': 'libx264', '.webm': 'libvpx-vp9',
            '.wmv': 'wmv2', '.flv': 'libx264',
            '.ts': 'mpeg2video', '.m2ts': 'h264',
        }
        if opts.use_gpu and self.gpu_type:
            gpu_codec = self._get_gpu_encoder(ext)
            if gpu_codec:
                for k in list(codec_map.keys()):
                    if k not in ('.webm', '.wmv'):
                        codec_map[k] = gpu_codec
        if opts.codec:
            args.extend(['-c:v', opts.codec])
        elif ext in codec_map:
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

        args.extend(self._build_audio_opts(ext, opts))
        if opts.extra_args:
            args.extend(validate_extra_args(opts.extra_args))
        return args

    def _build_gif_opts(self, opts: ConvertOptions) -> List[str]:
        quality = opts.quality if opts.quality is not None else 5
        max_colors = min(256, max(32, 32 + quality * 24))
        filter_parts = []
        w = opts.width or -1
        h = opts.height or -1
        if w == -1 and h == -1:
            w = 480
        filter_parts.append(f"scale={w}:{h}:flags=lanczos")
        fps_val = opts.fps or 30
        filter_parts.append(f"fps={fps_val}")
        filter_parts.append(f"split[s0][s1];[s0]palettegen=max_colors={max_colors}[p];[s1][p]paletteuse")
        return ['-vf', ','.join(filter_parts), '-loop', '0']

    def _build_audio_opts(self, ext: str, opts: ConvertOptions) -> List[str]:
        if opts.remove_audio:
            return ['-an']
        audio_codec_map = {
            '.webm': 'libopus', '.wmv': 'wmav2',
            '.mp4': 'aac', '.mov': 'aac', '.m4v': 'aac',
            '.mkv': 'aac', '.avi': 'aac', '.flv': 'aac',
            '.mp3': 'libmp3lame', '.wav': 'pcm_s16le',
            '.aac': 'aac', '.flac': 'flac', '.ogg': 'libvorbis',
            '.m4a': 'aac', '.wma': 'wmav2',
        }
        codec = opts.audio_codec or audio_codec_map.get(ext, 'aac')
        br = opts.audio_bitrate or '192k'
        return ['-c:a', codec, '-b:a', br]

    def _build_image_opts(self, output_ext: str, opts: ConvertOptions) -> List[str]:
        args = []
        vf = []
        if opts.width or opts.height:
            w = opts.width or -1
            h = opts.height or -1
            vf.append(f"scale={w}:{h}:flags=lanczos")
        q = opts.quality if opts.quality is not None else 85
        ext = output_ext.lower()
        if ext in ['.jpg', '.jpeg']:
            vf.append("format=yuvj420p")
            jpeg_q = max(2, min(31, 32 - int((q / 100) * 30)))
            args.extend(['-q:v', str(jpeg_q)])
        elif ext == '.png':
            compression = 9 - min(9, max(0, int((q / 100) * 9)))
            args.extend(['-compression_level', str(compression)])
        elif ext == '.webp':
            args.extend(['-q:v', str(min(max(q, 1), 100))])
        if vf:
            args.extend(['-vf', ','.join(vf)])
        return args

    def _build_stream_copy_cmd(self, output_ext: str, opts: ConvertOptions) -> List[str]:
        args = ['-map_metadata', '0']
        if opts.remove_audio:
            args.extend(['-c:v', 'copy', '-an'])
        elif opts.replace_audio_file:
            args.extend(['-c:v', 'copy', '-c:a', 'copy'])
        else:
            args.extend(['-c:v', 'copy', '-c:a', 'copy'])
        return args

    def _build_img_to_video_cmd(self, input_file: str, opts: ConvertOptions, prefix: List[str]) -> List[str]:
        duration = opts.trim_duration or "5"
        codec = opts.codec
        if not codec and opts.use_gpu:
            codec = self._get_gpu_encoder('.mp4')
        if not codec:
            codec = 'libx264'
        cmd = list(prefix)
        cmd.extend([
            '-loop', '1',
            '-i', input_file, '-c:v', codec,
            '-t', str(duration), '-pix_fmt', 'yuv420p'
        ])
        cmd.extend(self._build_filter(opts))
        if opts.quality is not None:
            if opts.use_gpu and self.gpu_type:
                cmd.extend(self._get_gpu_quality_args(opts.quality))
            else:
                cmd.extend(['-crf', str(opts.quality)])
        return cmd

    def detect_crop(self, filepath: str) -> Optional[Dict]:
        if not self.ffmpeg_path:
            return None
        cmd = [self.ffmpeg_path, '-i', filepath, '-vf', 'cropdetect=24:2',
               '-f', 'null', '-']
        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding='utf-8', errors='replace',
                timeout=30, creationflags=subprocess.CREATE_NO_WINDOW
            )
            for line in reversed(r.stderr.split('\n')):
                m = re.search(r'crop=(\d+):(\d+):(\d+):(\d+)', line)
                if m:
                    return {'w': int(m.group(1)), 'h': int(m.group(2)),
                            'x': int(m.group(3)), 'y': int(m.group(4))}
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
        return None

    def extract_thumbnail(self, input_file: str, output_image: str, time_sec: float = 1.0) -> bool:
        if not self.ffmpeg_path:
            return False
        cmd = [self.ffmpeg_path, '-y', '-ss', str(time_sec),
               '-i', input_file, '-vframes', '1', '-q:v', '2', output_image]
        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding='utf-8', errors='replace',
                timeout=30, creationflags=subprocess.CREATE_NO_WINDOW
            )
            return r.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def export_file_info(self, input_file: str, output_path: str, format: str = 'txt') -> bool:
        info = self.get_file_summary(input_file)
        if not info or not info.get('valid'):
            return False
        import json
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

    def concat_videos(self, input_files: List[str], output_file: str,
                      stream_copy: bool = True) -> bool:
        if not self.ffmpeg_path or len(input_files) < 2:
            return False

        total_duration = 0.0
        for f in input_files:
            info = self.get_file_summary(f)
            if info and info.get('duration'):
                total_duration += info['duration']

        import tempfile
        filelist = tempfile.NamedTemporaryFile(mode='w', suffix='.txt',
                                               delete=False, encoding='utf-8')
        try:
            for f in input_files:
                escaped = f.replace("'", "'\\''")
                filelist.write(f"file '{escaped}'\n")
            filelist.close()
            cmd = [self.ffmpeg_path, '-y', '-f', 'concat', '-safe', '0',
                   '-i', filelist.name]
            if stream_copy:
                cmd.extend(['-c', 'copy'])
            cmd.extend(['-map_metadata', '0', output_file])

            if total_duration > 0:
                opts = ConvertOptions(trim_duration=str(total_duration))
            else:
                opts = ConvertOptions()
            success = self._run_ffmpeg(cmd, input_files[0], output_file,
                                       Path(output_file).suffix, opts)
            return success
        except (OSError, ValueError) as e:
            logger.error(f"拼接失败: {e}")
            return False
        finally:
            try:
                os.unlink(filelist.name)
            except OSError:
                pass

    def _parse_time_to_seconds(self, time_str: str) -> float:
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

    def _parse_ffmpeg_progress(self, line: str, total_duration: float) -> Optional[int]:
        match = re.search(r'time=(\d+):(\d+):(\d+)\.(\d+)', line)
        if match and total_duration > 0:
            h, m, s, cs_str = match.groups()
            current = int(h) * 3600 + int(m) * 60 + int(s) + int(cs_str) / 100
            return min(100, int(current / total_duration * 100))
        return None

    def _run_ffmpeg(self, cmd: List[str], input_file: str, output_file: str,
                    output_ext: str, opts: ConvertOptions, add_to_history: bool = True) -> bool:
        process = None
        try:
            total_duration = self.get_audio_duration(input_file)
            if opts.trim_duration:
                parsed = self._parse_time_to_seconds(opts.trim_duration)
                if parsed > 0:
                    total_duration = parsed

            with self._process_lock:
                process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding='utf-8', errors='replace',
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                self._active_processes.add(process)

            for line in process.stdout:
                line = line.strip()
                if any(x in line for x in ['frame=', 'size=', 'time=', 'out_time_ms']):
                    self._on_progress(line)
                    pct = self._parse_ffmpeg_progress(line, total_duration)
                    if pct is not None:
                        self._on_progress_pct(pct)
                    time_match = re.search(r'time=(\d+):(\d+):(\d+)\.(\d+)', line)
                    speed_match = re.search(r'speed=([\d.]+)x', line)
                    if time_match and speed_match and total_duration > 0:
                        speed = float(speed_match.group(1))
                        if speed > 0:
                            h, m, s, cs = time_match.groups()
                            current = int(h)*3600 + int(m)*60 + int(s) + int(cs)/100
                            remaining = max(0, total_duration - current) / speed
                            hrs, rem = divmod(int(remaining), 60)
                            mins, secs = divmod(rem, 60)
                            if hrs > 0:
                                self._on_eta(f"ETA {hrs}:{mins:02d}:{secs:02d}")
                            else:
                                self._on_eta(f"ETA {mins}:{secs:02d}")

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
        except (OSError, subprocess.SubprocessError, ValueError) as e:
            self._on_log('error', f'错误: {e}')
            logger.error(f"FFmpeg 执行错误: {e}", exc_info=True)
            return False
        finally:
            if process is not None:
                if process.poll() is None:
                    try:
                        process.terminate()
                        process.wait(timeout=3)
                    except (OSError, subprocess.TimeoutExpired):
                        try:
                            process.kill()
                        except OSError:
                            pass
                with self._process_lock:
                    self._active_processes.discard(process)

    def convert(self, input_file: str, output_file: str,
                opts: Optional[ConvertOptions] = None, add_to_history: bool = True) -> bool:
        if not os.path.exists(input_file):
            self._on_log('error', f'文件不存在: {input_file}')
            return False
        opts = opts or ConvertOptions()
        input_path = Path(input_file)
        output_path = Path(output_file)
        input_ext = input_path.suffix.lower()
        output_ext = output_path.suffix.lower()

        is_video_input = input_ext in VIDEO_EXTS or input_ext == '.gif'
        is_image_input = input_ext in IMAGE_EXTS
        is_audio_input = input_ext in AUDIO_EXTS
        is_video_output = output_ext in VIDEO_EXTS or output_ext == '.gif'
        is_image_output = output_ext in IMAGE_EXTS
        is_audio_output = output_ext in AUDIO_EXTS

        cmd = [self.ffmpeg_path, '-y']
        if is_video_input and is_video_output and opts.use_gpu and self.hwaccel:
            cmd.extend(['-hwaccel', self.hwaccel])
        if opts.start_time:
            cmd.extend(['-ss', opts.start_time])
        if opts.trim_duration:
            cmd.extend(['-t', opts.trim_duration])
        cmd.extend(['-i', input_file])

        if opts.replace_audio_file and is_video_output:
            cmd.extend(['-i', opts.replace_audio_file, '-c:v', 'copy', '-c:a', 'copy',
                        '-map', '0:v:0', '-map', '1:a:0', '-map_metadata', '0',
                        '-shortest'])
            cmd.append(output_file)
            return self._run_ffmpeg(cmd, input_file, output_file, output_ext, opts, add_to_history)

        if opts.stream_copy and is_video_output and not is_image_input:
            self._on_log('info', '流复制模式（不重编码）')
            cmd.extend(self._build_stream_copy_cmd(output_ext, opts))
            cmd.append(output_file)
            return self._run_ffmpeg(cmd, input_file, output_file, output_ext, opts, add_to_history)

        if is_video_output:
            if is_image_input:
                self._on_log('info', '图片转视频模式')
                prefix = [self.ffmpeg_path, '-y']
                if opts.use_gpu and self.hwaccel:
                    prefix.extend(['-hwaccel', self.hwaccel])
                if opts.start_time:
                    prefix.extend(['-ss', opts.start_time])
                cmd = self._build_img_to_video_cmd(input_file, opts, prefix)
                cmd.extend(['-map_metadata', '0'])
                cmd.append(output_file)
                return self._run_ffmpeg(cmd, input_file, output_file, output_ext, opts, add_to_history)
            else:
                cmd.extend(self._build_video_opts(output_ext, opts))
        elif is_image_output:
            if is_video_input:
                self._on_log('info', '视频转图片模式（提取第一帧）')
                if not opts.start_time:
                    cmd.extend(['-ss', '00:00:00'])
                cmd.extend(['-vframes', '1'])
            cmd.extend(self._build_image_opts(output_ext, opts))
        elif is_audio_output:
            if is_video_input:
                self._on_log('info', '视频提取音频模式')
                cmd.extend(['-vn'])
            cmd.extend(self._build_audio_opts(output_ext, opts))

        cmd.extend(['-map_metadata', '0'])
        cmd.append(output_file)
        return self._run_ffmpeg(cmd, input_file, output_file, output_ext, opts, add_to_history)

    def get_default_opts(self, target_format: str, media_type: str = 'video') -> ConvertOptions:
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
                'jpg': 85, 'jpeg': 85, 'png': 85,
                'webp': 85, 'bmp': None, 'gif': None,
            }
            return ConvertOptions(quality=quality_map.get(target_format, 85))
