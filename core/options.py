from dataclasses import dataclass
from typing import Optional, List


@dataclass
class ConvertOptions:
    """转换参数配置"""
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[int] = None
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
    replace_audio_file: Optional[str] = None
    crop_w: int = 0
    crop_h: int = 0
    crop_x: int = 0
    crop_y: int = 0
