"""Evidence from a filtered FastF1 dataset, Jolpica, and curated official accounts."""
import json
import openf1_live
import sqlite3
import statistics
from functools import lru_cache
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).parent
DB = ROOT / 'data' / 'fastf1' / 'clean_laps.sqlite3'
DATASET = 'https://github.com/straightchlorine/f1-ml-lab/blob/master/data/laps_all.parquet'
METHOD = 'https://github.com/straightchlorine/f1-ml-lab/blob/master/scripts/build_dataset.py'
LIMITATION = ('This FastF1-derived research dataset is filtered: only accurate green-flag timed laps, '
              'excluding pit in/out laps and laps over 107% of the fastest clean lap. This can exclude '
              'wet or slow laps and bias comparisons; missing laps are not proof they did not occur. '
              'No position, pit stop timing, unfiltered telemetry, or full race chronology is available here.')
SPECIAL = {'2024_12': '9558', '2024_16': '9590', '2024_21': '9636'}

@lru_cache(maxsize=1)
def catalog():
    with sqlite3.connect(DB) as db:
        rows = db.execute('select season, round, race_id, min(event) from laps group by season, round, race_id order by season, round').fetchall()
    return {SPECIAL.get(rid, rid): {'session_key': SPECIAL.get(rid, rid), 'fastf1_key': rid,
             'year': season, 'round': rnd, 'race': event.replace('S�o', 'Sao')}
            for season, rnd, rid, event in rows}

def find_races(year=0, query=''):
    text = query.casefold().strip()
    bundled = [dict(row, openf1_snapshot=key in SPECIAL.values(), official_context=key in SPECIAL.values())
               for key, row in catalog().items() if (not year or row['year'] == year)
               and (not text or text in row['race'].casefold())]
    live = []
    error = None
    if year >= 2023:
        try:
            live = openf1_live.find_races(year, query)
        except (OSError, ValueError) as exc:
            error = 'OpenF1 lookup failed: ' + str(exc)
    # Prefer the detailed OpenF1 session when it matches a bundled snapshot or race.
    if live:
        bundled_names = {openf1_live._normalize(r['race']) for r in live}
        bundled = [r for r in bundled if openf1_live._normalize(r['race']) not in bundled_names]
    result = {'races': live + bundled, 'count': len(live) + len(bundled),
              'coverage': 'OpenF1 detailed historical data fetched on demand for completed races from 2023 onward, subject to availability. Filtered FastF1-derived laps and Jolpica results bundled for 147 races in 2018–2024. Curated official accounts for the three original 2024 races.'}
    if error:
        result['lookup_warning'] = error + '; showing bundled races only.'
    return result

def _driver(key, driver):
    if key not in catalog():
        return None, {'error': 'Unknown race. Use find_race first.'}
    code = driver.strip().upper()
    with sqlite3.connect(DB) as db:
        choices = [r[0] for r in db.execute('select distinct driver from laps where race_id = ? order by driver', (catalog()[key]['fastf1_key'],))]
    if code not in choices:
        return None, {'error': 'Driver code unavailable in the filtered laps; use a three-letter code.', 'available_codes': choices}
    return code, None

def laps(key, driver, start_lap=1, end_lap=100):
    code, error = _driver(str(key), driver)
    if error: return error
    if start_lap < 1 or end_lap < start_lap or end_lap - start_lap > 100:
        return {'error': 'Provide a valid lap window of at most 101 laps.'}
    with sqlite3.connect(DB) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute('select lap, stint, compound, tyre_life, rainfall, air_temp, track_temp, lap_time from laps where race_id=? and driver=? and lap between ? and ? order by lap', (catalog()[str(key)]['fastf1_key'], code, start_lap, end_lap)).fetchall()
    return {'race': catalog()[str(key)]['race'], 'driver': code, 'records': [dict(row) for row in rows], 'source': DATASET, 'method_source': METHOD, 'limitation': LIMITATION}

def pace(key, a, b, start_lap, end_lap):
    first, second = laps(key, a, start_lap, end_lap), laps(key, b, start_lap, end_lap)
    if 'error' in first or 'error' in second:
        return {'error': 'Cannot compare drivers', 'details': [first.get('error'), second.get('error')]}
    aa = {r['lap']: r['lap_time'] for r in first['records']}; bb = {r['lap']: r['lap_time'] for r in second['records']}
    common = sorted(aa.keys() & bb.keys())
    if not common: return {'error': 'No paired clean laps available in that window.', 'limitation': LIMITATION}
    return {'race': first['race'], 'drivers': [a, b], 'window': [start_lap, end_lap], 'paired_laps': common,
            'sample_size': len(common), 'median_paired_difference_seconds_a_minus_b': round(statistics.median(aa[n]-bb[n] for n in common), 3),
            'method': 'Median of per-lap A minus B, on the same numbered retained laps. Negative means A was faster. Compounds and traffic may differ.',
            'source': DATASET, 'method_source': METHOD, 'limitation': LIMITATION}

def season_strategy(year, driver):
    """Summarize retained tyre observations and results across a bundled season."""
    path = ROOT / 'data' / 'jolpica' / f'{year}_all_results.json'
    if not path.exists():
        return {'error': 'Season overview is available for 2018–2024 only.'}
    races = json.loads(path.read_text(encoding='utf-8'))
    candidates = {}
    for race in races:
        for result in race.get('Results', []):
            item = result.get('Driver', {})
            if item.get('driverId'):
                candidates[item['driverId']] = item
    query = driver.strip().casefold()
    matches = [d for d in candidates.values() if query in {
        str(d.get('code', '')).casefold(), str(d.get('driverId', '')).casefold(),
        str(d.get('familyName', '')).casefold(),
        (str(d.get('givenName', '')) + ' ' + str(d.get('familyName', ''))).casefold()}]
    if len(matches) != 1:
        return {'error': 'Driver missing or ambiguous; use a surname or three-letter code.', 'matches': [d.get('driverId') for d in matches]}
    selected = matches[0]
    code = selected.get('code')
    if not code:
        return {'error': 'This driver has no code in the bundled data.'}
    with sqlite3.connect(DB) as db:
        rows = db.execute('select round, stint, compound, min(lap), max(lap), count(*) from laps where season=? and driver=? group by round, stint, compound order by round, stint, compound', (year, code)).fetchall()
    observations = {}
    for rnd, stint, compound, first, last, count in rows:
        observations.setdefault(rnd, []).append({'stint': stint, 'compound': compound,
            'first_retained_lap': first, 'last_retained_lap': last, 'retained_laps': count})
    timeline = []
    for race in races:
        entry = next((r for r in race.get('Results', []) if r.get('Driver', {}).get('driverId') == selected['driverId']), None)
        if entry is None:
            continue
        rnd = int(race['round'])
        timeline.append({'round': rnd, 'race': race['raceName'], 'grid': entry.get('grid'),
                         'finish': entry.get('positionText'), 'status': entry.get('status'),
                         'observed_tyres': observations.get(rnd, [])})
    return {'year': year, 'driver': selected.get('givenName', '') + ' ' + selected.get('familyName', ''),
            'driver_code': code, 'races': timeline, 'race_count': len(timeline),
            'races_with_retained_laps': sum(bool(r['observed_tyres']) for r in timeline),
            'sources': [DATASET, f'https://api.jolpi.ca/ergast/f1/{year}/results.json?limit=100'],
            'note': LIMITATION + ' Tyre stints and lap ranges are only what survived filtering, not full stint boundaries or a complete pit-stop record. Some tyre changes may be missing; do not infer an exact stop count. Examine selected races with OpenF1 for a fuller picture.'}

@lru_cache(maxsize=128)
def results(key):
    race = catalog().get(str(key))
    if not race: return {'error': 'Unknown race. Use find_race first.'}
    url = f"https://api.jolpi.ca/ergast/f1/{race['year']}/{race['round']}/results.json?limit=100"
    snapshot = ROOT / 'data' / 'jolpica' / f"{race['year']}_all_results.json"
    if snapshot.exists():
        try:
            races = json.loads(snapshot.read_text(encoding='utf-8'))
            match = next((item for item in races if int(item['round']) == race['round']), None)
            if match:
                return {'race': race['race'], 'records': match['Results'], 'source': url,
                        'note': 'Bundled Jolpica snapshot. Jolpica is unofficial; underlying sources may overlap.'}
        except (OSError, ValueError, KeyError):
            pass
    try:
        request = Request(url, headers={'User-Agent': 'ApexF1Research/1.0 (educational project)'})
        with urlopen(request, timeout=8) as response:
            payload = json.load(response)
        races = payload.get('MRData', {}).get('RaceTable', {}).get('Races', [])
        if not races: return {'error': 'Jolpica returned no race results.', 'source': url}
        records = races[0].get('Results', [])
        return {'race': race['race'], 'records': records, 'source': url, 'note': 'Jolpica is an unofficial structured results API. Timing sources may overlap.'}
    except (OSError, ValueError, URLError) as exc:
        return {'error': 'Jolpica results are temporarily unavailable: ' + str(exc), 'source': url}

@lru_cache(maxsize=1)
def documents():
    return json.loads((ROOT / 'data' / 'official_context.json').read_text(encoding='utf-8'))

def official_context(key):
    docs = documents().get(str(key), [])
    return {'documents': docs, 'note': 'Brief human-curated paraphrases, not full articles. Team accounts reflect the team perspective. Official accounts are available only for the three listed 2024 races.' if docs else 'No curated official account is available for this race; do not claim it was checked.'}
