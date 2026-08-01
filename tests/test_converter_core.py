import unittest
import subprocess
import sys
from pathlib import Path
from queue import Empty
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
        self.assertNotIn('yuvj420p', result)

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


class TestMediaConverterRunFfmpeg(unittest.TestCase):

    def setUp(self):
        self.conv = MediaConverter()
        self.conv._ffmpeg_mgr.ffmpeg_path = '/fake/ffmpeg'
        self.conv._ffmpeg_mgr.ffprobe_path = '/fake/ffprobe'

    @patch('subprocess.Popen')
    @patch('os.path.getsize', return_value=1024)
    @patch('core.converter.MediaConverter.get_duration', return_value=60.0)
    def test_run_ffmpeg_success(self, mock_dur, mock_size, mock_popen):
        mock_proc = MagicMock()
        mock_proc.stdout = iter(['frame=100 time=00:00:30.00 speed=2.0x\n'])
        mock_proc.wait.return_value = None
        mock_proc.returncode = 0
        mock_proc.poll.return_value = 0
        mock_popen.return_value = mock_proc
        self.conv.history = MagicMock()

        cmd = ['/fake/ffmpeg', '-y', '-i', 'in.mp4', 'out.mp4']
        result = self.conv._run_ffmpeg(cmd, 'in.mp4', 'out.mp4', '.mp4', ConvertOptions())
        self.assertTrue(result)
        self.conv.history.add_record.assert_called_once()

    @patch('subprocess.Popen')
    @patch('core.converter.MediaConverter.get_duration', return_value=0.0)
    def test_run_ffmpeg_failure(self, mock_dur, mock_popen):
        mock_proc = MagicMock()
        mock_proc.stdout = iter([])
        mock_proc.wait.return_value = None
        mock_proc.returncode = 1
        mock_proc.poll.return_value = 1
        mock_popen.return_value = mock_proc

        cmd = ['/fake/ffmpeg', '-y', '-i', 'in.mp4', 'out.mp4']
        result = self.conv._run_ffmpeg(cmd, 'in.mp4', 'out.mp4', '.mp4', ConvertOptions())
        self.assertFalse(result)

    @patch('subprocess.Popen', side_effect=OSError("file not found"))
    def test_run_ffmpeg_exception(self, mock_popen):
        cmd = ['/fake/ffmpeg', '-y', '-i', 'in.mp4', 'out.mp4']
        result = self.conv._run_ffmpeg(cmd, 'in.mp4', 'out.mp4', '.mp4', ConvertOptions())
        self.assertFalse(result)

    @patch('subprocess.Popen')
    @patch('core.converter.MediaConverter.get_duration', return_value=60.0)
    def test_run_ffmpeg_eta_emitted(self, mock_dur, mock_popen):
        mock_proc = MagicMock()
        mock_proc.stdout = iter(['frame=100 time=00:00:30.00 speed=2.0x\n'])
        mock_proc.wait.return_value = None
        mock_proc.returncode = 0
        mock_proc.poll.return_value = 0
        mock_popen.return_value = mock_proc

        eta_signals = []
        self.conv.set_callbacks(on_eta=lambda eta: eta_signals.append(eta))
        cmd = ['/fake/ffmpeg', '-y', '-i', 'in.mp4', 'out.mp4']
        self.conv._run_ffmpeg(cmd, 'in.mp4', 'out.mp4', '.mp4', ConvertOptions())
        self.assertTrue(any('ETA' in e for e in eta_signals))

    @patch('subprocess.Popen')
    @patch('core.converter.MediaConverter.get_duration', return_value=60.0)
    def test_run_ffmpeg_process_cleaned_up(self, mock_dur, mock_popen):
        mock_proc = MagicMock()
        mock_proc.stdout = iter([])
        mock_proc.wait.return_value = None
        mock_proc.returncode = 0
        mock_proc.poll.return_value = 0
        mock_popen.return_value = mock_proc

        cmd = ['/fake/ffmpeg', '-y', '-i', 'in.mp4', 'out.mp4']
        self.conv._run_ffmpeg(cmd, 'in.mp4', 'out.mp4', '.mp4', ConvertOptions())
        self.assertEqual(len(self.conv._active_processes), 0)

    @patch('subprocess.Popen')
    @patch('core.converter.MediaConverter.get_duration', return_value=60.0)
    @patch('queue.Queue.get', side_effect=Empty())
    def test_run_ffmpeg_timeout_kills_hung_process(self, mock_qget, mock_dur, mock_popen):
        """ffmpeg 挂起且输出管道不关闭时，超时也必须触发（读循环不能无限阻塞）。

        模拟方式：Queue.get 永远抛 Empty（等价于管道永远不出行、进程不退出），
        stdout 用空迭代器让读取线程立即结束，避免测试自身死循环或悬挂线程。
        """
        mock_proc = MagicMock()
        mock_proc.stdout = iter([])
        mock_proc.poll.return_value = None     # 进程仍在运行
        mock_proc.wait.return_value = None
        mock_proc.returncode = 1
        mock_popen.return_value = mock_proc

        mono_vals = iter([100.0, 100.0, 100.0, 2000.0])
        with patch('core.converter.time.monotonic', side_effect=lambda: next(mono_vals)):
            cmd = ['/fake/ffmpeg', '-y', '-i', 'in.mp4', 'out.mp4']
            result = self.conv._run_ffmpeg(cmd, 'in.mp4', 'out.mp4', '.mp4', ConvertOptions())
        self.assertFalse(result)
        mock_proc.kill.assert_called_once()

    @patch('subprocess.Popen')
    @patch('core.converter.MediaConverter.get_duration', return_value=0.0)
    def test_run_ffmpeg_cancel_before_popen(self, mock_dur, mock_popen):
        self.conv.cleanup()
        cmd = ['/fake/ffmpeg', '-y', '-i', 'in.mp4', 'out.mp4']
        result = self.conv._run_ffmpeg(cmd, 'in.mp4', 'out.mp4', '.mp4', ConvertOptions())
        self.assertFalse(result)
        self.assertFalse(self.conv._active_processes)

    @patch('subprocess.Popen')
    @patch('os.path.exists', return_value=True)
    def test_convert_rejected_after_cancel_without_reset(self, mock_exists, mock_popen):
        self.conv.cleanup()
        result = self.conv.convert('in.mp4', 'out.mp4', ConvertOptions())
        self.assertFalse(result)
        self.assertFalse(self.conv._active_processes)

    def test_convert_allowed_after_reset_cancellation(self):
        self.conv.cleanup()
        self.conv.reset_cancellation()
        self.assertFalse(self.conv._cancel_event.is_set())

    def test_reset_callbacks_restores_defaults(self):
        calls = []
        self.conv.set_callbacks(on_log=lambda lvl, msg: calls.append(msg))
        self.conv._on_log('info', 'hi')
        self.assertEqual(calls, ['hi'])
        self.conv.reset_callbacks()
        calls.clear()
        self.conv._on_log('info', 'bye')
        self.assertEqual(calls, [])


class TestMediaConverterCleanup(unittest.TestCase):

    def setUp(self):
        self.conv = MediaConverter()

    def test_cleanup_terminates_running_process(self):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        self.conv._active_processes.add(mock_proc)
        self.conv.cleanup()
        mock_proc.terminate.assert_called_once()

    def test_cleanup_clears_process_set(self):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        self.conv._active_processes.add(mock_proc)
        self.conv.cleanup()
        self.assertEqual(len(self.conv._active_processes), 0)

    def test_cleanup_handles_wait_timeout(self):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.wait.side_effect = subprocess.TimeoutExpired(cmd='', timeout=3)
        self.conv._active_processes.add(mock_proc)
        self.conv.cleanup()
        mock_proc.kill.assert_called_once()


class TestMediaConverterDetectCrop(unittest.TestCase):

    def setUp(self):
        self.conv = MediaConverter()
        self.conv._ffmpeg_mgr.ffmpeg_path = '/fake/ffmpeg'

    def test_detect_crop_no_ffmpeg(self):
        self.conv._ffmpeg_mgr.ffmpeg_path = None
        result = self.conv.detect_crop('input.mp4')
        self.assertIsNone(result)

    @patch('subprocess.run')
    def test_detect_crop_success(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stderr='some lines\n[cropdetect @ 0x55] crop=1280:720:0:30\nmore lines'
        )
        result = self.conv.detect_crop('input.mp4')
        self.assertEqual(result, {'w': 1280, 'h': 720, 'x': 0, 'y': 30})

    @patch('subprocess.run', side_effect=OSError("fail"))
    def test_detect_crop_exception(self, mock_run):
        result = self.conv.detect_crop('input.mp4')
        self.assertIsNone(result)


class TestMediaConverterExtractThumbnail(unittest.TestCase):

    def setUp(self):
        self.conv = MediaConverter()
        self.conv._ffmpeg_mgr.ffmpeg_path = '/fake/ffmpeg'

    def test_thumbnail_no_ffmpeg(self):
        self.conv._ffmpeg_mgr.ffmpeg_path = None
        result = self.conv.extract_thumbnail('in.mp4', 'out.jpg')
        self.assertFalse(result)

    @patch('subprocess.run')
    def test_thumbnail_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        result = self.conv.extract_thumbnail('in.mp4', 'out.jpg', time_sec=5.0)
        self.assertTrue(result)
        cmd = mock_run.call_args[0][0]
        self.assertIn('-ss', cmd)
        self.assertIn('5.0', cmd)

    @patch('subprocess.run')
    def test_thumbnail_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        result = self.conv.extract_thumbnail('in.mp4', 'out.jpg')
        self.assertFalse(result)


class TestMediaConverterConcatVideos(unittest.TestCase):

    def setUp(self):
        self.conv = MediaConverter()
        self.conv._ffmpeg_mgr.ffmpeg_path = '/fake/ffmpeg'
        self.conv._ffmpeg_mgr.ffprobe_path = '/fake/ffprobe'

    def test_concat_too_few_files(self):
        result = self.conv.concat_videos(['single.mp4'], 'out.mp4')
        self.assertFalse(result)

    @patch('core.converter.MediaConverter._run_ffmpeg', return_value=True)
    @patch('core.converter.MediaConverter.get_file_summary')
    def test_concat_success(self, mock_summary, mock_run):
        mock_summary.return_value = {'duration': 10.0, 'valid': True}
        result = self.conv.concat_videos(['a.mp4', 'b.mp4'], 'out.mp4')
        self.assertTrue(result)
        mock_run.assert_called_once()

    @patch('core.converter.MediaConverter._run_ffmpeg', return_value=True)
    @patch('core.converter.MediaConverter.get_file_summary')
    def test_concat_computes_total_duration(self, mock_summary, mock_run):
        mock_summary.return_value = {'duration': 15.5, 'valid': True}
        self.conv.concat_videos(['a.mp4', 'b.mp4'], 'out.mp4')
        call_args = mock_run.call_args
        opts = call_args[0][4]
        self.assertEqual(opts.trim_duration, '31.0')


class TestMediaConverterConvertErrorPaths(unittest.TestCase):

    def setUp(self):
        self.conv = MediaConverter()
        self.conv._ffmpeg_mgr.ffmpeg_path = '/fake/ffmpeg'
        self.conv._ffmpeg_mgr.ffprobe_path = '/fake/ffprobe'

    def test_convert_no_ffmpeg(self):
        conv = MediaConverter()
        result = conv.convert('in.mp4', 'out.mp4', ConvertOptions())
        self.assertFalse(result)

    @patch('os.path.exists', return_value=True)
    def test_convert_invalid_output_dir(self, mock_exists):
        opts = ConvertOptions(output_dir='..\\..\\Windows')
        result = self.conv.convert('in.mp4', 'out.mp4', opts)
        self.assertFalse(result)

    @patch('core.converter.MediaConverter._run_ffmpeg', return_value=True)
    @patch('os.path.exists', return_value=True)
    def test_convert_stream_copy(self, mock_exists, mock_run):
        opts = ConvertOptions(stream_copy=True)
        result = self.conv.convert('in.mp4', 'out.mp4', opts)
        self.assertTrue(result)
        cmd = mock_run.call_args[0][0]
        self.assertIn('-c:v', cmd)
        self.assertIn('copy', cmd)


class TestBuildCommand(unittest.TestCase):

    def setUp(self):
        self.conv = MediaConverter()
        self.conv._ffmpeg_mgr.ffmpeg_path = '/fake/ffmpeg'
        self.conv._ffmpeg_mgr.ffprobe_path = '/fake/ffprobe'

    @patch('os.path.exists', return_value=True)
    def test_build_command_success(self, mock_exists):
        opts = ConvertOptions(quality=23)
        cmd = self.conv.build_command('in.mp4', 'out.mp4', opts)
        self.assertIsNotNone(cmd)
        self.assertIn('out.mp4', cmd)

    def test_build_command_no_ffmpeg(self):
        conv = MediaConverter()
        cmd = conv.build_command('in.mp4', 'out.mp4', ConvertOptions())
        self.assertIsNone(cmd)

    def test_build_command_input_missing(self):
        cmd = self.conv.build_command('/nonexistent.mp4', 'out.mp4', ConvertOptions())
        self.assertIsNone(cmd)

    @patch('os.path.exists', return_value=True)
    def test_build_command_invalid_output_dir(self, mock_exists):
        opts = ConvertOptions(output_dir='..\\..\\Windows')
        cmd = self.conv.build_command('in.mp4', 'out.mp4', opts)
        self.assertIsNone(cmd)


if __name__ == '__main__':
    unittest.main()
