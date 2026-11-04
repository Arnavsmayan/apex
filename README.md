# Project 2: Apex

### The story behind every F1 race.

- **Path:** Deep Research
- **Deployed agent:** [apex-f1.cloud.run](https://apex-f1.cloud.run/)
- **Model:** Gemini 3.8 Flash on Vertex AI

## Project overview

Apex investigates how F1 race strategy, tyre choices, pace, and race events shaped a result. It is intended for F1 fans and students who want to explore what happened during a race or across a season, with evidence from race data and selected reports.

The exploration problem is to explain the decisions and events behind a race result, including questions such as how two drivers' pit stops compared or how their strategies shaped a battle. Apex uses multiple researchers to examine different parts of a question before combining the findings.

## Deep Research implementation

1. **Lead:** identifies the race or season, breaks the question into focused tasks, and starts three researchers in parallel.
2. **Researchers:** work in separate contexts, retrieve race data, calculate comparisons, and investigate their assigned angles.
3. **Lead review:** examines their findings and can send one additional researcher to investigate a gap.
4. **Writer:** combines the findings into a readable report with a source link.

The activity feed shows the steps as they happen, and the pit wall shows the agents’ contexts. Reports can be expanded for easier reading. All agents use **Gemini 3.8 Flash on Vertex AI**. The `/chat` endpoint returns `response`, `session_id`, and `tool_calls`, including an `agent` field on recorded sub-agent calls.

## Data sources and loading

| Source | What Apex uses | Coverage and how it is loaded |
| --- | --- | --- |
| **[FastF1-derived laps](https://github.com/straightchlorine/f1-ml-lab/blob/master/data/laps_all.parquet)** | Lap times, tyre compounds, stints, and associated weather observations | The FastF1-based [source pipeline](https://github.com/straightchlorine/f1-ml-lab/blob/master/scripts/build_dataset.py) generated the original Parquet data. Apex includes a converted SQLite snapshot at `data/fastf1/clean_laps.sqlite3`: 147 races across 2018–2024. |
| **[OpenF1](https://openf1.org/docs/)** | Lap times, pit stops, tyre stints, positions, intervals, weather, race control, and session results | `openf1_live.py` finds completed races and fetches historical data on demand from 2023 onward; availability varies. Snapshots for the 2024 British, Italian, and São Paulo Grands Prix are included in `data/openf1/`. |
| **[Jolpica](https://api.jolpi.ca/docs/)** | Race classifications, grid positions, and results | Season snapshots for 2018–2024 are in `data/jolpica/`; the code can request race results from the API when a snapshot is missing. |
| **FIA, F1, and team reports** | Selected classifications, race accounts, and team explanations | Short, attributed summaries and source URLs for the three bundled 2024 races are in `data/official_context.json`. Apex does not search all reports on the web. |

The FastF1-derived laps are **filtered**: the original pipeline keeps accurate green-flag laps, excludes pit in- and out-laps, and removes laps slower than 107% of the fastest eligible lap. Missing laps or observed stint ranges therefore cannot establish a complete tyre strategy or exact pit-stop count. FastF1 and OpenF1 can share underlying timing feeds, so agreement is not automatically independent confirmation. OpenF1 pit-lane duration is not the same as stationary wheel-change time.

The SQLite database, Jolpica snapshots, and selected OpenF1 snapshots ship with the Cloud Run deployment. Apex reads those files when needed; no download or setup is required to use the deployed app.

Apex fetches OpenF1 data as needed. For example, the [2024 British GP pit records](https://api.openf1.org/v1/pit?session_key=9558) use session key `9558`. Historical OpenF1 and Jolpica access does not require an API key; live OpenF1 data is outside this project’s scope.

## Grader questions and model comparisons

These are the same examples available in the app. The **expected answers** below identify specific facts to look for. The side-by-side columns are excerpts from actual runs on **November 3, 2026**; [full captured outputs](COMPARISONS.md) are included. The baseline used the same `gemini-3.8-flash` model in separate Vertex AI Studio conversations, with an empty system-instructions field and Google grounding, function calling, code execution, and URL context disabled. These are individual outputs, not an accuracy benchmark, and may contain errors.

### 1. How did Hamilton and Verstappen’s pit stops compare at the 2024 British Grand Prix?

**Expected:** Verstappen pitted on laps **26 and 38**; Hamilton pitted on laps **27 and 38**. Both moved from medium tyres to intermediates, then Hamilton finished on softs and Verstappen on hards. OpenF1 records pit-lane time rather than the stationary wheel-change time for these stops.

**Evidence:** [`9558_pit.json`](data/openf1/9558_pit.json), [`9558_stints.json`](data/openf1/9558_stints.json), [OpenF1 pit endpoint](https://api.openf1.org/v1/pit?session_key=9558).

| Apex answer, excerpt | Same model without tools, excerpt |
| --- | --- |
| “Max Verstappen spent less total time in the pit lane than Lewis Hamilton during both pit stop phases, gaining 0.6 seconds … and 1.0 second…” Apex also stated that the stationary times were unrecorded. | “Verstappen’s stops were both well under **2.5 seconds** stationary” and Hamilton’s were “in the **2.6 to 2.8-second** range.” |

The no-tool response gives stationary times that cannot be verified from these OpenF1 records. The Apex excerpt distinguishes pit-lane duration from stationary time; other claims in its full report should still be checked against their sources.

<details>
<summary>Full Apex answer</summary>

At the 2024 British Grand Prix, Max Verstappen spent less total time in the pit lane than Lewis Hamilton during both pit stop phases, gaining 0.6 seconds during the switch to intermediate tyres and 1.0 second on the transition back to dry slicks. However, strategic timing and tyre warm-up allowed Hamilton to retain crucial track position in both instances.

First Stop: Transition to Intermediates (Laps 26–27)

As rain began falling and Race Control disabled DRS on Lap 25, Verstappen made an early call to pit for intermediate tyres on Lap 26. He spent 28.3 seconds traversing the pit lane, producing an in-lap of 1:41.491 and an out-lap of 1:59.169.

Hamilton stayed out on medium slicks for one additional lap, entering the pits on Lap 27 just as Race Control noted slippery conditions in Sector 17. Hamilton spent 28.9 seconds in the pit lane. Suffering from the worsening rainfall on his in-lap, Hamilton logged a 1:45.183 and followed with a 2:00.866 out-lap. While Hamilton led the Mercedes double-stack without being delayed by teammate George Russell, Verstappen's earlier stop and sharper in-lap and out-lap pace significantly eroded Hamilton's advantage, slashing an approximate 10.1-second deficit on Lap 25 down to a 3.603-second gap when Hamilton emerged in second position on Lap 28.

Second Stop: Transition to Slicks (Lap 38)

Both drivers made their second pit stop simultaneously on Lap 38 as a dry line emerged, diverging on tyre compound choice:

Max Verstappen: Fitted new hard tyres, spending 29.0 seconds in the pit lane.
Lewis Hamilton: Fitted one-lap-old soft tyres, spending 30.0 seconds in the pit lane.

Verstappen entered the pits faster, recording an in-lap of 1:35.963 compared to Hamilton's 1:37.220. Combined with a pit lane duration that was 1.0 second shorter, Verstappen chipped away at the gap on pit entry. However, Hamilton countered on cold tyres: his soft compound generated superior immediate grip, clocking an out-lap of 1:57.389 on Lap 39 against Verstappen's 1:58.311 on the harder compound. When leader Lando Norris pitted a lap later, Hamilton assumed the race lead, maintaining an initial 6.418-second cushion over Verstappen on Lap 40.

Pit Execution Comparison

Across both phases, Red Bull recorded faster total pit lane durations (28.3 seconds versus 28.9 seconds on the first stop; 29.0 seconds versus 30.0 seconds on the second stop). Stationary wheel-change durations were unrecorded in the timing data, leaving it undetermined whether Red Bull's pit lane advantage stemmed from faster stationary service, pit box approach and departure speed, or pit-limiter transit. Race Control recorded no pit box overshoots, equipment faults, or unsafe release holds for either crew.

Source

Apex source link: https://www.formula1.com/en/latest/article/hamilton-beats-verstappen-to-first-win-since-2021-with-record-breaking-9th.3teU9bznaWJlC2TGAYh0Vl.3teU9bznaWJlC2TGAYh0Vl

</details>

<details>
<summary>Full Gemini answer without tools or a system prompt</summary>

At the dramatic, rain-affected 2024 British Grand Prix, the pit stops between Lewis Hamilton (Mercedes) and Max Verstappen (Red Bull) were defined by **strategic timing and tire choices** rather than pit crew errors. Both drivers executed their stops almost flawlessly, but their different approaches directly shaped the fight for the win.

Here is how their pit stops compared across the race:

---

### 1. First Pit Stop: Slicks to Intermediates (The Rain Arrives)
As rain began falling heavily around Lap 25–27, timing the crossover to intermediate tires was critical.

* **Max Verstappen (Lap 26):**
  * **Strategy:** Verstappen was struggling heavily for grip on slicks and dropping back from the leaders. Red Bull pulled off a tactical masterstroke by pitting him **one lap early** on Lap 26.
  * **Result:** The rain intensified immediately on his out-lap. Because he was already on intermediate tires, he instantly gained massive lap time over those still slipping on slicks, vaulting him back into contention.
* **Lewis Hamilton (Lap 27):**
  * **Strategy:** Hamilton stayed out one lap longer than Verstappen, coming in on Lap 27 alongside his teammate George Russell (Mercedes successfully double-stacked without delay).
  * **Result:** While Hamilton lost a bit of time to Verstappen during that transition lap, his stop was cleanly executed, and he re-entered the track still ahead of Max, chasing Lando Norris.

---

### 2. Second Pit Stop: Intermediates to Slicks (The Track Dries)
Around Lap 38, the track had dried sufficiently for dry tires. This was the decisive moment of the race.

* **Timing (Identical – Lap 38):**
  * Both Hamilton and Verstappen pitted on the **exact same lap (Lap 38)** to switch back to slicks.
  * Crucially, the race leader at the time, Lando Norris (McLaren), stayed out one lap too long (pitting on Lap 39). Because Hamilton and Verstappen stopped on Lap 38, they executed a powerful undercut on Norris.
* **Tire Choice (The Deciding Factor):**
  * **Hamilton chose Soft tires:** Mercedes fitted scrubbed (used) Softs. This gave Hamilton instant grip and rapid warm-up, allowing him to easily undercut Norris and seize the lead. However, the risk was high tire degradation toward the end of the race.
  * **Verstappen chose Hard tires:** Red Bull did not have a fresh set of competitive softs, so they fitted the Hard compound. The hards took a lap or two longer to switch on, but once up to temperature, Verstappen had by far the fastest pace on track and didn't suffer from thermal degradation.

---

### 3. Pit Crew Execution (Stationary Times)
* **Red Bull:** As usual, Red Bull's crew was clinical. Verstappen’s stops were both well under **2.5 seconds** stationary, giving him optimal delta times on entry and exit.
* **Mercedes:** Mercedes delivered two clean, trouble-free stops for Hamilton (both in the **2.6 to 2.8-second** range), including a smooth double-stack in the first phase.
* **Contrast with McLaren:** Both Hamilton and Verstappen heavily benefited from their crews' consistency compared to McLaren, who fumbled Norris’s final stop with a 3.8-second delay, handing Hamilton the net lead.

---

### Summary of Impact
* **Verstappen’s pit stops saved his race:** His early gamble to fit intermediates on Lap 26 mitigated a poor early stint, and the decision to fit **Hard tires** on Lap 38 allowed him to pass Norris late in the race and hunt down Hamilton, ultimately finishing P2.
* **Hamilton’s pit stops won him the race:** Mercedes timed both stops without hesitation. Fitting **Soft tires** on Lap 38 gave him the immediate pace required to take the lead from Norris and build just enough of a buffer to hold off Verstappen’s hard-charging Red Bull at the checkered flag.

</details>

### 2. How did Leclerc and Piastri battle for victory at the 2024 Italian Grand Prix?

**Expected:** Leclerc made one stop, on lap **15**, and finished on hard tyres. Piastri stopped on laps **16 and 38** and chased Leclerc on fresher hards. Leclerc won by **2.664 seconds**.

**Evidence:** [`9590_pit.json`](data/openf1/9590_pit.json), [`9590_stints.json`](data/openf1/9590_stints.json), [`9590_results.json`](data/jolpica/9590_results.json), and the [McLaren race report](https://www.mclaren.com/racing/formula-1/2024/italian-grand-prix/2024-italian-grand-prix-race-report/).

| Apex answer, excerpt | Same model without tools, excerpt |
| --- | --- |
| “Leclerc executing a bold one-stop strategy to hold off a charging, two-stopping Piastri by just 2.664 seconds.” Apex also calculated Piastri’s median paired-lap advantage over laps 40–53 as **1.228 seconds per lap**. | “Piastri pitted from the lead on Lap 38” while Ferrari chose “the one-stop strategy.” The baseline also gave the **2.664-second** finish margin. |

Both answers captured the main outcome. Apex additionally used a calculated lap-by-lap comparison; it is a median of paired laps, with pit and out laps excluded, rather than proof of why either driver won.

<details>
<summary>Full Apex answer</summary>

Charles Leclerc and Oscar Piastri fought for victory at the 2024 Italian Grand Prix through divergent tyre strategies, with Leclerc executing a bold one-stop strategy to hold off a charging, two-stopping Piastri by just 2.664 seconds.

Opening Laps and First Stint

Piastri started second behind pole-sitter Lando Norris, while Leclerc started fourth. On Lap 1, Piastri seized the lead by overtaking Norris around the outside at the Roggia chicane (Turns 4–5). Norris was compromised on exit, allowing Leclerc—who had already gained third place—to pass Norris for second.

Both leaders started on medium tyres. Leclerc shadowed Piastri within DRS range through Lap 10, keeping the interval between 0.43s and 1.23s. As tyres degraded from Lap 11 onward, Leclerc experienced a steeper drop in pace, recording a 1:25.529 on Lap 13 and a 1:25.606 on Lap 14, compared to Piastri’s 1:24.670 and 1:25.048. Over the 13 paired laps between Laps 2 and 14, Piastri held a median paired lap advantage of 0.115 seconds over Leclerc.

Norris pitted on Lap 14, prompting Ferrari to pit Leclerc on Lap 15 with a pit lane duration of 24.500s. Piastri pitted from the lead on Lap 16 (23.700s pit lane duration), with both switching to hard tyres.

Stint 2 and Strategic Divergence

After the cycle shook out, Piastri retained the net lead. Leclerc ran third behind Norris until McLaren brought Norris in for a second pit stop on Lap 32, elevating Leclerc to second.

Between Laps 18 and 37 (a 20 paired-lap sample), Piastri held a slight median paired pace advantage of 0.118 seconds per lap over Leclerc. Leclerc posted remarkably stable lap times around the mid-to-high 1:23s, trailing Piastri by 5.532 seconds on Lap 33 and 5.824 seconds on Lap 37.

Citing tyre degradation concerns, McLaren committed Piastri to a two-stop strategy, pitting him from the lead on Lap 38 for a second set of hard tyres (24.600s pit lane duration). Ferrari, by contrast, chose to keep Leclerc out on a one-stop strategy, committing him to a 38-lap final stint on his existing hard tyres.

The Final Stint Pursuit

Leclerc inherited the race lead when Piastri pitted. Piastri rejoined in third place behind Carlos Sainz, facing an initial deficit to Leclerc of 18.54s at the end of Lap 39.

Equipped with fresh rubber, Piastri mounted an aggressive chase, lapping between 1:21.943 and 1:23.675. Across Laps 40–53 (14 paired laps), Piastri held a median paired lap advantage of 1.228 seconds over Leclerc. However, Piastri's pursuit met two key obstacles:

Traffic and Sainz: Piastri had to clear backmarkers operating under blue flags and spent laps closing on Sainz, finally overtaking him for second on Lap 45 (where Piastri logged a 1:23.675).
Leclerc's Tyre Management: Despite tyres over 20 laps older than Piastri's, Leclerc avoided a dramatic performance cliff. He maintained lap times strictly between 1:23.268 and 1:23.867 across Laps 40 to 53.

Piastri reduced the deficit from 11.60s on Lap 45 to 3.99s by Lap 52. However, the 15-lap window was too short to erase the entire pit stop delta. Leclerc crossed the finish line to take victory for Ferrari in 1:14:40.727, keeping Piastri 2.664 seconds behind at the chequered flag.

Source

Apex source link: https://www.formula1.com/en/latest/article/leclerc-thrills-the-tifosi-to-triumph-at-monza-ahead-of-piastri-and-norris.1aiYZF3rWZp2Q9yQtcuvqV

</details>

<details>
<summary>Full Gemini answer without tools or a system prompt</summary>

The battle for victory between Charles Leclerc and Oscar Piastri at the 2024 Italian Grand Prix was not a traditional wheel-to-wheel dogfight, but rather an **intense, high-stakes strategic duel**—a battle of raw pace on fresh tyres versus a masterclass in tyre conservation.

Here is how the battle unfolded across the race:

---

### 1. The Opening Lap: Setting the Stage
* McLaren entered the race as the favorites after locking out the front row (Lando Norris P1, Piastri P2), while Leclerc started P4.
* On Lap 1, into the *Variante della Roggia* (Turns 4–5), **Piastri pulled off a stunning, aggressive around-the-outside overtake on his teammate Norris** to take the lead.
* Norris’ compromised exit allowed **Leclerc to sneak past into P2**. This immediately set up Piastri in P1 and Leclerc in P2, putting Ferrari right in the fight at their home circuit.

---

### 2. The First Stint and the Undercut
* Piastri controlled the opening phase from the lead, while Leclerc stayed within his DRS window or just outside it.
* However, extreme front-left tyre graining began affecting the entire field due to the newly resurfaced Monza asphalt and high track temperatures.
* On Lap 14, McLaren pitted Norris to attempt an undercut on Leclerc. Ferrari responded by pitting Leclerc on Lap 15, but Norris jumped him.
* Piastri pitted on Lap 16 to cover both, retaining the net lead. At this stage, Piastri looked in complete control, pulling out a comfortable gap over Norris and Leclerc.

---

### 3. The Turning Point: 2-Stop vs. 1-Stop
As the second stint progressed, the McLarens once again began suffering from heavy front-left graining. Convinced that the tyres could not survive to the end without failing or suffering massive lap-time drop-offs, McLaren committed to a **two-stop strategy**:
* Norris pitted for his second set of hard tyres on Lap 32.
* **Piastri pitted from the lead on Lap 38.**

Ferrari, however, realized they had nothing to lose and pulled off a bold gamble: **the one-stop strategy.**
* When Piastri exited the pits on Lap 39, **Leclerc inherited the race lead**, with his teammate Carlos Sainz running in second.
* Leclerc was on 24-lap-old hard tyres, and Piastri was roughly **11.5 seconds behind** on brand-new rubber, with 15 laps remaining.

---

### 4. The Hunt (Laps 39–53)
What followed was a thrilling, 15-lap cat-and-mouse chase against the clock:

* **Piastri’s Charge:** On fresh tyres, Piastri was blistering fast, initially lapping between 1.5 to 2.0 seconds faster than the Ferraris.
* **The Sainz Obstacle:** Piastri quickly caught Carlos Sainz and overtook him for P2 on Lap 45, but fighting past the sister Ferrari cost Piastri about a second of vital time.
* **Leclerc’s Tyre Whisper:** Everyone expected Leclerc’s tyres to hit the "cliff" (a sudden drop-off in grip). Instead, Leclerc managed his front-left tyre masterfully. As the fuel burned off, Leclerc’s graining actually cleared up, and he began stabilizing his lap times into the 1m22s.
* **The Math:** With 5 laps to go, Piastri needed to gain over a second per lap to catch Leclerc, but the dirty air and tyre wear on his own car began slowing his charge. He was taking tenths out of Leclerc, not seconds.

---

### 5. The Finish
Piastri simply ran out of laps.

Leclerc crossed the finish line to take an emotional victory for Ferrari in front of the *Tifosi* by **2.664 seconds** ahead of Piastri.

### Why It Was Significant
The duel was decided by bravery on the pit wall and perfection in the cockpit:
* **McLaren and Piastri** drove the theoretically "correct" and safe race based on their telemetry, and Piastri’s driving was near-flawless.
* **Ferrari and Leclerc** pulled off an audaciously risky strategy that relied 100% on Leclerc driving fast enough to stay ahead while driving gently enough to keep tyres alive that were never meant to run 38 consecutive laps at full speed.

</details>

### 3. How did Verstappen’s tyre strategy vary across the 2024 season?

**Expected:** The retained FastF1-derived laps show different compounds across races, including soft–hard–soft observations in Bahrain and soft–medium–soft observations in Spain. The OpenF1 Spanish GP stint records show **soft, medium, soft**. A season answer should avoid treating the filtered SQLite rows as a complete record of every stint.

**Evidence:** `laps` table in [`clean_laps.sqlite3`](data/fastf1/clean_laps.sqlite3), [`2024_all_results.json`](data/jolpica/2024_all_results.json), and [OpenF1 Spanish GP stints](https://api.openf1.org/v1/stints?session_key=9539&driver_number=1).

| Apex answer, excerpt | Same model without tools, excerpt |
| --- | --- |
| “At the Spanish Grand Prix … he executed a **Soft–Medium–Soft** strategy.” Apex compared several races and weather conditions. | “**Spain (Soft–Medium–Hard)**,” followed by an explanation of an early undercut. |

The OpenF1 stint records support the compounds in the Apex excerpt and disagree with the baseline’s final compound. The full Apex season report also makes broader claims that cannot all be established from its filtered season overview; its single Jolpica results link does not itself document tyre compounds. The [captured answers](COMPARISONS.md) preserve both responses without presenting them as verified ground truth.

<details>
<summary>Full Apex answer</summary>

Across the 24 rounds of the 2024 season, Max Verstappen’s tyre strategy varied between a baseline medium-to-hard one-stop, aggressive soft- or medium-oriented two-stops, inverted hard-compound starting plans, and weather-dictated wet-to-dry transitions. In total, Verstappen started on medium tyres in 18 races, using alternative dry starting compounds only four times (soft in Bahrain and Spain; hard in Monaco and Italy) alongside two wet-weather starts.

1. Baseline Medium-to-Hard One-Stop

Verstappen’s default dry-weather approach across low-to-moderate degradation circuits was a single pit stop transitioning from the medium compound to the hard compound.

Circuits: Saudi Arabia, Miami, Emilia Romagna, the Netherlands, Singapore, the United States (Austin), Mexico City, Qatar, and Abu Dhabi.
Execution: Verstappen typically ran an opening medium stint between 20 and 28 laps before switching to the hard tyre to finish the race.
Operational Note: While data records for Qatar (Round 23) log pit-lane entries on laps 35, 36, and 37, Verstappen conducted only one operational tyre stop on lap 35 (switching from medium to hard). His pit-lane entries on laps 36 and 37 were safety-car pass-throughs directed by Race Control to avoid debris on the main straight, running the same set of hard tyres consecutively to the finish.
2. Planned Multi-Stop Strategies

At circuits featuring higher tyre degradation or specific track-position requirements, Red Bull deployed multiple two-stop variations:

Soft-Starting Two-Stops: At the season opener in Bahrain, Verstappen used a Soft–Hard–Soft sequence to capitalise on cooler evening track temperatures. At the Spanish Grand Prix (Round 10), he executed a Soft–Medium–Soft strategy, pitting on laps 17 and 44 to retain track position.
Medium-Centric Two-Stops: In Japan (Round 4), following a lap 1 red flag, Verstappen ran Medium–Medium–Hard. In Hungary (Round 13) and Belgium (Round 14), he ran Medium–Hard–Medium run plans. In Las Vegas (Round 22), high thermal demand and graining led to a Medium–Hard–Hard strategy with pit stops on laps 11 and 27.
Late-Race Stops: In Azerbaijan (Round 17), Verstappen pitted on lap 49 for a brief two-lap final stint on softs. In Austria (Round 11), what was initially an intended strategy variation became a three-stop race (Medium–Hard–Medium–Soft), as his lap 65 pit stop for softs was an emergency service necessitated by a rear puncture after contact with Lando Norris.
3. Inverted Starting Strategies

When qualifying further down the order, Red Bull deviated from starting on the medium compound:

Italy (Monza, Round 16): Starting from P7, Verstappen ran an inverted Hard–Hard–Medium strategy, using two consecutive hard stints (laps 1–22 and 23–41) to run longer in clean air before switching to mediums for the final 12 laps.
Monaco (Round 8): Starting P6, he took the grid on hard tyres. However, a red flag on lap 1 allowed the team to switch to medium tyres in the pit lane without a green-flag pit loss, completing laps 1 to 51 on mediums before a final stop for hards on lap 52.
4. Wet and Mixed-Weather Transitions

Variable weather conditions required dynamic intermediate tyre shifts across three Grands Prix:

Canada (Round 9): A wet-to-dry two-stop progression where Verstappen opened with two consecutive stints on intermediate tyres (pitting on laps 25 and 45) before concluding on medium slicks from lap 45 to 70.
Great Britain (Round 12): Starting on mediums (laps 1–26), Verstappen pitted for intermediates on lap 26 as rain intensified, then transitioned to hard slicks on lap 38 as the track dried.
São Paulo (Round 21): In full wet conditions, Verstappen ran exclusively on intermediate tyres across two stints. He completed laps 1 to 32 on his starting set before switching to a fresh set of intermediates during the lap 32 red-flag stoppage, avoiding a green-flag pit-lane time loss on his way from 17th on the grid to victory.

Source

Apex source link: https://api.jolpi.ca/ergast/f1/2024/results.json?limit=100

</details>

<details>
<summary>Full Gemini answer without tools or a system prompt</summary>

Max Verstappen’s tyre strategy throughout the 2024 Formula 1 season underwent a dramatic evolution. It shifted from **proactive, textbook dominance** in the early rounds to **reactive, aggressive damage limitation** as the Red Bull RB20 lost its tyre-whispering advantage to McLaren and Ferrari.

Here is a breakdown of how Verstappen’s tyre strategies varied across the key phases of the 2024 season:

---

### 1. The Early Season: Absolute Control and Planned Offsets (Bahrain – China)
In the opening flyaway races, the RB20 was the class of the field. Verstappen enjoyed superior tyre degradation compared to his rivals, which allowed Red Bull to dictate the strategy rather than react to others.

* **Bahrain (Soft–Hard–Soft):** While most teams ran Soft–Hard–Hard, Red Bull had specifically saved a scrubbed set of Soft tyres from qualifying. Verstappen used the Softs at the start to pull a gap, switched to Hards, and finished on Softs against rivals on Hards—purely demonstrating superior tyre management.
* **Japan (Medium–Hard–Hard):** In a race with high thermal degradation, Verstappen and Red Bull comfortably ran standard, optimal stints, never under pressure to pivot or pit early to defend against undercuts.
* **Characteristics:** Long first stints, predictable pit windows, and minimal tyre graining.

---

### 2. The Mid-Season Turning Point: Pressure and Balance Woes (Miami – Spain)
Starting in Miami, McLaren’s upgrade package transformed the MCL38 into the gentlest car on its tyres. Concurrently, the RB20 developed severe balance issues (specifically mid-corner understeer turning into exit oversteer), which began rapidly eating front or rear tyres depending on the circuit.

* **Imola (Medium–Hard):** A classic one-stop that nearly unraveled. On the Mediums, Verstappen pulled a 7-second lead, but his Hard tyres “switched off” late in the race due to temperature drop-off. Lando Norris, with superior late-stint tyre life, hunted him down, forcing Verstappen to drive completely defensively on dead tyres.
* **Spain (Soft–Medium–Hard):** Red Bull recognized they were no longer the fastest car on pure tyre life. Instead of running a long second stint, they triggered an **early undercut** on Norris to maintain track position, sacrificing late-race tyre performance to gain dirty-air advantage over the McLaren.

---

### 3. The Crisis Phase: High Degradation & Strategic Frustration (Austria – Monza)
By mid-summer, Red Bull’s degradation was visibly worse than McLaren’s and Mercedes’. Verstappen was frequently complaining over team radio about lack of grip and graining, forcing Red Bull into suboptimal strategies.

* **Hungary (Medium–Hard–Hard):** A strategic disaster for Red Bull. Because of poor tyre life, Verstappen was undercut by Lewis Hamilton and Charles Leclerc. Red Bull kept Verstappen out long to build a tyre delta (offset), hoping he could overtake them late on fresher rubber. However, overtaking proved too difficult, the tyres overheated in dirty air, and Verstappen’s frustration boiled over into a collision with Hamilton.
* **Belgium (Spa) (Medium–Hard–Hard):** Starting 11th due to an engine penalty, Verstappen couldn't rely on his traditional slow-burn tyre management. Red Bull used an aggressive two-stop strategy, pitting early in both windows to undercut cars into clean air rather than saving rubber for a long stint.
* **Zandvoort (Soft-defense failure):** Starting P2, Verstappen beat Norris off the line, but by Lap 15, his tyres completely dropped off a cliff. Norris easily overtook him. Verstappen abandoned any aggressive strategy and ran a passive one-stop to simply bank P2.
* **Monza (Hard–Hard–Medium):** Knowing they lacked pace, Red Bull gambled by starting on the Hard compound to run deep into the race. However, severe front-tyre graining ruined the plan, and a slow pit stop forced them into an awkward, uncompetitive two-stop strategy.

---

### 4. The Late Season: Opportunism, Wet Weather, and Damage Limitation (Austin – Abu Dhabi)
Following a floor upgrade in Austin, the car’s balance stabilized somewhat, but Verstappen’s strategies in the final third of the season were defined by qualifying compromises and opportunistic execution.

* **Austin (Medium–Hard):** Verstappen used his tyres defensively. Knowing Ferrari had far better race pace, he didn't fight Leclerc or Sainz to avoid cooking his tyres, instead managing his stint to hold off Norris, heavily leaning on defensive positioning as his rear tyres died.
* **Brazil (Interlagos – The Wet Masterclass):**
  Starting 17th on the grid in heavy rain, tyre strategy won him the race. While rivals like Norris and Russell pitted for fresh Intermediate tyres under a virtual safety car (fearing tyre wear on a drying/wet track), Verstappen stayed out on heavily worn Inters, managing tyre temperatures in standing water. He correctly banked on an impending red flag (which materialized), earning a "free" tyre change that propelled him to victory.
* **Qatar (Medium–Hard):** In a race heavily dictated by high-speed front-left tyre stress, Verstappen controlled the pace from the front, mimicking his early-2023 form by driving just fast enough to protect the tyre's vulnerable shoulder without letting rivals into DRS range.

---

### Summary of Key Strategic Shifts:
1. **From Overcuts to Undercuts:** In 2023 and early 2024, Verstappen often ran longer than everyone else (overcut) because his tyres didn't degrade. By mid-2024, Red Bull was forced to rely on early undercuts to secure track position because they could no longer overtake on equal or older tyres.
2. **Compound Sensitivity:** The RB20 was fast on Softs for one lap, but deeply volatile on the Hard compound (frequently struggling to get Hards into the proper operating window, as seen at Monza and Hungary).
3. **Driver Management over Car Superiority:** In the final third of the season, Verstappen’s tyre strategy was often "salvaged" by his individual driving inputs—backing off in high-energy corners to preserve thermal limits—rather than the car naturally taking care of the rubber.

</details>

## Tool parameters

| Tool | What to pass | What it does |
| --- | --- | --- |
| `find_race` | Four-digit `year` and part of the race name, such as `2024` and `British` | Finds the race key and reports source availability. A year is needed to discover on-demand OpenF1 sessions. |
| `get_season_strategy` | `year` from 2018–2024 and driver surname, full name, or code, such as `2024` and `VER` | Summarizes retained tyre observations and results by race. The observed ranges are not complete stint boundaries. |
| `get_race_evidence` | OpenF1 `session_key`, one to three driver names or codes, and types such as `pit`, `stints`, `laps`, `weather`, `race_control`, or `results` | Retrieves several kinds of evidence together. |
| `get_race_data` | OpenF1 session key, one data type, and a driver when needed; intervals require `start_lap` and `end_lap` | Retrieves one kind of race data or a short interval window. |
| `compare_lap_pace` | OpenF1 session key, two drivers, and a lap range, such as `9558`, `HAM`, `VER`, `40`, `52` | Calculates the median of same-numbered paired lap differences, excluding pit and out laps. |
| `get_historical_laps` / `compare_historical_pace` | Bundled race key such as `2021_22`, driver codes such as `HAM` and `VER`, and a lap range | Retrieves or compares filtered FastF1-derived laps. |
| `get_structured_results` / `get_official_context` | A race session key returned by `find_race` | Retrieves classifications or the selected official and team summaries when available. |
