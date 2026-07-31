import os
import json
import re
import tempfile
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
from .probe import MediaProbe
from .command_builder import CommandBuilder
from .progress_parser import ProgressParser

logger = logging.getLogger('MediaConverter')

_FFMPEG_ERROR_RE = re.compile(
    r'\b(error|invalid|failed|unable|no such|not found|permission denied|'
    r'cannot|denied|aborted|doesn.t exist)\b', re.IGNORECASE)


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
        self._callback_lock = threading.Lock()
        self._cancel_event = threading.Event()
        self._cancel_gen = 0
        self._probe = MediaProbe(self._ffmpeg_mgr)
        self._cmd_builder = CommandBuilder(self._ffmpeg_mgr)
        self._progress = ProgressParser()

    def set_callbacks(self, on_log=None, on_progress=None, on_progress_pct=None, on_eta=None):
        with self._callback_lock:
            if on_log is not None:
                self._on_log = on_log
            if on_progress is not None:
                self._on_progress = on_progress
            if on_progress_pct is not None:
                self._on_progress_pct = on_progress_pct
            if on_eta is not None:
                self._on_eta = on_eta

    def reset_callbacks(self):
        """清除回调引用（worker 完成/失败后调用），防止悬空闭包指向已删除的 QThread。"""
        with self._callback_lock:
            self._on_log = lambda lvl, msg: None
            self._on_progress = lambda msg: None
            self._on_progress_pct = lambda pct: None
            self._on_eta = lambda eta: None

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
        self._cancel_event.set()
        with self._process_lock:
            self._cancel_gen += 1
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

    def reset_cancellation(self):
        """用户显式开始新任务前的授权调用：解除上次取消状态并递增代际。

        取消是单向的 —— `cleanup()`/`cancel()` 之后，任何在途或排队中的
        `convert()`/`concat_videos()` 调用都会被拒绝（代际不匹配），
        只有调用本方法后才能启动新任务，从而消除"取消后任务仍偷偷启动"的竞态。
        """
        with self._process_lock:
            self._cancel_gen += 1
            self._cancel_event.clear()

    # ── 探测委托 ──

    def get_info(self, filepath: str) -> dict:
        return self._probe.get_info(filepath)

    def get_duration(self, filepath: str) -> float:
        return self._probe.get_duration(filepath)

    def get_file_summary(self, filepath: str) -> Dict:
        return self._probe.get_file_summary(filepath)

    def estimate_output_size(self, input_file: str, opts: ConvertOptions) -> Optional[float]:
        return self._probe.estimate_output_size(input_file, opts)

    def detect_crop(self, filepath: str) -> Optional[Dict]:
        return self._probe.detect_crop(filepath)

    def extract_thumbnail(self, input_file: str, output_image: str, time_sec: float = 1.0) -> bool:
        return self._probe.extract_thumbnail(input_file, output_image, time_sec)

    def export_file_info(self, input_file: str, output_path: str, format: str = 'txt') -> bool:
        return self._probe.export_file_info(input_file, output_path, format)

    # ── 命令构建委托 ──

    def _build_filter(self, opts: ConvertOptions) -> List[str]:
        return self._cmd_builder.build_filter(opts)

    def _get_gpu_encoder(self, ext: str) -> Optional[str]:
        return self._cmd_builder.get_gpu_encoder(ext)

    def _get_gpu_quality_args(self, quality: int) -> List[str]:
        return self._cmd_builder.get_gpu_quality_args(quality)

    def _map_gpu_preset(self, preset: str) -> str:
        return self._cmd_builder.map_gpu_preset(preset)

    def _build_video_opts(self, output_ext: str, opts: ConvertOptions) -> List[str]:
        return self._cmd_builder.build_video_opts(output_ext, opts)

    def _build_gif_opts(self, opts: ConvertOptions) -> List[str]:
        return self._cmd_builder.build_gif_opts(opts)

    def _build_audio_opts(self, ext: str, opts: ConvertOptions) -> List[str]:
        return self._cmd_builder.build_audio_opts(ext, opts)

    def _build_image_opts(self, output_ext: str, opts: ConvertOptions) -> List[str]:
        return self._cmd_builder.build_image_opts(output_ext, opts)

    def _build_stream_copy_cmd(self, opts: ConvertOptions) -> List[str]:
        return self._cmd_builder.build_stream_copy_cmd(opts)

    def _build_img_to_video_cmd(self, input_file: str, opts: ConvertOptions, prefix: List[str]) -> List[str]:
        return self._cmd_builder.build_img_to_video_cmd(input_file, opts, prefix)

    # ── 进度解析委托 ──

    def _parse_time_to_seconds(self, time_str: str) -> float:
        return self._progress.parse_time_to_seconds(time_str)

    def _parse_ffmpeg_progress(self, line: str, total_duration: float) -> Optional[int]:
        return self._progress.parse_progress(line, total_duration)

    def concat_videos(self, input_files: List[str], output_file: str,
                      stream_copy: bool = True) -> bool:
        if not self.ffmpeg_path or len(input_files) < 2:
            return False

        total_duration = 0.0
        for f in input_files:
            info = self.get_file_summary(f)
            if info and info.get('duration'):
                total_duration += info['duration']

        filelist = tempfile.NamedTemporaryFile(mode='w', suffix='.txt',
                                                 delete=False, encoding='utf-8')
        filelist.close()
        try:
            with open(filelist.name, 'w', encoding='utf-8') as fh:
                for f in input_files:
                    escaped = f.replace("\\", "\\\\").replace("'", "'\\''").replace("\n", "_").replace("\r", "_")
                    fh.write(f"file '{escaped}'\n")
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

    def _run_ffmpeg(self, cmd: List[str], input_file: str, output_file: str,
                    output_ext: str, opts: ConvertOptions, add_to_history: bool = True,
                    gen: Optional[int] = None) -> bool:
        process = None
        try:
            total_duration = self.get_duration(input_file)
            if opts.trim_duration:
                parsed = self._progress.parse_time_to_seconds(opts.trim_duration)
                if parsed > 0:
                    total_duration = parsed
            if total_duration <= 0 and Path(input_file).suffix.lower() in IMAGE_EXTS:
                total_duration = 5.0

            with self._process_lock:
                if self._cancel_event.is_set():
                    return False
                if gen is not None and gen != self._cancel_gen:
                    return False
                process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding='utf-8', errors='replace',
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                self._active_processes.add(process)

            error_lines = []
            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue
                if any(x in line for x in ['frame=', 'size=', 'time=', 'out_time_ms']):
                    self._on_progress(line)
                    pct = self._progress.parse_progress(line, total_duration)
                    if pct is not None:
                        self._on_progress_pct(pct)
                    eta = self._progress.compute_eta(line, total_duration)
                    if eta:
                        self._on_eta(eta)
                elif _FFMPEG_ERROR_RE.search(line):
                    error_lines.append(line)
                    self._on_log('error', line)

            if total_duration > 0:
                max_wait = int(total_duration * 10 + 120)
            else:
                max_wait = 3600
            try:
                process.wait(timeout=max_wait)
            except subprocess.TimeoutExpired:
                self._on_log('error', f'转换超时 ({max_wait}s)，已终止')
                logger.error(f"FFmpeg 执行超时 ({max_wait}s)，强制终止")
                process.kill()
                process.wait(timeout=5)
                return False
            if process.returncode == 0:
                try:
                    size = os.path.getsize(output_file) / 1024 / 1024
                except OSError as e:
                    logger.warning(f"输出文件大小获取失败: {e}")
                    size = 0.0
                self._on_log('info', f'转换成功: {size:.2f} MB')
                logger.info(f"转换成功: {input_file} -> {output_file} ({size:.2f} MB)")
                if add_to_history:
                    target_format = output_ext.replace('.', '')
                    self.history.add_record(input_file, target_format, opts, output_file)
                return True
            self._on_log('error', '转换失败')
            for line in error_lines[-3:]:
                self._on_log('error', line)
            logger.error(f"转换失败，返回码: {process.returncode}")
            return False
        except (OSError, subprocess.SubprocessError, ValueError, RuntimeError, TypeError, AttributeError) as e:
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
                stdout = getattr(process, 'stdout', None)
                if stdout is not None and hasattr(stdout, 'close'):
                    try:
                        stdout.close()
                    except (OSError, ValueError):
                        pass
                with self._process_lock:
                    self._active_processes.discard(process)

    def build_command(self, input_file: str, output_file: str,
                      opts: Optional[ConvertOptions] = None) -> Optional[List[str]]:
        """构建 FFmpeg 命令（不执行），返回命令列表或 None"""
        if not self.ffmpeg_path:
            return None
        if not os.path.exists(input_file):
            return None
        opts = opts or ConvertOptions()
        input_path = Path(input_file)
        output_path = Path(output_file)
        if opts.output_dir:
            validated = validate_output_dir(opts.output_dir)
            if validated is None:
                return None
        input_ext = input_path.suffix.lower()
        output_ext = output_path.suffix.lower()

        is_video_input = input_ext in VIDEO_EXTS or input_ext == '.gif'
        is_image_input = input_ext in IMAGE_EXTS
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
                        '-shortest', output_file])
            return cmd

        if opts.stream_copy and is_video_output and not is_image_input:
            cmd.extend(self._build_stream_copy_cmd(opts))
            cmd.append(output_file)
            return cmd

        if is_video_output:
            if is_image_input:
                prefix = [self.ffmpeg_path, '-y']
                if opts.use_gpu and self.hwaccel:
                    prefix.extend(['-hwaccel', self.hwaccel])
                if opts.start_time:
                    prefix.extend(['-ss', opts.start_time])
                cmd = self._build_img_to_video_cmd(input_file, opts, prefix)
                cmd.extend(['-map_metadata', '0'])
                cmd.append(output_file)
                return cmd
            else:
                cmd.extend(self._build_video_opts(output_ext, opts))
        elif is_image_output:
            if is_video_input:
                if not opts.start_time:
                    cmd.extend(['-ss', '00:00:00'])
                cmd.extend(['-vframes', '1'])
            cmd.extend(self._build_image_opts(output_ext, opts))
        elif is_audio_output:
            if is_video_input:
                cmd.extend(['-vn'])
            cmd.extend(self._build_audio_opts(output_ext, opts))

        cmd.extend(['-map_metadata', '0'])
        cmd.append(output_file)
        return cmd

    def convert(self, input_file: str, output_file: str,
                opts: Optional[ConvertOptions] = None, add_to_history: bool = True) -> bool:
        with self._process_lock:
            if self._cancel_event.is_set():
                self._on_log('error', '上次操作已取消，请重新开始')
                return False
            gen = self._cancel_gen
        if not self.ffmpeg_path:
            self._on_log('error', 'FFmpeg 未初始化，请先调用 init()')
            return False
        if not os.path.exists(input_file):
            self._on_log('error', f'文件不存在: {input_file}')
            return False
        opts = opts or ConvertOptions()
        if opts.output_dir:
            validated = validate_output_dir(opts.output_dir)
            if validated is None:
                self._on_log('error', f'无效输出目录: {opts.output_dir}')
                return False

        input_ext = Path(input_file).suffix.lower()
        output_ext = Path(output_file).suffix.lower()
        is_video_input = input_ext in VIDEO_EXTS or input_ext == '.gif'
        is_image_input = input_ext in IMAGE_EXTS
        is_video_output = output_ext in VIDEO_EXTS or output_ext == '.gif'
        is_image_output = output_ext in IMAGE_EXTS
        is_audio_output = output_ext in AUDIO_EXTS

        if opts.replace_audio_file and is_video_output:
            self._on_log('info', '替换音频模式')
        elif opts.stream_copy and is_video_output and not is_image_input:
            self._on_log('info', '流复制模式（不重编码）')
        elif is_video_output and is_image_input:
            self._on_log('info', '图片转视频模式')
        elif is_image_output and is_video_input:
            self._on_log('info', '视频转图片模式（提取第一帧）')
        elif is_audio_output and is_video_input:
            self._on_log('info', '视频提取音频模式')

        cmd = self.build_command(input_file, output_file, opts)
        if cmd is None:
            self._on_log('error', '无法构建命令')
            return False
        return self._run_ffmpeg(cmd, input_file, output_file,
                                output_ext, opts, add_to_history, gen)

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
        elif media_type == 'audio':
            audio_presets = {
                'mp3': ConvertOptions(audio_codec='libmp3lame', audio_bitrate='192k'),
                'wav': ConvertOptions(audio_codec='pcm_s16le'),
                'aac': ConvertOptions(audio_codec='aac', audio_bitrate='192k'),
                'flac': ConvertOptions(audio_codec='flac'),
                'ogg': ConvertOptions(audio_codec='libvorbis', audio_bitrate='192k'),
                'm4a': ConvertOptions(audio_codec='aac', audio_bitrate='192k'),
                'wma': ConvertOptions(audio_codec='wmav2', audio_bitrate='192k'),
            }
            return audio_presets.get(target_format, ConvertOptions(audio_bitrate='192k'))
        else:
            quality_map = {
                'jpg': 85, 'jpeg': 85, 'png': 85,
                'webp': 85, 'bmp': None, 'gif': None,
            }
            return ConvertOptions(quality=quality_map.get(target_format, 85))
