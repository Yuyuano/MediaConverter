import re
import logging
from dataclasses import dataclass
from typing import Optional, List

logger = logging.getLogger('MediaConverter')


_VALID_CODECS = {
    'libx264', 'libx265', 'libxvid', 'libvpx-vp9', 'libvpx',
    'wmv2', 'mpeg2video', 'gif', 'mjpeg', 'rawvideo',
    'h264_nvenc', 'h264_amf', 'h264_qsv',
    'hevc_nvenc', 'hevc_amf', 'hevc_qsv',
    'av1_nvenc', 'av1_amf', 'av1_qsv',
}

_VALID_PRESETS = {
    'ultrafast', 'superfast', 'veryfast', 'faster', 'fast',
    'medium', 'slow', 'slower', 'veryslow',
    'p1', 'p2', 'p3', 'p4', 'p5', 'p6', 'p7',
    'speed', 'balanced', 'quality',
    'very_slow',
}

_VALID_AUDIO_CODECS = {
    'aac', 'libmp3lame', 'libopus', 'libvorbis', 'flac',
    'pcm_s16le', 'wmav2', 'copy',
}

_BITRATE_RE = re.compile(r'^\d+[kKmM]?$')
_TIME_RE = re.compile(r'^(\d+:)?(\d+:)?\d+(\.\d+)?$')


@dataclass
class ConvertOptions:
    """转换参数配置"""
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    quality: Optional[int] = None
    bitrate: Optional[str] = None
    audio_bitrate: Optional[str] = None
    audio_codec: Optional[str] = None
    codec: Optional[str] = None
    preset: Optional[str] = None
    extra_args: Optional[List[str]] = None
    output_dir: Optional[str] = None
    start_time: Optional[str] = None
    trim_duration: Optional[str] = None
    use_gpu: bool = False
    stream_copy: bool = False
    remove_audio: bool = False
    rotate: Optional[int] = None
    flip_h: bool = False
    flip_v: bool = False
    replace_audio_file: Optional[str] = None
    crop_w: Optional[int] = None
    crop_h: Optional[int] = None
    crop_x: Optional[int] = None
    crop_y: Optional[int] = None

    def __post_init__(self):
        if self.quality is not None and self.quality < 0:
            logger.warning(f"quality 不能为负数，已设为 0")
            self.quality = 0
        if self.fps is not None and self.fps <= 0:
            logger.warning(f"fps 必须为正数，已忽略: {self.fps}")
            self.fps = None
        if self.codec and self.codec not in _VALID_CODECS:
            logger.warning(f"未知编码器 '{self.codec}'，已忽略")
            self.codec = None
        if self.preset and self.preset not in _VALID_PRESETS:
            logger.warning(f"未知预设 '{self.preset}'，已忽略")
            self.preset = None
        if self.audio_codec and self.audio_codec not in _VALID_AUDIO_CODECS:
            logger.warning(f"未知音频编码器 '{self.audio_codec}'，已忽略")
            self.audio_codec = None
        if self.bitrate and not _BITRATE_RE.match(self.bitrate):
            logger.warning(f"无效比特率格式 '{self.bitrate}'，已忽略")
            self.bitrate = None
        if self.audio_bitrate and not _BITRATE_RE.match(self.audio_bitrate):
            logger.warning(f"无效音频比特率格式 '{self.audio_bitrate}'，已忽略")
            self.audio_bitrate = None
        if self.start_time and not _TIME_RE.match(self.start_time):
            logger.warning(f"无效开始时间格式 '{self.start_time}'，已忽略")
            self.start_time = None
        if self.trim_duration and not _TIME_RE.match(self.trim_duration):
            logger.warning(f"无效时长格式 '{self.trim_duration}'，已忽略")
            self.trim_duration = None
        if self.width is not None and self.width < 0:
            self.width = None
        if self.height is not None and self.height < 0:
            self.height = None
        if self.crop_w is not None and self.crop_w < 0:
            self.crop_w = None
        if self.crop_h is not None and self.crop_h < 0:
            self.crop_h = None
        if self.crop_x is not None and self.crop_x < 0:
            self.crop_x = None
        if self.crop_y is not None and self.crop_y < 0:
            self.crop_y = None
