# apex
Apex is an AI research agent that explores F1 race data to explain how pit stops, tire choices, and race conditions shaped battles on track.

The deployed version currently contains the temporary Wikipedia research starter. Local F1 research functionality is in development and is not yet deployed.

## Race data coverage

The local F1 prototype currently includes three races from 2024: the British, Italian, and São Paulo Grands Prix. Its bundled snapshots currently come from OpenF1 and Jolpica. Questions about other races should be identified as outside the available data.

We plan to expand the detailed race data using FastF1. Its timing and telemetry data are generally available from 2018 onward, subject to session availability; older results may be available from other sources. Do not treat 2018 onward as current coverage until the corresponding races have been added and checked. See the [FastF1 data reference](https://docs.fastf1.dev/data_reference/index.html).
