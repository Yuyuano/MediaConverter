import unittest
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

from core.converter import MediaConverter
from core.options import ConvertOptions


class TestMediaConverterHelpers(unittest.TestCase):

    def setUp(self):
        self.conv = MediaConverter()
        self.conv._ffmpeg_mgr.ffmpeg_path = '/fake/ffmpeg'
        self.conv._ffmpeg_mgr.ffprobe_path = '/fake/ffprobe'

    # ── _build_filter ──

    def test_build_filter_empty(self):
        opts = ConvertOptions()
        result = self.conv._build_filter(opts)
        self.assertEqual(result, [])

    def test_build_filter_width_only(self):
        opts = ConvertOptions(width=1920)
        result = self.conv._build_filter(opts)
        self.assertEqual(result, ['-vf', 'scale=1920:-1'])

    def test_build_filter_height_only(self):
        opts = ConvertOptions(height=1080)
        result = self.conv._build_filter(opts)
        self.assertEqual(result, ['-vf', 'scale=-1:1080'])

    def test_build_filter_both(self):
        opts = ConvertOptions(width=1920, height=1080)
        result = self.conv._build_filter(opts)
        self.assertEqual(result, ['-vf', 'scale=1920:1080'])

    def test_build_filter_fps_only(self):
        opts = ConvertOptions(fps=30)
        result = self.conv._build_filter(opts)
        self.assertEqual(result, ['-vf', 'fps=30'])

    def test_build_filter_combined(self):
        opts = ConvertOptions(width=1280, height=720, fps=60)
        result = self.conv._build_filter(opts)
        self.assertIn('scale=1280:720', result[1])
        self.assertIn('fps=60', result[1])

    # ── _get_gpu_encoder ──

    def test_get_gpu_encoder_nvidia_mp4(self):
        self.conv._ffmpeg_mgr.gpu_type = 'nvidia'
        result = self.conv._get_gpu_encoder('.mp4')
        self.assertEqual(result, 'h264_nvenc')

    def test_get_gpu_encoder_amd(self):
        self.conv._ffmpeg_mgr.gpu_type = 'amd'
        result = self.conv._get_gpu_encoder('.mov')
        self.assertEqual(result, 'h264_amf')

    def test_get_gpu_encoder_intel(self):
        self.conv._ffmpeg_mgr.gpu_type = 'intel'
        result = self.conv._get_gpu_encoder('.mkv')
        self.assertEqual(result, 'h264_qsv')

    def test_get_gpu_encoder_unsupported_format(self):
        self.conv._ffmpeg_mgr.gpu_type = 'nvidia'
        result = self.conv._get_gpu_encoder('.webm')
        self.assertIsNone(result)

    def test_get_gpu_encoder_none(self):
        result = self.conv._get_gpu_encoder('.mp4')
        self.assertIsNone(result)

    # ── _map_gpu_preset ──

    def test_map_gpu_preset_nvidia(self):
        self.conv._ffmpeg_mgr.gpu_type = 'nvidia'
        self.assertEqual(self.conv._map_gpu_preset('ultrafast'), 'p1')
        self.assertEqual(self.conv._map_gpu_preset('medium'), 'p5')
        self.assertEqual(self.conv._map_gpu_preset('veryslow'), 'p7')
        self.assertEqual(self.conv._map_gpu_preset('unknown'), 'p4')

    def test_map_gpu_preset_non_nvidia(self):
        self.conv._ffmpeg_mgr.gpu_type = 'amd'
        self.assertEqual(self.conv._map_gpu_preset('medium'), 'balanced')
        self.conv._ffmpeg_mgr.gpu_type = 'intel'
        self.assertEqual(self.conv._map_gpu_preset('medium'), 'medium')

    # ── _get_gpu_quality_args ──

    def test_gpu_quality_nvidia(self):
        self.conv._ffmpeg_mgr.gpu_type = 'nvidia'
        result = self.conv._get_gpu_quality_args(23)
        self.assertEqual(result, ['-cq', '23'])

    def test_gpu_quality_amd(self):
        self.conv._ffmpeg_mgr.gpu_type = 'amd'
        result = self.conv._get_gpu_quality_args(23)
        self.assertEqual(result, ['-qp_i', '23', '-qp_p', '23'])

    def test_gpu_quality_intel(self):
        self.conv._ffmpeg_mgr.gpu_type = 'intel'
        result = self.conv._get_gpu_quality_args(23)
        self.assertEqual(result, ['-global_quality', '23'])

    def test_gpu_quality_default(self):
        result = self.conv._get_gpu_quality_args(23)
        self.assertEqual(result, ['-crf', '23'])

    # ── parse_ffmpeg_progress ──

    def test_parse_progress(self):
        line = 'frame=100 fps=30 time=00:00:30.50 bitrate=1000k'
        pct = self.conv._parse_ffmpeg_progress(line, 60.0)
        self.assertAlmostEqual(pct, 50, delta=1)

    def test_parse_progress_no_duration(self):
        line = 'frame=100 fps=30 time=00:00:30.50 bitrate=1000k'
        pct = self.conv._parse_ffmpeg_progress(line, 0.0)
        self.assertIsNone(pct)

    def test_parse_progress_exceeds_100(self):
        line = 'frame=999 time=02:00:00.00'
        pct = self.conv._parse_ffmpeg_progress(line, 10.0)
        self.assertEqual(pct, 100)


class TestMediaConverterBuildVideoOpts(unittest.TestCase):

    def setUp(self):
        self.conv = MediaConverter()
        self.conv._ffmpeg_mgr.ffmpeg_path = '/fake/ffmpeg'

    # ── _build_video_opts ──

    def test_video_opts_mp4_default(self):
        opts = ConvertOptions()
        result = self.conv._build_video_opts('.mp4', opts)
        self.assertIn('-c:v', result)
        self.assertIn('libx264', result)
        self.assertIn('-c:a', result)
        self.assertIn('aac', result)

    def test_video_opts_webm_audio_codec(self):
        opts = ConvertOptions()
        result = self.conv._build_video_opts('.webm', opts)
        self.assertIn('libvpx-vp9', result)
        self.assertIn('libopus', result)

    def test_video_opts_wmv_audio_codec(self):
        opts = ConvertOptions()
        result = self.conv._build_video_opts('.wmv', opts)
        self.assertIn('wmv2', result)
        self.assertIn('wmav2', result)

    def test_video_opts_avi_codec(self):
        opts = ConvertOptions()
        result = self.conv._build_video_opts('.avi', opts)
        self.assertIn('libxvid', result)

    def test_video_opts_with_quality(self):
        opts = ConvertOptions(quality=20)
        result = self.conv._build_video_opts('.mp4', opts)
        self.assertIn('-crf', result)
        self.assertIn('20', result)

    def test_video_opts_with_bitrate(self):
        opts = ConvertOptions(bitrate='5M')
        result = self.conv._build_video_opts('.mp4', opts)
        self.assertIn('-b:v', result)
        self.assertIn('5M', result)

    def test_video_opts_with_preset(self):
        opts = ConvertOptions(preset='slow')
        result = self.conv._build_video_opts('.mp4', opts)
        self.assertIn('-preset', result)
        self.assertIn('slow', result)

    def test_video_opts_custom_codec(self):
        opts = ConvertOptions(codec='libx265')
        result = self.conv._build_video_opts('.mp4', opts)
        self.assertIn('-c:v', result)
        self.assertIn('libx265', result)

    def test_video_opts_gif_no_dual_vf(self):
        opts = ConvertOptions(width=320, fps=10, quality=8)
        result = self.conv._build_video_opts('.gif', opts)
        vf_count = sum(1 for a in result if a == '-vf')
        self.assertEqual(vf_count, 1)
        vf_idx = result.index('-vf')
        vf_value = result[vf_idx + 1]
        self.assertIn('scale=320:-1', vf_value)
        self.assertIn('fps=10', vf_value)
        self.assertIn('palettegen', vf_value)
        self.assertIn('paletteuse', vf_value)

    def test_video_opts_with_extra_args(self):
        opts = ConvertOptions(extra_args=['-pix_fmt', 'yuv420p'])
        result = self.conv._build_video_opts('.mp4', opts)
        self.assertIn('-pix_fmt', result)
        self.assertIn('yuv420p', result)

    # ── _build_image_opts ──

    def test_image_opts_jpg(self):
        opts = ConvertOptions(quality=5)
        result = self.conv._build_image_opts('.jpg', opts)
        self.assertIn('-q:v', result)
        self.assertIn('format=yuvj420p', result)

    def test_image_opts_png(self):
        opts = ConvertOptions(quality=5)
        result = self.conv._build_image_opts('.png', opts)
        self.assertIn('-compression_level', result)

    def test_image_opts_webp(self):
        opts = ConvertOptions(quality=85)
        result = self.conv._build_image_opts('.webp', opts)
        self.assertIn('-q:v', result)
        self.assertIn('85', result)

    def test_image_opts_with_resize(self):
        opts = ConvertOptions(width=800, height=600)
        result = self.conv._build_image_opts('.jpg', opts)
        self.assertTrue(any('scale=800:600' in a for a in result))

    # ── _build_audio_opts ──

    def test_audio_opts_mp3(self):
        result = self.conv._build_audio_opts('.mp3', ConvertOptions())
        self.assertIn('-c:a', result)
        self.assertIn('libmp3lame', result)

    def test_audio_opts_wav(self):
        result = self.conv._build_audio_opts('.wav', ConvertOptions())
        self.assertIn('pcm_s16le', result)

    def test_audio_opts_flac(self):
        result = self.conv._build_audio_opts('.flac', ConvertOptions())
        self.assertIn('flac', result)

    def test_audio_opts_custom_bitrate(self):
        opts = ConvertOptions(audio_bitrate='320k')
        result = self.conv._build_audio_opts('.mp3', opts)
        self.assertIn('320k', result)


class TestMediaConverterConvert(unittest.TestCase):

    def setUp(self):
        self.conv = MediaConverter()
        self.conv._ffmpeg_mgr.ffmpeg_path = '/fake/ffmpeg'
        self.conv._ffmpeg_mgr.ffprobe_path = '/fake/ffprobe'

    @patch('core.converter.MediaConverter._run_ffmpeg', return_value=True)
    @patch('os.path.exists', return_value=True)
    @patch('os.path.getsize', return_value=1024000)
    def test_convert_video_to_video(self, mock_size, mock_exists, mock_run):
        opts = ConvertOptions(quality=23, preset='medium')
        result = self.conv.convert('input.mp4', 'output.avi', opts)
        self.assertTrue(result)

    @patch('core.converter.MediaConverter._run_ffmpeg', return_value=True)
    @patch('os.path.exists', return_value=True)
    def test_convert_image_to_image(self, mock_exists, mock_run):
        opts = ConvertOptions(quality=5)
        result = self.conv.convert('input.jpg', 'output.png', opts)
        self.assertTrue(result)

    @patch('core.converter.MediaConverter._run_ffmpeg', return_value=True)
    @patch('os.path.exists', return_value=True)
    def test_convert_video_to_image(self, mock_exists, mock_run):
        opts = ConvertOptions()
        result = self.conv.convert('input.mp4', 'output.jpg', opts)
        self.assertTrue(result)

    @patch('core.converter.MediaConverter._run_ffmpeg', return_value=True)
    @patch('os.path.exists', return_value=True)
    def test_convert_video_to_audio(self, mock_exists, mock_run):
        opts = ConvertOptions()
        result = self.conv.convert('input.mp4', 'output.mp3', opts)
        self.assertTrue(result)

    @patch('core.converter.MediaConverter._run_ffmpeg', return_value=True)
    @patch('os.path.exists', return_value=True)
    def test_convert_audio_to_audio(self, mock_exists, mock_run):
        opts = ConvertOptions(audio_bitrate='320k')
        result = self.conv.convert('input.wav', 'output.mp3', opts)
        self.assertTrue(result)

    def test_convert_file_not_found(self):
        result = self.conv.convert('/nonexistent/file.mp4', '/tmp/out.mp4')
        self.assertFalse(result)

    @patch('core.converter.MediaConverter._run_ffmpeg', return_value=True)
    @patch('os.path.exists', return_value=True)
    def test_convert_image_to_video(self, mock_exists, mock_run):
        opts = ConvertOptions(trim_duration='10')
        result = self.conv.convert('input.jpg', 'output.mp4', opts)
        self.assertTrue(result)

    @patch('core.converter.MediaConverter._run_ffmpeg', return_value=True)
    @patch('os.path.exists', return_value=True)
    def test_convert_with_trim(self, mock_exists, mock_run):
        opts = ConvertOptions(start_time='00:01:00', trim_duration='00:00:30')
        result = self.conv.convert('input.mp4', 'output.mp4', opts)
        self.assertTrue(result)

    @patch('core.converter.MediaConverter._run_ffmpeg', return_value=True)
    @patch('os.path.exists', return_value=True)
    def test_convert_with_gpu(self, mock_exists, mock_run):
        self.conv._ffmpeg_mgr.gpu_type = 'nvidia'
        self.conv._ffmpeg_mgr._hwaccel = 'cuda'
        opts = ConvertOptions(use_gpu=True)
        result = self.conv.convert('input.mp4', 'output.mp4', opts)
        self.assertTrue(result)


class TestMediaConverterGetDefaultOpts(unittest.TestCase):

    def setUp(self):
        self.conv = MediaConverter()

    def test_default_mp4(self):
        opts = self.conv.get_default_opts('mp4', 'video')
        self.assertEqual(opts.quality, 23)
        self.assertEqual(opts.preset, 'medium')

    def test_default_gif(self):
        opts = self.conv.get_default_opts('gif', 'video')
        self.assertEqual(opts.width, 480)
        self.assertEqual(opts.fps, 15)
        self.assertEqual(opts.quality, 10)

    def test_default_jpg(self):
        opts = self.conv.get_default_opts('jpg', 'image')
        self.assertEqual(opts.quality, 85)

    def test_default_unknown(self):
        opts = self.conv.get_default_opts('xyz', 'video')
        self.assertIsNone(opts.quality)


if __name__ == '__main__':
    unittest.main()
