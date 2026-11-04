import unittest
from unittest.mock import patch
import historical_data
import openf1_live
import race_data

class OnDemandRaceTests(unittest.TestCase):
    def tearDown(self):
        openf1_live._sessions.pop('9693', None)

    def test_discovers_and_fetches_race_outside_bundled_set(self):
        def fake_get(endpoint, **params):
            records = {
                'sessions': [{'session_key': 9693, 'meeting_key': 1254, 'date_end': '2025-03-16T06:00:00+00:00', 'location': 'Melbourne', 'country_name': 'Australia'}],
                'meetings': [{'meeting_key': 1254, 'meeting_name': 'Australian Grand Prix'}],
                'drivers': [{'driver_number': 4, 'name_acronym': 'NOR', 'full_name': 'Lando Norris'}],
                'pit': [{'driver_number': 4, 'lap_number': 34}],
                'session_result': [{'driver_number': 4, 'position': 1}],
            }
            return records[endpoint], 'https://api.openf1.org/v1/' + endpoint
        with patch.object(openf1_live, '_get', side_effect=fake_get):
            found = historical_data.find_races(2025, 'Australia')
            self.assertEqual(found['races'][0]['session_key'], '9693')
            self.assertTrue(found['races'][0]['openf1_available'])
            pits = race_data.get_data('9693', 'pit', 'NOR')
            self.assertEqual(pits['records'][0]['lap_number'], 34)
            result = race_data.get_evidence('9693', ['NOR'], ['results'])
            self.assertEqual(result['evidence']['results']['records'][0]['position'], 1)

    def test_api_failure_returns_bundled_fallback(self):
        with patch.object(openf1_live, 'find_races', side_effect=OSError('offline')):
            found = historical_data.find_races(2024, 'British')
            self.assertEqual(found['races'][0]['session_key'], '9558')
            self.assertIn('offline', found['lookup_warning'])

if __name__ == '__main__': unittest.main()
