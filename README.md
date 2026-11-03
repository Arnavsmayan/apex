# Apex

Apex investigates questions about Formula 1 races. A lead finds the race and assigns distinct research tasks, researchers analyze data and check accounts, and a review may request one focused follow-up before the report is written and checked. All agents use the configured Vertex AI model.

## Evidence and coverage

- **FastF1-derived historical laps:** 147 races in 2018–2024, from [f1-ml-lab's dataset](https://github.com/straightchlorine/f1-ml-lab/blob/master/data/laps_all.parquet), converted to SQLite. These are not full race histories: the [source pipeline](https://github.com/straightchlorine/f1-ml-lab/blob/master/scripts/build_dataset.py) retains accurate green-flag laps, excludes pit in/out laps, and filters laps slower than 107% of the fastest eligible lap. This can remove wet and slow laps and bias comparisons. Coverage varies by race and driver.
- **OpenF1:** bundled laps, pit records, stints, positions, intervals, weather and race control for the 2024 British, Italian and São Paulo Grands Prix. Intervals refer to the car ahead, not necessarily another named driver. Pit-lane duration is not stationary stop time.
- **Jolpica:** bundled race classifications for 2018–2024. The app can fall back to the [Jolpica API](https://api.jolpi.ca/docs/) if a snapshot is missing.
- **FIA, Formula 1, and team accounts:** short attributed, source-linked paraphrases for the three detailed 2024 races. They are selected context, not complete articles or coverage of every race. Teams describe their own perspective.

FastF1 and OpenF1 may derive observations from the same timing feeds. Agreement is not automatically independent confirmation. Detailed telemetry, pit history and official accounts are not available for every historical race. The reports should state these limits and avoid causal or counterfactual claims that evidence cannot support.

## Example questions

- How did Hamilton and Verstappen's pit stops compare at the 2024 British Grand Prix?
- Why did Leclerc finish ahead of the McLarens at the 2024 Italian Grand Prix?
- How did Hamilton and Verstappen's retained clean-lap pace compare during laps 20–30 of the 2021 Abu Dhabi Grand Prix?

## Run locally

Install the dependencies in `pyproject.toml`, configure Vertex AI application default credentials, and run `uvicorn app:app --reload`. The app listens on the port set by the deployment environment. No separate OpenF1 or Jolpica API key is required for the bundled data.
