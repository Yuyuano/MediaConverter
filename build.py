# build.py - GUI 版打包脚本
import PyInstaller.__main__
import shutil
import os
import zipfile
import urllib.request
import urllib.error
import sys
from pathlib import Path

# ============ 配置 ============
from core.constants import APP_VERSION
FFMPEG_SOURCE = os.environ.get(
    'FFMPEG_PATH',
    ''
)
AUTO_DOWNLOAD = os.environ.get('FFMPEG_AUTO_DOWNLOAD', 'false').lower() == 'true'
SKIP_CONFIRM = os.environ.get('FFMPEG_SKIP_CONFIRM', 'false').lower() == 'true'
FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"


def download_ffmpeg(target_dir: Path):
    print("[*] 正在下载 FFmpeg...")
    zip_path = target_dir / "ffmpeg.zip"

    try:
        with urllib.request.urlopen(FFMPEG_URL, timeout=120) as resp, \
                open(zip_path, 'wb') as out:
            total = int(resp.headers.get('Content-Length', 0))
            downloaded = 0
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                out.write(chunk)
                downloaded += len(chunk)
                percent = min(100, int(downloaded * 100 / total)) if total > 0 else 0
                mb = downloaded / 1024 / 1024
                total_mb = total / 1024 / 1024
                sys.stdout.write(f"\r[*] 下载进度: {percent}% ({mb:.1f}/{total_mb:.1f} MB)")
                sys.stdout.flush()
        print("\n[*] 下载完成，正在解压...")

        extract_dir = target_dir / "temp"
        with zipfile.ZipFile(zip_path, 'r') as z:
            base = extract_dir.resolve()
            for member in z.infolist():
                if not member.filename or member.is_dir():
                    continue
                target = (extract_dir / member.filename).resolve()
                if not str(target).startswith(str(base)):
                    raise ValueError(f"非法压缩包路径: {member.filename}")
            z.extractall(extract_dir)

        found = False
        for root, dirs, files in os.walk(extract_dir):
            if 'ffmpeg.exe' in files:
                src_dir = Path(root)
                for f in ['ffmpeg.exe', 'ffprobe.exe']:
                    src = src_dir / f
                    if src.exists():
                        shutil.copy2(src, target_dir / f)
                for dll in src_dir.rglob("*.dll"):
                    shutil.copy2(dll, target_dir / dll.name)
                found = True
                break

        zip_path.unlink(missing_ok=True)
        shutil.rmtree(extract_dir, ignore_errors=True)

        if not found:
            print("[!] 错误：压缩包中未找到 ffmpeg.exe")
            return False
        if not (target_dir / "ffprobe.exe").exists():
            print("[!] 警告：未找到 ffprobe.exe，媒体信息探测将不可用")
        print("[+] FFmpeg 准备完成")
        return True
    except (OSError, urllib.error.URLError, zipfile.BadZipFile, ValueError, TimeoutError) as e:
        print(f"\n[!] 下载失败: {e}")
        return False


def prepare_ffmpeg():
    ffmpeg_dir = Path("ffmpeg")
    ffmpeg_dir.mkdir(exist_ok=True)

    if (ffmpeg_dir / "ffmpeg.exe").exists() and (ffmpeg_dir / "ffprobe.exe").exists():
        print("[*] 使用现有的 ffmpeg 文件")
        return True

    if FFMPEG_SOURCE and os.path.exists(FFMPEG_SOURCE):
        print(f"[*] 从 {FFMPEG_SOURCE} 复制 ffmpeg...")
        copied = []
        for f in ['ffmpeg.exe', 'ffprobe.exe']:
            src = Path(FFMPEG_SOURCE) / f
            if src.exists():
                shutil.copy2(src, ffmpeg_dir / f)
                copied.append(f)
                print(f"  [+] {f}")
        dlls = list(Path(FFMPEG_SOURCE).glob("*.dll"))
        for dll in dlls:
            shutil.copy2(dll, ffmpeg_dir / dll.name)
        if dlls:
            print(f"  [+] {len(dlls)} 个 DLL 文件")
        if 'ffmpeg.exe' in copied:
            if 'ffprobe.exe' not in copied:
                print("[!] 警告：未找到 ffprobe.exe，媒体信息探测将不可用")
            return True
        print("[!] 警告：未找到 ffmpeg.exe，请检查 FFMPEG_PATH 环境变量")

    if AUTO_DOWNLOAD:
        print("[*] 本地未找到，尝试自动下载...")
        if download_ffmpeg(ffmpeg_dir):
            return True

    print("\n[!] 未找到 ffmpeg 源文件")
    print("[!] 请设置 FFMPEG_PATH 环境变量指向 ffmpeg/bin 目录，或开启 FFMPEG_AUTO_DOWNLOAD=true")
    return False


def collect_binaries():
    binaries = []
    ffmpeg_dir = Path("ffmpeg")
    if not ffmpeg_dir.exists():
        return binaries
    print("\n[*] 扫描打包文件:")
    for f in ffmpeg_dir.iterdir():
        if f.suffix in ['.exe', '.dll']:
            binaries.append((str(f), '.'))
            size = f.stat().st_size / 1024 / 1024
            print(f"    {f.name:<20} {size:>6.1f} MB")
    total = sum(Path(b[0]).stat().st_size for b in binaries) / 1024 / 1024
    print(f"    {'总计':<20} {total:>6.1f} MB")
    return binaries


def build():
    print("=" * 60)
    print(f"  MediaConverter v{APP_VERSION} - GUI 打包脚本")
    print("=" * 60)

    if not prepare_ffmpeg():
        if SKIP_CONFIRM:
            print("[*] FFMPEG_SKIP_CONFIRM=true，继续打包")
        else:
            cont = input("\n是否继续打包? (可能没有 ffmpeg 功能) [Y/N]: ").strip().upper()
            if cont != 'Y':
                print("[*] 已取消")
                return

    binaries = collect_binaries()

    icon_path = Path("icon.ico")
    icon_arg = ['--icon', str(icon_path)] if icon_path.exists() else []

    args = [
        'main.py',
        '--name=MediaConverter',
        '--windowed',
        '--clean',
        '--noconfirm',
        '--add-data=ico;ico',
        '--add-data=gui/styles;gui/styles',
    ]

    if icon_arg:
        args.extend(icon_arg)

    for src, dst in binaries:
        args.append(f'--add-binary={src};{dst}')

    print(f"\n[*] 开始打包...")
    print(f"[*] PyInstaller 参数:")
    for arg in args:
        print(f"    {arg}")

    try:
        PyInstaller.__main__.run(args)
    except (RuntimeError, SystemExit) as e:
        if isinstance(e, SystemExit) and e.code == 0:
            pass
        else:
            print(f"\n[!] 打包错误: {e}")
            return

    dist_dir = Path("dist") / "MediaConverter"
    exe_path = dist_dir / "MediaConverter.exe"
    if exe_path.exists():
        final_dir = Path("MediaConverter")
        if final_dir.exists():
            shutil.rmtree(final_dir)
        shutil.copytree(dist_dir, final_dir)

        dir_size = sum(f.stat().st_size for f in final_dir.rglob('*') if f.is_file()) / 1024 / 1024

        print("\n" + "=" * 60)
        print("[+] 打包成功!")
        print(f"[+] 输出目录: {final_dir.absolute()}")
        print(f"[+] 总大小: {dir_size:.1f} MB")
        print(f"[+] 运行方式: 双击 MediaConverter/MediaConverter.exe")
        if binaries:
            print(f"[+] 内置 FFmpeg: 无需用户配置")
        print("=" * 60)
    else:
        print("\n[!] 打包失败，请检查错误信息")


if __name__ == "__main__":
    try:
        build()
    except KeyboardInterrupt:
        print("\n\n[*] 用户取消")
    except (OSError, RuntimeError) as e:
        print(f"\n[!] 错误: {e}")
        import traceback
        traceback.print_exc()
