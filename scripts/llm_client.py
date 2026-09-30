#!/usr/bin/env python3
"""
Unified per-agent LLM routing layer.

Every agent call in the scripts/ pipeline goes through chat() here. By default
everything routes to the local model_server.py on localhost:8000 (unchanged
behavior). Any agent can be rerouted to a hosted OpenAI-compatible API by
adding an entry to scripts/llm_endpoints.json:

  {
    "default": {"base_url": "http://localhost:8000/v1/chat/completions",
                "model": "caiaad", "api_key_env": null},
    "coordinator": {"base_url": "https://your-endpoint/v1/chat/completions",
            "model_env": "HOSTED_MODEL_NAME", "api_key_env": "HOSTED_API_KEY"}
  }

Semantics:
- An agent entry overrides "default" field-by-field; unknown agents fall back
  to "default".
- "api_key_env" names an environment variable holding the API key, sent as
  "Authorization: Bearer <key>". null = no auth header (local server).
- "model" sets the request model directly; "model_env" names an environment
  variable holding the model name (takes precedence over "model"). Likewise
  "base_url_env" names an environment variable holding the endpoint URL
  (takes precedence over "base_url") — use these to keep provider URLs and
  model names out of the repo. A configured-but-missing variable returns a
  clear ERROR string, same as a missing API key.
- Local endpoints (localhost / 127.0.0.1) keep the extra "agent" field in the
  request body — model_server uses it to switch LoRA adapters. Non-local
  endpoints receive a standard OpenAI request body WITHOUT "agent".

Agent raw outputs are returned verbatim (project iron rule: no cleaning).
Errors are returned as "ERROR ..." strings, never raised, matching the
existing scripts' conventions.
"""

import json
import os
import time
from pathlib import Path

import httpx

CONFIG_PATH = Path(__file__).resolve().parent / "llm_endpoints.json"

LOCAL_CHAT_URL = "http://localhost:8000/v1/chat/completions"

# Built-in fallback when llm_endpoints.json is absent: everything local.
_BUILTIN_CONFIG = {
    "default": {"base_url": LOCAL_CHAT_URL, "model": "caiaad", "api_key_env": None}
}


def load_endpoints(path=None) -> dict:
    """Load the per-agent endpoint config.

    Missing file -> built-in local default. Each agent entry is merged over
    "default" field-by-field. Returns a dict with at least "default".
    """
    p = Path(path) if path else CONFIG_PATH
    cfg = {}
    if p.exists():
        with open(p, encoding="utf-8") as f:
            cfg = json.load(f)
    default = dict(_BUILTIN_CONFIG["default"])
    default.update(cfg.get("default") or {})
    endpoints = {"default": default}
    for name, ep in cfg.items():
        if name == "default" or not isinstance(ep, dict):
            continue
        merged = dict(default)
        merged.update(ep)
        endpoints[name] = merged
    return endpoints


def resolve_endpoint(agent: str, endpoints: dict = None) -> dict:
    """Endpoint dict for an agent (per-agent override or the default)."""
    eps = endpoints if endpoints is not None else load_endpoints()
    return eps.get(agent, eps["default"])


def is_local_endpoint(ep: dict) -> bool:
    """True when the endpoint is the local model_server (localhost/127.0.0.1)."""
    url = ep.get("base_url", "")
    return "localhost" in url or "127.0.0.1" in url


def chat(agent: str, prompt: str, max_tokens: int = 6144, temperature: float = 0.1,
         timeout: int = 1800, retries: int = 3, retry_on_timeout: bool = True,
         endpoints: dict = None) -> str:
    """Send one user-prompt chat completion for an agent, return the raw text.

    Retry policy (mirrors the existing scripts): 502/503 wait 10s and retry;
    connection errors wait 5s and retry; ReadTimeout retries too unless
    retry_on_timeout=False (task_100_materials relies on that: the local
    server is likely still generating, so a retry would queue a duplicate).
    Non-retryable HTTP statuses return an "ERROR <status>: ..." string.
    A configured-but-missing API key returns a clear ERROR string immediately.
    """
    ep = resolve_endpoint(agent, endpoints)

    # Endpoint URL: "base_url_env" (env var, keeps provider URLs out of the
    # repo) takes precedence over the inline "base_url" field. Resolved before
    # the local check so an env-routed localhost endpoint still counts as local.
    base_url = ep.get("base_url")
    base_url_env = ep.get("base_url_env")
    if base_url_env:
        base_url = os.getenv(base_url_env)
        if not base_url:
            return (f"ERROR: endpoint for agent '{agent}' requires base URL env "
                    f"var '{base_url_env}', but it is not set")
    local = is_local_endpoint({"base_url": base_url})

    headers = {}
    key_env = ep.get("api_key_env")
    if key_env:
        key = os.getenv(key_env)
        if not key:
            return (f"ERROR: endpoint for agent '{agent}' requires API key env "
                    f"var '{key_env}', but it is not set")
        headers["Authorization"] = f"Bearer {key}"

    # Model name: "model_env" (env var, keeps model names out of the repo)
    # takes precedence over the inline "model" field.
    model = ep.get("model", "caiaad")
    model_env = ep.get("model_env")
    if model_env:
        model = os.getenv(model_env)
        if not model:
            return (f"ERROR: endpoint for agent '{agent}' requires model env "
                    f"var '{model_env}', but it is not set")

    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if local:
        body["agent"] = agent  # model_server switches LoRA adapters on this

    for attempt in range(retries):
        try:
            r = httpx.post(base_url, json=body, headers=headers or None,
                           timeout=timeout)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"]
            if r.status_code in (502, 503):
                print(f"  {agent} got {r.status_code}, retrying in 10s ({attempt+1}/{retries})")
                time.sleep(10)
            else:
                return f"ERROR {r.status_code}: {r.text[:300]}"
        except httpx.ReadTimeout:
            if not retry_on_timeout:
                return f"ERROR: generation exceeded timeout ({timeout}s)"
            print(f"  {agent} ReadTimeout, retrying ({attempt+1}/{retries})")
            time.sleep(5)
        except httpx.TransportError as e:
            # ConnectError / ConnectTimeout / network resets etc.
            print(f"  {agent} {type(e).__name__}: {e}, retrying ({attempt+1}/{retries})")
            time.sleep(5)
    return f"ERROR: failed after {retries} retries"
