import os
import re
import logging
from pathlib import Path
from typing import Optional, List, Tuple

logger = logging.getLogger('MediaConverter')

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
            logger.warning(f"已过滤不安全的 FFmpeg 参数: {arg}")
        i += 1
    return safe_args


def validate_output_dir(output_dir: Optional[str]) -> Optional[str]:
    if not output_dir:
        return None
    try:
        normalized = output_dir.replace('/', os.sep)
        if '..' in normalized.split(os.sep):
            logger.warning(f"路径包含 '..'，已拒绝: {output_dir}")
            return None
        resolved = Path(output_dir).resolve()
        return str(resolved)
    except (OSError, ValueError) as e:
        logger.error(f"无效路径: {e}")
        return None


SIZE_PRESETS = {'1080p': (1920, 1080), '720p': (1280, 720), '480p': (854, 480), '4k': (3840, 2160)}


def parse_size(size_str: str) -> Tuple[Optional[int], Optional[int]]:
    if not size_str:
        return None, None
    m = re.match(r'(\d+)[xX×](\d+)', size_str)
    if m:
        return int(m.group(1)), int(m.group(2))
    if size_str.lower() in SIZE_PRESETS:
        return SIZE_PRESETS[size_str.lower()]
    if size_str.isdigit():
        return int(size_str), None
    return None, None
