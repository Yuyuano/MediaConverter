# 注意：此测试文件测试的是旧版 CLI 模块 converter.py（legacy）。
# 新版 core/ 模块的测试位于 tests/ 目录下。
import unittest
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent))

from converter import ConvertOptions, parse_size, MediaConverter


class TestParseSize(unittest.TestCase):
    """测试尺寸解析函数"""

    def test_width_x_height(self):
        self.assertEqual(parse_size("1920x1080"), (1920, 1080))

    def test_width_x_height_uppercase(self):
        self.assertEqual(parse_size("1920X1080"), (1920, 1080))

    def test_1080p(self):
        self.assertEqual(parse_size("1080p"), (1920, 1080))

    def test_720p(self):
        self.assertEqual(parse_size("720p"), (1280, 720))

    def test_480p(self):
        self.assertEqual(parse_size("480p"), (854, 480))

    def test_width_only(self):
        self.assertEqual(parse_size("1280"), (1280, None))

    def test_empty_string(self):
        self.assertEqual(parse_size(""), (None, None))

    def test_invalid_input(self):
        self.assertEqual(parse_size("abc"), (None, None))


class TestConvertOptions(unittest.TestCase):
    """测试 ConvertOptions 数据类"""

    def test_default_values(self):
        opts = ConvertOptions()
        self.assertIsNone(opts.width)
        self.assertIsNone(opts.height)
        self.assertIsNone(opts.fps)
        self.assertIsNone(opts.quality)
        self.assertFalse(opts.use_gpu)

    def test_custom_values(self):
        opts = ConvertOptions(width=1920, height=1080, quality=23, use_gpu=True)
        self.assertEqual(opts.width, 1920)
        self.assertEqual(opts.height, 1080)
        self.assertEqual(opts.quality, 23)
        self.assertTrue(opts.use_gpu)


class TestValidateExtraArgs(unittest.TestCase):
    """测试 extra_args 白名单校验"""

    def setUp(self):
        self.converter = MagicMock(spec=MediaConverter)
        self.converter.SAFE_FFMPEG_FLAGS = MediaConverter.SAFE_FFMPEG_FLAGS
        self.converter._validate_extra_args = MediaConverter._validate_extra_args.__get__(self.converter)

    def test_safe_flag_passes(self):
        result = self.converter._validate_extra_args(['-pix_fmt', 'yuv420p'])
        self.assertEqual(result, ['-pix_fmt', 'yuv420p'])

    def test_unsafe_flag_filtered(self):
        result = self.converter._validate_extra_args(['-i', '/etc/passwd'])
        self.assertEqual(result, [])

    def test_multiple_safe_flags(self):
        result = self.converter._validate_extra_args(['-pix_fmt', 'yuv420p', '-threads', '4'])
        self.assertEqual(result, ['-pix_fmt', 'yuv420p', '-threads', '4'])

    def test_empty_args(self):
        result = self.converter._validate_extra_args([])
        self.assertEqual(result, [])

    def test_none_args(self):
        result = self.converter._validate_extra_args(None)
        self.assertEqual(result, [])


class TestValidateOutputDir(unittest.TestCase):
    """测试输出目录路径校验"""

    def test_valid_path(self):
        result = MediaConverter._validate_output_dir("C:\\Users\\test\\output")
        self.assertIsNotNone(result)

    def test_path_traversal_rejected(self):
        result = MediaConverter._validate_output_dir("C:\\Users\\..\\..\\Windows")
        self.assertIsNone(result)

    def test_empty_path(self):
        result = MediaConverter._validate_output_dir("")
        self.assertIsNone(result)

    def test_none_path(self):
        result = MediaConverter._validate_output_dir(None)
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
