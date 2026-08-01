import unittest
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

from core.ffmpeg import FFmpegManager, clear_gpu_cache


class TestFFmpegManager(unittest.TestCase):

    def setUp(self):
        clear_gpu_cache()
        self.mgr = FFmpegManager()

    def test_init_not_frozen(self):
        mgr = FFmpegManager()
        self.assertFalse(mgr.ffmpeg_path)
        self.assertFalse(mgr.ffprobe_path)
        self.assertIsNone(mgr.gpu_type)
        self.assertIsNone(mgr.hwaccel)

    @patch('subprocess.run')
    @patch('pathlib.Path.exists', return_value=True)
    def test_find_ffmpeg_success(self, mock_exists, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='ffmpeg version 7.0')
        mgr = FFmpegManager()
        mgr.base_dir = Path("/fake")
        result = mgr.find_ffmpeg()
        self.assertIsNotNone(result)

    @patch('subprocess.run')
    @patch('pathlib.Path.exists', return_value=False)
    def test_find_ffmpeg_not_found_locally(self, mock_exists, mock_run):
        mock_run.side_effect = subprocess.SubprocessError()
        mgr = FFmpegManager()
        mgr.base_dir = Path("/fake")
        result = mgr.find_ffmpeg()
        self.assertIsNone(result)

    @patch('subprocess.run')
    def test_detect_gpu_nvidia(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='encoders\nh264_nvenc\nh264_amf\n')
        mgr = FFmpegManager()
        mgr.ffmpeg_path = '/fake/ffmpeg'
        gpu_type, hwaccel = mgr.detect_gpu()
        self.assertEqual(gpu_type, 'nvidia')
        self.assertEqual(hwaccel, 'cuda')

    @patch('subprocess.run')
    def test_detect_gpu_amd(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='encoders\nh264_amf\n')
        mgr = FFmpegManager()
        mgr.ffmpeg_path = '/fake/ffmpeg'
        gpu_type, hwaccel = mgr.detect_gpu()
        self.assertEqual(gpu_type, 'amd')
        self.assertEqual(hwaccel, 'd3d11va')

    @patch('subprocess.run')
    def test_detect_gpu_intel(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='encoders\nh264_qsv\n')
        mgr = FFmpegManager()
        mgr.ffmpeg_path = '/fake/ffmpeg'
        gpu_type, hwaccel = mgr.detect_gpu()
        self.assertEqual(gpu_type, 'intel')
        self.assertEqual(hwaccel, 'qsv')

    @patch('subprocess.run')
    def test_detect_gpu_none(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='encoders\n')
        mgr = FFmpegManager()
        mgr.ffmpeg_path = '/fake/ffmpeg'
        gpu_type, hwaccel = mgr.detect_gpu()
        self.assertIsNone(gpu_type)
        self.assertIsNone(hwaccel)

    @patch('subprocess.run')
    def test_detect_gpu_encoder_unusable_falls_back_to_cpu(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout='encoders\nh264_nvenc\n')
        mgr = FFmpegManager()
        mgr.ffmpeg_path = '/fake/ffmpeg'
        gpu_type, hwaccel = mgr.detect_gpu()
        self.assertIsNone(gpu_type)
        self.assertIsNone(hwaccel)

    @patch('subprocess.run')
    def test_verify_gpu_encoder_uses_min_128_frame(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='')
        mgr = FFmpegManager()
        mgr.ffmpeg_path = '/fake/ffmpeg'
        self.assertTrue(mgr._verify_gpu_encoder('h264_nvenc'))
        calls = [c.args[0] for c in mock_run.call_args_list]
        self.assertTrue(any('color=size=256x256:rate=1:duration=1' in cmd for cmd in calls),
                        "NVENC 要求最小帧 128x128，实测帧不得低于此值")

    @patch('subprocess.run')
    def test_verify_gpu_encoder_logs_stderr_on_failure(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stdout='',
            stderr='InitializeEncoder failed: invalid param (8)'
        )
        mgr = FFmpegManager()
        mgr.ffmpeg_path = '/fake/ffmpeg'
        with self.assertLogs('MediaConverter', level='DEBUG'):
            self.assertFalse(mgr._verify_gpu_encoder('h264_nvenc'))

    @patch('subprocess.run')
    def test_detect_gpu_no_ffmpeg(self, mock_run):
        mgr = FFmpegManager()
        gpu_type, hwaccel = mgr.detect_gpu()
        self.assertIsNone(gpu_type)
        self.assertIsNone(hwaccel)

    def test_gpu_name_property(self):
        mgr = FFmpegManager()
        self.assertEqual(mgr.gpu_name, '')
        mgr.gpu_type = 'nvidia'
        self.assertEqual(mgr.gpu_name, 'NVIDIA (NVENC)')
        mgr.gpu_type = 'amd'
        self.assertEqual(mgr.gpu_name, 'AMD (AMF)')
        mgr.gpu_type = 'intel'
        self.assertEqual(mgr.gpu_name, 'Intel (QSV)')

    @patch('subprocess.run')
    def test_get_version(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout='ffmpeg version 7.0.1-full_build-2024'
        )
        mgr = FFmpegManager()
        mgr.ffmpeg_path = '/fake/ffmpeg'
        ver = mgr.get_version()
        self.assertEqual(ver, '7.0.1-full_build-2024')

    @patch('subprocess.run')
    def test_get_version_no_stdout(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='')
        mgr = FFmpegManager()
        mgr.ffmpeg_path = '/fake/ffmpeg'
        ver = mgr.get_version()
        self.assertEqual(ver, 'unknown')


    @patch('subprocess.run')
    @patch('pathlib.Path.exists', return_value=True)
    @patch.dict('os.environ', {'FFMPEG_PATH': '/custom/ffmpeg'})
    def test_find_ffmpeg_env_var(self, mock_exists, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='ffmpeg version 7.0')
        mgr = FFmpegManager()
        mgr.base_dir = Path("/fake")
        result = mgr.find_ffmpeg()
        self.assertIn('custom', result)


if __name__ == '__main__':
    unittest.main()
