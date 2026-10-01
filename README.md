# AD Multi-Agent Evaluator (CAIAAD)

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)](#)

A multi-agent system for Alzheimer's disease (AD) therapeutic candidate design and evaluation, built on a locally served open-source VLM base model with **per-agent LoRA adapters** (PEFT multi-adapter hot-swapping). The project ships a candidate-design pipeline and a blind benchmark evaluation suite.

## Features

- 🤖 **Specialized agents** — task orchestration (coordinator), creative design (designer), knowledge extraction from text/literature (extractor), manufacturability scoring (manufacturing), delivery-efficiency scoring (delivery), biosafety (safety), mechanism mining (mechanism), comparison/ranking (ranker)
- 🔬 **Per-agent LoRA adapters** — one base model loaded once; adapters switched per request by `scripts/model_server.py` (FastAPI, OpenAI-compatible)
- ☁️ **Per-agent hosted-LLM routing** — any agent can be rerouted to a hosted OpenAI-compatible API via `scripts/llm_endpoints.json`, no code changes (coordinator and extractor are routed out of the box; the model name and key live in `.env`)
- 🖥️ **Web chat UI** — SSE orchestration with per-step agent cards, session history, a workspace picker (raw outputs are written there), and a direct-consultation mode that calls any single agent without the full pipeline (`scripts/web_server.py` + `scripts/static/index.html`)
- 📊 **Blind benchmark suite** — AD-TxBench-100 (drug scoring) with harness-vs-prompt and LoRA-vs-base 2×2 protocols, rubric anchoring, AD-relevance gating, anonymization, and deterministic scoring
- 📐 **Deterministic scoring engine** — agent subscores are mechanically extracted and fused by `scripts/scoring_engine.py` with the weights in `scripts/scoring_rubric.json`; changing the rubric re-scores historical runs without re-running any agent

## Pipeline

Two entry points share the same prompt builders (`scripts/pipeline_prompts.py`) and config (`scripts/pipeline_config.json`):

```bash
# 1. Start the LoRA multi-adapter server (loads the base model once)
python scripts/model_server.py          # port 8000; CAIAAD_SEED="" disables deterministic seeding

# 2a. CLI pipeline: coordinator -> designer x4 -> manufacturing/delivery/safety/mechanism -> ranker
python scripts/task_100_materials.py --config scripts/pipeline_config.json
#    --base            control run with the raw base model (all LoRA adapters disabled)
#    --redo-batch TS N / --experts-only TS    surgical re-runs

# 2b. Web chat entry (SSE orchestration, chat-style UI)
python scripts/web_server.py            # port 8001 (CAIAAD_WEB_PORT to override)
#    coordinator mode runs the full pipeline as agent cards;
#    the Agent selector switches to direct single-agent consultation;
#    the sidebar workspace picker chooses where raw outputs are written

# 3. Deterministic ranking (no agent involved; raw outputs never modified)
python scripts/extract_subscores.py <TS>
python scripts/rank_ad100.py <TS> --rubric scripts/scoring_rubric.json
python scripts/rank_to_excel.py <TS>   # Excel export (Ranking / Run Metrics / Type_Top5)
```

## Hosted LLM routing per agent

`scripts/llm_client.py` routes every agent call. Default: everything local. Any agent (or all) can be put on a hosted OpenAI-compatible API by editing `scripts/llm_endpoints.json`:

```json
{
  "default": {"base_url": "http://localhost:8000/v1/chat/completions", "model": "caiaad", "api_key_env": null},
  "coordinator": {"base_url": "https://your-endpoint/v1/chat/completions",
          "model_env": "QWEN_MODEL_NAME", "api_key_env": "QWEN_API_KEY"},
  "extractor": {"base_url": "https://your-endpoint/v1/chat/completions",
          "model_env": "QWEN_MODEL_NAME", "api_key_env": "QWEN_API_KEY"}
}
```

- An agent entry overrides `default` field-by-field; unknown agents fall back to `default`.
- `api_key_env` names the environment variable holding the API key (sent as a Bearer token); `null` = no auth.
- `model` sets the request model inline; `model_env` names an environment variable holding the model name (takes precedence) — use it to keep model names out of the repo.
- Local endpoints keep the extra `agent` field (model_server switches adapters on it); hosted endpoints receive a standard OpenAI request body.

## Blind benchmark suite

```bash
python scripts/benchmark_adtb100.py --rubric --gate hard --benchmark benchmark/AD-TxBench-100.json
#   --use-base            raw base model arm
#   --mode prompt         single consolidated scoring prompt (no agent chain)
#   --gate off|hard|soft  AD-relevance gating formula
#   --name-only           agents see ONLY the drug name
#   --anonymize           agents see Candidate_NNN codes + class/mechanism (name prior removed)
python scripts/compare_adtb100.py <TS>    # per-tier stats, Spearman, concordance, confusion, P@k
python scripts/adtb100_aggregate.py       # mean +/- std across repeated runs
```

Note: `adtb100_scores_<TS>_complete.json` is not written by the benchmark script itself — it is produced by a manual merge step (merging retried/completed items into the per-run scores file) before compare/aggregate/export consume it; when present it automatically wins over the raw scores file.

All agent outputs are saved RAW and unmodified under `outputs/run_<TS>/`; scoring and ranking are mechanical extraction only.

## Scoring rubric

`rubric/rubric.md` — five weighted dimensions (target-tissue delivery 30%, multi-target synergy 15%, effect duration 10%, manufacturing control 25%, biosafety 20%) plus an optional AD-relevance gate (hard: ×ad/10; soft: ×(0.5+0.5·ad/10)). Mirrored in `scripts/scoring_rubric.json` for deterministic ranking.

## Project Structure

```
├── scripts/
│   ├── paths.py              # centralized filesystem paths (env-overridable)
│   ├── pipeline_prompts.py   # shared prompt builders (CLI + web share these)
│   ├── model_server.py       # LoRA multi-adapter server (port 8000)
│   ├── llm_client.py         # unified per-agent LLM routing
│   ├── llm_endpoints.json    # per-agent endpoint config (local/hosted)
│   ├── task_100_materials.py # CLI candidate-design pipeline
│   ├── web_server.py         # SSE chat orchestration (:8001) + static/index.html
│   ├── output_schema.py      # output contract (current/legacy) single source of truth
│   ├── scoring_engine.py     # deterministic scoring engine (rubric-driven)
│   ├── extract_subscores.py  # mechanical subscore extraction
│   ├── rank_ad100.py / rank_designer_outputs.py / rank_to_excel.py
│   ├── benchmark_adtb100.py / compare_adtb100.py / adtb100_aggregate.py
│   ├── formula_lookup.py     # DB verification of agent identifiers
│   └── pipeline_config.json / scoring_rubric.json
├── src/                      # agent framework + domain tools (CrewAI)
├── finetune/                 # (local only, not committed) literature index + training-data builders + trainer
├── benchmark/                # AD-TxBench-100
└── .env.example
```

## Portability

All absolute paths resolve through `scripts/paths.py` and can be overridden with environment variables (defaults point under the project root):

| Variable | Purpose | Default |
|---|---|---|
| `CAIAAD_ROOT` | project root | `scripts/..` |
| `CAIAAD_MODEL_PATH` | base model directory | `<root>/models/base/vlm-instruct` |
| `CAIAAD_LORA_DIR` | LoRA adapters directory | `<root>/models/lora_enhanced` |
| `CAIAAD_OUTPUT_DIR` | outputs directory | `<root>/outputs` |
| `CAIAAD_LITERATURE_DIR` | literature PDF library | `<root>/agent_literature` |
| `CAIAAD_SEED` | base seed for per-prompt deterministic sampling (`""` disables seeding) | `42` |
| `CAIAAD_WEB_PORT` | web chat server port (`scripts/web_server.py`) | `8001` |
| `CAIAAD_LLM_BASE` | upstream LLM base URL for the web server's health proxy | `http://localhost:8000` |

## Configuration

API keys live in `.env` (see `.env.example`): `QWEN_API_KEY`, `MATERIALS_PROJECT_API_KEY`, optional `MOLPORT_API_KEY`, `DRUGBANK_API_KEY`, `NCBI_API_KEY`. Never commit `.env`.

## Requirements

- Python 3.11 or 3.12
- `pip install -r requirements.txt`

## License

GNU General Public License v3.0 — see [LICENSE](LICENSE). Derivative works must be open-sourced under the same license.
