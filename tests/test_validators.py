import unittest
import os
import tempfile
from pathlib import Path
from core.validators import validate_extra_args, validate_output_dir, parse_size


class TestParseSize(unittest.TestCase):

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

    def test_4k(self):
        self.assertEqual(parse_size("4K"), (3840, 2160))

    def test_width_only(self):
        self.assertEqual(parse_size("1280"), (1280, None))

    def test_height_only(self):
        self.assertEqual(parse_size("x720"), (None, 720))

    def test_2k(self):
        self.assertEqual(parse_size("2K"), (2560, 1440))

    def test_zero_dimensions_rejected(self):
        self.assertEqual(parse_size("0x1080"), (None, None))

    def test_empty_string(self):
        self.assertEqual(parse_size(""), (None, None))

    def test_invalid_input(self):
        self.assertEqual(parse_size("abc"), (None, None))


class TestValidateExtraArgs(unittest.TestCase):

    def test_safe_flag_with_value(self):
        result = validate_extra_args(['-pix_fmt', 'yuv420p'])
        self.assertEqual(result, ['-pix_fmt', 'yuv420p'])

    def test_safe_flag_no_value(self):
        result = validate_extra_args(['-map_metadata'])
        self.assertEqual(result, ['-map_metadata'])

    def test_unsafe_flag_filtered(self):
        result = validate_extra_args(['-i', '/etc/passwd'])
        self.assertEqual(result, [])

    def test_bool_flag_does_not_consume_next_arg(self):
        result = validate_extra_args(['-an', 'foo', '-sn', 'bar', '-dn', 'baz'])
        self.assertEqual(result, ['-an', '-sn', '-dn'])

    def test_bool_flag_with_value_after_rejected(self):
        result = validate_extra_args(['-an', '-pix_fmt', 'yuv420p'])
        self.assertEqual(result, ['-an', '-pix_fmt', 'yuv420p'])

    def test_mixed_safe_and_unsafe(self):
        result = validate_extra_args(['-pix_fmt', 'yuv420p', '-i', '/bad', '-threads', '4'])
        self.assertEqual(result, ['-pix_fmt', 'yuv420p', '-threads', '4'])

    def test_multiple_safe_flags(self):
        result = validate_extra_args(['-pix_fmt', 'yuv420p', '-threads', '4', '-g', '250'])
        self.assertEqual(result, ['-pix_fmt', 'yuv420p', '-threads', '4', '-g', '250'])

    def test_empty_args(self):
        self.assertEqual(validate_extra_args([]), [])

    def test_none_args(self):
        self.assertEqual(validate_extra_args(None), [])


class TestValidateOutputDir(unittest.TestCase):

    def test_valid_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = validate_output_dir(tmp)
            self.assertIsNotNone(result)
            self.assertTrue(os.path.isabs(result))

    def test_none_path(self):
        self.assertIsNone(validate_output_dir(None))

    def test_empty_string(self):
        self.assertIsNone(validate_output_dir(""))

    def test_path_traversal_rejected(self):
        result = validate_output_dir(os.path.join("..", "..", "Windows"))
        self.assertIsNone(result)


    def test_shell_injection_semicolon(self):
        result = validate_extra_args(['-pix_fmt', 'yuv420p;rm -rf /'])
        self.assertEqual(result, ['-pix_fmt'])

    def test_shell_injection_pipe(self):
        result = validate_extra_args(['-pix_fmt', 'yuv420p|cat /etc/passwd'])
        self.assertEqual(result, ['-pix_fmt'])

    def test_shell_injection_backtick(self):
        result = validate_extra_args(['-pix_fmt', '`whoami`'])
        self.assertEqual(result, ['-pix_fmt'])

    def test_shell_injection_dollar(self):
        result = validate_extra_args(['-pix_fmt', '$HOME'])
        self.assertEqual(result, ['-pix_fmt'])

    def test_safe_value_with_path(self):
        result = validate_extra_args(['-pix_fmt', 'yuv420p'])
        self.assertEqual(result, ['-pix_fmt', 'yuv420p'])


if __name__ == '__main__':
    unittest.main()
