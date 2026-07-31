import unittest
from unittest.mock import MagicMock, patch
from core.probe import MediaProbe
from core.options import ConvertOptions
import json


class TestMediaProbe(unittest.TestCase):

    def setUp(self):
        self.mgr = MagicMock()
        self.mgr.ffmpeg_path = '/fake/ffmpeg'
        self.mgr.ffprobe_path = '/fake/ffprobe'
        self.probe = MediaProbe(self.mgr)

    def test_get_info_no_ffprobe(self):
        self.mgr.ffprobe_path = None
        result = self.probe.get_info('test.mp4')
        self.assertEqual(result, {})

    def test_get_info_cache_hit(self):
        mock_data = {
            'streams': [{'width': 1920, 'height': 1080, 'duration': '60.0',
                         'r_frame_rate': '30/1', 'codec_name': 'h264', 'bit_rate': '1000000'}],
            'format': {'duration': '60.0', 'size': '1000000', 'bit_rate': '1000000', 'format_name': 'mov,mp4,m4a'}
        }
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(mock_data))
            result1 = self.probe.get_info('test.mp4')
            result2 = self.probe.get_info('test.mp4')
            mock_run.assert_called_once()
            self.assertEqual(result1, result2)

    def test_get_info_json_parsing(self):
        mock_data = {
            'streams': [{'width': 1920, 'height': 1080, 'duration': '60.0',
                         'r_frame_rate': '30/1', 'codec_name': 'h264', 'bit_rate': '1000000'}],
            'format': {'duration': '60.0', 'size': '1000000', 'bit_rate': '1000000', 'format_name': 'mov,mp4,m4a'}
        }
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(mock_data))
            result = self.probe.get_info('test.mp4')
            self.assertEqual(result['width'], '1920')
            self.assertEqual(result['height'], '1080')
            self.assertEqual(result['duration'], '60.0')
            self.assertEqual(result['codec_name'], 'h264')
            self.assertEqual(result['r_frame_rate'], '30/1')
            self.assertEqual(result['format_name'], 'mov,mp4,m4a')

    def test_get_info_no_stream_audio_only(self):
        mock_data = {
            'streams': [],
            'format': {'duration': '120.0', 'size': '5000000', 'bit_rate': '320000', 'format_name': 'mp3'}
        }
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(mock_data))
            result = self.probe.get_info('test.mp3')
            self.assertEqual(result.get('codec_name'), None)
            self.assertEqual(result['duration'], '120.0')
            self.assertEqual(result['format_name'], 'mp3')

    def test_get_info_format_overwrites_stream(self):
        mock_data = {
            'streams': [{'duration': '59.0', 'bit_rate': '900000'}],
            'format': {'duration': '60.0', 'bit_rate': '1000000', 'format_name': 'mp4'}
        }
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(mock_data))
            result = self.probe.get_info('test.mp4')
            self.assertEqual(result['duration'], '60.0')
            self.assertEqual(result['bit_rate'], '1000000')

    def test_get_duration_from_cache(self):
        mock_data = {
            'streams': [{'duration': '60.0'}],
            'format': {'duration': '60.0'}
        }
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(mock_data))
            self.probe.get_info('test.mp4')
            duration1 = self.probe.get_duration('test.mp4')
            duration2 = self.probe.get_duration('test.mp4')
            mock_run.assert_called_once()
            self.assertEqual(duration1, 60.0)
            self.assertEqual(duration2, 60.0)

    def test_get_file_summary_valid(self):
        mock_data = {
            'streams': [{'width': 1920, 'height': 1080, 'duration': '60.0',
                         'r_frame_rate': '30/1', 'codec_name': 'h264', 'bit_rate': '1000000'}],
            'format': {'duration': '60.0', 'size': '1000000', 'bit_rate': '1000000', 'format_name': 'mov,mp4,m4a'}
        }
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(mock_data))
            result = self.probe.get_file_summary('test.mp4')
            self.assertTrue(result['valid'])
            self.assertEqual(result['width'], 1920)
            self.assertEqual(result['height'], 1080)
            self.assertEqual(result['duration'], 60.0)
            self.assertEqual(result['size_mb'], 1000000 / (1024 * 1024))
            self.assertEqual(result['fps'], 30.0)

    def test_get_file_summary_invalid(self):
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout='')
            result = self.probe.get_file_summary('test.mp4')
            self.assertFalse(result['valid'])

    def test_get_file_summary_non_fractional_fps(self):
        mock_data = {
            'streams': [{'r_frame_rate': '30', 'duration': '60.0'}],
            'format': {'duration': '60.0', 'format_name': 'mp4'}
        }
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(mock_data))
            result = self.probe.get_file_summary('test.mp4')
            self.assertEqual(result['fps'], 30.0)

    def test_estimate_output_size_by_bitrate(self):
        mock_data = {
            'streams': [{'duration': '60.0'}],
            'format': {'duration': '60.0', 'size': '1000000'}
        }
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(mock_data))
            opts = ConvertOptions(bitrate='2M')
            result = self.probe.estimate_output_size('test.mp4', opts)
            self.assertIsNotNone(result)
            expected = (2000000 * 60 / 8 + 128000 * 60 / 8) / (1024 * 1024)
            self.assertAlmostEqual(result, expected, delta=0.01)

    def test_estimate_output_size_by_quality(self):
        mock_data = {
            'streams': [],
            'format': {'duration': '60.0', 'size': '10000000'}
        }
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(mock_data))
            opts = ConvertOptions(quality=20)
            result = self.probe.estimate_output_size('test.mp4', opts)
            self.assertIsNotNone(result)
            expected = (10000000 / (1024 * 1024)) * (2 ** ((23 - 20) / 6))
            self.assertAlmostEqual(result, expected, delta=0.01)

    def test_estimate_output_size_zero_duration(self):
        mock_data = {'streams': [], 'format': {'duration': '0'}}
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(mock_data))
            result = self.probe.estimate_output_size('test.mp4', ConvertOptions())
            self.assertIsNone(result)

    def test_detect_crop_success(self):
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stderr='some lines\n[cropdetect @ 0x55] crop=1280:720:0:30\nmore lines'
            )
            result = self.probe.detect_crop('test.mp4')
            self.assertEqual(result, {'w': 1280, 'h': 720, 'x': 0, 'y': 30})

    def test_detect_crop_no_ffmpeg(self):
        self.mgr.ffmpeg_path = None
        result = self.probe.detect_crop('test.mp4')
        self.assertIsNone(result)

    def test_extract_thumbnail_success(self):
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = self.probe.extract_thumbnail('test.mp4', 'out.jpg')
            self.assertTrue(result)

    def test_extract_thumbnail_no_ffmpeg(self):
        self.mgr.ffmpeg_path = None
        result = self.probe.extract_thumbnail('test.mp4', 'out.jpg')
        self.assertFalse(result)

    def test_export_file_info_txt(self):
        mock_data = {
            'streams': [{'width': 1920, 'height': 1080, 'duration': '60.0',
                         'r_frame_rate': '30/1', 'codec_name': 'h264', 'bit_rate': '1000000'}],
            'format': {'duration': '60.0', 'size': '1000000', 'bit_rate': '1000000', 'format_name': 'mov,mp4,m4a'}
        }
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(mock_data))
            with patch('builtins.open', MagicMock()) as mock_open:
                mock_open.return_value.__enter__ = MagicMock(return_value=mock_open.return_value)
                mock_open.return_value.write = MagicMock()
                result = self.probe.export_file_info('test.mp4', 'out.txt', 'txt')
                self.assertTrue(result)

    def test_export_file_info_json(self):
        mock_data = {
            'streams': [],
            'format': {'duration': '60.0', 'size': '1000000', 'format_name': 'mp4'}
        }
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(mock_data))
            with patch('builtins.open', MagicMock()) as mock_open:
                mock_open.return_value.__enter__ = MagicMock(return_value=mock_open.return_value)
                mock_open.return_value.write = MagicMock()
                result = self.probe.export_file_info('test.mp4', 'out.json', 'json')
                self.assertTrue(result)

    def test_export_file_info_invalid(self):
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout='')
            result = self.probe.export_file_info('test.mp4', 'out.txt')
            self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()