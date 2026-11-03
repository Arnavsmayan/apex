import asyncio
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import uvicorn
from agents import Agent, ModelSettings, RunContextWrapper, Runner, function_tool, set_tracing_disabled
from agents.extensions.models.litellm_model import LitellmModel
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

import race_data
from context_panel import AgentContexts, PanelHooks, add_context_panel

# WIKIMEDIA_USERNAME and WIKIMEDIA_PASSWORD come from the .env file next to this one.
load_dotenv(Path(__file__).parent / ".env")

# Traces upload to OpenAI by default, which needs an OpenAI key. We're on Gemini.
set_tracing_disabled(True)

# LiteLLM routes the call to Gemini. api_key is unused: Vertex AI uses your gcloud credentials.
MODEL = LitellmModel(model="vertex_ai/gemini-3.5-flash", api_key="unused")
# Researchers only read and take notes: the cheaper model is enough.
RESEARCHER_MODEL = LitellmModel(model="vertex_ai/gemini-3.5-flash-lite", api_key="unused")
# A stalled model call would hang the page: give up after 90 s, and retry twice.
SETTINGS = ModelSettings(extra_args={"vertex_location": "global", "timeout": 90, "num_retries": 2})

# The Lead gets this many researchers in all. Prompts ask for restraint; code enforces it.
MAX_RESEARCHERS = 6


@dataclass
class Research:
    """One run's state, shared by every agent and tool in it. The model never sees it."""

    hooks: PanelHooks
    researchers: int = 0  # how many researchers have started, to number them
    findings: list[str] = field(default_factory=list)
    race_keys: list[str] = field(default_factory=list)
    researcher_limit: int = 4


# --- Tools ---


@function_tool
def get_race_data(session_key: str, kind: str, driver: str = "") -> str:
    """Read historical race observations from a bundled OpenF1 snapshot.

    Args:
        session_key: 9558 for 2024 British GP, 9590 for 2024 Italian GP, or 9636 for 2024 Sao Paulo GP.
        kind: sessions, drivers, laps, pit, stints, race_control, position, intervals, weather, or results (Jolpica).
        driver: Driver surname, three-letter abbreviation, or number. Required for laps.
    """
    if kind in {"laps", "position", "intervals"} and not driver:
        return json.dumps({"error": f"Supply one driver when requesting {kind}."})
    try:
        return json.dumps(race_data.get_data(session_key, kind, driver))
    except (OSError, ValueError) as exc:
        return json.dumps({"error": f"Data unavailable: {exc}"})


@function_tool
def compare_lap_pace(session_key: str, driver_a: str, driver_b: str, start_lap: int, end_lap: int) -> str:
    """Calculate a paired lap pace comparison in a race window.

    Args:
        session_key: 9558, 9590, or 9636.
        driver_a: First driver surname, three-letter code, or number, e.g. HAM.
        driver_b: Second driver surname, three-letter code, or number, e.g. VER.
        start_lap: First lap to include, e.g. 20.
        end_lap: Last lap to include, e.g. 25.
    """
    try:
        return json.dumps(race_data.compare_pace(session_key, driver_a, driver_b, start_lap, end_lap))
    except (OSError, ValueError) as exc:
        return json.dumps({"error": f"Comparison unavailable: {exc}"})


# --- Independent researchers ---

researcher = Agent(
    name="Researcher",
    instructions="""\
Investigate your assigned F1 question using get_race_data and compare_lap_pace. Use only tool results.
Cite each factual finding with the exact source URL provided by the tool and include relevant
lap numbers and values. Report missing information and do not infer causation or invent gaps.
Use compare_lap_pace for relevant windows, including sample size and caveats. Check race control and
weather where relevant. Investigate rival explanations and identify counter-evidence and unresolved gaps.
OpenF1 and Jolpica are unofficial, not official sources. Do not assert counterfactual outcomes.""",
    model=RESEARCHER_MODEL,
    model_settings=SETTINGS,
    tools=[get_race_data, compare_lap_pace],
)


async def run_research(state: Research, task: str, session_key: str) -> str:
    if state.researchers >= state.researcher_limit:
        return "No researchers left. Reply DONE."
    if session_key not in race_data.RACES:
        return "Unknown race session. Available keys: 9558, 9590, 9636."
    state.researchers += 1
    state.race_keys.append(session_key)
    agent = researcher.clone(name=f"Researcher {state.researchers}")
    prompt = f"Task: {task}\nRace session key: {session_key}"
    result = await Runner.run(agent, prompt, context=state, hooks=state.hooks, max_turns=12)
    state.findings.append(f"{task}\n\n{result.final_output}")
    return str(result.final_output)


@function_tool
async def research(ctx: RunContextWrapper[Research], task: str, session_key: str) -> str:
    """Send a fresh researcher to investigate a focused task.

    Args:
        task: Specific hypothesis, evidence gap, or rival explanation to investigate.
        session_key: Race identifier: 9558, 9590, or 9636.
    """
    return await run_research(ctx.context, task, session_key)


# --- The lead: plans, fans out to researchers, and checks for gaps ---

lead = Agent(
    name="Lead",
    instructions="""\
You lead an F1 research team using bundled snapshots: 2024 British GP (9558), 2024 Italian GP
(9590), 2024 Sao Paulo GP (9636). If the question lacks a race or is too vague, ask one
clarifying question. If a requested race is unavailable, explain the available races.
Otherwise call research in parallel in one turn for 3 independent, question-specific tasks.
Investigate plausible explanations and rival explanations, including timing, pace, and race context.
Tell each researcher the relevant race and driver names. Then say DONE; a separate review follows.
Do not infer that a pit stop caused a result or claim an alternative strategy would win.""",
    model=MODEL,
    model_settings=SETTINGS,
    tools=[research],
)

reviewer = Agent(
    name="Lead Review",
    instructions="""Review the question and initial findings skeptically. Identify the most consequential
unresolved gap, counter-explanation, conflict, or weak inference. Call research at least once to investigate it,
passing the correct race key and driver names. Use a second follow-up if necessary and available. If the data
cannot resolve a point, say so. End with a short synthesis of supported conclusions and uncertainties.
Do not merely repeat a lookup already completed. Investigate whether evidence supports a causal claim, or
look for relevant race context and competing explanations. Never infer a specific cause from timing alone.""",
    model=MODEL,
    model_settings=SETTINGS,
    tools=[research],
)

# --- The writer: one call, after the research ends ---

writer = Agent(
    name="Writer",
    instructions="""\
Write a short report in markdown that answers the question, using only the findings you're given.

- Answer directly, explain relevant evidence and competing explanations, and state limitations.
- Be concise; don't repeat the same numbers in multiple sections.
- Cite factual claims with markdown links from findings; don't call unofficial sources official.
- Never state a cause, driver intention, tire temperature, track condition, or crew advantage as fact unless
  a source directly measures or reports it. Frame plausible explanations as hypotheses, or omit them.
- A median of paired lap differences is NOT the difference between the drivers' individual median lap times.
  Include the actual laps and sample size. Do not characterize mixed-compound windows as a single stint.
- If the findings don't answer part of the question, say so.
- Write plain, specific sentences. Don't claim more significance than the findings do: no
  "profoundly", "pivotal", "paving the way", or "it is worth noting".""",
    model=MODEL,
    model_settings=SETTINGS,
)

auditor = Agent(
    name="Evidence Check",
    instructions="""Audit the proposed report against the supplied tool-based findings. Return the complete corrected
report, not a critique. Remove or qualify claims about causes, tire temperature, weather, team decisions, track
position and counterfactuals unless directly supported. Check all arithmetic, lap windows and tire compounds.
The median of paired differences is not the difference of individual medians. State the sample and laps for pace
comparisons, avoid treating a mixed-compound interval as one stint, and retain clickable markdown citations.
If uncertain, omit a claim or state the limitation. Do not introduce new unsupported information.""",
    model=MODEL,
    model_settings=SETTINGS,
)


async def deep_research(question: str, hooks: PanelHooks) -> str:
    research_run = Research(hooks=hooks)

    # 1. Research: plan, fan out, check for gaps
    prompt = f"Question: {question}"
    lead_result = await Runner.run(lead, prompt, context=research_run, hooks=hooks, max_turns=12)
    if not research_run.findings:
        return str(lead_result.final_output)

    research_run.researcher_limit = MAX_RESEARCHERS
    initial_count = research_run.researchers
    initial_findings = "\n\n---\n\n".join(research_run.findings)
    review = await Runner.run(reviewer, f"Question: {question}\n\nInitial findings:\n{initial_findings}",
                              context=research_run, hooks=hooks, max_turns=8)
    if research_run.researchers == initial_count and research_run.race_keys:
        await run_research(research_run,
            f"For the question {question}, independently test the most important rival explanation or evidence gap. "
            f"Initial findings: {initial_findings}", research_run.race_keys[0])

    # Write using both the initial and follow-up evidence.
    findings = "\n\n---\n\n".join(research_run.findings)
    report = await Runner.run(writer, f"Question: {question}\n\nFindings:\n\n{findings}\n\nReview:\n{review.final_output}", hooks=hooks, max_turns=4)
    checked = await Runner.run(auditor, f"Question: {question}\n\nEvidence:\n{findings}\n\nProposed report:\n{report.final_output}", hooks=hooks, max_turns=3)
    return str(checked.final_output)


# --- FastAPI App ---

HERE = Path(__file__).parent

# run_id -> every agent's context, in order. In-memory, single process. The context panel reads it.
sessions: dict[str, AgentContexts] = {}

app = FastAPI()
add_context_panel(app, sessions)


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


@app.post("/chat")
async def chat(body: ChatRequest):
    """Return the report and the agent tool calls for a research question."""
    session_id = body.session_id or str(uuid.uuid4())
    contexts = AgentContexts()
    sessions[session_id] = contexts
    hooks = PanelHooks(contexts, lambda event: None)
    report = await asyncio.wait_for(deep_research(body.message, hooks), timeout=270)
    calls = []
    for event in contexts.events:
        message = event.get("message", {})
        for call in message.get("tool_calls") or []:
            calls.append({**call, "agent": event.get("agent")})
    return {"response": report, "session_id": session_id, "tool_calls": calls}


@app.get("/")
def index():
    # no-cache: browsers otherwise keep serving an old page after a redeploy
    return FileResponse(HERE / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/run")
async def run(question: str):
    """Research one question and stream what happens as Server-Sent Events."""
    run_id = str(uuid.uuid4())
    sessions[run_id] = AgentContexts()
    queue: asyncio.Queue = asyncio.Queue()
    hooks = PanelHooks(sessions[run_id], queue.put_nowait)

    async def work():
        try:
            report = await asyncio.wait_for(deep_research(question, hooks), timeout=270)
            queue.put_nowait({"type": "done", "markdown": report})
        except Exception as e:
            # Auth, quota, a model that won't stop: show it on the page, not as a dropped stream.
            queue.put_nowait({"type": "error", "message": f"{type(e).__name__}: {str(e)[:500]}"})

    task = asyncio.create_task(work())

    async def events():
        try:
            yield f"data: {json.dumps({'type': 'start', 'run_id': run_id})}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=10)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                yield f"data: {json.dumps(event, default=str)}\n\n"
                if event["type"] in ("done", "error"):
                    break
        finally:
            task.cancel()  # the page closed the stream: stop spending tokens

    return StreamingResponse(events(), media_type="text/event-stream")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
