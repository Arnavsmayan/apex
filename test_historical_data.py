import unittest
import historical_data as h

class HistoricalTests(unittest.TestCase):
    def test_catalog_and_specific_race(self):
        self.assertEqual(len(h.catalog()), 147)
        race = h.find_races(2021, 'Abu Dhabi')['races'][0]
        self.assertEqual(race['session_key'], '2021_22')
        self.assertFalse(race['official_context'])
        self.assertEqual(h.find_races(2017, '')['count'], 0)

    def test_paired_lap_calculation_and_limitations(self):
        result = h.pace('2021_22', 'HAM', 'VER', 20, 30)
        self.assertEqual(result['sample_size'], 9)
        self.assertEqual(result['median_paired_difference_seconds_a_minus_b'], -0.2)
        self.assertIn('107%', result['limitation'])
        self.assertIn('error', h.pace('2021_22', 'HAM', 'BAD', 20, 30))

    def test_local_results_and_context(self):
        result = h.results('2021_22')
        self.assertEqual(result['records'][0]['Driver']['driverId'], 'max_verstappen')
        self.assertIn('Bundled', result['note'])
        self.assertEqual(len(h.official_context('9558')['documents']), 3)
        self.assertEqual(h.official_context('2021_22')['documents'], [])
        self.assertIn('No curated official account', h.official_context('2021_22')['note'])

if __name__ == '__main__': unittest.main()
