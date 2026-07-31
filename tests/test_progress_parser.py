import unittest
from core.progress_parser import ProgressParser


class TestProgressParser(unittest.TestCase):

    def setUp(self):
        self.parser = ProgressParser()

    def test_parse_progress_no_match(self):
        result = self.parser.parse_progress('frame=100 fps=30 bitrate=1000k', 0.0)
        self.assertIsNone(result)

    def test_parse_progress_zero_duration(self):
        result = self.parser.parse_progress('time=00:00:30.000000', 0.0)
        self.assertIsNone(result)

    def test_parse_progress_50_percent(self):
        result = self.parser.parse_progress('time=00:00:30.000000', 60.0)
        self.assertEqual(result, 50)

    def test_parse_progress_exceeds_100(self):
        result = self.parser.parse_progress('time=00:10:00.000000', 10.0)
        self.assertEqual(result, 100)

    def test_parse_time_to_seconds_seconds_only(self):
        result = self.parser.parse_time_to_seconds('30.5')
        self.assertAlmostEqual(result, 30.5)

    def test_parse_time_to_seconds_mmss(self):
        result = self.parser.parse_time_to_seconds('1:30')
        self.assertEqual(result, 90)

    def test_parse_time_to_seconds_hhmmss(self):
        result = self.parser.parse_time_to_seconds('1:01:30')
        self.assertEqual(result, 3690)

    def test_parse_time_to_seconds_invalid(self):
        result = self.parser.parse_time_to_seconds('invalid')
        self.assertEqual(result, 0.0)

    def test_compute_eta_no_time(self):
        result = self.parser.compute_eta('frame=100 speed=2.0x', 60.0)
        self.assertIsNone(result)

    def test_compute_eta_no_speed(self):
        result = self.parser.compute_eta('time=00:00:30.000000', 60.0)
        self.assertIsNone(result)

    def test_compute_eta_zero_speed(self):
        result = self.parser.compute_eta('time=00:00:30.000000 speed=0.0x', 60.0)
        self.assertIsNone(result)

    def test_compute_eta_half_speed(self):
        result = self.parser.compute_eta('time=00:00:30.000000 speed=0.5x', 60.0)
        self.assertEqual(result, 'ETA 1:00')

    def test_compute_eta_double_speed(self):
        result = self.parser.compute_eta('time=00:00:30.000000 speed=2.0x', 60.0)
        self.assertEqual(result, 'ETA 0:15')


if __name__ == '__main__':
    unittest.main()