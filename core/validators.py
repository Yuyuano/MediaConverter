import os
from pathlib import Path
from typing import Optional, List


# FFmpeg 安全参数白名单
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


def validate_extra_args(extra_args: Optional[List[str]]) -> List[str]:
    """校验 extra_args 白名单，过滤危险参数"""
    if not extra_args:
        return []
    safe_args = []
    i = 0
    while i < len(extra_args):
        arg = extra_args[i]
        if arg.startswith('-') and arg in SAFE_FFMPEG_FLAGS:
            safe_args.append(arg)
            if i + 1 < len(extra_args) and not extra_args[i + 1].startswith('-'):
                i += 1
                safe_args.append(extra_args[i])
        else:
            print(f"[!] 已过滤不安全的 FFmpeg 参数: {arg}")
        i += 1
    return safe_args


def validate_output_dir(output_dir: Optional[str]) -> Optional[str]:
    """验证输出目录路径安全性，拒绝路径遍历"""
    if not output_dir:
        return None
    try:
        if '..' in output_dir.split(os.sep):
            print(f"[!] 路径包含 '..'，已拒绝: {output_dir}")
            return None
        resolved = Path(output_dir).resolve()
        return str(resolved)
    except (OSError, ValueError) as e:
        print(f"[!] 无效路径: {e}")
        return None


def parse_size(size_str: str) -> tuple:
    """解析尺寸字符串，返回 (width, height)"""
    import re
    if not size_str:
        return None, None
    m = re.match(r'(\d+)[xX×](\d+)', size_str)
    if m:
        return int(m.group(1)), int(m.group(2))
    presets = {'1080p': (1920, 1080), '720p': (1280, 720), '480p': (854, 480)}
    if size_str.lower() in presets:
        return presets[size_str.lower()]
    if size_str.isdigit():
        return int(size_str), None
    return None, None
