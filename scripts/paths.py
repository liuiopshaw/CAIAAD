#!/usr/bin/env python3
"""Centralized filesystem paths.

Every absolute path in the project resolves through this module. Override via
environment variables; defaults point under the project root so the toolchain
runs on any machine without edits.

    CU_AGENT_ROOT          project root (default: parent of this scripts/ dir)
    CU_AGENT_MODEL_PATH    base model directory
    CU_AGENT_LORA_DIR      per-agent LoRA adapters directory
    CU_AGENT_OUTPUT_DIR    outputs directory
    CU_AGENT_LITERATURE_DIR  literature PDF library (finetune scripts)
"""

import os
from pathlib import Path

PROJECT_ROOT = Path(
    os.environ.get("CU_AGENT_ROOT", Path(__file__).resolve().parent.parent)
)

MODEL_PATH = os.environ.get(
    "CU_AGENT_MODEL_PATH",
    str(PROJECT_ROOT / "models" / "qwen" / "Qwen3-VL-8B-Instruct"),
)

LORA_DIR = os.environ.get(
    "CU_AGENT_LORA_DIR",
    str(PROJECT_ROOT / "models" / "lora_enhanced"),
)

OUTPUT_ROOT = Path(
    os.environ.get("CU_AGENT_OUTPUT_DIR", str(PROJECT_ROOT / "outputs"))
)

LITERATURE_DIR = Path(
    os.environ.get("CU_AGENT_LITERATURE_DIR", str(PROJECT_ROOT / "agent_literature"))
)
