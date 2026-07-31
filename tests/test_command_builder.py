import unittest
from unittest.mock import MagicMock
from core.command_builder import CommandBuilder
from core.options import ConvertOptions


class TestCommandBuilder(unittest.TestCase):

    def setUp(self):
        self.mgr = MagicMock()
        self.builder = CommandBuilder(self.mgr)

    def test_build_filter_empty(self):
        opts = ConvertOptions()
        result = self.builder.build_filter(opts)
        self.assertEqual(result, [])

    def test_build_filter_width_only(self):
        opts = ConvertOptions(width=1920)
        result = self.builder.build_filter(opts)
        self.assertEqual(result, ['-vf', 'scale=1920:-1'])

    def test_build_filter_height_only(self):
        opts = ConvertOptions(height=1080)
        result = self.builder.build_filter(opts)
        self.assertEqual(result, ['-vf', 'scale=-1:1080'])

    def test_build_filter_both(self):
        opts = ConvertOptions(width=1920, height=1080)
        result = self.builder.build_filter(opts)
        self.assertEqual(result, ['-vf', 'scale=1920:1080'])

    def test_build_filter_fps(self):
        opts = ConvertOptions(fps=30)
        result = self.builder.build_filter(opts)
        self.assertEqual(result, ['-vf', 'fps=30'])

    def test_build_filter_combined(self):
        opts = ConvertOptions(width=1280, height=720, fps=60)
        result = self.builder.build_filter(opts)
        self.assertIn('scale=1280:720', result[1])
        self.assertIn('fps=60', result[1])

    def test_get_gpu_encoder_nvidia_mp4(self):
        self.mgr.gpu_type = 'nvidia'
        result = self.builder.get_gpu_encoder('.mp4')
        self.assertEqual(result, 'h264_nvenc')

    def test_get_gpu_encoder_nvidia_webm(self):
        self.mgr.gpu_type = 'nvidia'
        result = self.builder.get_gpu_encoder('.webm')
        self.assertIsNone(result)

    def test_get_gpu_encoder_none(self):
        self.mgr.gpu_type = None
        result = self.builder.get_gpu_encoder('.mp4')
        self.assertIsNone(result)

    def test_get_gpu_quality_args_nvidia(self):
        self.mgr.gpu_type = 'nvidia'
        result = self.builder.get_gpu_quality_args(23)
        self.assertEqual(result, ['-cq', '23'])

    def test_get_gpu_quality_args_amd(self):
        self.mgr.gpu_type = 'amd'
        result = self.builder.get_gpu_quality_args(23)
        self.assertEqual(result, ['-qp_i', '23', '-qp_p', '23'])

    def test_get_gpu_quality_args_intel(self):
        self.mgr.gpu_type = 'intel'
        result = self.builder.get_gpu_quality_args(23)
        self.assertEqual(result, ['-global_quality', '23'])

    def test_get_gpu_quality_args_default(self):
        self.mgr.gpu_type = None
        result = self.builder.get_gpu_quality_args(23)
        self.assertEqual(result, ['-crf', '23'])

    def test_map_gpu_preset_nvidia(self):
        self.mgr.gpu_type = 'nvidia'
        self.assertEqual(self.builder.map_gpu_preset('ultrafast'), 'p1')
        self.assertEqual(self.builder.map_gpu_preset('medium'), 'p5')
        self.assertEqual(self.builder.map_gpu_preset('veryslow'), 'p7')

    def test_map_gpu_preset_amd(self):
        self.mgr.gpu_type = 'amd'
        self.assertEqual(self.builder.map_gpu_preset('medium'), 'balanced')

    def test_map_gpu_preset_intel(self):
        self.mgr.gpu_type = 'intel'
        self.assertEqual(self.builder.map_gpu_preset('medium'), 'medium')

    def test_build_video_opts_mp4_default(self):
        opts = ConvertOptions()
        result = self.builder.build_video_opts('.mp4', opts)
        self.assertIn('-c:v', result)
        self.assertIn('libx264', result)
        self.assertIn('-c:a', result)
        self.assertIn('aac', result)

    def test_build_video_opts_with_quality(self):
        opts = ConvertOptions(quality=20)
        result = self.builder.build_video_opts('.mp4', opts)
        self.assertIn('-crf', result)
        self.assertIn('20', result)

    def test_build_gif_opts_default(self):
        opts = ConvertOptions()
        result = self.builder.build_gif_opts(opts)
        self.assertIn('-vf', result)
        self.assertIn('palettegen', result[1])
        self.assertIn('paletteuse', result[1])
        self.assertIn('-loop', result)

    def test_build_gif_opts_custom(self):
        opts = ConvertOptions(width=320, fps=10, quality=8)
        result = self.builder.build_gif_opts(opts)
        self.assertIn('scale=320:-1', result[1])
        self.assertIn('fps=10', result[1])

    def test_build_audio_opts_mp3(self):
        result = self.builder.build_audio_opts('.mp3', ConvertOptions())
        self.assertIn('-c:a', result)
        self.assertIn('libmp3lame', result)

    def test_build_audio_opts_wav(self):
        result = self.builder.build_audio_opts('.wav', ConvertOptions())
        self.assertIn('pcm_s16le', result)

    def test_build_audio_opts_custom_bitrate(self):
        opts = ConvertOptions(audio_bitrate='320k')
        result = self.builder.build_audio_opts('.mp3', opts)
        self.assertIn('320k', result)

    def test_build_image_opts_jpg(self):
        opts = ConvertOptions(quality=85)
        result = self.builder.build_image_opts('.jpg', opts)
        self.assertIn('-q:v', result)
        self.assertNotIn('yuvj420p', result)

    def test_build_image_opts_png(self):
        opts = ConvertOptions(quality=85)
        result = self.builder.build_image_opts('.png', opts)
        self.assertIn('-compression_level', result)

    def test_build_image_opts_webp(self):
        opts = ConvertOptions(quality=85)
        result = self.builder.build_image_opts('.webp', opts)
        self.assertIn('-q:v', result)
        self.assertIn('85', result)

    def test_build_stream_copy_cmd(self):
        opts = ConvertOptions()
        result = self.builder.build_stream_copy_cmd(opts)
        self.assertIn('-c:v', result)
        self.assertIn('copy', result)
        self.assertIn('-c:a', result)

    def test_build_stream_copy_cmd_remove_audio(self):
        opts = ConvertOptions(remove_audio=True)
        result = self.builder.build_stream_copy_cmd(opts)
        self.assertIn('-c:v', result)
        self.assertIn('copy', result)
        self.assertIn('-an', result)

    def test_build_img_to_video_cmd(self):
        opts = ConvertOptions(quality=23, trim_duration='10')
        prefix = ['/fake/ffmpeg', '-y']
        result = self.builder.build_img_to_video_cmd('input.jpg', opts, prefix)
        self.assertIn('-loop', result)
        self.assertIn('-i', result)
        self.assertIn('input.jpg', result)
        self.assertIn('-t', result)
        self.assertIn('10', result)


if __name__ == '__main__':
    unittest.main()