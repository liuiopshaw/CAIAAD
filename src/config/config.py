# -*- coding: utf-8 -*-
# Line 1: specify the source file encoding as UTF-8 to ensure correct character parsing
import os
# Line 3: import the os module for reading environment variables
from dotenv import load_dotenv
# Line 4: import the load_dotenv function from the python-dotenv library to load environment variables from a .env file

# Line 6: immediately load environment variables from the .env file into os.environ at module level
# Note: this load happens early; if main.py later loads again with override=True, the values set here may be overwritten
load_dotenv()

class Config:
    # Line 10: define the Config class; all configuration items are class attributes read from environment variables via os.getenv with default values

    # --- Hosted LLM API configuration (OpenAI-compatible) ---
    # QWEN_API_BASE — endpoint of a hosted OpenAI-compatible API; no default,
    # set it via an environment variable or the .env file
    QWEN_API_BASE = os.getenv("QWEN_API_BASE", "")
    # QWEN_API_KEY — API key of the hosted endpoint; no default, set via env or .env
    QWEN_API_KEY = os.getenv("QWEN_API_KEY")
    # QWEN_MODEL_NAME — hosted model name; no default, set via env or .env
    # (also consumed by scripts/llm_endpoints.json via model_env routing)
    QWEN_MODEL_NAME = os.getenv("QWEN_MODEL_NAME", "")

    # --- OpenAI-compatible configuration (required by the CrewAI framework) ---
    # OPENAI_API_BASE — OpenAI-compatible endpoint used internally by CrewAI
    OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "")
    # Line 22: OPENAI_API_KEY — API key used internally by CrewAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    # --- External scientific database API configuration ---
    # Line 25: Materials Project materials database API key (optional), used to query material properties such as crystal structures and band structures
    MATERIALS_PROJECT_API_KEY = os.getenv("MATERIALS_PROJECT_API_KEY")
    # Line 28: PubChem compound database API key (optional), used to query chemical safety, toxicity, and related information
    PUBCHEM_API_KEY = os.getenv("PUBCHEM_API_KEY")
    # DrugBank pharmacology database API key
    DRUGBANK_API_KEY = os.getenv("DRUGBANK_API_KEY", "")

    # --- LLaVA vLLM local model server endpoint ---
    LLAVA_API_BASE = os.getenv("LLAVA_API_BASE", "http://localhost:8000/v1")
    LLAVA_MODEL_NAME = os.getenv("LLAVA_MODEL_NAME", "")

    # --- Model parameter configuration ---
    # Line 32: MODEL_TEMPERATURE — default temperature parameter (0.0~1.0), controls output randomness; defaults to 0.7
    MODEL_TEMPERATURE = float(os.getenv("MODEL_TEMPERATURE", "0.7"))
    # Line 33: MODEL_MAX_TOKENS — maximum number of output tokens; defaults to 2048
    MODEL_MAX_TOKENS = int(os.getenv("MODEL_MAX_TOKENS", "2048"))

    # --- Agent-specific temperature configuration ---
    # The material design expert uses a higher temperature of 0.8 to increase output diversity and encourage innovative designs
    MATERIAL_DESIGNER_TEMPERATURE = float(os.getenv("MATERIAL_DESIGNER_TEMPERATURE", "0.8"))

    # The three evaluation experts use a lower temperature of 0.3 to ensure consistency and accuracy of scoring
    EXPERT_A_TEMPERATURE = float(os.getenv("EXPERT_A_TEMPERATURE", "0.3"))
    EXPERT_B_TEMPERATURE = float(os.getenv("EXPERT_B_TEMPERATURE", "0.3"))
    EXPERT_C_TEMPERATURE = float(os.getenv("EXPERT_C_TEMPERATURE", "0.3"))

    # The final validation expert uses a moderate temperature of 0.5, balancing stability and flexibility of comprehensive judgment
    FINAL_VALIDATOR_TEMPERATURE = float(os.getenv("FINAL_VALIDATOR_TEMPERATURE", "0.5"))

    # The other experts (mechanism analysis, synthesis guidance, operation suggestion, literature processing) uniformly use the evaluation-grade temperature of 0.3
    MECHANISM_EXPERT_TEMPERATURE = float(os.getenv("MECHANISM_EXPERT_TEMPERATURE", "0.3"))
    SYNTHESIS_EXPERT_TEMPERATURE = float(os.getenv("SYNTHESIS_EXPERT_TEMPERATURE", "0.3"))
    OPERATION_SUGGESTING_TEMPERATURE = float(os.getenv("OPERATION_SUGGESTING_TEMPERATURE", "0.3"))
    LITERATURE_PROCESSOR_TEMPERATURE = float(os.getenv("LITERATURE_PROCESSOR_TEMPERATURE", "0.3"))

    # ---- Temperatures for the newly added agents in the nano-bio evaluation system ----
    APA_TEMPERATURE = float(os.getenv("APA_TEMPERATURE", "0.3"))
    EPA_TEMPERATURE = float(os.getenv("EPA_TEMPERATURE", "0.3"))
    BSA_TEMPERATURE = float(os.getenv("BSA_TEMPERATURE", "0.3"))
    MMA_TEMPERATURE = float(os.getenv("MMA_TEMPERATURE", "0.3"))
    CA_TEMPERATURE = float(os.getenv("CA_TEMPERATURE", "0.1"))

    # Backward-compatible unified evaluation temperature configuration
    EXPERT_EVALUATION_TEMPERATURE = float(os.getenv("EXPERT_EVALUATION_TEMPERATURE", "0.3"))

    # ---- Nano-bio evaluation scoring weights ----
    APA_WEIGHTS = {
        "potency": 0.40,
        "selectivity": 0.35,
        "spectrum": 0.15,
        "resistance_risk": 0.10
    }

    EPA_WEIGHTS = {
        "activity_strength": 0.65,
        "substrate_affinity": 0.25,
        "condition_window": 0.10
    }

    BSA_WEIGHTS = {
        "cytotoxicity": 0.30,
        "organ_damage": 0.25,
        "in_vivo_toxicity": 0.20,
        "environmental_risk": 0.15,
        "structural_stability": 0.10
    }

    # --- Language configuration ---
    # Line 64: LANGUAGE — interface language selection; "zh" for Chinese, "en" for English
    LANGUAGE = os.getenv("LANGUAGE", "en")

    # --- Other configuration ---
    # Line 67: VERBOSE — whether to output detailed logs; the string read from the environment variable is converted to a boolean
    VERBOSE = os.getenv("VERBOSE", "True").lower() == "true"

    @classmethod
    def is_api_key_valid(cls, api_key):
        # Class method that validates whether an API key is valid
        # Checks that the key is non-empty and still has content after stripping whitespace (strip() being truthy already implies length > 0)
        return bool(api_key and api_key.strip())
