"""Read the bundled OpenF1 race snapshots."""
import json
import openf1_live
import statistics
from datetime import datetime, timedelta
from pathlib import Path

DATA = Path(__file__).parent / "data" / "openf1"
RACES = {"9558": "2024 British Grand Prix, Silverstone", "9590": "2024 Italian Grand Prix, Monza", "9636": "2024 Sao Paulo Grand Prix, Interlagos"}
KINDS = {"sessions", "drivers", "laps", "pit", "stints", "race_control", "position", "intervals", "weather"}
ROUNDS = {"9558": "12", "9590": "16", "9636": "21"}


def get_evidence(session_key: str, drivers: list[str], kinds: list[str]) -> dict:
    """Gather requested race evidence in one call while keeping each source identifiable."""
    if not drivers or len(drivers) > 3:
        return {"error": "Provide one to three drivers."}
    allowed = {"pit", "stints", "laps", "position", "weather", "race_control", "results"}
    if not kinds or len(kinds) > 7 or any(kind not in allowed for kind in kinds):
        return {"error": "Choose from pit, stints, laps, position, weather, race_control, results."}
    evidence = {}
    def safe_get(kind, driver=""):
        try:
            return get_data(session_key, kind, driver)
        except (OSError, ValueError) as exc:
            return {"error": f"{kind} data unavailable: {exc}"}
    for kind in dict.fromkeys(kinds):
        if kind in {"weather", "race_control", "results"}:
            result = safe_get(kind)
            if kind == "results" and result.get("records") and "Results" in result["records"][0]:
                race = result["records"][0]
                fields = ("position", "grid", "status", "points", "Driver", "Time")
                result["records"] = [{key: row.get(key) for key in fields if row.get(key) is not None}
                                     for row in race.get("Results", [])]
                result["note"] = "Selected result fields for all drivers; consult the source for the full classification."
            evidence[kind] = result
            continue
        evidence[kind] = {}
        for driver in dict.fromkeys(drivers):
            result = safe_get(kind, driver)
            if kind == "laps" and "records" in result:
                fields = ("driver_number", "lap_number", "date_start", "lap_duration", "is_pit_out_lap")
                result["records"] = [{key: row.get(key) for key in fields} for row in result["records"]]
            evidence[kind][driver] = result
    return {"race": RACES.get(str(session_key)) or openf1_live._sessions.get(str(session_key), {}).get("race"), "evidence": evidence}


def get_data(session_key: str, kind: str, driver: str = "") -> dict:
    key = str(session_key)
    if key not in RACES and openf1_live.has_session(key):
        return openf1_live.get_data(key, kind, driver)
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
    total = len(rows)
    note = ""
    if kind == "position":
        # Preserve every position change per driver, rather than repeated identical readings.
        previous = {}
        changes = []
        for row in rows:
            number = row.get("driver_number")
            if number not in previous or previous[number] != row.get("position"):
                changes.append(row)
                previous[number] = row.get("position")
        rows = changes
        note = "Only the first position reading and subsequent position changes for each driver are shown. Timestamps reflect observations, not the exact instant of an overtake."
    elif kind == "weather" and rows:
        # Keep rainfall transitions and periodic points; do not suggest it is the full record.
        selected = []
        last_time = None
        previous_rain = object()
        for row in rows:
            current = datetime.fromisoformat(row["date"])
            rain = row.get("rainfall")
            if last_time is None or (current - last_time).total_seconds() >= 300 or rain != previous_rain:
                selected.append(row)
                last_time = current
            previous_rain = rain
        if selected[-1] != rows[-1]:
            selected.append(rows[-1])
        rows = selected
        note = "Sampled approximately every five minutes plus each observed rainfall change and final reading; other readings omitted. Rainfall is an observation at the sensor, not a complete track condition."
    if kind == "race_control":
        fields = ("date", "driver_number", "lap_number", "category", "flag", "scope", "sector", "message")
        rows = [{k: row[k] for k in fields if row.get(k) is not None} for row in rows]
    if kind == "weather":
        fields = ("date", "air_temperature", "track_temperature", "rainfall", "humidity", "wind_speed")
        rows = [{k: row[k] for k in fields if row.get(k) is not None} for row in rows]
    result = {"race": RACES[key], "source": f"https://api.openf1.org/v1/{kind}?session_key={key}", "driver_filter": filtered, "count": len(rows), "records": rows}
    if note:
        result.update({"original_count": total, "note": note})
    return result


def get_interval_window(session_key: str, driver: str, start_lap: int, end_lap: int) -> dict:
    """Return interval records within a short window, using this driver's lap timestamps."""
    if start_lap < 1 or end_lap < start_lap or end_lap - start_lap > 7:
        return {"error": "For intervals, specify a window of one to eight laps."}
    laps = get_data(session_key, "laps", driver)
    intervals = get_data(session_key, "intervals", driver)
    if "error" in laps or "error" in intervals:
        return {"error": "Race or driver not found."}
    by_lap = {r.get("lap_number"): r for r in laps["records"]}
    first, last = by_lap.get(start_lap), by_lap.get(end_lap)
    if not first or not last or not first.get("date_start") or not last.get("date_start"):
        return {"error": "Lap timestamps are unavailable for the requested window."}
    start = datetime.fromisoformat(first["date_start"])
    next_lap = by_lap.get(end_lap + 1, {})
    if next_lap.get("date_start"):
        end = datetime.fromisoformat(next_lap["date_start"])
    elif isinstance(last.get("lap_duration"), (int, float)):
        end = datetime.fromisoformat(last["date_start"]) + timedelta(seconds=last["lap_duration"])
    else:
        return {"error": "The end time is unavailable for the requested window."}
    records = [r for r in intervals["records"] if start <= datetime.fromisoformat(r["date"]) < end]
    return {**intervals, "lap_window": [start_lap, end_lap], "time_window_utc": [start.isoformat(), end.isoformat()],
            "count": len(records), "records": records,
            "note": "Intervals are to the car ahead, not necessarily the other named driver; timestamps use this driver's lap boundaries."}


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
    return {"race": RACES.get(str(session_key)) or openf1_live._sessions.get(str(session_key), {}).get("race"), "drivers": [driver_a, driver_b], "lap_range": [start_lap, end_lap],
            "paired_laps": common, "sample_size": len(common),
            "median_paired_difference_seconds_a_minus_b": round(statistics.median(differences), 3),
            "method": "Median of per-lap differences, not a difference between driver medians. Same numbered laps; pit and following out laps excluded for both drivers. Negative difference means driver A was faster. The selected range may span multiple tire compounds. Safety cars, traffic, weather, fuel, and other effects are not automatically removed.",
            "sources": [f"https://api.openf1.org/v1/laps?session_key={session_key}", f"https://api.openf1.org/v1/pit?session_key={session_key}"]}
