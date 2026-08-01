import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt6.QtWidgets import QApplication

from gui.widgets.param_panel import ParamPanel


class TestParamPanel(unittest.TestCase):
    """apply_options 冒烟测试：历史记录回放必须能无异常恢复全部参数。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _panel(self, media_type: str) -> ParamPanel:
        panel = ParamPanel()
        panel.set_media_type(media_type)
        return panel

    def test_apply_options_video_full(self):
        panel = self._panel('video')
        opts = {
            'width': 1920, 'height': 1080, 'fps': 30, 'quality': 23,
            'bitrate': '5000k', 'codec': 'libx264', 'preset': 'medium',
            'crop_w': 100, 'crop_h': 80, 'crop_x': 10, 'crop_y': 20,
            'start_time': '00:01:00', 'trim_duration': '00:00:30',
        }
        panel.apply_options(opts)
        self.assertEqual(panel.input_resolution.text(), '1920x1080')
        self.assertEqual(panel.input_fps.text(), '30')
        self.assertEqual(panel.spin_quality.value(), 23)
        self.assertEqual(panel.input_bitrate.text(), '5000k')
        self.assertTrue(panel._preset_btns['medium'].isChecked())
        self.assertEqual(panel.spin_crop_w.value(), 100)
        self.assertEqual(panel.spin_crop_h.value(), 80)
        self.assertEqual(panel.spin_crop_x.value(), 10)
        self.assertEqual(panel.spin_crop_y.value(), 20)
        self.assertEqual(panel.input_start.text(), '00:01:00')
        self.assertEqual(panel.input_duration.text(), '00:00:30')

    def test_apply_options_video_partial(self):
        panel = self._panel('video')
        panel.apply_options({'fps': 29.97, 'preset': 'faster'})
        self.assertEqual(panel.input_fps.text(), '29.97')
        self.assertTrue(panel._preset_btns['faster'].isChecked())
        self.assertFalse(panel._preset_btns['medium'].isChecked())

    def test_apply_options_image(self):
        panel = self._panel('image')
        panel.apply_options({'quality': 85, 'width': 800, 'height': 600})
        self.assertEqual(panel.spin_img_quality.value(), 85)
        self.assertEqual(panel.spin_img_width.value(), 800)
        self.assertEqual(panel.spin_img_height.value(), 600)

    def test_apply_options_audio(self):
        panel = self._panel('audio')
        panel.apply_options({'audio_codec': 'aac', 'audio_bitrate': '192k'})
        idx = panel.combo_audio_only_codec.findData('aac')
        self.assertGreaterEqual(idx, 0)
        self.assertEqual(panel.combo_audio_only_codec.currentIndex(), idx)
        idx2 = panel.combo_audio_only_bitrate.findText('192k')
        self.assertGreaterEqual(idx2, 0)
        self.assertEqual(panel.combo_audio_only_bitrate.currentIndex(), idx2)

    def test_apply_options_audio_legacy_codec_key(self):
        """旧历史记录把音频编码器存进 codec 字段，回放需兼容。"""
        panel = self._panel('audio')
        panel.apply_options({'codec': 'flac', 'audio_bitrate': '128k'})
        idx = panel.combo_audio_only_codec.findData('flac')
        self.assertGreaterEqual(idx, 0)
        self.assertEqual(panel.combo_audio_only_codec.currentIndex(), idx)
        idx2 = panel.combo_audio_only_bitrate.findText('128k')
        self.assertGreaterEqual(idx2, 0)
        self.assertEqual(panel.combo_audio_only_bitrate.currentIndex(), idx2)

    def test_apply_options_video_trim_checks_checkbox(self):
        """回放裁剪参数时必须勾选裁剪开关，否则输入框禁用、重新转换时参数丢失。"""
        panel = self._panel('video')
        panel.apply_options({'start_time': '00:01:00', 'trim_duration': '00:00:30'})
        self.assertTrue(panel.check_trim.isChecked())
        self.assertTrue(panel.input_start.isEnabled())
        self.assertTrue(panel.input_duration.isEnabled())

    def test_apply_options_video_stream_copy_remove_audio(self):
        panel = self._panel('video')
        panel.apply_options({'stream_copy': True, 'remove_audio': True})
        self.assertTrue(panel.check_stream_copy.isChecked())
        self.assertTrue(panel.check_remove_audio.isChecked())

    def test_apply_options_video_rotate_flip_replace_audio(self):
        panel = self._panel('video')
        panel.apply_options({'rotate': 270, 'flip_h': True, 'flip_v': True})
        self.assertTrue(panel.btn_rot270.isChecked())
        self.assertFalse(panel.btn_rot90.isChecked())
        self.assertTrue(panel.btn_flip_h.isChecked())
        self.assertTrue(panel.btn_flip_v.isChecked())

    def test_get_options_audio_uses_audio_codec_field(self):
        """音频页 get_options 必须写入 audio_codec 而非 codec（回归：编码器被忽略）。"""
        panel = self._panel('audio')
        panel.combo_audio_only_codec.setCurrentIndex(
            panel.combo_audio_only_codec.findData('flac'))
        panel.combo_audio_only_bitrate.setCurrentText('256k')
        opts = panel.get_options()
        self.assertEqual(opts.audio_codec, 'flac')
        self.assertIsNone(opts.codec)
        self.assertEqual(opts.audio_bitrate, '256k')

    def test_apply_options_empty(self):
        panel = self._panel('video')
        panel.apply_options({})
        self.assertEqual(panel.input_resolution.text(), '')


if __name__ == '__main__':
    unittest.main()
