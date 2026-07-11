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


if __name__ == '__main__':
    unittest.main()
