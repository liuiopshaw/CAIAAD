# AD Multi-Agent Evaluator (Nano-Bio)

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)](#)

A multi-agent system for Alzheimer's disease (AD) therapeutic candidate design and evaluation, built on a locally served **Qwen3-VL-8B** base model with **per-agent LoRA adapters** (PEFT multi-adapter hot-swapping). The project ships a candidate-design pipeline and a blind benchmark evaluation suite.

## Features

- 🤖 **Specialized agents** — task orchestration (coordinator), creative design (designer), manufacturability scoring (manufacturing), delivery-efficiency scoring (delivery), biosafety (safety), mechanism mining (mechanism), comparison/ranking (ranker)
- 🔬 **Per-agent LoRA adapters** — one base model loaded once; adapters switched per request by `scripts/llava_server.py` (FastAPI, OpenAI-compatible)
- ☁️ **Per-agent cloud LLM routing** — any agent can be rerouted to a cloud OpenAI-compatible API (DashScope / OpenAI / DeepSeek ...) via `scripts/llm_endpoints.json`, no code changes
- 📊 **Blind benchmark suite** — AD-TxBench-100 (drug scoring) with harness-vs-prompt and LoRA-vs-base 2×2 protocols, rubric anchoring, AD-relevance gating, anonymization, and deterministic scoring
- 📐 **Deterministic ASA scoring** — agent subscores are mechanically extracted and fused by `scripts/asa_scoring.py` with the weights in `scripts/asa_rubric.json`; changing the rubric re-scores historical runs without re-running any agent

## Pipeline

Two entry points share the same prompt builders (`scripts/pipeline_prompts.py`) and config (`scripts/pipeline_config.json`):

```bash
# 1. Start the LoRA multi-adapter server (loads Qwen3-VL-8B once)
python scripts/llava_server.py          # port 8000; CU_AGENT_SEED="" disables deterministic seeding

# 2a. CLI pipeline: coordinator -> designer x4 -> manufacturing/delivery/safety/mechanism -> ranker
python scripts/task_100_materials.py --config scripts/pipeline_config.json
#    --base            control run with the raw base model (all LoRA adapters disabled)
#    --redo-batch TS N / --experts-only TS    surgical re-runs

# 2b. Web chat entry (SSE orchestration, Kimi-style UI)
python scripts/web_server.py            # port 8001 (CU_AGENT_WEB_PORT to override)

# 3. Deterministic ranking (no agent involved; raw outputs never modified)
python scripts/extract_subscores.py <TS>
python scripts/rank_ad100.py <TS> --rubric scripts/asa_rubric.json
```

## Cloud LLM per agent

`scripts/llm_client.py` routes every agent call. Default: everything local. To put a single agent (or all) on a cloud API, edit `scripts/llm_endpoints.json`:

```json
{
  "default": {"base_url": "http://localhost:8000/v1/chat/completions", "model": "nano-bio", "api_key_env": null},
  "delivery": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
          "model": "qwen-plus", "api_key_env": "QWEN_API_KEY"}
}
```

- An agent entry overrides `default` field-by-field; unknown agents fall back to `default`.
- `api_key_env` names the environment variable holding the API key (sent as a Bearer token); `null` = no auth.
- Local endpoints keep the extra `agent` field (llava_server switches adapters on it); cloud endpoints receive a standard OpenAI request body.

## Blind benchmark suite

```bash
python scripts/benchmark_adtb100.py --rubric --gate hard --benchmark benchmark/AD-TxBench-100_v3.0.json
#   --use-base            raw base model arm
#   --mode prompt         single consolidated scoring prompt (no agent chain)
#   --gate off|hard|soft  AD-relevance gating formula
#   --name-only           agents see ONLY the drug name
#   --anonymize           agents see Candidate_NNN codes + class/mechanism (name prior removed)
python scripts/compare_adtb100.py <TS>    # per-tier stats, Spearman, concordance, confusion, P@k
python scripts/adtb100_aggregate.py       # mean +/- std across repeated runs
```

All agent outputs are saved RAW and unmodified under `outputs/run_<TS>/`; scoring and ranking are mechanical extraction only.

## Scoring rubric

`rubric/rubric.md` — five weighted dimensions (target-tissue delivery 30%, multi-target synergy 15%, effect duration 10%, manufacturing control 25%, biosafety 20%) plus an optional AD-relevance gate (hard: ×ad/10; soft: ×(0.5+0.5·ad/10)). Mirrored in `scripts/asa_rubric.json` for deterministic ranking.

## Project Structure

```
├── scripts/
│   ├── paths.py              # centralized filesystem paths (env-overridable)
│   ├── pipeline_prompts.py   # shared prompt builders (CLI + web share these)
│   ├── llava_server.py       # LoRA multi-adapter server (port 8000)
│   ├── llm_client.py         # unified per-agent LLM routing
│   ├── llm_endpoints.json    # per-agent endpoint config (local/cloud)
│   ├── task_100_materials.py # CLI candidate-design pipeline
│   ├── web_server.py         # SSE chat orchestration (:8001) + static/index.html
│   ├── schema_v2.py          # output contract (v2/v3) single source of truth
│   ├── asa_scoring.py        # deterministic ASA engine (rubric-driven)
│   ├── extract_subscores.py  # mechanical subscore extraction
│   ├── rank_ad100.py / rank_cda_outputs.py / rank_to_excel.py
│   ├── benchmark_adtb100.py / compare_adtb100.py / adtb100_aggregate.py
│   ├── compound_lookup.py / formula_lookup.py   # DB verification of agent identifiers
│   └── pipeline_config*.json / asa_rubric*.json
├── src/tools/                # domain tools (PubChem, ChEMBL, UniProt, Open Targets, ...)
├── finetune/                 # literature index + LoRA training-data builders + trainer
├── benchmark/                # AD-TxBench-100
└── .env.example
```

## Portability

All absolute paths resolve through `scripts/paths.py` and can be overridden with environment variables (defaults point under the project root):

| Variable | Purpose | Default |
|---|---|---|
| `CU_AGENT_ROOT` | project root | `scripts/..` |
| `CU_AGENT_MODEL_PATH` | base model directory | `<root>/models/qwen/Qwen3-VL-8B-Instruct` |
| `CU_AGENT_LORA_DIR` | LoRA adapters directory | `<root>/models/lora_enhanced` |
| `CU_AGENT_OUTPUT_DIR` | outputs directory | `<root>/outputs` |
| `CU_AGENT_LITERATURE_DIR` | literature PDF library | `<root>/agent_literature` |

## Configuration

API keys live in `.env` (see `.env.example`): `QWEN_API_KEY`, `MATERIALS_PROJECT_API_KEY`, optional `MOLPORT_API_KEY`, `DRUGBANK_API_KEY`, `NCBI_API_KEY`. Never commit `.env`.

## Requirements

- Python 3.11 or 3.12
- `pip install -r requirements.txt`

## License

GNU General Public License v3.0 — see [LICENSE](LICENSE). Derivative works must be open-sourced under the same license.
