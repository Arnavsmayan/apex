# Race data

These JSON snapshots were downloaded from the OpenF1 API on 2026-11-02. The bundled sessions are the 2024 British Grand Prix (9558), Italian Grand Prix (9590), and Sao Paulo Grand Prix (9636). Each filename contains the OpenF1 session key and endpoint name. For example, `9558_laps.json` came from `https://api.openf1.org/v1/laps?session_key=9558`.

The snapshots include sessions, drivers, laps, pit, stints, race_control, position, intervals, and weather. Position, interval, and weather snapshots were added on 2026-11-03. Data is subject to source coverage and missing values. Pit timing and lap records alone cannot establish why a team made a decision or what would have happened under a different strategy. OpenF1 is an unofficial source. See https://openf1.org/docs/ for endpoint definitions and attribution.

The `jolpica` folder contains result snapshots from the Jolpica API for rounds 12, 16, and 21 respectively: `https://api.jolpi.ca/ergast/f1/2024/{round}/results.json`. See https://api.jolpi.ca/docs/.
