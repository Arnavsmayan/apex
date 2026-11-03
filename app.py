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
    findings: list[str] = field(default_factory=list)  # what each researcher reported, for the Writer


# --- Tools ---


@function_tool
def get_race_data(session_key: str, kind: str, driver: str = "") -> str:
    """Read historical race observations from a bundled OpenF1 snapshot.

    Args:
        session_key: 9558 for 2024 British GP, 9590 for 2024 Italian GP, or 9636 for 2024 Sao Paulo GP.
        kind: One of sessions, drivers, laps, pit, stints, race_control, results. Results come from Jolpica.
        driver: Driver surname, three-letter abbreviation, or number. Required for laps.
    """
    if kind == "laps" and not driver:
        return json.dumps({"error": "Supply one driver when requesting laps."})
    try:
        return json.dumps(race_data.get_data(session_key, kind, driver))
    except (OSError, ValueError) as exc:
        return json.dumps({"error": f"Data unavailable: {exc}"})


# --- The researcher: one task, by walking Wikipedia's links ---

researcher = Agent(
    name="Researcher",
    instructions="""\
Investigate your assigned F1 question using get_race_data. Use only returned records.
Cite each factual finding with the exact source URL provided by the tool and include relevant
lap numbers and values. Report missing information and do not infer causation or invent gaps.
When comparing pace, account for pit laps, safety cars, weather, and missing observations.
Call the tool for each driver you discuss. Report limited evidence when it is inconclusive.""",
    model=RESEARCHER_MODEL,
    model_settings=SETTINGS,
    tools=[get_race_data],
)


@function_tool
async def research(ctx: RunContextWrapper[Research], task: str, session_key: str) -> str:
    """Send an independent researcher to investigate one task in a bundled race.

    Args:
        task: One specific thing to find out.
        session_key: Race identifier: 9558, 9590, or 9636.
    """
    if ctx.context.researchers >= MAX_RESEARCHERS:
        return "No researchers left. Reply DONE."
    # What researcher.as_tool() does: run the researcher in a fresh context and return its answer.
    # Written out so each run gets a numbered copy, and its own column in the context panel.
    ctx.context.researchers += 1
    agent = researcher.clone(name=f"Researcher {ctx.context.researchers}")
    prompt = f"Task: {task}\nRace session key: {session_key}"
    result = await Runner.run(agent, prompt, context=ctx.context, hooks=ctx.context.hooks, max_turns=12)
    ctx.context.findings.append(f"{task}\n\n{result.final_output}")
    return str(result.final_output)


# --- The lead: plans, fans out to researchers, and checks for gaps ---

lead = Agent(
    name="Lead",
    instructions="""\
You lead an F1 research team using bundled snapshots: 2024 British GP (9558), 2024 Italian GP
(9590), 2024 Sao Paulo GP (9636). If the question lacks a race or is too vague, ask one
clarifying question. If a requested race is unavailable, explain the available races.
Otherwise call research in parallel in one turn for 3 independent tasks: pit stops and tires,
lap pace, and race context and results. Tell each researcher the relevant race and driver names.
Review findings and call research again for any important gap, at most twice. Then say DONE.
Do not infer that a pit stop caused a result or claim an alternative strategy would win.""",
    model=MODEL,
    model_settings=SETTINGS,
    tools=[research],
)

# --- The writer: one call, after the research ends ---

writer = Agent(
    name="Writer",
    instructions="""\
Write a short report in markdown that answers the question, using only the findings you're given.

- Start with a one-paragraph answer, then a section per part of the question.
- Keep the links: end every sentence that states a fact with the link from its finding.
- If the findings don't answer part of the question, say so.
- Write plain, specific sentences. Don't claim more significance than the findings do: no
  "profoundly", "pivotal", "paving the way", or "it is worth noting".""",
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

    # 2. Write: one call, outside the loop. The Writer sees only the question and the findings.
    findings = "\n\n---\n\n".join(research_run.findings)
    report = await Runner.run(writer, f"Question: {question}\n\nFindings:\n\n{findings}", hooks=hooks)
    return str(report.final_output)


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
                event = await queue.get()
                yield f"data: {json.dumps(event, default=str)}\n\n"
                if event["type"] in ("done", "error"):
                    break
        finally:
            task.cancel()  # the page closed the stream: stop spending tokens

    return StreamingResponse(events(), media_type="text/event-stream")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
