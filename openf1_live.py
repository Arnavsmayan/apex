"""Fetch completed 2023-onward races from OpenF1 on demand."""
import json
import threading
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = 'https://api.openf1.org/v1/'
_lock = threading.RLock()
_cache = {}
_sessions = {}
_last_request = 0.0

def _get(endpoint, **params):
    global _last_request
    url = BASE + endpoint + '?' + urlencode(params)
    with _lock:
        if url in _cache:
            cached_at, data = _cache[url]
            ttl = 300 if endpoint in {'sessions', 'meetings'} else 21600
            if time.monotonic() - cached_at < ttl:
                return data, url
            del _cache[url]
        delay = 0.4 - (time.monotonic() - _last_request)
        if delay > 0:
            time.sleep(delay)
        try:
            req = Request(url, headers={'User-Agent': 'ApexF1Research/1.0 educational project'})
            _last_request = time.monotonic()
            with urlopen(req, timeout=15) as response:
                data = json.load(response)
        except HTTPError as exc:
            if exc.code == 404:
                data = []
            else:
                raise
        if not isinstance(data, list):
            raise ValueError('OpenF1 returned an unexpected response')
        if len(_cache) >= 256:
            _cache.pop(next(iter(_cache)))
        _cache[url] = (time.monotonic(), data)
        return data, url

def _normalize(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value.casefold()) if not unicodedata.combining(c))

def find_races(year, query=''):
    if year < 2023 or year > datetime.now(timezone.utc).year:
        return []
    sessions, _ = _get('sessions', year=year, session_name='Race')
    meetings, _ = _get('meetings', year=year)
    by_id = {str(m['meeting_key']): m for m in meetings}
    found = []
    for session in sessions:
        if session.get('is_cancelled') or not session.get('date_end'):
            continue
        ended = datetime.fromisoformat(session['date_end'].replace('Z', '+00:00'))
        if ended.tzinfo is None:
            ended = ended.replace(tzinfo=timezone.utc)
        # OpenF1 historical data is free; do not request a current live session.
        if ended > datetime.now(timezone.utc) - timedelta(days=1):
            continue
        meeting = by_id.get(str(session['meeting_key']), {})
        name = meeting.get('meeting_name') or f"{session.get('country_name', '')} Grand Prix"
        search_text = ' '.join(str(x) for x in (name, session.get('country_name', ''), session.get('location', ''), session.get('circuit_short_name', '')))
        key = str(session['session_key'])
        row = {'session_key': key, 'year': year, 'race': name, 'openf1_available': True,
               'location': session.get('location'), 'official_context': key in {'9558', '9590', '9636'}}
        with _lock:
            _sessions[key] = row
        if not query or _normalize(query) in _normalize(search_text):
            found.append(row)
    return found

def has_session(key):
    with _lock:
        return str(key) in _sessions

def get_data(key, kind, driver=''):
    key = str(key)
    with _lock:
        race = _sessions.get(key)
    if not race:
        return {'error': 'Race not found. Call find_race with a year first.'}
    kinds = {'sessions', 'drivers', 'laps', 'pit', 'stints', 'race_control', 'position', 'intervals', 'weather', 'results'}
    if kind not in kinds:
        return {'error': 'Unknown data type.'}
    params = {'session_key': key}
    driver_kinds = {'drivers', 'laps', 'pit', 'stints', 'position', 'intervals'}
    if driver and kind in driver_kinds:
        all_drivers, _ = _get('drivers', session_key=key)
        query = driver.strip().casefold()
        matches = [d for d in all_drivers if query in {str(d.get('name_acronym', '')).casefold(), str(d.get('driver_number', '')), str(d.get('full_name', '')).casefold()}]
        if not matches:
            matches = [d for d in all_drivers if query in str(d.get('full_name', '')).casefold()]
        if len(matches) != 1:
            return {'error': 'Driver missing or ambiguous', 'matches': matches}
        params['driver_number'] = matches[0]['driver_number']
    endpoint = 'session_result' if kind == 'results' else kind
    rows, url = _get(endpoint, **params)
    total = len(rows)
    note = 'OpenF1 is an unofficial source; some fields or races may be unavailable.'
    if kind == 'position':
        previous = {}; changes = []
        for row in rows:
            number = row.get('driver_number')
            if number not in previous or previous[number] != row.get('position'):
                changes.append(row); previous[number] = row.get('position')
        rows = changes
        note += ' Only position changes are shown; timestamps are observations, not exact overtake times.'
    elif kind == 'weather' and rows:
        selected = []; last_time = None; previous_rain = object()
        for row in rows:
            current = datetime.fromisoformat(row['date'].replace('Z', '+00:00'))
            rain = row.get('rainfall')
            if last_time is None or (current - last_time).total_seconds() >= 300 or rain != previous_rain:
                selected.append(row); last_time = current
            previous_rain = rain
        if selected[-1] != rows[-1]: selected.append(rows[-1])
        rows = selected
        note += ' Sampled every five minutes plus observed rainfall changes and final reading; sensor readings do not prove track conditions.'
    if kind in {'weather', 'race_control'}:
        fields = ('date', 'air_temperature', 'track_temperature', 'rainfall', 'humidity', 'wind_speed') if kind == 'weather' else ('date', 'driver_number', 'lap_number', 'category', 'flag', 'scope', 'sector', 'message')
        rows = [{k: row[k] for k in fields if row.get(k) is not None} for row in rows]
    return {'race': f"{race['year']} {race['race']}", 'source': url, 'driver_filter': driver or None,
            'count': len(rows), 'original_count': total, 'records': rows, 'note': note}
