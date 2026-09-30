#!/usr/bin/env python3
"""
Task: 100 top-scoring materials, predict intervention, mechanism, category.
Auto-starts server, waits for ready, runs pipeline, cleans up.
ALL agent outputs preserved RAW.

Batch quotas and per-step parameters are externalized to pipeline_config.json
(--config to override). The default config is the current schema (AD100): the
designer emits the uniform 13-field current contract from
output_schema.designer_format_block_current, with no modality or element quotas —
the legacy-modality per-batch format block is only used when a config sets
"schema" to something else. The pre-Phase-4 nano-only config was deleted (its
purpose was reproducing the element-steered baseline, which no longer exists).

Pipeline order: coordinator -> designer -> manufacturing -> delivery -> safety -> mechanism -> ranker.
manufacturing/delivery/safety/mechanism append a JSON subscore tail per material line (raw output
preserved verbatim); scripts/extract_subscores.py mechanically collects them
into subscores_<TS>.json for the deterministic scoring engine (scoring_engine.py).
"""

import os, sys, json, time, subprocess, argparse
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from pathlib import Path
import httpx

HEALTH = "http://localhost:8000/health"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import llm_client
from output_utils import run_dir
import output_schema
import pipeline_prompts
from pipeline_prompts import (
    batch_focus, designer_format_block_for, split_chunks, build_expert_prompt,
    coordinator_prompt, designer_prompt, build_ranker_prompt, DEFAULT_COORDINATOR_GOAL,
    PROMPT_CHAR_CAP,
)

TS = int(time.time())
OUTPUT = run_dir(TS)  # Per-run folder: outputs/run_<TS>/ — every test run gets its own folder

DEFAULT_CONFIG = Path(__file__).parent / "pipeline_config.json"

def load_config(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def json_tail_fraction(text: str) -> float:
    """Fraction of non-empty lines containing a JSON-ish {...} tail."""
    lines = [l for l in text.split("\n") if l.strip()]
    if not lines:
        return 0.0
    return sum(1 for l in lines if "{" in l and "}" in l) / len(lines)


FORMAT_RETRY_SUFFIX = """

FORMAT CORRECTION: your previous answer ignored the required output format. Do NOT write prose, headings, criteria, or explanations. Output ONLY one pipe-separated line per material, each ending with a semicolon and its JSON subscore object. Nothing else."""


def call_expert(agent: str, prompt: str, save_prefix: str, n: int, max_tokens: int, temp: float,
                part_lines: "list | None" = None, is_current: bool = False):
    """Call an expert agent with two escalation levels for prose collapse:
      1. retry once with a sterner format correction AT HIGHER TEMPERATURE
         (low base temps make failures nearly deterministic);
      2. if the retry also fails and part_lines is available, SPLIT the chunk
         into halves and score each half separately (pathological inputs —
         e.g. live-biologics clusters OOD for the adapters — poison the whole
         chunk; halving isolates them).
    All raw outputs are saved (iron rule); the best result is used downstream."""
    chunk = call(agent, prompt, max_tokens=max_tokens, temp=temp)
    save(f"{save_prefix}_part{n}.txt", chunk)
    frac = json_tail_fraction(chunk)
    if frac >= 0.8:
        return chunk, frac, False
    retry_temp = min(0.9, temp + 0.4)
    print(f"  {agent} chunk {n}: JSON-tail fraction {frac:.0%} < 80% — retrying with format correction (temp {retry_temp})")
    retry = call(agent, prompt + FORMAT_RETRY_SUFFIX, max_tokens=max_tokens, temp=retry_temp)
    save(f"{save_prefix}_part{n}_retry.txt", retry)
    frac2 = json_tail_fraction(retry)
    print(f"  {agent} chunk {n} retry: JSON-tail fraction {frac2:.0%}")
    best, best_frac = (retry, frac2) if frac2 > frac else (chunk, frac)
    if best_frac >= 0.8 or not part_lines or len(part_lines) < 4:
        return best, best_frac, True
    # Level 2: split rescue — halves saved as part{n}a / part{n}b
    print(f"  {agent} chunk {n}: still {best_frac:.0%} — splitting into halves")
    halves = split_chunks(part_lines, 2)
    outs, fracs = [], []
    for suffix, half in zip(("a", "b"), halves):
        if not half:
            continue
        hp = build_expert_prompt(agent, "\n".join(half), is_current)
        h = call(agent, hp, max_tokens=max_tokens, temp=retry_temp)
        save(f"{save_prefix}_part{n}{suffix}.txt", h)
        hf = json_tail_fraction(h)
        print(f"  {agent} chunk {n}{suffix}: JSON-tail fraction {hf:.0%}")
        outs.append(h)
        fracs.append(hf)
    joined = "\n".join(outs)
    jfrac = sum(fracs) / len(fracs) if fracs else 0.0
    return (joined if jfrac > best_frac else best), max(jfrac, best_frac), True


def start_server():
    """Start model_server.py and wait until it responds.

    If a healthy server is already running, reuse it and return None
    (stop_server(None) is a no-op, so a reused server is left alive).
    """
    try:
        r = httpx.get(HEALTH, timeout=3)
        if r.status_code == 200:
            print("Reusing already-running server.")
            return None
    except:
        pass

    print("Starting server...")
    server_script = Path(__file__).parent / "model_server.py"
    proc = subprocess.Popen(
        [sys.executable, str(server_script)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    print(f"  Server PID: {proc.pid}")

    # Wait for server to be ready (health check responds)
    for i in range(60):  # Up to 5 minutes
        try:
            r = httpx.get(HEALTH, timeout=3)
            if r.status_code == 200:
                print(f"  Server ready after {i*5}s")
                return proc
        except:
            pass
        time.sleep(5)
        if i % 6 == 0:
            print(f"  Waiting... ({i*5}s)")

    proc.kill()
    raise RuntimeError("Server failed to start within 5 minutes")


def stop_server(proc):
    """Kill the server process (None = reused server, left alive)."""
    if proc:
        proc.kill()
        proc.wait()
        print("Server stopped.")


BASE_MODE = False  # --base: route every step to the unfine-tuned base model


def call(agent: str, prompt: str, max_tokens: int = 10240, temp: float = 0.3, timeout: int = 2400) -> str:
    global server_proc
    if BASE_MODE:
        agent = "base"  # model_server disables all LoRA adapters for this channel

    local = llm_client.is_local_endpoint(llm_client.resolve_endpoint(agent))

    if local:
        # Check server health before attempting. Health stays responsive during
        # generation (fixed server), so a failure here means the server is
        # genuinely dead.
        for health_check in range(3):
            try:
                r = httpx.get(HEALTH, timeout=5)
                if r.status_code == 200:
                    break
            except:
                pass
            print(f"  Server health check failed (attempt {health_check+1}/3)")
            time.sleep(5)
        else:
            # Server dead — restart it
            print("  Server appears dead, restarting...")
            try:
                server_proc.kill()
                server_proc.wait()
            except:
                pass
            server_proc = start_server()

    # retry_on_timeout=False: on a local ReadTimeout the server is likely
    # still generating this very request, and a retry would queue a duplicate
    # long generation that cannot finish within its own timeout window.
    # The cap only guards against pathological prompt sizes; build_expert_prompt
    # already clips the records body so the format footer always survives.
    return llm_client.chat(agent, prompt[:PROMPT_CHAR_CAP], max_tokens=max_tokens,
                           temperature=temp, timeout=timeout, retries=3,
                           retry_on_timeout=False)


def save(name, content):
    p = OUTPUT / name
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  -> {p}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="100-material pipeline (config-driven batches)")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG),
                        help="pipeline config JSON (default: scripts/pipeline_config.json)")
    parser.add_argument("--base", action="store_true",
                        help="run the whole pipeline with the UNFINE-TUNED base model "
                             "(agent=base channel, all LoRA adapters disabled) — control experiment")
    parser.add_argument("--redo-batch", nargs=2, metavar=("TS", "BATCH_ID"), default=None,
                        help="redo ONE designer batch of run TS (saved as task100_designer_<TS>_redo_part<N>.txt), "
                             "then re-run all experts on the rebuilt list. Ranking prefers redo over the original batch.")
    parser.add_argument("--note", default="",
                        help="extra instruction appended to the redo batch focus (e.g. stronger constraints)")
    parser.add_argument("--experts-only", metavar="TS", default=None,
                        help="re-run ONLY manufacturing/delivery/safety/mechanism against the designer output of run TS "
                             "(files saved as task100_<agent>_<TS>_redo_part*.txt in that run dir; "
                             "extract_subscores lets redo scores override)")
    args = parser.parse_args()
    CFG = load_config(Path(args.config))
    if args.base:
        BASE_MODE = True
        print("** BASE-MODEL MODE: all steps use the unfine-tuned base model (no LoRA) **")

    if args.redo_batch:
        from output_utils import find_run_dir
        TS = int(args.redo_batch[0])
        batch_id = int(args.redo_batch[1])
        OUTPUT = find_run_dir(str(TS))
        batch_cfg = next(b for b in CFG["designer"]["batches"] if b["batch_id"] == batch_id)
        total_batches = len(CFG["designer"]["batches"])
        is_current = CFG.get("schema") == "current"
        server_proc = start_server()
        try:
            fmt_block = output_schema.designer_format_block_current() if is_current else designer_format_block_for(batch_cfg)
            chunk = call("designer", designer_prompt(
                batch_cfg["count"], batch_id, total_batches,
                batch_focus(batch_cfg), fmt_block, exclusion=args.note),
                max_tokens=batch_cfg["max_tokens"], temp=CFG["designer"]["temperature"])
            save(f"task100_designer_{TS}_redo_part{batch_id}.txt", chunk)
            print(f"  designer batch {batch_id} redo done ({len(chunk)} chars)")
            time.sleep(3)

            # Rebuild the candidate list: every batch EXCEPT the old one, plus the redo
            mat_lines = []
            for f in sorted(OUTPUT.glob(f"task100_designer_{TS}_part*.txt")):
                if f.name == f"task100_designer_{TS}_part{batch_id}.txt":
                    continue
                mat_lines += [l for l in f.read_text(encoding="utf-8").split("\n") if l.strip() and "|" in l]
            mat_lines += [l for l in chunk.split("\n") if l.strip() and "|" in l]

            redo_idx = 1
            while list(OUTPUT.glob(f"task100_manufacturing_{TS}_redo{'' if redo_idx == 1 else redo_idx}_part1.txt")):
                redo_idx += 1
            redo_tag = "" if redo_idx == 1 else str(redo_idx)
            print(f"  rebuilt list: {len(mat_lines)} lines; experts redo (suffix redo{redo_tag})")
            for agent in ("manufacturing", "delivery", "safety", "mechanism"):
                for n, part in enumerate(split_chunks(mat_lines, CFG[agent]["chunks"]), start=1):
                    if not part:
                        continue
                    prompt = build_expert_prompt(agent, "\n".join(part), is_current)
                    chunk2, jfrac, retried = call_expert(
                        agent, prompt, f"task100_{agent}_{TS}_redo{redo_tag}", n,
                        CFG[agent]["max_tokens"], CFG[agent]["temperature"],
                        part_lines=part, is_current=is_current)
                    print(f"  {agent} redo chunk {n} done (json={jfrac:.0%}{' after retry' if retried else ''})")
                    time.sleep(3)
        finally:
            stop_server(server_proc)
        raise SystemExit(0)

    if args.experts_only:
        from output_utils import find_run_dir
        TS = int(args.experts_only)
        OUTPUT = find_run_dir(args.experts_only)
        designer_files = sorted(OUTPUT.glob(f"task100_designer_{TS}_part*.txt"))
        if not designer_files:
            raise SystemExit(f"No designer parts found for run {TS} in {OUTPUT}")
        mat_lines = [l for f in designer_files for l in f.read_text(encoding="utf-8").split("\n") if l.strip() and "|" in l]
        # Redo suffix increments (redo, redo2, redo3...) so previous reruns'
        # raw files are never overwritten (iron rule).
        redo_idx = 1
        while list(OUTPUT.glob(f"task100_manufacturing_{TS}_redo{'' if redo_idx == 1 else redo_idx}_part1.txt")):
            redo_idx += 1
        redo_tag = "" if redo_idx == 1 else str(redo_idx)
        print(f"EXPERTS-ONLY rerun for run {TS}: {len(mat_lines)} candidate lines from {len(designer_files)} designer parts (suffix redo{redo_tag})")

        server_proc = start_server()
        try:
            is_current = CFG.get("schema") == "current"
            expert_prompts = {}
            # Prompt builders duplicated from the main flow below (same text,
            # redo save prefix). Kept as a dict so the loop stays uniform.
            # ---- manufacturing / delivery / safety / mechanism redo over the same chunks ----
            for agent in ("manufacturing", "delivery", "safety", "mechanism"):
                print("=" * 60)
                print(f"REDO {agent.upper()} ({CFG[agent]['chunks']} chunks)")
                print("=" * 60)
                for n, part in enumerate(split_chunks(mat_lines, CFG[agent]["chunks"]), start=1):
                    if not part:
                        continue
                    part_text = "\n".join(part)
                    prompt = build_expert_prompt(agent, part_text, is_current)
                    chunk, jfrac, retried = call_expert(
                        agent, prompt, f"task100_{agent}_{TS}_redo{redo_tag}", n,
                        CFG[agent]["max_tokens"], CFG[agent]["temperature"],
                        part_lines=part, is_current=is_current)
                    print(f"  {agent} redo chunk {n} done ({len(chunk)} chars, json={jfrac:.0%}{' after retry' if retried else ''})")
                    time.sleep(3)
        finally:
            stop_server(server_proc)
        raise SystemExit(0)

    server_proc = start_server()  # Global, used by call() for auto-restart

    try:
        if BASE_MODE:
            save(f"BASE_MODEL_RUN_{TS}.txt",
                 "This run used the UNFINE-TUNED base model (agent=base, no LoRA adapters) "
                 "for every step (control experiment, --base flag).\n")
        # ============================================================
        # Step 1: coordinator plans the task
        # ============================================================
        print("=" * 60)
        print("STEP 1: coordinator — Task planning")
        print("=" * 60)

        coordinator_goal = CFG.get("coordinator_goal", DEFAULT_COORDINATOR_GOAL)
        coordinator_raw = call("coordinator", coordinator_prompt(coordinator_goal),
                               max_tokens=CFG["coordinator"]["max_tokens"],
                               temp=CFG["coordinator"]["temperature"])
        save(f"task100_coordinator_{TS}.txt", coordinator_raw)
        print("  coordinator done")
        time.sleep(3)  # adapter switch is synchronous now; no unload wait needed

        # ============================================================
        # Step 2: designer designs 100 top-scoring materials (batched)
        # Long single-shot generations pin VRAM at the 24GB ceiling and
        # stall (allocator thrashing). Chunked calls stay in the fast
        # regime (~40 tok/s) and checkpoint one raw file per chunk.
        # Batch quotas come from pipeline_config.json.
        # ============================================================
        batches = CFG["designer"]["batches"]
        total_batches = len(batches)
        total_count = sum(b["count"] for b in batches)
        print("=" * 60)
        print(f"STEP 2: designer — Design {total_count} top-scoring materials ({total_batches} batches from config)")
        print("=" * 60)

        # The designer format block is the legacy-modality contract generated
        # per batch by output_schema.designer_format_block via designer_format_block_for()
        # (modality_focus). schema="current" (AD100): single uniform current
        # format block, no element quota.
        is_current = CFG.get("schema") == "current"
        designer_chunks = []
        designed_names = []  # cross-batch anti-duplication (see below)
        for b in batches:
            n = b["batch_id"]
            fmt_block = output_schema.designer_format_block_current() if is_current else designer_format_block_for(b)
            # With per-prompt seeds the batches are decorrelated, but the model
            # still gravitates to the same famous candidates. Give later
            # batches the names already produced and forbid repeats
            # (mechanical, prompt-level only — raw outputs unchanged).
            exclusion = ""
            if designed_names:
                shown = designed_names[-60:]
                exclusion = ("\n\nAlready designed in previous batches — do NOT repeat these "
                             "candidates or near-variants of them:\n" + ", ".join(shown))
            chunk = call("designer", designer_prompt(b["count"], n, total_batches,
                                                     batch_focus(b), fmt_block,
                                                     exclusion=exclusion),
                         max_tokens=b["max_tokens"], temp=CFG["designer"]["temperature"])
            save(f"task100_designer_{TS}_part{n}.txt", chunk)
            print(f"  designer batch {n}/{total_batches} done ({len(chunk)} chars)")
            designer_chunks.append(chunk)
            for line in chunk.split("\n"):
                if "|" in line and "Material_Name" not in line:
                    designed_names.append(line.split("|")[0].strip())
            time.sleep(3)  # adapter switch is synchronous now; no unload wait needed

        # In-memory join as downstream INPUT only; raw per-chunk files are the saved outputs
        designer_raw = "\n".join(designer_chunks)

        # Input hygiene: designer chatter lines (no "|") are kept in the raw files
        # but never fed to the expert agents (they poison chunk quality).
        mat_lines = [l for l in designer_raw.split("\n") if l.strip() and "|" in l]

        # ============================================================
        # Step 3: manufacturing scores manufacturability subscores (chunked)
        # Subscore JSON tail feeds the deterministic scoring engine
        # (scripts/scoring_engine.py + scoring_rubric.json) — raw output unchanged.
        # ============================================================
        print("=" * 60)
        print("STEP 3: manufacturing — Manufacturability subscores")
        print("=" * 60)

        manufacturing_chunks = []
        for n, part in enumerate(split_chunks(mat_lines, CFG["manufacturing"]["chunks"]), start=1):
            if not part:
                continue
            part_text = "\n".join(part)
            chunk, jfrac, retried = call_expert("manufacturing", build_expert_prompt("manufacturing", part_text, is_current), f"task100_manufacturing_{TS}", n, CFG["manufacturing"]["max_tokens"], CFG["manufacturing"]["temperature"], part_lines=part, is_current=is_current)
            print(f"  manufacturing chunk {n} done ({len(chunk)} chars, json={jfrac:.0%}{' after retry' if retried else ''})")
            manufacturing_chunks.append(chunk)
            time.sleep(3)

        manufacturing_raw = "\n".join(manufacturing_chunks)

        # ============================================================
        # Step 4: delivery scores target-tissue delivery efficiency (chunked)
        # ============================================================
        print("=" * 60)
        print("STEP 4: delivery — Target-tissue delivery subscores")
        print("=" * 60)

        delivery_chunks = []
        for n, part in enumerate(split_chunks(mat_lines, CFG["delivery"]["chunks"]), start=1):
            if not part:
                continue
            part_text = "\n".join(part)
            chunk, jfrac, retried = call_expert("delivery", build_expert_prompt("delivery", part_text, is_current), f"task100_delivery_{TS}", n, CFG["delivery"]["max_tokens"], CFG["delivery"]["temperature"], part_lines=part, is_current=is_current)
            print(f"  delivery chunk {n} done ({len(chunk)} chars, json={jfrac:.0%}{' after retry' if retried else ''})")
            delivery_chunks.append(chunk)
            time.sleep(3)

        delivery_raw = "\n".join(delivery_chunks)

        # ============================================================
        # Step 5: safety scores biosafety subscores (chunked)
        # ============================================================
        print("=" * 60)
        print("STEP 5: safety — Biosafety subscores")
        print("=" * 60)

        safety_chunks = []
        for n, part in enumerate(split_chunks(mat_lines, CFG["safety"]["chunks"]), start=1):
            if not part:
                continue
            part_text = "\n".join(part)
            chunk, jfrac, retried = call_expert("safety", build_expert_prompt("safety", part_text, is_current), f"task100_safety_{TS}", n, CFG["safety"]["max_tokens"], CFG["safety"]["temperature"], part_lines=part, is_current=is_current)
            print(f"  safety chunk {n} done ({len(chunk)} chars, json={jfrac:.0%}{' after retry' if retried else ''})")
            safety_chunks.append(chunk)
            time.sleep(3)

        safety_raw = "\n".join(safety_chunks)

        # ============================================================
        # Step 6: mechanism explains mechanisms (chunked)
        # ============================================================
        print("=" * 60)
        print("STEP 6: mechanism — Mechanism and intervention analysis")
        print("=" * 60)

        mechanism_chunks = []
        for n, part in enumerate(split_chunks(mat_lines, CFG["mechanism"]["chunks"]), start=1):
            if not part:
                continue
            part_text = "\n".join(part)
            chunk, jfrac, retried = call_expert("mechanism", build_expert_prompt("mechanism", part_text, is_current), f"task100_mechanism_{TS}", n, CFG["mechanism"]["max_tokens"], CFG["mechanism"]["temperature"], part_lines=part, is_current=is_current)
            print(f"  mechanism chunk {n} done ({len(chunk)} chars, json={jfrac:.0%}{' after retry' if retried else ''})")
            mechanism_chunks.append(chunk)
            time.sleep(3)

        mechanism_raw = "\n".join(mechanism_chunks)

        # ============================================================
        # Step 7: ranker produces final ranked summary
        # ============================================================
        print("=" * 60)
        print("STEP 7: ranker — Final ranked summary")
        print("=" * 60)

        trunc = CFG["ranker"]["input_truncation"]
        ranker_raw = call("ranker", build_ranker_prompt(designer_raw, delivery_raw, mechanism_raw, is_current, trunc),
                          max_tokens=CFG["ranker"]["max_tokens"],
                          temp=CFG["ranker"]["temperature"])
        save(f"task100_ranker_{TS}.txt", ranker_raw)

        print(f"\n{'='*60}")
        print("PIPELINE COMPLETE")
        print(f"{'='*60}")
        print(f"All outputs in: {OUTPUT}/")
        print(f"  task100_coordinator_{TS}.txt           — coordinator task plan")
        print(f"  task100_designer_{TS}_part1-{total_batches}.txt   — {total_count} materials with all fields ({total_batches} raw chunks)")
        print(f"  task100_manufacturing_{TS}_part1-{CFG['manufacturing']['chunks']}.txt   — manufacturing manufacturability subscores (raw chunks)")
        print(f"  task100_delivery_{TS}_part1-{CFG['delivery']['chunks']}.txt   — delivery target-tissue delivery subscores (raw chunks)")
        print(f"  task100_safety_{TS}_part1-{CFG['safety']['chunks']}.txt   — safety biosafety subscores (raw chunks)")
        print(f"  task100_mechanism_{TS}_part1-{CFG['mechanism']['chunks']}.txt   — mechanism mechanism analysis + axis score (raw chunks)")
        print(f"  task100_ranker_{TS}.txt            — ranker final summary")
        print(f"  (extract: python scripts/extract_subscores.py {TS} -> subscores_{TS}.json)")
        print(f"\nALL RAW, ZERO MODIFICATION.")

    finally:
        stop_server(server_proc)
