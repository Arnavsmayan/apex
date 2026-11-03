import unittest

import race_data


class RaceDataTests(unittest.TestCase):
    def test_intervals_are_limited_to_requested_lap_window(self):
        result = race_data.get_interval_window("9558", "VER", 25, 26)
        self.assertEqual(result["lap_window"], [25, 26])
        self.assertGreater(result["count"], 0)
        self.assertLess(result["count"], race_data.get_data("9558", "intervals", "VER")["count"])
        self.assertIn("car ahead", result["note"])
        self.assertIn("error", race_data.get_interval_window("9558", "VER", 1, 20))

    def test_batch_returns_distinct_drivers_and_sources(self):
        result = race_data.get_evidence("9558", ["HAM", "VER"], ["pit", "stints", "weather"])
        self.assertEqual(result["evidence"]["pit"]["HAM"]["records"][0]["lap_number"], 27)
        self.assertEqual(result["evidence"]["pit"]["VER"]["records"][0]["lap_number"], 26)
        self.assertIn("weather?session_key=9558", result["evidence"]["weather"]["source"])

    def test_pace_uses_common_laps_and_excludes_pit_and_out_laps(self):
        result = race_data.compare_pace("9558", "HAM", "VER", 20, 32)
        self.assertEqual(result["paired_laps"], [20, 21, 22, 23, 24, 25, 29, 30, 31, 32])
        self.assertEqual(result["sample_size"], 10)
        self.assertEqual(result["median_paired_difference_seconds_a_minus_b"], -1.056)

    def test_empty_and_invalid_comparisons_report_errors(self):
        self.assertIn("error", race_data.compare_pace("9558", "HAM", "VER", 27, 28))
        self.assertIn("error", race_data.compare_pace("9999", "HAM", "VER", 1, 5))
        self.assertIn("error", race_data.compare_pace("9558", "HAM", "VER", 5, 1))

    def test_weather_summary_preserves_rainfall_transitions(self):
        import json
        raw = json.loads((race_data.DATA / "9558_weather.json").read_text(encoding="utf-8-sig"))
        sampled = race_data.get_data("9558", "weather")
        dates = {row["date"] for row in sampled["records"]}
        transitions = {raw[i]["date"] for i in range(1, len(raw)) if raw[i].get("rainfall") != raw[i-1].get("rainfall")}
        self.assertTrue(transitions <= dates)
        self.assertLess(sampled["count"], sampled["original_count"])
        self.assertIn("Sampled", sampled["note"])

    def test_new_sources_exist_for_each_race(self):
        for key in race_data.RACES:
            for kind in ("position", "intervals", "weather"):
                with self.subTest(race=key, kind=kind):
                    self.assertGreater(race_data.get_data(key, kind)["count"], 0)


if __name__ == "__main__":
    unittest.main()
