#!/usr/bin/env python3
"""
Web chat server — coordinator orchestration entry (chat-style UI).

Independent of model_server.py (:8000). This service (:8001) only PROXIES the
upstream LLM server; it never starts/stops/modifies it.

- GET  /                     -> static/index.html
- GET  /static/*             -> scripts/static/
- GET  /api/health           -> upstream /health proxy
- POST /api/orchestrate      -> SSE stream running the pipeline semantics
                                coordinator -> designer(batches) -> manufacturing -> delivery -> safety -> mechanism -> ranker
- GET  /api/sessions         -> chat session list (outputs/chat/)
- GET  /api/sessions/<id>    -> one session's history

Agent traffic routing: every model call goes through llm_client.chat()
(same as the CLI pipeline), so the web coordinator honors
scripts/llm_endpoints.json per-agent routing — hosted endpoints get their
Authorization header and model name from the endpoint config, local endpoints
keep the extra "agent" field that switches LoRA adapters. call_agent() is a
ONE-SHOT call (no token streaming from the model server): the SSE stream toward
the browser carries whole-step events, and the blocking llm_client.chat()
synchronous request runs in a worker thread so the event loop stays responsive.
LLM_BASE (env NANO_BIO_LLM_BASE, default http://localhost:8000) is kept ONLY
for the /api/health upstream proxy.

Iron rules (project docs): every agent output is saved RAW — no cleaning, no
truncation beyond the pipeline's own prompt/input conventions, no fallback
data. Per-request raw outputs land in outputs/run_<TS>/ (output_utils.run_dir).
"""

import os, sys, json, time, asyncio, re, uuid
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
from output_utils import run_dir, OUTPUT_ROOT  # noqa: E402
import llm_client  # noqa: E402
import output_schema  # noqa: E402
import pipeline_prompts  # noqa: E402
from pipeline_prompts import (  # noqa: E402
    batch_focus, designer_format_block_for, split_chunks, build_expert_prompt,
    coordinator_prompt, DIRECT_ANSWER_TEMPLATE, VALID_ANSWER_AGENTS,
    designer_prompt, build_ranker_prompt, DEFAULT_COORDINATOR_GOAL, PROMPT_CHAR_CAP,
)

LLM_BASE = os.environ.get("NANO_BIO_LLM_BASE", "http://localhost:8000").rstrip("/")
CONFIG_PATH = BASE_DIR / "pipeline_config.json"
STATIC_DIR = BASE_DIR / "static"
CHAT_DIR = OUTPUT_ROOT / "chat"
GEN_TIMEOUT = 2400  # long generations, same as the pipeline

# ---------------------------------------------------------------------------
# Pipeline semantics — prompt text and helpers come from pipeline_prompts.py
# (shared with task_100_materials.py). We do NOT import task_100_materials
# because importing that module executes its module-level run_dir(TS) and
# would create a spurious empty outputs/run_<TS>/ folder on every server start.
# ---------------------------------------------------------------------------

def parse_plan(coordinator_raw: str) -> dict:
    """Best-effort extraction of the coordinator plan JSON; {} when unparseable
    (callers then keep the default pipeline behavior)."""
    start, end = coordinator_raw.find("{"), coordinator_raw.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        obj = json.loads(coordinator_raw[start:end + 1])
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Nano-Bio Evaluator — coordinator Chat")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

orch_lock = asyncio.Lock()

SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def save_raw(out_dir: Path, name: str, content: str) -> None:
    """Save agent output RAW (zero modification)."""
    with open(out_dir / name, "w", encoding="utf-8") as f:
        f.write(content)


async def call_agent(client: httpx.AsyncClient, agent: str, prompt: str,
                     max_tokens: int, temp: float) -> str:
    """Single upstream call through llm_client.chat() so the web coordinator
    honors llm_endpoints.json per-agent routing exactly like the CLI pipeline
    (hosted endpoints get auth header + model name from the endpoint config;
    local endpoints keep the "agent" field that switches LoRA adapters).

    The upstream request is a ONE-SHOT call (no token streaming); the blocking
    synchronous llm_client.chat() runs in a worker thread so the SSE event
    loop stays responsive. llm_client's retry policy applies, with
    retry_on_timeout=False because on a local ReadTimeout the server is likely
    still generating this very request. The `client` argument is accepted for
    call-site compatibility — the request itself is issued inside llm_client.
    A non-OK upstream result raises RuntimeError (feeds the SSE error event)."""
    text = await asyncio.to_thread(
        llm_client.chat, agent, prompt[:PROMPT_CHAR_CAP],
        max_tokens=max_tokens, temperature=temp, timeout=GEN_TIMEOUT,
        retries=3, retry_on_timeout=False,
    )
    if text.startswith("ERROR"):
        raise RuntimeError(f"upstream {agent}: {text}")
    return text


def load_cfg() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def session_path(session_id: str) -> Path:
    return CHAT_DIR / f"{session_id}.json"


def load_session(session_id: str) -> dict:
    p = session_path(session_id)
    if p.is_file():
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"session_id": session_id, "created": int(time.time()), "messages": []}


def save_session(sess: dict) -> None:
    CHAT_DIR.mkdir(parents=True, exist_ok=True)
    with open(session_path(sess["session_id"]), "w", encoding="utf-8") as f:
        json.dump(sess, f, ensure_ascii=False, indent=2)


async def orchestrate_stream(message: str, session_id: str):
    """SSE generator: run the full pipeline semantics, yielding one JSON
    event per step. Raw outputs are saved per-step BEFORE the event is
    yielded, so a mid-stream failure still leaves completed raw files."""
    ts = int(time.time())
    out = run_dir(ts)
    run_dir_str = str(out)
    sess = load_session(session_id)
    sess["messages"].append({"role": "user", "content": message, "ts": ts})
    sess["run_dir"] = run_dir_str
    # Full event sequence is kept in the session so the frontend can replay
    # the whole orchestration (cards + agent contents) when reopened.
    events = sess.setdefault("events", [])

    def emit(ev: dict) -> str:
        events.append(ev)
        return sse(ev)

    async def finish(status: str, assistant_content: str):
        sess["messages"].append({
            "role": "assistant", "content": assistant_content,
            "run_dir": run_dir_str, "status": status, "ts": int(time.time()),
        })
        save_session(sess)

    try:
        cfg = load_cfg()
        is_current = cfg.get("schema") == "current"
        async with httpx.AsyncClient() as client:
            # ---- Step 1: coordinator plan ----
            # (prompt built by pipeline_prompts.coordinator_prompt; the user
            # request is appended by concatenation — the template contains
            # literal JSON braces and must NOT go through str.format)
            coordinator_raw = await call_agent(
                client, "coordinator",
                coordinator_prompt(cfg.get("coordinator_goal", DEFAULT_COORDINATOR_GOAL),
                                   needs_pipeline=True) + "\n\nUser request: " + message,
                cfg["coordinator"]["max_tokens"], cfg["coordinator"]["temperature"])
            save_raw(out, f"task100_coordinator_{ts}.txt", coordinator_raw)
            yield emit({"type": "plan", "content": coordinator_raw})

            # ---- Intent routing: honor coordinator's needs_pipeline decision ----
            plan_obj = parse_plan(coordinator_raw)
            needs_pipeline = bool(plan_obj.get("needs_pipeline", True))

            if not needs_pipeline:
                wanted = plan_obj.get("agents_needed") or []
                answer_agent = next(
                    (a for a in wanted if a in VALID_ANSWER_AGENTS), "ranker")
                yield emit({"type": "agent_start", "agent": answer_agent,
                            "batch": 1})
                answer = await call_agent(
                    client, answer_agent,
                    DIRECT_ANSWER_TEMPLATE.format(message=message),
                    4096, 0.3)
                save_raw(out, f"chat_{answer_agent}_{ts}.txt", answer)
                yield emit({"type": "direct_answer",
                            "agent": answer_agent, "content": answer})
                await finish("done", answer)
                yield emit({"type": "done", "run_dir": run_dir_str})
                return

            # ---- Step 2: designer batches ----
            batches = cfg["designer"]["batches"]
            total_batches = len(batches)
            designer_chunks = []
            designed_names = []  # cross-batch anti-duplication (matches CLI pipeline)
            for b in batches:
                n = b["batch_id"]
                fmt_block = output_schema.designer_format_block_current() if is_current else designer_format_block_for(b)
                exclusion = ""
                if designed_names:
                    shown = designed_names[-60:]
                    exclusion = ("\n\nAlready designed in previous batches — do NOT repeat these "
                                 "candidates or near-variants of them:\n" + ", ".join(shown))
                yield emit({"type": "agent_start", "agent": "designer", "batch": n})
                chunk = await call_agent(
                    client, "designer",
                    designer_prompt(b["count"], n, total_batches,
                                    batch_focus(b), fmt_block, exclusion=exclusion),
                    b["max_tokens"], cfg["designer"]["temperature"])
                save_raw(out, f"task100_designer_{ts}_part{n}.txt", chunk)
                designer_chunks.append(chunk)
                for line in chunk.split("\n"):
                    if "|" in line and "Material_Name" not in line:
                        designed_names.append(line.split("|")[0].strip())
                yield emit({"type": "agent_done", "agent": "designer", "batch": n,
                            "chars": len(chunk), "content": chunk})

            designer_raw = "\n".join(designer_chunks)
            # Same input hygiene as the CLI: designer chatter lines (no "|") are
            # kept in the raw files but never fed to the expert agents.
            mat_lines = [l for l in designer_raw.split("\n") if l.strip() and "|" in l]

            # ---- Steps 3-6: manufacturing / delivery / safety / mechanism (chunked per config) ----
            raws = {}
            for agent in ("manufacturing", "delivery", "safety", "mechanism"):
                chunks_out = []
                for n, part in enumerate(
                        split_chunks(mat_lines, cfg[agent]["chunks"]), start=1):
                    if not part:
                        continue
                    yield emit({"type": "agent_start", "agent": agent, "batch": n})
                    chunk = await call_agent(
                        client, agent,
                        build_expert_prompt(agent, "\n".join(part), is_current),
                        cfg[agent]["max_tokens"], cfg[agent]["temperature"])
                    save_raw(out, f"task100_{agent}_{ts}_part{n}.txt", chunk)
                    chunks_out.append(chunk)
                    yield emit({"type": "agent_done", "agent": agent,
                                "batch": n, "chars": len(chunk),
                                "content": chunk})
                raws[agent] = "\n".join(chunks_out)

            # ---- Step 7: ranker summary ----
            yield emit({"type": "agent_start", "agent": "ranker", "batch": 1})
            trunc = cfg["ranker"]["input_truncation"]
            ranker_raw = await call_agent(
                client, "ranker",
                build_ranker_prompt(designer_raw, raws["delivery"], raws["mechanism"],
                                    is_current, trunc),
                cfg["ranker"]["max_tokens"], cfg["ranker"]["temperature"])
            save_raw(out, f"task100_ranker_{ts}.txt", ranker_raw)
            yield emit({"type": "summary", "content": ranker_raw})

        await finish("done", ranker_raw)
        yield emit({"type": "done", "run_dir": run_dir_str})
    except Exception as e:
        # Graceful error: report and end the stream; completed raw files stay.
        try:
            await finish("error", f"ERROR: {e}")
        except Exception:
            pass
        yield sse({"type": "error", "message": str(e), "run_dir": run_dir_str})


@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/health")
async def api_health():
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{LLM_BASE}/health")
        return {"llm_base": LLM_BASE, "status": "ok" if r.status_code == 200 else "error",
                "upstream_status": r.status_code}
    except Exception as e:
        return {"llm_base": LLM_BASE, "status": "unreachable", "error": str(e)}


@app.post("/api/orchestrate")
async def api_orchestrate(payload: dict):
    message = (payload.get("message") or "").strip()
    if not message:
        return JSONResponse({"error": "message is required"}, status_code=400)
    session_id = payload.get("session_id") or uuid.uuid4().hex[:16]
    if not SESSION_ID_RE.match(session_id):
        return JSONResponse({"error": "invalid session_id"}, status_code=400)

    if orch_lock.locked():
        async def busy():
            yield sse({"type": "error",
                       "message": "An orchestration task is already in progress; please wait for it to finish before submitting a new request."})
        return StreamingResponse(busy(), media_type="text/event-stream",
                                 headers={"X-Session-Id": session_id})

    async def locked_stream():
        async with orch_lock:
            async for chunk in orchestrate_stream(message, session_id):
                yield chunk

    return StreamingResponse(locked_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Session-Id": session_id})


@app.get("/api/sessions")
async def api_sessions():
    CHAT_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    for p in sorted(CHAT_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime,
                    reverse=True):
        try:
            with open(p, "r", encoding="utf-8") as f:
                s = json.load(f)
            first_user = next((m for m in s.get("messages", [])
                               if m.get("role") == "user"), None)
            items.append({
                "session_id": s.get("session_id", p.stem),
                "created": s.get("created"),
                "run_dir": s.get("run_dir"),
                "title": (first_user["content"][:40] if first_user else "(empty session)"),
                "message_count": len(s.get("messages", [])),
            })
        except Exception:
            continue
    return {"sessions": items}


@app.get("/api/sessions/{session_id}")
async def api_session(session_id: str):
    if not SESSION_ID_RE.match(session_id):
        return JSONResponse({"error": "invalid session_id"}, status_code=400)
    p = session_path(session_id)
    if not p.is_file():
        return JSONResponse({"error": "session not found"}, status_code=404)
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1",
                port=int(os.environ.get("NANO_BIO_WEB_PORT", "8001")),
                log_level="info")
