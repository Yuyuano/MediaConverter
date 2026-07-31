from typing import Optional, List

from .options import ConvertOptions
from .validators import validate_extra_args
from .constants import DEFAULT_AUDIO_BITRATE, DEFAULT_IMAGE_QUALITY

_JPEG_EXT_SET = ('.jpg', '.jpeg')


class CommandBuilder:
    """构建 FFmpeg 命令行参数（无状态，从 FFmpegManager 读取 GPU 状态）"""

    def __init__(self, ffmpeg_mgr):
        self._mgr = ffmpeg_mgr

    @property
    def _gpu_type(self) -> Optional[str]:
        return self._mgr.gpu_type

    def _build_transform_filters(self, opts: ConvertOptions) -> List[str]:
        """旋转/翻转/裁剪滤镜（裁剪基于原始分辨率，必须置于 scale 之前）。"""
        filters = []
        if opts.rotate == 90 or opts.rotate == 180 or opts.rotate == 270:
            if opts.rotate == 90:
                filters.append("transpose=1")
            elif opts.rotate == 270:
                filters.append("transpose=2")
            else:
                filters.append("transpose=2,transpose=2")
        if opts.flip_h:
            filters.append("hflip")
        if opts.flip_v:
            filters.append("vflip")
        if opts.crop_w and opts.crop_h:
            x = opts.crop_x or 0
            y = opts.crop_y or 0
            filters.append(f"crop={opts.crop_w}:{opts.crop_h}:{x}:{y}")
        return filters

    def build_filter(self, opts: ConvertOptions) -> List[str]:
        filters = self._build_transform_filters(opts)
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

    def get_gpu_encoder(self, ext: str) -> Optional[str]:
        gpu_encoders = {'nvidia': 'h264_nvenc', 'amd': 'h264_amf', 'intel': 'h264_qsv'}
        gpu_codec = gpu_encoders.get(self._gpu_type)
        if gpu_codec and ext in ('.mp4', '.mov', '.mkv', '.m4v', '.flv', '.avi'):
            return gpu_codec
        return None

    def get_gpu_quality_args(self, quality: int) -> List[str]:
        if self._gpu_type == 'nvidia':
            return ['-cq', str(quality)]
        elif self._gpu_type == 'amd':
            return ['-qp_i', str(quality), '-qp_p', str(quality)]
        elif self._gpu_type == 'intel':
            return ['-global_quality', str(quality)]
        return ['-crf', str(quality)]

    def map_gpu_preset(self, preset: str) -> str:
        if self._gpu_type == 'nvidia':
            p_map = {
                'ultrafast': 'p1', 'superfast': 'p2', 'veryfast': 'p3',
                'faster': 'p4', 'fast': 'p4', 'medium': 'p5',
                'slow': 'p6', 'slower': 'p7', 'veryslow': 'p7'
            }
            return p_map.get(preset, 'p4')
        elif self._gpu_type == 'amd':
            p_map = {
                'ultrafast': 'speed', 'superfast': 'speed', 'veryfast': 'speed',
                'faster': 'speed', 'fast': 'balanced',
                'medium': 'balanced',
                'slow': 'quality', 'slower': 'quality', 'veryslow': 'quality'
            }
            return p_map.get(preset, 'balanced')
        elif self._gpu_type == 'intel':
            p_map = {
                'ultrafast': 'veryfast', 'superfast': 'veryfast', 'veryfast': 'veryfast',
                'faster': 'faster', 'fast': 'medium',
                'medium': 'medium',
                'slow': 'slow', 'slower': 'very_slow', 'veryslow': 'very_slow'
            }
            return p_map.get(preset, 'medium')
        return preset

    def build_video_opts(self, output_ext: str, opts: ConvertOptions) -> List[str]:
        args = []
        ext = output_ext.lower()

        if ext == '.gif':
            return self.build_gif_opts(opts)

        args.extend(self.build_filter(opts))
        codec_map = {
            '.mp4': 'libx264', '.mov': 'libx264', '.m4v': 'libx264',
            '.avi': 'libxvid', '.mkv': 'libx264', '.webm': 'libvpx-vp9',
            '.wmv': 'wmv2', '.flv': 'libx264',
            '.ts': 'mpeg2video', '.m2ts': 'libx264',
        }
        if opts.use_gpu and self._gpu_type:
            gpu_codec = self.get_gpu_encoder(ext)
            if gpu_codec:
                for k in list(codec_map.keys()):
                    if k not in ('.webm', '.wmv'):
                        codec_map[k] = gpu_codec
        if opts.codec:
            args.extend(['-c:v', opts.codec])
        elif ext in codec_map:
            args.extend(['-c:v', codec_map[ext]])
        if opts.quality is not None:
            if opts.use_gpu and self._gpu_type and self.get_gpu_encoder(ext):
                args.extend(self.get_gpu_quality_args(opts.quality))
            else:
                args.extend(['-crf', str(opts.quality)])
        elif opts.bitrate:
            args.extend(['-b:v', opts.bitrate])
        if opts.preset:
            if opts.use_gpu and self._gpu_type and self.get_gpu_encoder(ext):
                args.extend(['-preset', self.map_gpu_preset(opts.preset)])
            else:
                args.extend(['-preset', opts.preset])

        args.extend(self.build_audio_opts(ext, opts))
        if opts.extra_args:
            args.extend(validate_extra_args(opts.extra_args))
        return args

    def build_gif_opts(self, opts: ConvertOptions) -> List[str]:
        quality = opts.quality if opts.quality is not None else 5
        max_colors = min(256, max(32, 32 + quality * 24))
        filter_parts = self._build_transform_filters(opts)
        w = opts.width or -1
        h = opts.height or -1
        if w == -1 and h == -1:
            w = 480
        filter_parts.append(f"scale={w}:{h}:flags=lanczos")
        fps_val = opts.fps or 30
        filter_parts.append(f"fps={fps_val}")
        filter_parts.append(f"split[s0][s1];[s0]palettegen=max_colors={max_colors}[p];[s1][p]paletteuse")
        return ['-vf', ','.join(filter_parts), '-loop', '0']

    def build_audio_opts(self, ext: str, opts: ConvertOptions) -> List[str]:
        if opts.remove_audio:
            return ['-an']
        audio_codec_map = {
            '.webm': 'libopus', '.wmv': 'wmav2',
            '.mp4': 'aac', '.mov': 'aac', '.m4v': 'aac',
            '.mkv': 'aac', '.avi': 'aac', '.flv': 'aac',
            '.mp3': 'libmp3lame', '.wav': 'pcm_s16le',
            '.aac': 'aac', '.flac': 'flac', '.ogg': 'libvorbis',
            '.m4a': 'aac', '.wma': 'wmav2',
        }
        codec = opts.audio_codec or audio_codec_map.get(ext, 'aac')
        br = opts.audio_bitrate or DEFAULT_AUDIO_BITRATE
        return ['-c:a', codec, '-b:a', br]

    def build_image_opts(self, output_ext: str, opts: ConvertOptions) -> List[str]:
        args = []
        vf = []
        if opts.width or opts.height:
            w = opts.width or -1
            h = opts.height or -1
            vf.append(f"scale={w}:{h}:flags=lanczos")
        q = opts.quality if opts.quality is not None else DEFAULT_IMAGE_QUALITY
        ext = output_ext.lower()
        if ext in _JPEG_EXT_SET:
            jpeg_q = max(2, min(31, 32 - int((q / 100) * 30)))
            args.extend(['-q:v', str(jpeg_q)])
        elif ext == '.png':
            compression = 9 - min(9, max(0, int((q / 100) * 9)))
            args.extend(['-compression_level', str(compression)])
        elif ext == '.webp':
            args.extend(['-q:v', str(min(max(q, 1), 100))])
        if vf:
            args.extend(['-vf', ','.join(vf)])
        return args

    def build_stream_copy_cmd(self, opts: ConvertOptions) -> List[str]:
        args = ['-map_metadata', '0']
        if opts.remove_audio:
            args.extend(['-c:v', 'copy', '-an'])
        else:
            args.extend(['-c:v', 'copy', '-c:a', 'copy'])
        return args

    def build_img_to_video_cmd(self, input_file: str, opts: ConvertOptions, prefix: List[str]) -> List[str]:
        duration = opts.trim_duration or "5"
        codec = opts.codec
        if not codec and opts.use_gpu:
            codec = self.get_gpu_encoder('.mp4')
        if not codec:
            codec = 'libx264'
        cmd = list(prefix)
        cmd.extend([
            '-loop', '1',
            '-i', input_file, '-c:v', codec,
            '-t', str(duration), '-pix_fmt', 'yuv420p'
        ])
        cmd.extend(self.build_filter(opts))
        if opts.quality is not None:
            if opts.use_gpu and self._gpu_type:
                cmd.extend(self.get_gpu_quality_args(opts.quality))
                if opts.preset:
                    cmd.extend(['-preset', self.map_gpu_preset(opts.preset)])
            else:
                cmd.extend(['-crf', str(opts.quality)])
        return cmd
