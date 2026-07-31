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
    '-map', '-map_metadata', '-map_chapters',
    '-threads', '-max_muxing_queue_size', '-avoid_negative_ts',
}

SAFE_FFMPEG_BOOL_FLAGS = {'-sn', '-dn', '-an'}


_EXTRA_ARG_DENY_RE = re.compile(r'[;&|`$(){}\\\n\r=<>]')


def validate_extra_args(extra_args: Optional[List[str]]) -> List[str]:
    if not extra_args:
        return []
    safe_args = []
    i = 0
    while i < len(extra_args):
        arg = extra_args[i]
        if arg.startswith('-') and arg in SAFE_FFMPEG_BOOL_FLAGS:
            safe_args.append(arg)
        elif arg.startswith('-') and arg in SAFE_FFMPEG_FLAGS:
            safe_args.append(arg)
            if i + 1 < len(extra_args) and not extra_args[i + 1].startswith('-'):
                i += 1
                val = extra_args[i]
                if not _EXTRA_ARG_DENY_RE.search(val):
                    safe_args.append(val)
                else:
                    logger.warning(f"已过滤不安全的 FFmpeg 参数值: {val}")
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
        resolved_str = str(resolved)
        if os.path.exists(resolved_str):
            real_path = os.path.realpath(resolved_str)
            if os.path.exists(real_path):
                resolved = Path(real_path)
        return str(resolved)
    except (OSError, ValueError) as e:
        logger.error(f"无效路径: {e}")
        return None


SIZE_PRESETS = {'4k': (3840, 2160), '2k': (2560, 1440), '1080p': (1920, 1080), '720p': (1280, 720), '480p': (854, 480)}

_SIZE_RE = re.compile(r'(\d+)[xX×](\d+)')


def parse_size(size_str: str) -> Tuple[Optional[int], Optional[int]]:
    if not size_str:
        return None, None
    size_str = size_str.strip()
    m = _SIZE_RE.match(size_str)
    if m:
        w, h = int(m.group(1)), int(m.group(2))
        if w == 0 or h == 0:
            return None, None
        return w, h
    if size_str.lower() in SIZE_PRESETS:
        return SIZE_PRESETS[size_str.lower()]
    if size_str.isdigit():
        val = int(size_str)
        if val > 0:
            return val, None
    if size_str.startswith('x'):
        h_str = size_str[1:]
        if h_str.isdigit():
            val = int(h_str)
            if val > 0:
                return None, val
    return None, None
