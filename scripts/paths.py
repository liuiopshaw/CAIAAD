#!/usr/bin/env python3
"""Centralized filesystem paths.

Every absolute path in the project resolves through this module. Override via
environment variables; defaults point under the project root so the toolchain
runs on any machine without edits.

    NANO_BIO_ROOT          project root (default: parent of this scripts/ dir)
    NANO_BIO_MODEL_PATH    base model directory
    NANO_BIO_LORA_DIR      per-agent LoRA adapters directory
    NANO_BIO_OUTPUT_DIR    outputs directory
    NANO_BIO_LITERATURE_DIR  literature PDF library (finetune scripts)
"""

import os
from pathlib import Path

PROJECT_ROOT = Path(
    os.environ.get("NANO_BIO_ROOT", Path(__file__).resolve().parent.parent)
)

MODEL_PATH = os.environ.get(
    "NANO_BIO_MODEL_PATH",
    str(PROJECT_ROOT / "models" / "base" / "vlm-instruct"),
)

LORA_DIR = os.environ.get(
    "NANO_BIO_LORA_DIR",
    str(PROJECT_ROOT / "models" / "lora_enhanced"),
)

OUTPUT_ROOT = Path(
    os.environ.get("NANO_BIO_OUTPUT_DIR", str(PROJECT_ROOT / "outputs"))
)

LITERATURE_DIR = Path(
    os.environ.get("NANO_BIO_LITERATURE_DIR", str(PROJECT_ROOT / "agent_literature"))
)
