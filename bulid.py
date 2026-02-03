# build.py
import PyInstaller.__main__
import shutil
import os
import zipfile
import urllib.request
import sys
from pathlib import Path

# ============ 配置 ============
# 方式1: 指定本地ffmpeg路径（推荐）
FFMPEG_SOURCE = r"C:\ffmpeg\bin"  # 修改为你的ffmpeg路径

# 方式2: 自动下载（如果上面路径不存在且设为True）
AUTO_DOWNLOAD = False
FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"


# =============================

def download_ffmpeg(target_dir: Path):
    """下载ffmpeg"""
    print("[*] 正在下载 FFmpeg...")
    print(f"[*] 来源: {FFMPEG_URL}")
    zip_path = target_dir / "ffmpeg.zip"

    def progress(block_num, block_size, total_size):
        downloaded = block_num * block_size
        percent = min(100, int(downloaded * 100 / total_size)) if total_size > 0 else 0
        mb = downloaded / 1024 / 1024
        total_mb = total_size / 1024 / 1024
        sys.stdout.write(f"\r[*] 下载进度: {percent}% ({mb:.1f}/{total_mb:.1f} MB)")
        sys.stdout.flush()

    try:
        urllib.request.urlretrieve(FFMPEG_URL, zip_path, reporthook=progress)
        print("\n[*] 下载完成，正在解压...")

        extract_dir = target_dir / "temp"
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(extract_dir)

        # 查找并复制ffmpeg
        found = False
        for root, dirs, files in os.walk(extract_dir):
            if 'ffmpeg.exe' in files:
                src_dir = Path(root)
                print(f"[*] 找到ffmpeg目录: {src_dir}")

                # 复制必要文件
                for f in ['ffmpeg.exe', 'ffprobe.exe']:
                    src = src_dir / f
                    if src.exists():
                        dst = target_dir / f
                        shutil.copy2(src, dst)
                        print(f"  [+] {f}")

                # 复制DLL文件
                dll_count = 0
                for dll in src_dir.glob("*.dll"):
                    shutil.copy2(dll, target_dir / dll.name)
                    dll_count += 1
                print(f"  [+] {dll_count} 个DLL文件")
                found = True
                break

        # 清理
        zip_path.unlink(missing_ok=True)
        shutil.rmtree(extract_dir, ignore_errors=True)

        if not found:
            print("[!] 错误：压缩包中未找到ffmpeg.exe")
            return False

        print("[+] FFmpeg 准备完成")
        return True

    except Exception as e:
        print(f"\n[!] 下载失败: {e}")
        return False


def prepare_ffmpeg():
    """准备ffmpeg文件"""
    ffmpeg_dir = Path("ffmpeg")
    ffmpeg_dir.mkdir(exist_ok=True)

    # 检查是否已有ffmpeg
    if (ffmpeg_dir / "ffmpeg.exe").exists() and (ffmpeg_dir / "ffprobe.exe").exists():
        print("[*] 使用现有的ffmpeg文件")
        return True

    # 从指定路径复制
    if os.path.exists(FFMPEG_SOURCE):
        print(f"[*] 从 {FFMPEG_SOURCE} 复制ffmpeg...")

        copied = []
        for f in ['ffmpeg.exe', 'ffprobe.exe']:
            src = Path(FFMPEG_SOURCE) / f
            dst = ffmpeg_dir / f
            if src.exists():
                shutil.copy2(src, dst)
                copied.append(f)
                print(f"  [+] {f}")

        # 复制DLL
        dlls = list(Path(FFMPEG_SOURCE).glob("*.dll"))
        for dll in dlls:
            shutil.copy2(dll, ffmpeg_dir / dll.name)
        if dlls:
            print(f"  [+] {len(dlls)} 个DLL文件")

        if 'ffmpeg.exe' in copied:
            return True
        else:
            print("[!] 警告：未找到ffmpeg.exe，请检查路径")

    # 自动下载
    if AUTO_DOWNLOAD:
        print("[*] 本地未找到，尝试自动下载...")
        if download_ffmpeg(ffmpeg_dir):
            return True

    print("\n[!] 未找到ffmpeg源文件")
    print(f"    请执行以下操作之一：")
    print(f"    1. 修改 build.py 中的 FFMPEG_SOURCE = r\"你的ffmpeg路径\"")
    print(f"    2. 手动创建 ffmpeg/ 目录，放入 ffmpeg.exe 和 ffprobe.exe")
    print(f"    3. 设置 AUTO_DOWNLOAD = True 启用自动下载")
    return False


def collect_binaries():
    """收集需要打包的二进制文件"""
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
    """执行打包"""
    print("=" * 60)
    print("  媒体转换工具 - 打包脚本")
    print("=" * 60)

    # 准备ffmpeg
    if not prepare_ffmpeg():
        cont = input("\n是否继续打包? (可能没有ffmpeg功能) [Y/N]: ").strip().upper()
        if cont != 'Y':
            print("[*] 已取消")
            return

    # 收集文件
    binaries = collect_binaries()

    # 构建参数
    args = [
        'converter.py',
        '--name=MediaConverter',
        '--onefile',
        '--console',  # 保留控制台窗口（命令行工具必需）
        '--clean',
        '--noconfirm',
        # 图标（可选）
        # '--icon=icon.ico',
    ]

    # 添加二进制文件
    for src, dst in binaries:
        args.append(f'--add-binary={src};{dst}')

    print(f"\n[*] 开始打包...")
    print(f"[*] PyInstaller参数:")
    for arg in args:
        print(f"    {arg}")

    # 执行打包
    PyInstaller.__main__.run(args)

    # 检查结果
    exe_path = Path("dist") / "MediaConverter.exe"
    if exe_path.exists():
        # 复制到项目根目录方便使用
        final_path = Path("MediaConverter.exe")
        shutil.copy2(exe_path, final_path)

        final_size = final_path.stat().st_size / 1024 / 1024

        print("\n" + "=" * 60)
        print("[+] 打包成功!")
        print(f"[+] 输出文件: {final_path.absolute()}")
        print(f"[+] 文件大小: {final_size:.1f} MB")
        print(f"[+] 运行方式: 双击运行 或 命令行运行 MediaConverter.exe")
        if binaries:
            print(f"[+] 内置ffmpeg: 无需用户配置环境")
        else:
            print(f"[!] 警告: 未打包ffmpeg，用户需自行安装")
        print("=" * 60)
    else:
        print("\n[!] 打包失败，请检查错误信息")


if __name__ == "__main__":
    try:
        build()
    except KeyboardInterrupt:
        print("\n\n[*] 用户取消")
    except Exception as e:
        print(f"\n[!] 错误: {e}")
        import traceback

        traceback.print_exc()