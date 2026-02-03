# converter.py
import os
import sys
import subprocess
import shutil
import re
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Tuple


@dataclass
class ConvertOptions:
    """转换参数配置"""
    width: Optional[int] = None  # 输出宽度（高度自动等比）
    height: Optional[int] = None  # 输出高度（宽度自动等比）
    fps: Optional[int] = None  # 视频帧率
    quality: Optional[int] = None  # 图片质量(2-31)或视频CRF(0-51)
    bitrate: Optional[str] = None  # 视频码率 (如 "2M")
    audio_bitrate: Optional[str] = None  # 音频码率 (如 "192k")
    codec: Optional[str] = None  # 指定编码器
    preset: Optional[str] = None  # 编码速度预设
    extra_args: Optional[List[str]] = None  # 额外参数
    output_dir: Optional[str] = None  # 输出目录（新增）


class MediaConverter:
    # 支持的格式
    VIDEO_EXTS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.ts', '.m2ts'}
    IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.tiff', '.tif', '.ico', '.raw', '.cr2', '.nef'}
    AUDIO_EXTS = {'.mp3', '.wav', '.aac', '.flac', '.ogg', '.m4a', '.wma'}

    def __init__(self):
        if getattr(sys, 'frozen', False):
            self.base_dir = Path(sys._MEIPASS)
            self.app_dir = Path(sys.executable).parent
        else:
            self.base_dir = Path(__file__).parent
            self.app_dir = self.base_dir

        self.ffmpeg_path = self._find_ffmpeg()
        self.ffprobe_path = self._find_ffprobe() if self.ffmpeg_path else None

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
            result = subprocess.run(['where', 'ffmpeg'], capture_output=True, text=True)
            if result.returncode == 0:
                path = result.stdout.strip().split('\n')[0]
                if self._verify(path):
                    return path
        except:
            pass
        return None

    def _find_ffprobe(self):
        base = Path(self.ffmpeg_path).parent
        probe = base / 'ffprobe.exe'
        return str(probe) if probe.exists() else None

    def _verify(self, path):
        try:
            r = subprocess.run([path, '-version'], capture_output=True,
                               text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
            return r.returncode == 0 and 'version' in r.stdout
        except:
            return False

    def check(self):
        if not self.ffmpeg_path:
            print("\n[!] 未找到 FFmpeg")
            print("[!] 请将 ffmpeg.exe 和 ffprobe.exe 放在程序目录")
            input("\n按回车退出...")
            sys.exit(1)

        v = subprocess.run([self.ffmpeg_path, '-version'], capture_output=True, text=True,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        print(f"[+] FFmpeg: {v.stdout.split()[2] if v.stdout else 'OK'}")
        return True

    def get_info(self, filepath: str) -> dict:
        """获取媒体信息"""
        if not self.ffprobe_path:
            return {}

        cmd = [
            self.ffprobe_path,
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,duration,r_frame_rate,codec_name',
            '-show_entries', 'format=duration,size,bit_rate',
            '-of', 'default=noprint_wrappers=1',
            filepath
        ]

        try:
            r = subprocess.run(cmd, capture_output=True, text=True,
                               creationflags=subprocess.CREATE_NO_WINDOW)
            info = {}
            for line in r.stdout.split('\n'):
                if '=' in line:
                    k, v = line.split('=', 1)
                    info[k] = v
            return info
        except:
            return {}

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

        codec_map = {
            '.mp4': 'libx264', '.mov': 'libx264', '.m4v': 'libx264',
            '.avi': 'libxvid',
            '.mkv': 'libx264',
            '.webm': 'libvpx-vp9',
            '.wmv': 'wmv2',
            '.flv': 'libx264',
            '.gif': 'gif',
        }

        if opts.codec:
            args.extend(['-c:v', opts.codec])
        elif output_ext.lower() in codec_map:
            if output_ext.lower() == '.gif':
                args.extend([
                    '-vf',
                    f"fps={opts.fps or 30},scale={opts.width or 480}:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse",
                    '-loop', '0'
                ])
                return args
            else:
                args.extend(['-c:v', codec_map[output_ext.lower()]])

        if opts.quality is not None:
            args.extend(['-crf', str(opts.quality)])
        elif opts.bitrate:
            args.extend(['-b:v', opts.bitrate])

        if opts.preset:
            args.extend(['-preset', opts.preset])

        if opts.audio_bitrate:
            args.extend(['-c:a', 'aac', '-b:a', opts.audio_bitrate])
        else:
            args.extend(['-c:a', 'aac', '-b:a', '192k'])

        if opts.extra_args:
            args.extend(opts.extra_args)

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
            vf.append(f"format=yuvj420p")
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
        """构建输出路径（支持自定义目录）"""
        input_path = Path(input_file)

        # 确定输出目录
        if opts.output_dir:
            output_dir = Path(opts.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
        else:
            output_dir = input_path.parent

        # 构建文件名：原文件名_后缀.扩展名
        output_name = f"{input_path.stem}_{suffix}.{ext}"
        return str(output_dir / output_name)

    def convert(self, input_file: str, output_file: str, opts: Optional[ConvertOptions] = None) -> bool:
        """通用转换接口"""
        if not os.path.exists(input_file):
            print(f"[!] 文件不存在: {input_file}")
            return False

        opts = opts or ConvertOptions()
        input_path = Path(input_file)
        output_path = Path(output_file)
        input_ext = input_path.suffix.lower()
        output_ext = output_path.suffix.lower()

        is_video_input = input_ext in self.VIDEO_EXTS or input_ext in {'.gif'}
        is_image_input = input_ext in self.IMAGE_EXTS
        is_video_output = output_ext in self.VIDEO_EXTS or output_ext == '.gif'
        is_image_output = output_ext in self.IMAGE_EXTS

        cmd = [self.ffmpeg_path, '-i', input_file]

        if is_video_output:
            if is_image_input:
                print("[*] 图片转视频模式")
                duration = 5
                fps = opts.fps or 30
                cmd = [
                    self.ffmpeg_path,
                    '-loop', '1',
                    '-i', input_file,
                    '-c:v', opts.codec or 'libx264',
                    '-t', str(duration),
                    '-pix_fmt', 'yuv420p'
                ]
                cmd.extend(self._build_filter(opts))
                if opts.quality:
                    cmd.extend(['-crf', str(opts.quality)])
            else:
                cmd.extend(self._build_video_opts(output_ext, opts))
        else:
            if is_video_input:
                print("[*] 视频转图片模式（提取第一帧）")
                cmd.extend(['-ss', '00:00:01', '-vframes', '1'])

            cmd.extend(self._build_image_opts(output_ext, opts))

        cmd.append(output_file)

        print(f"\n[*] 输入: {input_path.name}")
        print(f"[*] 输出: {output_path.name}")
        if opts.output_dir:
            print(f"[*] 目录: {opts.output_dir}")
        if opts.width or opts.height:
            print(f"[*] 尺寸: {opts.width or '自动'}x{opts.height or '自动'}")

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            for line in process.stdout:
                line = line.strip()
                if any(x in line for x in ['frame=', 'size=', 'time=', 'out_time_ms']):
                    print(f"\r[*] {line[:60]}", end='', flush=True)

            process.wait()
            print()

            if process.returncode == 0:
                size = os.path.getsize(output_file) / 1024 / 1024
                print(f"[+] 成功! 大小: {size:.2f} MB")
                return True
            else:
                print("[!] 转换失败")
                return False
        except Exception as e:
            print(f"[!] 错误: {e}")
            return False

    def quick_video_convert(self, input_file: str, target_format: str, opts: Optional[ConvertOptions] = None):
        """一键视频转换"""
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
        # 合并选项：保留用户设置的output_dir
        default_opts.output_dir = opts.output_dir
        if opts.quality: default_opts.quality = opts.quality
        if opts.preset: default_opts.preset = opts.preset

        return self.convert(input_file, output, default_opts)

    def quick_image_convert(self, input_file: str, target_format: str, opts: Optional[ConvertOptions] = None):
        """一键图片转换"""
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

        return self.convert(input_file, output, default_opts)

    def compress_media(self, input_file: str, target_size_mb: int = 50, opts: Optional[ConvertOptions] = None):
        """智能压缩"""
        opts = opts or ConvertOptions()
        info = self.get_info(input_file)
        if not info:
            print("[!] 无法获取文件信息")
            return False

        duration = float(info.get('duration', 0) or info.get('format.duration', 0))
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
            output_dir=opts.output_dir
        )

        print(f"[*] 目标大小: {target_size_mb}MB")
        print(f"[*] 计算码率: {comp_opts.bitrate}")

        return self.convert(input_file, output, comp_opts)


def clear():
    os.system('cls')


def banner():
    print("=" * 60)
    print("    媒体格式转换工具 v2.0 (视频+图片)")
    print("    支持: 视频转视频 | 图片转图片 | 视频图片互转")
    print("    By Yuyuan")
    print("=" * 60)


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
        if d and os.path.isdir(d):
            return d
        elif d:
            try:
                Path(d).mkdir(parents=True, exist_ok=True)
                return d
            except:
                print("[!] 无法创建目录，使用默认")
                return None
    return None


def advanced_options() -> ConvertOptions:
    """交互式高级参数设置"""
    opts = ConvertOptions()

    print("\n[高级参数设置] (直接回车使用默认)")

    # 输出目录（新增）
    opts.output_dir = get_output_dir()

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

    print("编码速度: ultrafast|superfast|veryfast|faster|fast|medium|slow|slower|veryslow")
    pr = input("选择预设: ").strip()
    if pr:
        opts.preset = pr

    return opts


def main():
    if os.name != 'nt':
        print("仅支持 Windows")
        return

    conv = MediaConverter()
    conv.check()

    while True:
        clear()
        banner()

        print("\n【快速模式 - 一键懒人转换】")
        print("-" * 50)
        print("1. 视频 → MP4 (H.264)")
        print("2. 视频 → AVI")
        print("3. 视频 → MKV")
        print("4. 视频 → MOV")
        print("5. 视频 → WEBM")
        print("6. 视频 → GIF (动图)")
        print("7. 视频 → MP3 (提取音频)")
        print("-" * 50)
        print("8. 图片 → JPG")
        print("9. 图片 → PNG")
        print("10. 图片 → WEBP")
        print("11. 图片 → BMP")
        print("-" * 50)
        print("【高级模式 - 自定义参数】")
        print("12. 视频转换 + 调尺寸/质量/码率")
        print("13. 图片转换 + 调尺寸/质量")
        print("14. 视频 ↔ 图片 互转")
        print("15. 智能压缩 (指定目标大小MB)")
        print("-" * 50)
        print("0. 退出")
        print("=" * 50)

        choice = input("\n选择功能 [0-15]: ").strip()

        if choice == '0':
            print("\n[*] 再见!")
            break

        # 视频快速转换
        elif choice in ['1', '2', '3', '4', '5']:
            formats = ['mp4', 'avi', 'mkv', 'mov', 'webm']
            f = get_file("拖入视频文件: ")
            if f:
                output_dir = get_output_dir()
                opts = ConvertOptions(output_dir=output_dir)
                conv.quick_video_convert(f, formats[int(choice) - 1], opts)
            input("\n回车继续...")

        # 视频转GIF
        elif choice == '6':
            f = get_file("拖入视频文件: ")
            if f:
                output_dir = get_output_dir()
                base = os.path.splitext(os.path.basename(f))[0]
                if output_dir:
                    output = os.path.join(output_dir, f"{base}.gif")
                else:
                    output = f"{os.path.splitext(f)[0]}.gif"
                opts = ConvertOptions(width=480, fps=15, quality=10, output_dir=output_dir)
                conv.convert(f, output, opts)
            input("\n回车继续...")

        # 提取音频
        elif choice == '7':
            f = get_file("拖入视频文件: ")
            if f:
                output_dir = get_output_dir()
                base = os.path.splitext(os.path.basename(f))[0]
                if output_dir:
                    output = os.path.join(output_dir, f"{base}_audio.mp3")
                else:
                    output = f"{os.path.splitext(f)[0]}_audio.mp3"
                opts = ConvertOptions(output_dir=output_dir)
                conv.convert(f, output, opts)
            input("\n回车继续...")

        # 图片快速转换
        elif choice in ['8', '9', '10', '11']:
            formats = ['jpg', 'png', 'webp', 'bmp']
            f = get_file("拖入图片文件: ")
            if f:
                output_dir = get_output_dir()
                opts = ConvertOptions(output_dir=output_dir)
                conv.quick_image_convert(f, formats[int(choice) - 8], opts)
            input("\n回车继续...")

        # 高级视频转换
        elif choice == '12':
            f = get_file("拖入视频文件: ")
            if not f:
                input("\n回车继续...")
                continue

            print("\n输出格式: mp4, avi, mkv, mov, wmv, flv, webm")
            fmt = input("输入格式: ").strip().lower()
            if fmt not in ['mp4', 'avi', 'mkv', 'mov', 'wmv', 'flv', 'webm']:
                print("[!] 不支持的格式")
                input("\n回车继续...")
                continue

            opts = advanced_options()
            output = conv._get_output_path(f, "custom", fmt, opts)
            conv.convert(f, output, opts)
            input("\n回车继续...")

        # 高级图片转换
        elif choice == '13':
            f = get_file("拖入图片文件: ")
            if not f:
                input("\n回车继续...")
                continue

            print("\n输出格式: jpg, png, webp, bmp, gif, tiff")
            fmt = input("输入格式: ").strip().lower()

            opts = advanced_options()
            output = conv._get_output_path(f, "custom", fmt, opts)
            conv.convert(f, output, opts)
            input("\n回车继续...")

        # 视频图片互转
        elif choice == '14':
            print("\n1. 视频 → 图片 (提取帧)")
            print("2. 图片 → 视频 (生成幻灯片)")
            sub = input("选择 [1-2]: ").strip()

            if sub == '1':
                f = get_file("拖入视频文件: ")
                if f:
                    print("\n输出格式: jpg, png, webp")
                    fmt = input("输入格式: ").strip().lower()
                    time = input("提取时间点 (秒，默认1): ").strip() or "1"

                    output_dir = get_output_dir()
                    opts = advanced_options()
                    opts.output_dir = output_dir

                    base = os.path.splitext(os.path.basename(f))[0]
                    if output_dir:
                        output = os.path.join(output_dir, f"{base}_frame.{fmt}")
                    else:
                        output = f"{os.path.splitext(f)[0]}_frame.{fmt}"

                    cmd = [
                        conv.ffmpeg_path, '-ss', time, '-i', f,
                        '-vframes', '1'
                    ]
                    cmd.extend(conv._build_image_opts(f'.{fmt}', opts))
                    cmd.append(output)

                    subprocess.run(cmd, creationflags=subprocess.CREATE_NO_WINDOW)
                    print("[+] 提取完成")

            elif sub == '2':
                f = get_file("拖入图片文件: ")
                if f:
                    duration = input("视频时长(秒，默认5): ").strip() or "5"
                    output_dir = get_output_dir()
                    opts = advanced_options()
                    opts.output_dir = output_dir
                    opts.fps = opts.fps or 30

                    base = os.path.splitext(os.path.basename(f))[0]
                    if output_dir:
                        output = os.path.join(output_dir, f"{base}_video.mp4")
                    else:
                        output = f"{os.path.splitext(f)[0]}_video.mp4"

                    cmd = [
                        conv.ffmpeg_path,
                        '-loop', '1', '-i', f,
                        '-c:v', 'libx264',
                        '-t', str(duration),
                        '-pix_fmt', 'yuv420p'
                    ]
                    if opts.width or opts.height:
                        cmd.extend(['-vf', f"scale={opts.width or -1}:{opts.height or -1}"])
                    if opts.quality:
                        cmd.extend(['-crf', str(opts.quality)])

                    cmd.append(output)
                    subprocess.run(cmd, creationflags=subprocess.CREATE_NO_WINDOW)
                    print("[+] 生成完成")

            input("\n回车继续...")

        # 智能压缩
        elif choice == '15':
            f = get_file("拖入视频文件: ")
            if f:
                size = input("目标大小(MB，默认50): ").strip() or "50"
                output_dir = get_output_dir()
                opts = ConvertOptions(output_dir=output_dir)
                conv.compress_media(f, int(size), opts)
            input("\n回车继续...")

        else:
            print("[!] 无效选择")
            input("回车继续...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[*] 已取消")