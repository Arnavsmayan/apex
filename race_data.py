"""Read the bundled OpenF1 race snapshots."""
import json
import statistics
from pathlib import Path

DATA = Path(__file__).parent / "data" / "openf1"
RACES = {"9558": "2024 British Grand Prix, Silverstone", "9590": "2024 Italian Grand Prix, Monza", "9636": "2024 Sao Paulo Grand Prix, Interlagos"}
KINDS = {"sessions", "drivers", "laps", "pit", "stints", "race_control", "position", "intervals", "weather"}
ROUNDS = {"9558": "12", "9590": "16", "9636": "21"}


def get_data(session_key: str, kind: str, driver: str = "") -> dict:
    key = str(session_key)
    if key not in RACES or kind not in KINDS | {"results"}:
        return {"error": "Unknown race or data type", "available_races": RACES, "available_types": sorted(KINDS | {"results"})}
    if kind == "results":
        payload = json.loads((DATA.parent / "jolpica" / f"{key}_results.json").read_text(encoding="utf-8-sig"))
        races = payload.get("MRData", {}).get("RaceTable", {}).get("Races", [])
        return {"race": RACES[key], "source": f"https://api.jolpi.ca/ergast/f1/2024/{ROUNDS[key]}/results.json", "records": races, "note": "Results contain all drivers; driver filter is not applied."}
    rows = json.loads((DATA / f"{key}_{kind}.json").read_text(encoding="utf-8-sig"))
    if driver and kind in {"drivers", "laps", "pit", "stints", "position", "intervals"}:
        drivers = json.loads((DATA / f"{key}_drivers.json").read_text(encoding="utf-8-sig"))
        query = driver.strip().casefold()
        matches = [d for d in drivers if query in {str(d.get("name_acronym", "")).casefold(), str(d.get("driver_number", "")), str(d.get("full_name", "")).casefold()}]
        if not matches:
            matches = [d for d in drivers if query in str(d.get("full_name", "")).casefold()]
        if len(matches) != 1:
            return {"error": "Driver missing or ambiguous", "matches": matches}
        number = matches[0]["driver_number"]
        rows = [row for row in rows if row.get("driver_number") == number]
    filtered = driver if kind in {"drivers", "laps", "pit", "stints", "position", "intervals"} else None
    return {"race": RACES[key], "source": f"https://api.openf1.org/v1/{kind}?session_key={key}", "driver_filter": filtered, "count": len(rows), "records": rows}


def compare_pace(session_key: str, driver_a: str, driver_b: str, start_lap: int, end_lap: int) -> dict:
    """Compare paired laps, excluding pit laps and out laps, without inferring causation."""
    if start_lap < 1 or end_lap < start_lap or end_lap - start_lap > 80:
        return {"error": "Provide a valid lap range, at most 81 laps."}
    series = []
    for driver in (driver_a, driver_b):
        laps = get_data(session_key, "laps", driver)
        pits = get_data(session_key, "pit", driver)
        if "error" in laps or "error" in pits:
            return {"error": "Could not resolve driver or race", "details": [laps.get("error"), pits.get("error")]}
        pit_laps = {p["lap_number"] for p in pits["records"] if p.get("lap_number") is not None}
        valid = {row["lap_number"]: row["lap_duration"] for row in laps["records"]
                 if start_lap <= row.get("lap_number", 0) <= end_lap
                 and isinstance(row.get("lap_duration"), (int, float)) and row["lap_duration"] > 0
                 and row["lap_number"] not in pit_laps and row["lap_number"] - 1 not in pit_laps
                 and not row.get("is_pit_out_lap")}
        series.append(valid)
    common = sorted(series[0].keys() & series[1].keys())
    if not common:
        return {"error": "No comparable laps in this range after excluding pit and out laps."}
    differences = [series[0][lap] - series[1][lap] for lap in common]
    return {"race": RACES[str(session_key)], "drivers": [driver_a, driver_b], "lap_range": [start_lap, end_lap],
            "paired_laps": common, "sample_size": len(common),
            "median_paired_difference_seconds_a_minus_b": round(statistics.median(differences), 3),
            "method": "Median of per-lap differences, not a difference between driver medians. Same numbered laps; pit and following out laps excluded for both drivers. Negative difference means driver A was faster. The selected range may span multiple tire compounds. Safety cars, traffic, weather, fuel, and other effects are not automatically removed.",
            "sources": [f"https://api.openf1.org/v1/laps?session_key={session_key}", f"https://api.openf1.org/v1/pit?session_key={session_key}"]}
