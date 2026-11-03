import unittest

import race_data


class RaceDataTests(unittest.TestCase):
    def test_pace_uses_common_laps_and_excludes_pit_and_out_laps(self):
        result = race_data.compare_pace("9558", "HAM", "VER", 20, 32)
        self.assertEqual(result["paired_laps"], [20, 21, 22, 23, 24, 25, 29, 30, 31, 32])
        self.assertEqual(result["sample_size"], 10)
        self.assertEqual(result["median_paired_difference_seconds_a_minus_b"], -1.056)

    def test_empty_and_invalid_comparisons_report_errors(self):
        self.assertIn("error", race_data.compare_pace("9558", "HAM", "VER", 27, 28))
        self.assertIn("error", race_data.compare_pace("9999", "HAM", "VER", 1, 5))
        self.assertIn("error", race_data.compare_pace("9558", "HAM", "VER", 5, 1))

    def test_new_sources_exist_for_each_race(self):
        for key in race_data.RACES:
            for kind in ("position", "intervals", "weather"):
                with self.subTest(race=key, kind=kind):
                    self.assertGreater(race_data.get_data(key, kind)["count"], 0)


if __name__ == "__main__":
    unittest.main()
