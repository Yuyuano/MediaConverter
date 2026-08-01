# converter.py
import os
import sys
import subprocess
import shutil
import re
import json
import time
import signal
import atexit
import logging
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, List, Tuple, Dict
from datetime import datetime
from queue import Queue
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
except ImportError:
    init = lambda autoreset=True: None
    class Fore:
        RED = GREEN = YELLOW = CYAN = MAGENTA = BLUE = WHITE = RESET = ''
    class Style:
        RESET_ALL = DIM = BRIGHT = ''

# 日志配置
# 注意：legacy 模块，默认使用 LOCALAPPDATA；受限环境下创建失败时
# 回退到项目内 history/ 目录（与新版应用约定一致），保证导入不抛异常。
LOG_DIR = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local'))) / 'FFmpegConverter'
try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    LOG_DIR = Path(__file__).resolve().parent.parent / 'history' / 'FFmpegConverter'
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        LOG_DIR = Path.home()
logging.basicConfig(
    filename=str(LOG_DIR / 'converter.log'),
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    encoding='utf-8'
)
logger = logging.getLogger('MediaConverter')


def _c(prefix, msg, color=Fore.CYAN):
    """彩色输出辅助"""
    print(f"{color}{prefix}{Style.RESET_ALL} {msg}")


@dataclass
class ConvertOptions:
    """转换参数配置"""
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[int] = None
    quality: Optional[int] = None
    bitrate: Optional[str] = None
    audio_bitrate: Optional[str] = None
    codec: Optional[str] = None
    preset: Optional[str] = None
    extra_args: Optional[List[str]] = None
    output_dir: Optional[str] = None
    start_time: Optional[str] = None
    trim_duration: Optional[str] = None
    use_gpu: bool = False


class HistoryManager:
    """转换历史记录管理器"""

    def __init__(self):
        self.app_name = "FFmpegConverter"
        local_app_data = os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local'))
        self.history_dir = Path(local_app_data) / self.app_name
        self.history_file = self.history_dir / "history.json"
        self.max_history = 20

    def _ensure_dir(self):
        """确保历史记录目录存在"""
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def load_history(self) -> List[Dict]:
        """加载历史记录"""
        if not self.history_file.exists():
            return []
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('recent', [])
        except (json.JSONDecodeError, OSError, KeyError) as e:
            return []

    def save_history(self, history: List[Dict]):
        """保存历史记录"""
        self._ensure_dir()
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump({'recent': history}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[!] 保存历史记录失败: {e}")

    def add_record(self, input_file: str, output_format: str, options: ConvertOptions):
        """添加新的转换记录"""
        history = self.load_history()
        record = {
            'file': str(input_file),
            'format': output_format,
            'options': {k: v for k, v in asdict(options).items() if v is not None},
            'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        history = [h for h in history if h['file'] != str(input_file)]
        history.insert(0, record)
        history = history[:self.max_history]
        self.save_history(history)

    def show_history(self) -> Optional[Dict]:
        """显示历史记录并让用户选择"""
        history = self.load_history()
        if not history:
            print("\n[!] 暂无历史记录")
            return None
        print("\n[*] 最近转换记录:")
        print("-" * 60)
        for i, record in enumerate(history[:10], 1):
            filename = Path(record['file']).name
            opts_items = [(k, v) for k, v in record['options'].items() if k != 'output_dir'][:3]
            opts_str = ", ".join([f"{k}={v}" for k, v in opts_items])
            print(f"{i}. {filename} => {record['format']} ({opts_str})")
            print(f"   时间: {record['time']}")
        choice = input("\n选择要重新转换的序号 (1-10, 0取消): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(history):
            return history[int(choice) - 1]
        return None


class ConversionQueue:
    """转换队列管理器（支持并发和取消）"""

    def __init__(self, max_workers: int = 2):
        self.queue = Queue()
        self.max_workers = max_workers
        self.current_task = None
        self.cancel_all = False
        self.results = []
        self._lock = threading.Lock()

    def add_task(self, input_file: str, output_file: str, opts: ConvertOptions, task_id: int = None):
        """添加任务到队列"""
        task = {
            'id': task_id or self.queue.qsize() + 1,
            'input': input_file,
            'output': output_file,
            'options': opts,
            'status': 'waiting'
        }
        self.queue.put(task)
        return task['id']

    def cancel_current_task(self, converter=None):
        """标记取消当前任务并终止子进程"""
        with self._lock:
            self.cancel_all = True
        if converter and converter._current_process:
            converter._cleanup_process()
        print("\n[*] 正在取消所有任务...")

    def process_queue(self, converter) -> List[bool]:
        """处理队列中的所有任务"""
        self.results = []
        self.cancel_all = False
        tasks = []
        while not self.queue.empty():
            tasks.append(self.queue.get())
        total = len(tasks)
        if total == 0:
            return []
        print(f"\n[*] 开始批量转换，共 {total} 个文件，并发数: {self.max_workers}")
        print("-" * 60)
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {}
            for task in tasks:
                with self._lock:
                    if self.cancel_all:
                        task['status'] = 'cancelled'
                        self.results.append(False)
                        continue
                future = executor.submit(self._convert_wrapper, converter, task, total)
                future_to_task[future] = task
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    success = future.result()
                    with self._lock:
                        self.results.append(success)
                    print(f"\n[+] 任务 {task['id']}/{total} 完成: {'成功' if success else '失败'}")
                except Exception as e:
                    with self._lock:
                        print(f"\n[!] 任务 {task['id']} 异常: {e}")
                        self.results.append(False)
                    logger.error(f"任务 {task['id']} 异常: {e}")
        print(f"\n[*] 批量转换完成: {sum(self.results)}/{total} 成功")
        return self.results

    def _convert_wrapper(self, converter, task: Dict, total: int) -> bool:
        """包装转换方法，支持取消检测"""
        with self._lock:
            self.current_task = task['id']
            if self.cancel_all:
                task['status'] = 'cancelled'
                print(f"\n[!] 任务 {task['id']} 已取消")
                return False
        task['status'] = 'running'
        try:
            result = converter.convert(task['input'], task['output'], task['options'])
            task['status'] = 'completed' if result else 'failed'
            return result
        except Exception as e:
            task['status'] = 'failed'
            print(f"\n[!] 转换错误: {e}")
            logger.error(f"转换错误: {e}", exc_info=True)
            return False


class MediaConverter:
    VIDEO_EXTS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.ts', '.m2ts'}
    IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.tiff', '.tif', '.ico', '.raw', '.cr2', '.nef'}
    AUDIO_EXTS = {'.mp3', '.wav', '.aac', '.flac', '.ogg', '.m4a', '.wma'}

    # FFmpeg 安全参数白名单（不含值的纯 flag 和带值的 key）
    SAFE_FFMPEG_FLAGS = {
        '-movflags', '-pix_fmt', '-profile:v', '-level', '-tune',
        '-g', '-bf', '-refs', '-me_method', '-subq', '-trellis',
        '-directpred', '-flags', '-rc-lookahead', '-b_strategy',
        '-coder', '-partitions', '-weightb', '-weightp', '-8x8dct',
        '-fast-pskip', '-mixed-refs', '-keyint_min', '-sc_threshold',
        '-deblock', '-aq-mode', '-aq-strength', '-psy-rd', '-psy',
        '-sar', '-aspect', '-colorspace', '-color_primaries', '-color_trc',
        '-map', '-map_metadata', '-map_chapters', '-sn', '-dn', '-an',
        '-threads', '-max_muxing_queue_size', '-avoid_negative_ts',
    }

    def __init__(self):
        if getattr(sys, 'frozen', False):
            self.base_dir = Path(sys._MEIPASS)
            self.app_dir = Path(sys.executable).parent
        else:
            self.base_dir = Path(__file__).parent
            self.app_dir = self.base_dir
        self.ffmpeg_path = self._find_ffmpeg()
        self.ffprobe_path = self._find_ffprobe() if self.ffmpeg_path else None
        self.history = HistoryManager()
        self._current_process = None
        self.gpu_type = None
        self._hwaccel = None
        atexit.register(self._cleanup_process)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _cleanup_process(self):
        """终止正在运行的ffmpeg子进程"""
        if self._current_process and self._current_process.poll() is None:
            try:
                self._current_process.terminate()
                self._current_process.wait(timeout=3)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    self._current_process.kill()
                except OSError:
                    pass

    def _signal_handler(self, signum, frame):
        """信号处理：先杀子进程再退出"""
        self._cleanup_process()
        sys.exit(0)

    def _validate_extra_args(self, extra_args: List[str]) -> List[str]:
        """校验 extra_args 白名单，过滤危险参数"""
        if not extra_args:
            return []
        safe_args = []
        i = 0
        while i < len(extra_args):
            arg = extra_args[i]
            # 允许纯 flag（以 - 开头且在白名单中）
            if arg.startswith('-') and arg in self.SAFE_FFMPEG_FLAGS:
                safe_args.append(arg)
                # 如果下一个参数不是以 - 开头，认为是该 flag 的值
                if i + 1 < len(extra_args) and not extra_args[i + 1].startswith('-'):
                    i += 1
                    safe_args.append(extra_args[i])
            else:
                # 非白名单参数，跳过并警告
                print(f"[!] 已过滤不安全的 FFmpeg 参数: {arg}")
            i += 1
        return safe_args

    def _detect_gpu(self):
        """检测可用的GPU硬件编码器"""
        if not self.ffmpeg_path:
            return
        try:
            r = subprocess.run([self.ffmpeg_path, '-encoders'], capture_output=True,
                               text=True, encoding='utf-8', errors='replace',
                               timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
            output = r.stdout
            if 'h264_nvenc' in output:
                self.gpu_type = 'nvidia'
                self._hwaccel = 'cuda'
            elif 'h264_amf' in output:
                self.gpu_type = 'amd'
                self._hwaccel = 'd3d11va'
            elif 'h264_qsv' in output:
                self.gpu_type = 'intel'
                self._hwaccel = 'qsv'
        except Exception:
            pass

    def _get_gpu_encoder(self, ext: str) -> Optional[str]:
        """返回当前GPU对应的视频编码器"""
        gpu_encoders = {
            'nvidia': 'h264_nvenc',
            'amd': 'h264_amf',
            'intel': 'h264_qsv',
        }
        gpu_codec = gpu_encoders.get(self.gpu_type)
        if gpu_codec and ext in ('.mp4', '.mov', '.mkv', '.m4v', '.flv', '.avi'):
            return gpu_codec
        return None

    def _get_gpu_quality_args(self, quality: int) -> List[str]:
        """GPU编码器的质量参数"""
        if self.gpu_type == 'nvidia':
            return ['-cq', str(quality)]
        elif self.gpu_type == 'amd':
            return ['-qp_i', str(quality), '-qp_p', str(quality)]
        elif self.gpu_type == 'intel':
            return ['-global_quality', str(quality)]
        return ['-crf', str(quality)]

    def _map_gpu_preset(self, preset: str) -> str:
        """将CPU预设映射到GPU预设"""
        if self.gpu_type == 'nvidia':
            p_map = {'ultrafast': 'p1', 'superfast': 'p2', 'veryfast': 'p3',
                     'faster': 'p4', 'fast': 'p4', 'medium': 'p5',
                     'slow': 'p6', 'slower': 'p7', 'veryslow': 'p7'}
            return p_map.get(preset, 'p4')
        return preset

    def _find_ffmpeg(self):
        """查找ffmpeg"""
        paths = [
            self.base_dir / "ffmpeg.exe",
            self.base_dir / "ffmpeg" / "ffmpeg.exe",
            self.app_dir / "ffmpeg.exe",
            self.app_dir / "ffmpeg" / "ffmpeg.exe",
        ]
        for p in paths:
            if p.exists() and self._verify(str(p)):
                return str(p)
        try:
            result = subprocess.run(['where', 'ffmpeg'], capture_output=True, text=True,
                                    encoding='utf-8', errors='replace')
            if result.returncode == 0:
                path = result.stdout.strip().split('\n')[0]
                if self._verify(path):
                    return path
        except (OSError, subprocess.SubprocessError):
            pass
        return None

    def _find_ffprobe(self):
        base = Path(self.ffmpeg_path).parent
        probe = base / 'ffprobe.exe'
        return str(probe) if probe.exists() else None

    def _verify(self, path):
        try:
            r = subprocess.run([path, '-version'], capture_output=True,
                               text=True, encoding='utf-8', errors='replace',
                               timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
            return r.returncode == 0 and 'version' in r.stdout
        except (OSError, subprocess.SubprocessError):
            return False

    def check(self):
        if not self.ffmpeg_path:
            _c("[!]", "未找到 FFmpeg", Fore.RED)
            print("[!] 请将 ffmpeg.exe 和 ffprobe.exe 放在程序目录")
            logger.error("未找到 FFmpeg")
            input("\n按回车退出...")
            sys.exit(1)
        v = subprocess.run([self.ffmpeg_path, '-version'], capture_output=True, text=True,
                           encoding='utf-8', errors='replace',
                           creationflags=subprocess.CREATE_NO_WINDOW)
        ffmpeg_ver = v.stdout.split()[2] if v.stdout else 'OK'
        _c("[+]", f"FFmpeg: {ffmpeg_ver}", Fore.GREEN)
        logger.info(f"FFmpeg 版本: {ffmpeg_ver}")
        self._detect_gpu()
        if self.gpu_type:
            gpu_name = {'nvidia': 'NVIDIA (NVENC)', 'amd': 'AMD (AMF)', 'intel': 'Intel (QSV)'}
            _c("[+]", f"GPU 加速: {gpu_name.get(self.gpu_type, self.gpu_type)}", Fore.GREEN)
            logger.info(f"GPU: {self.gpu_type}")
        else:
            _c("[*]", "未检测到 GPU 硬件编码器，将使用 CPU 软解", Fore.YELLOW)
        return True

    def get_info(self, filepath: str) -> dict:
        """获取媒体信息"""
        if not self.ffprobe_path:
            return {}
        cmd = [
            self.ffprobe_path,
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,duration,r_frame_rate,codec_name,bit_rate',
            '-show_entries', 'format=duration,size,bit_rate,format_name',
            '-of', 'default=noprint_wrappers=1',
            filepath
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True,
                               encoding='utf-8', errors='replace',
                               creationflags=subprocess.CREATE_NO_WINDOW)
            info = {}
            for line in r.stdout.split('\n'):
                if '=' in line:
                    k, v = line.split('=', 1)
                    info[k] = v
            return info
        except (OSError, subprocess.SubprocessError):
            return {}

    def preview_file_info(self, filepath: str) -> Dict:
        """转换前文件信息预览（带智能建议）"""
        info = self.get_info(filepath)
        if not info:
            return {'valid': False}
        codec = info.get('codec_name', 'unknown').upper()
        try:
            width = int(info.get('width', 0) or 0)
            height = int(info.get('height', 0) or 0)
            duration_sec = float(info.get('duration', info.get('format.duration', 0)) or 0)
            size_bytes = int(info.get('size', info.get('format.size', 0)) or 0)
            bitrate = int(info.get('bit_rate', info.get('format.bit_rate', 0)) or 0)
        except (ValueError, TypeError):
            width, height, duration_sec, size_bytes, bitrate = 0, 0, 0, 0, 0
        duration_str = self._format_duration(duration_sec)
        size_mb = size_bytes / (1024 * 1024)
        size_str = f"{size_mb:.1f} MB" if size_mb < 1024 else f"{size_mb/1024:.2f} GB"
        resolution = f"{width}x{height}"
        resolution_desc = ""
        if width >= 3840:
            resolution_desc = " (4K)"
        elif width >= 1920:
            resolution_desc = " (1080p)"
        elif width >= 1280:
            resolution_desc = " (720p)"
        bitrate_mbps = bitrate / 1000000
        bitrate_str = f"{bitrate_mbps:.1f} Mbps" if bitrate > 0 else "Unknown"
        suggestions = []
        if size_mb > 1000:
            suggestions.append("文件较大，建议压缩或降低分辨率")
        if bitrate_mbps > 50:
            suggestions.append("码率较高，可适当降低以减小体积")
        if width > 1920 and duration_sec > 300:
            suggestions.append("高清长视频，建议转为720p节省空间")
        result = {
            'valid': True,
            'format': codec,
            'resolution': resolution + resolution_desc,
            'duration': duration_str,
            'size': size_str,
            'bitrate': bitrate_str,
            'suggestions': suggestions
        }
        print("\n[*] 文件信息:")
        print(f"    格式: {codec} / {info.get('format_name', 'unknown')}")
        print(f"    分辨率: {resolution}{resolution_desc}")
        print(f"    时长: {duration_str}")
        print(f"    大小: {size_str}")
        print(f"    码率: {bitrate_str}")
        if suggestions:
            print(f"\n    建议: {' | '.join(suggestions)}")
        return result

    def _format_duration(self, seconds: float) -> str:
        """格式化时长"""
        if seconds < 60:
            return f"{int(seconds)}秒"
        elif seconds < 3600:
            return f"{int(seconds//60)}:{int(seconds%60):02d}"
        else:
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = int(seconds % 60)
            return f"{h}:{m:02d}:{s:02d}"

    def preview_conversion_params(self, input_file: str, output_file: str, opts: ConvertOptions) -> bool:
        """实时预览转换参数（确认步骤）"""
        input_path = Path(input_file)
        output_path = Path(output_file)
        output_ext = output_path.suffix.lower()
        is_video = output_ext in self.VIDEO_EXTS or output_ext == '.gif'
        _c("[*]", "转换参数预览:", Fore.YELLOW)
        print(f"    输入文件: {input_path.name}")
        print(f"    输出格式: {output_ext.upper().replace('.', '')}")
        if is_video:
            resolution = f"{opts.width or '原图'}x{opts.height or '原图'}"
            quality_desc = f"CRF {opts.quality}" if opts.quality is not None else "默认质量"
            if opts.bitrate:
                quality_desc = f"码率 {opts.bitrate}"
            print(f"    分辨率: {resolution}")
            print(f"    质量: {quality_desc}")
            if opts.fps:
                print(f"    帧率: {opts.fps} fps")
            if opts.codec:
                print(f"    编码器: {opts.codec}")
            elif opts.use_gpu and self.gpu_type:
                gpu_codec = self._get_gpu_encoder(output_ext)
                if gpu_codec:
                    gpu_label = {'nvidia': 'NVIDIA NVENC', 'amd': 'AMD AMF', 'intel': 'Intel QSV'}
                    print(f"    编码器: {gpu_codec} ({gpu_label.get(self.gpu_type, 'GPU')})")
            if opts.preset:
                print(f"    预设: {opts.preset}")
        else:
            resolution = f"{opts.width or '原图'}x{opts.height or '原图'}"
            quality_desc = f"质量 {opts.quality}" if opts.quality is not None else "默认质量"
            print(f"    分辨率: {resolution}")
            print(f"    质量: {quality_desc}")
        output_dir = opts.output_dir or input_path.parent
        if opts.start_time or opts.trim_duration:
            trim_info = []
            if opts.start_time:
                trim_info.append(f"起始 {opts.start_time}")
            if opts.trim_duration:
                trim_info.append(f"时长 {opts.trim_duration}")
            print(f"    裁剪: {', '.join(trim_info)}")
        print(f"    输出目录: {output_dir}")
        print(f"    输出文件: {output_path.name}")
        confirm = input("\n确认开始转换? (Y/N): ").strip().upper()
        return confirm == 'Y' or confirm == 'YES'

    def estimate_output_size(self, input_file: str, opts: ConvertOptions) -> Optional[str]:
        """预估输出文件大小（用于智能压缩）"""
        info = self.get_info(input_file)
        if not info:
            return None
        try:
            duration = float(info.get('duration', info.get('format.duration', 0)))
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
                total_mb = size_mb + audio_size_mb
                return f"{total_mb:.1f} MB"
            if opts.quality is not None:
                input_size_mb = int(info.get('size', 0)) / (1024 * 1024)
                quality_factor = (23 - opts.quality) / 6
                estimated_mb = input_size_mb * (2 ** quality_factor)
                return f"{estimated_mb:.1f} MB"
        except (ValueError, ZeroDivisionError, TypeError):
            pass
        return None

    def _build_filter(self, opts: ConvertOptions) -> List[str]:
        """构建视频/图片滤镜"""
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

    def _build_video_opts(self, output_ext: str, opts: ConvertOptions) -> List[str]:
        """构建视频编码参数"""
        args = []
        args.extend(self._build_filter(opts))
        ext = output_ext.lower()
        codec_map = {
            '.mp4': 'libx264', '.mov': 'libx264', '.m4v': 'libx264',
            '.avi': 'libxvid',
            '.mkv': 'libx264',
            '.webm': 'libvpx-vp9',
            '.wmv': 'wmv2',
            '.flv': 'libx264',
            '.gif': 'gif',
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
                # quality 参数控制调色板颜色数量 (1-10 -> 32-256 colors)
                quality = opts.quality if opts.quality is not None else 5
                max_colors = min(256, max(32, 32 + quality * 24))
                args.extend([
                    '-vf',
                    f"fps={opts.fps or 30},scale={opts.width or 480}:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors={max_colors}[p];[s1][p]paletteuse",
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
            args.extend(self._validate_extra_args(opts.extra_args))
        return args

    def _build_image_opts(self, output_ext: str, opts: ConvertOptions) -> List[str]:
        """构建图片编码参数"""
        args = []
        vf = []
        if opts.width or opts.height:
            w = opts.width or -1
            h = opts.height or -1
            vf.append(f"scale={w}:{h}:flags=lanczos")
        q = opts.quality
        if q is None:
            q = 2
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

    @staticmethod
    def _validate_output_dir(output_dir: str) -> Optional[str]:
        """验证输出目录路径安全性，拒绝路径遍历"""
        if not output_dir:
            return None
        try:
            resolved = Path(output_dir).resolve()
            # 拒绝包含 .. 的原始路径（resolve 后已展开，需检查原始输入）
            if '..' in output_dir.split(os.sep) and '..' in output_dir:
                print(f"[!] 路径包含 '..'，已拒绝: {output_dir}")
                return None
            return str(resolved)
        except (OSError, ValueError) as e:
            print(f"[!] 无效路径: {e}")
            return None

    def _get_output_path(self, input_file: str, suffix: str, ext: str, opts: ConvertOptions) -> str:
        """构建输出路径（支持自定义目录）"""
        input_path = Path(input_file)
        if opts.output_dir:
            validated = self._validate_output_dir(opts.output_dir)
            if validated:
                output_dir = Path(validated)
                output_dir.mkdir(parents=True, exist_ok=True)
            else:
                output_dir = input_path.parent
        else:
            output_dir = input_path.parent
        output_name = f"{input_path.stem}_{suffix}.{ext}"
        return str(output_dir / output_name)

    def _print_output_info(self, input_path, output_path, opts):
        _c("[*]", f"输入: {input_path.name}")
        _c("[*]", f"输出: {output_path.name}")
        if opts.output_dir:
            _c("[*]", f"目录: {opts.output_dir}")
        if opts.width or opts.height:
            _c("[*]", f"尺寸: {opts.width or '自动'}x{opts.height or '自动'}")
        if opts.start_time or opts.trim_duration:
            trim_info = []
            if opts.start_time:
                trim_info.append(f"起始 {opts.start_time}")
            if opts.trim_duration:
                trim_info.append(f"时长 {opts.trim_duration}")
            _c("[*]", f"裁剪: {', '.join(trim_info)}")

    def _build_img_to_video_cmd(self, input_file, opts):
        duration = opts.trim_duration or "5"
        codec = opts.codec
        if not codec and opts.use_gpu:
            codec = self._get_gpu_encoder('.mp4')
        if not codec:
            codec = 'libx264'
        cmd = [
            self.ffmpeg_path,
            '-loop', '1',
            '-i', input_file,
            '-c:v', codec,
            '-t', str(duration),
            '-pix_fmt', 'yuv420p'
        ]
        cmd.extend(self._build_filter(opts))
        if opts.quality is not None:
            if opts.use_gpu and self.gpu_type:
                cmd.extend(self._get_gpu_quality_args(opts.quality))
            else:
                cmd.extend(['-crf', str(opts.quality)])
        return cmd

    def _run_ffmpeg(self, cmd, input_file, output_file, output_ext, opts, add_to_history):
        process = None
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True, encoding='utf-8', errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            self._current_process = process
            for line in process.stdout:
                line = line.strip()
                if any(x in line for x in ['frame=', 'size=', 'time=', 'out_time_ms']):
                    print(f"\r[*] {line[:60]}", end='', flush=True)
            process.wait()
            print()
            if process.returncode == 0:
                size = os.path.getsize(output_file) / 1024 / 1024
                _c("[+]", f"成功! 大小: {size:.2f} MB", Fore.GREEN)
                logger.info(f"转换成功: {input_file} -> {output_file} ({size:.2f} MB)")
                if add_to_history:
                    target_format = output_ext.replace('.', '')
                    self.history.add_record(input_file, target_format, opts)
                return True
            _c("[!]", "转换失败", Fore.RED)
            logger.error(f"转换失败，返回码: {process.returncode}")
            return False
        except Exception as e:
            _c("[!]", f"错误: {e}", Fore.RED)
            logger.error(f"FFmpeg 执行错误: {e}", exc_info=True)
            return False
        finally:
            self._current_process = None

    def convert(self, input_file: str, output_file: str, opts: Optional[ConvertOptions] = None, add_to_history: bool = True) -> bool:
        """通用转换接口"""
        if not os.path.exists(input_file):
            _c("[!]", f"文件不存在: {input_file}", Fore.RED)
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
        if is_video_input and is_video_output and opts.use_gpu and self._hwaccel:
            cmd.extend(['-hwaccel', self._hwaccel])
        if opts.start_time:
            cmd.extend(['-ss', opts.start_time])
        if opts.trim_duration:
            cmd.extend(['-t', opts.trim_duration])
        cmd.extend(['-i', input_file])

        if is_video_output:
            if is_image_input:
                _c("[*]", "图片转视频模式")
                cmd = self._build_img_to_video_cmd(input_file, opts)
            else:
                cmd.extend(self._build_video_opts(output_ext, opts))
        else:
            if is_video_input:
                _c("[*]", "视频转图片模式（提取第一帧）")
                if not opts.start_time:
                    cmd.extend(['-ss', '00:00:01'])
                cmd.extend(['-vframes', '1'])
            cmd.extend(self._build_image_opts(output_ext, opts))

        cmd.append(output_file)
        self._print_output_info(input_path, output_path, opts)
        return self._run_ffmpeg(cmd, input_file, output_file, output_ext, opts, add_to_history)

    def quick_video_convert(self, input_file: str, target_format: str, opts: Optional[ConvertOptions] = None):
        """一键视频转换（带参数预览）"""
        opts = opts or ConvertOptions()
        output = self._get_output_path(input_file, "converted", target_format, opts)
        presets = {
            'mp4': ConvertOptions(quality=23, preset='medium'),
            'avi': ConvertOptions(codec='libxvid'),
            'mkv': ConvertOptions(),
            'mov': ConvertOptions(quality=23),
            'wmv': ConvertOptions(),
            'webm': ConvertOptions(quality=28),
        }
        default_opts = presets.get(target_format, ConvertOptions())
        default_opts.output_dir = opts.output_dir
        default_opts.use_gpu = opts.use_gpu
        if opts.quality is not None:
            default_opts.quality = opts.quality
        if opts.preset:
            default_opts.preset = opts.preset
        if opts.start_time:
            default_opts.start_time = opts.start_time
        if opts.trim_duration:
            default_opts.trim_duration = opts.trim_duration
        if not self.preview_conversion_params(input_file, output, default_opts):
            print("[*] 已取消")
            return False
        return self.convert(input_file, output, default_opts)

    def quick_image_convert(self, input_file: str, target_format: str, opts: Optional[ConvertOptions] = None):
        """一键图片转换（带参数预览）"""
        opts = opts or ConvertOptions()
        output = self._get_output_path(input_file, "converted", target_format, opts)
        quality_map = {
            'jpg': 2, 'jpeg': 2,
            'png': 2,
            'webp': 85,
            'bmp': None,
            'gif': None,
        }
        default_opts = ConvertOptions(quality=quality_map.get(target_format, 2))
        default_opts.output_dir = opts.output_dir
        if not self.preview_conversion_params(input_file, output, default_opts):
            print("[*] 已取消")
            return False
        return self.convert(input_file, output, default_opts)

    def compress_media(self, input_file: str, target_size_mb: int = 50, opts: Optional[ConvertOptions] = None):
        """智能压缩（带大小预估）"""
        opts = opts or ConvertOptions()
        file_info = self.preview_file_info(input_file)
        if not file_info.get('valid'):
            print("[!] 无法获取文件信息")
            return False
        info = self.get_info(input_file)
        try:
            duration = float(info.get('duration', 0) or info.get('format.duration', 0) or 0)
        except (ValueError, TypeError):
            duration = 0
        if duration == 0:
            print("[!] 无法获取时长")
            return False
        target_bits = (target_size_mb * 8 * 1024 * 1024) / duration
        target_bits_safe = int(target_bits * 0.9)
        output = self._get_output_path(input_file, "compressed", "mp4", opts)
        comp_opts = ConvertOptions(
            bitrate=f"{target_bits_safe // 1024}k",
            audio_bitrate="128k",
            preset='slow',
            output_dir=opts.output_dir,
            use_gpu=opts.use_gpu
        )
        print(f"\n[*] 目标大小: {target_size_mb}MB")
        print(f"[*] 计算码率: {comp_opts.bitrate}")
        estimated_size = self.estimate_output_size(input_file, comp_opts)
        if estimated_size:
            print(f"[*] 预估输出大小: {estimated_size} (目标 {target_size_mb} MB)")
        if not self.preview_conversion_params(input_file, output, comp_opts):
            print("[*] 已取消")
            return False
        return self.convert(input_file, output, comp_opts)


def clear():
    os.system('cls')


def banner():
    print(Style.BRIGHT + Fore.MAGENTA + "=" * 60)
    print(Fore.CYAN + "    媒体格式转换工具 v2.0 (视频+图片)")
    print("    支持: 视频转视频 | 图片转图片 | 视频图片互转")
    print("    新增: 历史记录 | 批量队列 | 参数预览 | 视频裁剪")
    print("    By Yuyuan" + Style.RESET_ALL)
    print(Fore.MAGENTA + "=" * 60 + Style.RESET_ALL)


def parse_size(size_str: str) -> Tuple[Optional[int], Optional[int]]:
    """解析尺寸字符串"""
    if not size_str:
        return None, None
    m = re.match(r'(\d+)[xX](\d+)', size_str)
    if m:
        return int(m.group(1)), int(m.group(2))
    if size_str.lower() == '1080p':
        return 1920, 1080
    if size_str.lower() == '720p':
        return 1280, 720
    if size_str.lower() == '480p':
        return 854, 480
    if size_str.isdigit():
        return int(size_str), None
    return None, None


def get_file(prompt: str = "拖入文件: ") -> Optional[str]:
    f = input(prompt).strip().strip('"')
    return f if os.path.exists(f) else None


def get_output_dir() -> Optional[str]:
    """获取输出目录（新增）"""
    print("\n[输出目录]")
    print("1. 默认（与输入文件相同目录）")
    print("2. 自定义目录")
    choice = input("选择 [1-2]: ").strip()
    if choice == '2':
        d = input("输入目录路径: ").strip().strip('"')
        if not d:
            return None
        # 拒绝路径遍历
        if '..' in d.split(os.sep):
            print("[!] 路径包含 '..'，已拒绝")
            return None
        if os.path.isdir(d):
            return d
        try:
            Path(d).mkdir(parents=True, exist_ok=True)
            return d
        except OSError:
            print("[!] 无法创建目录，使用默认")
            return None
    return None


def get_trim_options(opts: ConvertOptions):
    """视频裁剪参数设置（直接回车跳过）"""
    start = input("\n视频裁剪起始时间 (如 00:01:30 或 90, 回车跳过): ").strip()
    if start:
        opts.start_time = start
        dur = input("裁剪时长 (如 00:00:30 或 30, 回车截取到结尾): ").strip()
        if dur:
            opts.trim_duration = dur


def advanced_options(gpu_available: bool = False) -> ConvertOptions:
    """交互式高级参数设置"""
    opts = ConvertOptions()
    print("\n[高级参数设置] (直接回车使用默认)")
    opts.output_dir = get_output_dir()
    if gpu_available:
        use_gpu = input("启用 GPU 硬件加速? (Y/N, 默认N): ").strip().upper()
        opts.use_gpu = use_gpu == 'Y' or use_gpu == 'YES'
    size = input("输出尺寸 (如 1920x1080, 1080p, 720p 或宽度): ").strip()
    if size:
        w, h = parse_size(size)
        opts.width = w
        opts.height = h
    q = input("质量等级 (视频:0-51,图片:2-31,默认自动): ").strip()
    if q.isdigit():
        opts.quality = int(q)
    fps = input("视频帧率 (如 30, 60): ").strip()
    if fps.isdigit():
        opts.fps = int(fps)
    br = input("视频码率 (如 2M, 5000k): ").strip()
    if br:
        opts.bitrate = br
    get_trim_options(opts)
    print("编码速度: ultrafast|superfast|veryfast|faster|fast|medium|slow|slower|veryslow")
    pr = input("选择预设: ").strip()
    if pr:
        opts.preset = pr
    return opts


def batch_convert_mode(conv: MediaConverter):
    """批量转换/队列模式"""
    print("\n[*] 批量转换模式")
    print("拖入多个文件（每行一个，输入空行结束）:")
    files = []
    while True:
        f = input().strip().strip('"')
        if not f:
            break
        if os.path.exists(f):
            files.append(f)
        else:
            print(f"[!] 文件不存在: {f}")
    if not files:
        print("[!] 没有有效文件")
        return
    print(f"\n[*] 已添加 {len(files)} 个文件到队列")
    print("\n选择转换格式:")
    print("1. MP4 (H.264)  2. AVI  3. MKV  4. MOV  5. WEBM")
    fmt_choice = input("选择 [1-5]: ").strip()
    formats = ['mp4', 'avi', 'mkv', 'mov', 'webm']
    target_format = formats[int(fmt_choice)-1] if fmt_choice.isdigit() and 1 <= int(fmt_choice) <= 5 else 'mp4'
    print("\n是否设置高级参数? (Y/N): ", end='')
    if input().strip().upper() == 'Y':
        opts = advanced_options(conv.gpu_type is not None)
    else:
        opts = ConvertOptions()
    workers = input("\n并发数 (1-4, 默认2): ").strip()
    max_workers = int(workers) if workers.isdigit() and 1 <= int(workers) <= 4 else 2
    queue = ConversionQueue(max_workers=max_workers)
    for i, f in enumerate(files, 1):
        output = conv._get_output_path(f, "batch", target_format, opts)
        queue.add_task(f, output, opts, task_id=i)
    queue.process_queue(conv)


def _quick_video_handler(fmt):
    def handler(conv):
        f = get_file("拖入视频文件: ")
        if f:
            conv.preview_file_info(f)
            output_dir = get_output_dir()
            opts = ConvertOptions(output_dir=output_dir)
            if conv.gpu_type and fmt in ('mp4', 'mov', 'mkv', 'avi', 'flv'):
                use_gpu = input("\n启用 GPU 硬件加速? (Y/N, 默认N): ").strip().upper()
                opts.use_gpu = use_gpu == 'Y' or use_gpu == 'YES'
            get_trim_options(opts)
            conv.quick_video_convert(f, fmt, opts)
        input("\n回车继续...")
    return handler


def _quick_image_handler(fmt):
    def handler(conv):
        f = get_file("拖入图片文件: ")
        if f:
            output_dir = get_output_dir()
            opts = ConvertOptions(output_dir=output_dir)
            conv.quick_image_convert(f, fmt, opts)
        input("\n回车继续...")
    return handler


def _video_to_gif(conv):
    f = get_file("拖入视频文件: ")
    if f:
        conv.preview_file_info(f)
        output_dir = get_output_dir()
        base = os.path.splitext(os.path.basename(f))[0]
        output = os.path.join(output_dir, f"{base}.gif") if output_dir else f"{os.path.splitext(f)[0]}.gif"
        opts = ConvertOptions(width=480, fps=15, quality=10, output_dir=output_dir)
        get_trim_options(opts)
        if conv.preview_conversion_params(f, output, opts):
            conv.convert(f, output, opts)
    input("\n回车继续...")


def _extract_audio(conv):
    f = get_file("拖入视频文件: ")
    if f:
        conv.preview_file_info(f)
        output_dir = get_output_dir()
        base = os.path.splitext(os.path.basename(f))[0]
        output = os.path.join(output_dir, f"{base}_audio.mp3") if output_dir else f"{os.path.splitext(f)[0]}_audio.mp3"
        opts = ConvertOptions(output_dir=output_dir)
        get_trim_options(opts)
        if conv.preview_conversion_params(f, output, opts):
            conv.convert(f, output, opts)
    input("\n回车继续...")


def _advanced_video(conv):
    f = get_file("拖入视频文件: ")
    if not f:
        input("\n回车继续...")
        return
    conv.preview_file_info(f)
    print("\n输出格式: mp4, avi, mkv, mov, wmv, flv, webm")
    fmt = input("输入格式: ").strip().lower()
    VALID_FMTS = {'mp4', 'avi', 'mkv', 'mov', 'wmv', 'flv', 'webm'}
    if fmt not in VALID_FMTS:
        print("[!] 不支持的格式")
        input("\n回车继续...")
        return
    opts = advanced_options(conv.gpu_type is not None)
    output = conv._get_output_path(f, "custom", fmt, opts)
    if conv.preview_conversion_params(f, output, opts):
        conv.convert(f, output, opts)
    input("\n回车继续...")



def _advanced_image(conv):
    f = get_file("拖入图片文件: ")
    if not f:
        input("\n回车继续...")
        return
    print("\n输出格式: jpg, png, webp, bmp, gif, tiff")
    fmt = input("输入格式: ").strip().lower()
    opts = advanced_options(conv.gpu_type is not None)
    output = conv._get_output_path(f, "custom", fmt, opts)
    if conv.preview_conversion_params(f, output, opts):
        conv.convert(f, output, opts)
    input("\n回车继续...")

def _interconvert(conv):
    print("\n1. 视频 -> 图片 (提取帧)")
    print("2. 图片 -> 视频 (生成幻灯片)")
    sub = input("选择 [1-2]: ").strip()
    if sub == '1':
        f = get_file("拖入视频文件: ")
        if not f:
            return
        conv.preview_file_info(f)
        print("\n输出格式: jpg, png, webp")
        fmt = input("输入格式: ").strip().lower()
        time_point = input("提取时间点 (秒，默认1): ").strip() or "1"
        output_dir = get_output_dir()
        opts = advanced_options(conv.gpu_type is not None)
        opts.output_dir = output_dir
        base = os.path.splitext(os.path.basename(f))[0]
        output = os.path.join(output_dir, f"{base}_frame.{fmt}") if output_dir else f"{os.path.splitext(f)[0]}_frame.{fmt}"
        if conv.preview_conversion_params(f, output, opts):
            cmd = [conv.ffmpeg_path, '-ss', time_point, '-i', f, '-vframes', '1']
            cmd.extend(conv._build_image_opts(f'.{fmt}', opts))
            cmd.append(output)
            conv._run_ffmpeg(cmd, f, output, f'.{fmt}', opts, add_to_history=False)
            _c("[+]", "提取完成", Fore.GREEN)
    elif sub == '2':
        f = get_file("拖入图片文件: ")
        if not f:
            return
        duration = input("视频时长(秒，默认5): ").strip() or "5"
        output_dir = get_output_dir()
        opts = advanced_options(conv.gpu_type is not None)
        opts.output_dir = output_dir
        opts.fps = opts.fps or 30
        opts.trim_duration = duration
        base = os.path.splitext(os.path.basename(f))[0]
        output = os.path.join(output_dir, f"{base}_video.mp4") if output_dir else f"{os.path.splitext(f)[0]}_video.mp4"
        if conv.preview_conversion_params(f, output, opts):
            cmd = conv._build_img_to_video_cmd(f, opts)
            cmd.append(output)
            conv._run_ffmpeg(cmd, f, output, '.mp4', opts, add_to_history=False)
            _c("[+]", "生成完成", Fore.GREEN)
    input("\n回车继续...")


def _compress(conv):
    f = get_file("拖入视频文件: ")
    if f:
        size_str = input("目标大小(MB，默认50): ").strip() or "50"
        if not size_str.isdigit():
            print("[!] 请输入有效的数字")
            input("\n回车继续...")
            return
        size = int(size_str)
        if size <= 0:
            print("[!] 目标大小必须大于 0")
            input("\n回车继续...")
            return
        output_dir = get_output_dir()
        opts = ConvertOptions(output_dir=output_dir)
        if conv.gpu_type:
            use_gpu = input("启用 GPU 硬件加速? (Y/N, 默认N): ").strip().upper()
            opts.use_gpu = use_gpu == 'Y' or use_gpu == 'YES'
        conv.compress_media(f, size, opts)
    input("\n回车继续...")


def _history(conv):
    record = conv.history.show_history()
    if record:
        f = record['file']
        if not os.path.exists(f):
            print(f"[!] 原文件已不存在: {f}")
            input("\n回车继续...")
            return
        conv.preview_file_info(f)
        opts = ConvertOptions(**record['options'])
        target_format = record['format']
        output = conv._get_output_path(f, "history", target_format, opts)
        print(f"\n[*] 使用历史参数:")
        print(f"    格式: {target_format}")
        print(f"    选项: {record['options']}")
        if conv.preview_conversion_params(f, output, opts):
            conv.convert(f, output, opts)
    input("\n回车继续...")


def _batch(conv):
    batch_convert_mode(conv)
    input("\n回车继续...")


MENU_SECTIONS = [
    ("header", "【快速模式 - 一键懒人转换】"),
    ("item",   "1", "视频 -> MP4 (H.264)",     _quick_video_handler('mp4')),
    ("item",   "2", "视频 -> AVI",            _quick_video_handler('avi')),
    ("item",   "3", "视频 -> MKV",            _quick_video_handler('mkv')),
    ("item",   "4", "视频 -> MOV",            _quick_video_handler('mov')),
    ("item",   "5", "视频 -> WEBM",           _quick_video_handler('webm')),
    ("item",   "6", "视频 -> GIF (动图)",       _video_to_gif),
    ("item",   "7", "视频 -> MP3 (提取音频)",    _extract_audio),
    ("sep", None, None),
    ("header", "【快速模式 - 图片】"),
    ("item",   "8", "图片 -> JPG",            _quick_image_handler('jpg')),
    ("item",   "9", "图片 -> PNG",            _quick_image_handler('png')),
    ("item",   "10", "图片 -> WEBP",          _quick_image_handler('webp')),
    ("item",   "11", "图片 -> BMP",           _quick_image_handler('bmp')),
    ("sep", None, None),
    ("header", "【高级模式 - 自定义参数】"),
    ("item",   "12", "视频转换 + 调尺寸/质量/码率", _advanced_video),
    ("item",   "13", "图片转换 + 调尺寸/质量",    _advanced_image),
    ("item",   "14", "视频 <-> 图片 互转",      _interconvert),
    ("item",   "15", "智能压缩 (指定目标大小MB)",  _compress),
    ("sep", None, None),
    ("header", "【其他功能】"),
    ("item",   "16", "重新转换最近文件",        _history),
    ("item",   "17", "批量转换队列模式",        _batch),
    ("sep", None, None),
    ("item",   "0", "退出",                  None),
]


def _print_menu():
    for section in MENU_SECTIONS:
        kind, *rest = section
        if kind == "header":
            print(f"\n{rest[0]}")
            print("-" * 50)
        elif kind == "sep":
            print("-" * 50)
        elif kind == "item":
            key, label, _ = rest
            print(f"{key}. {label}")


def main():
    if os.name != 'nt':
        print("仅支持 Windows")
        return
    conv = MediaConverter()
    conv.check()

    ROUTES = {}
    for section in MENU_SECTIONS:
        if section[0] == "item" and section[3] is not None:
            ROUTES[section[1]] = section[3]

    while True:
        clear()
        banner()
        _print_menu()
        print("=" * 50)
        choice = input("\n选择功能 [0-17]: ").strip()
        if choice == '0':
            _c("[*]", "再见!", Fore.CYAN)
            break
        handler = ROUTES.get(choice)
        if handler:
            handler(conv)
        else:
            print("[!] 无效选择")
            input("回车继续...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[*] 已取消")