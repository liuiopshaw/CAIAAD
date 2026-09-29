# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv

# Load environment variables from the .env file at import time
load_dotenv()


class Config:
    """Central configuration for the domain tools under src/tools.

    All values are read from environment variables (see .env.example).
    """

    # --- External scientific database API keys ---
    # DrugBank pharmacology database API key (used by src/tools/drugbank_tool.py)
    DRUGBANK_API_KEY = os.getenv("DRUGBANK_API_KEY", "")
