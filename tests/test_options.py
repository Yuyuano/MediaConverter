import unittest
from dataclasses import asdict
from core.options import ConvertOptions


class TestConvertOptions(unittest.TestCase):

    def test_default_values(self):
        opts = ConvertOptions()
        self.assertIsNone(opts.width)
        self.assertIsNone(opts.height)
        self.assertIsNone(opts.fps)
        self.assertIsNone(opts.quality)
        self.assertIsNone(opts.bitrate)
        self.assertIsNone(opts.audio_bitrate)
        self.assertIsNone(opts.codec)
        self.assertIsNone(opts.preset)
        self.assertIsNone(opts.extra_args)
        self.assertIsNone(opts.output_dir)
        self.assertIsNone(opts.start_time)
        self.assertIsNone(opts.trim_duration)
        self.assertFalse(opts.use_gpu)

    def test_custom_values(self):
        opts = ConvertOptions(
            width=1920, height=1080, fps=30, quality=23,
            bitrate='5M', audio_bitrate='192k',
            codec='libx264', preset='medium',
            output_dir='/tmp', start_time='00:01:00',
            trim_duration='00:00:30', use_gpu=True
        )
        self.assertEqual(opts.width, 1920)
        self.assertEqual(opts.height, 1080)
        self.assertEqual(opts.fps, 30)
        self.assertEqual(opts.quality, 23)
        self.assertEqual(opts.bitrate, '5M')
        self.assertEqual(opts.audio_bitrate, '192k')
        self.assertEqual(opts.codec, 'libx264')
        self.assertEqual(opts.preset, 'medium')
        self.assertEqual(opts.output_dir, '/tmp')
        self.assertEqual(opts.start_time, '00:01:00')
        self.assertEqual(opts.trim_duration, '00:00:30')
        self.assertTrue(opts.use_gpu)

    def test_asdict_excludes_none(self):
        opts = ConvertOptions(width=1920, quality=23)
        d = asdict(opts)
        self.assertEqual(d['width'], 1920)
        self.assertEqual(d['quality'], 23)
        self.assertIsNone(d['height'])

    def test_extra_args_list(self):
        opts = ConvertOptions(extra_args=['-pix_fmt', 'yuv420p'])
        self.assertEqual(opts.extra_args, ['-pix_fmt', 'yuv420p'])


    def test_negative_quality_clamped(self):
        opts = ConvertOptions(quality=-5)
        self.assertEqual(opts.quality, 0)

    def test_zero_fps_ignored(self):
        opts = ConvertOptions(fps=0)
        self.assertIsNone(opts.fps)

    def test_negative_fps_ignored(self):
        opts = ConvertOptions(fps=-30)
        self.assertIsNone(opts.fps)

    def test_invalid_codec_ignored(self):
        opts = ConvertOptions(codec='not_a_real_codec')
        self.assertIsNone(opts.codec)

    def test_invalid_preset_ignored(self):
        opts = ConvertOptions(preset='turbo')
        self.assertIsNone(opts.preset)

    def test_valid_codec_accepted(self):
        opts = ConvertOptions(codec='libx265')
        self.assertEqual(opts.codec, 'libx265')

    def test_valid_preset_accepted(self):
        opts = ConvertOptions(preset='slow')
        self.assertEqual(opts.preset, 'slow')

    def test_positive_quality_accepted(self):
        opts = ConvertOptions(quality=85)
        self.assertEqual(opts.quality, 85)

    def test_invalid_audio_codec_ignored(self):
        opts = ConvertOptions(audio_codec='not_a_codec')
        self.assertIsNone(opts.audio_codec)

    def test_valid_audio_codec_accepted(self):
        opts = ConvertOptions(audio_codec='libmp3lame')
        self.assertEqual(opts.audio_codec, 'libmp3lame')

    def test_invalid_bitrate_ignored(self):
        opts = ConvertOptions(bitrate='5kk')
        self.assertIsNone(opts.bitrate)

    def test_valid_bitrate_accepted(self):
        opts = ConvertOptions(bitrate='5000k')
        self.assertEqual(opts.bitrate, '5000k')

    def test_invalid_audio_bitrate_ignored(self):
        opts = ConvertOptions(audio_bitrate='abc')
        self.assertIsNone(opts.audio_bitrate)

    def test_valid_audio_bitrate_accepted(self):
        opts = ConvertOptions(audio_bitrate='192k')
        self.assertEqual(opts.audio_bitrate, '192k')

    def test_invalid_start_time_ignored(self):
        opts = ConvertOptions(start_time='not-a-time')
        self.assertIsNone(opts.start_time)

    def test_valid_start_time_accepted(self):
        opts = ConvertOptions(start_time='90')
        self.assertEqual(opts.start_time, '90')

    def test_invalid_trim_duration_ignored(self):
        opts = ConvertOptions(trim_duration='1:2:3:4')
        self.assertIsNone(opts.trim_duration)

    def test_valid_trim_duration_accepted(self):
        opts = ConvertOptions(trim_duration='00:01:30')
        self.assertEqual(opts.trim_duration, '00:01:30')

    def test_negative_width_clamped(self):
        opts = ConvertOptions(width=-100)
        self.assertIsNone(opts.width)

    def test_negative_crop_clamped(self):
        opts = ConvertOptions(crop_w=-1, crop_h=-2, crop_x=-3, crop_y=-4)
        self.assertIsNone(opts.crop_w)
        self.assertIsNone(opts.crop_h)
        self.assertIsNone(opts.crop_x)
        self.assertIsNone(opts.crop_y)

    def test_positive_crop_accepted(self):
        opts = ConvertOptions(crop_w=100, crop_h=80, crop_x=10, crop_y=20)
        self.assertEqual(opts.crop_w, 100)
        self.assertEqual(opts.crop_h, 80)
        self.assertEqual(opts.crop_x, 10)
        self.assertEqual(opts.crop_y, 20)


if __name__ == '__main__':
    unittest.main()
