import unittest
import historical_data as data

class SeasonStrategyTests(unittest.TestCase):
    def test_season_overview_covers_driver_and_marks_filtering(self):
        result = data.season_strategy(2024, 'Verstappen')
        self.assertEqual(result['driver_code'], 'VER')
        self.assertEqual(result['race_count'], 24)
        self.assertEqual(result['races_with_retained_laps'], 24)
        self.assertEqual(result['races'][0]['race'], 'Bahrain Grand Prix')
        self.assertTrue(result['races'][0]['observed_tyres'])
        self.assertIn('not full stint boundaries', result['note'])
        self.assertIn('do not infer an exact stop count', result['note'])

    def test_unknown_season_and_driver(self):
        self.assertIn('error', data.season_strategy(2025, 'VER'))
        self.assertIn('error', data.season_strategy(2024, 'nobody'))

if __name__ == '__main__': unittest.main()
