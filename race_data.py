"""Read the bundled OpenF1 race snapshots."""
import json
from pathlib import Path

DATA = Path(__file__).parent / "data" / "openf1"
RACES = {"9558": "2024 British Grand Prix, Silverstone", "9590": "2024 Italian Grand Prix, Monza", "9636": "2024 Sao Paulo Grand Prix, Interlagos"}
KINDS = {"sessions", "drivers", "laps", "pit", "stints", "race_control"}
ROUNDS = {"9558": "12", "9590": "16", "9636": "21"}


def get_data(session_key: str, kind: str, driver: str = "") -> dict:
    key = str(session_key)
    if key not in RACES or kind not in KINDS | {"results"}:
        return {"error": "Unknown race or data type", "available_races": RACES, "available_types": sorted(KINDS)}
    if kind == "results":
        payload = json.loads((DATA.parent / "jolpica" / f"{key}_results.json").read_text(encoding="utf-8-sig"))
        races = payload.get("MRData", {}).get("RaceTable", {}).get("Races", [])
        return {"race": RACES[key], "source": f"https://api.jolpi.ca/ergast/f1/2024/{ROUNDS[key]}/results.json", "records": races}
    rows = json.loads((DATA / f"{key}_{kind}.json").read_text(encoding="utf-8-sig"))
    if driver and kind in {"drivers", "laps", "pit", "stints"}:
        drivers = json.loads((DATA / f"{key}_drivers.json").read_text(encoding="utf-8-sig"))
        query = driver.strip().casefold()
        matches = [d for d in drivers if query in {str(d.get("name_acronym", "")).casefold(), str(d.get("driver_number", "")), str(d.get("full_name", "")).casefold()}]
        if not matches:
            matches = [d for d in drivers if query in str(d.get("full_name", "")).casefold()]
        if len(matches) != 1:
            return {"error": "Driver missing or ambiguous", "matches": matches}
        number = matches[0]["driver_number"]
        rows = [row for row in rows if row.get("driver_number") == number]
    return {"race": RACES[key], "source": f"https://api.openf1.org/v1/{kind}?session_key={key}", "driver_filter": driver or None, "count": len(rows), "records": rows}
