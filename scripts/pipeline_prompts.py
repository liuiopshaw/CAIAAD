#!/usr/bin/env python3
"""Shared prompt builders and pipeline helpers for the AD candidate pipeline.

Single source of truth for the coordinator / designer / expert / ranker prompt
templates and the small chunking/format helpers. Both ``task_100_materials.py``
(CLI pipeline) and ``web_server.py`` (SSE chat orchestration) import from here,
so prompt text cannot drift between the two entry points.

Nothing in this module performs I/O or calls an LLM — it only builds strings.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import output_schema  # noqa: E402


DEFAULT_TOA_GOAL = (
    "Design 100 candidates spanning nanomaterials, small-molecule drugs, and "
    "biologics, with AD-relevant mechanisms as the priority — selective direct "
    "antibacterial action and gut-microbiome remodeling alongside small molecules "
    "and biologics targeting amyloid/tau/neuroinflammation pathways. Validate "
    "NADH oxidase-like activity, assess antibacterial performance and biosafety, "
    "analyze mechanisms, and produce a ranked summary report."
)


# Hard character budget for one prompt sent to the model. Header + footer of
# build_expert_prompt / build_ca_prompt are a few hundred chars; the records
# body is what must fit. The old 10000-char cap truncated the FINAL string,
# which cut the mandatory JSON-tail format instruction at the prompt tail
# (the ranker input alone is ~17k chars from the config truncations).
PROMPT_CHAR_CAP = 60000


NANO_ONLY_LINE = ("This batch uses NANO modalities only: "
                  "nanocluster, nanoparticle, single_atom, dual_atom")


def batch_focus(batch: dict) -> str:
    """Prompt focus text for a designer batch: 'focus' (verbatim) wins, otherwise
    'description'."""
    if batch.get("focus"):
        return batch["focus"]
    return batch["description"].rstrip()


def cda_format_block_for(batch: dict) -> str:
    """Legacy-modality designer format block for a batch, driven by its optional
    'modality_focus' ("free" | "nano_mixed" | an output_schema.MODALITIES value;
    missing = legacy nano-only config -> "nano_mixed")."""
    mf = batch.get("modality_focus") or "nano_mixed"
    if mf == "free":
        return output_schema.cda_format_block(None)
    if mf == "nano_mixed":
        return output_schema.cda_format_block(None) + "\n" + NANO_ONLY_LINE
    return output_schema.cda_format_block(mf)


def split_chunks(lines: list, k: int) -> list:
    """Split lines into k nearly-equal contiguous chunks (k <= len(lines))."""
    k = max(1, min(k, len(lines)))
    base, rem = divmod(len(lines), k)
    chunks, start = [], 0
    for i in range(k):
        end = start + base + (1 if i < rem else 0)
        chunks.append(lines[start:end])
        start = end
    return chunks


def build_expert_prompt(agent: str, part_text: str, is_current: bool) -> str:
    """Single source of the four expert prompts (manufacturing / delivery /
    safety / mechanism). Subscore JSON tails feed the deterministic ASA engine
    (scripts/asa_scoring.py + asa_rubric.json).

    When the records body alone would push the prompt past PROMPT_CHAR_CAP,
    the BODY is clipped and the prompt rebuilt — the mandatory format footer
    at the end is never truncated away (raw agent outputs are unaffected)."""
    prompt = _expert_prompt(agent, part_text, is_current)
    over = len(prompt) - PROMPT_CHAR_CAP
    if over <= 0:
        return prompt
    return _expert_prompt(agent, part_text[:max(0, len(part_text) - over)], is_current)


def _expert_prompt(agent: str, part_text: str, is_current: bool) -> str:
    if agent == "manufacturing":
        return f"""Assess MANUFACTURABILITY & PRECISE CONTROL (manufacturability and precise-control capability) of each candidate below: is its preparation controllable, scalable, and precisely tunable in composition and dose?

Scoring anchors (from the project scoring standard):
- 9-10: definite chemical composition, controllable synthesis route, high batch-to-batch consistency, precisely tunable dose, easy to scale up (nano formulations and small molecules with defined formulas belong here)
- 7-8: mostly definite composition, controllable and scalable (e.g., antibodies/peptides — complex but consistent production)
- 5-6: complex but controllable composition; scale-up has challenges
- 3-4: ill-defined composition or highly donor/biological-source dependent, large batch variation, hard to standardize (e.g., FMT)
- 1-2: uncontrollable, cannot be scaled
Do NOT score by clinical maturity or market availability — a novel but well-defined, controllable formulation scores HIGH.

Candidates:
{part_text}

Output: ONE line per candidate with the original fields UNCHANGED, then append a semicolon and a JSON object with the manufacturability score, e.g.:
...original line...; {{"manufacturability": 9}}"""
    if agent == "delivery":
        if is_current:
            return f"""Score TARGET-TISSUE DELIVERY EFFICIENCY (target-tissue delivery efficiency, 1-10) for each candidate below: how efficiently the candidate reaches its intended target tissue — for gut-targeted candidates consider stability in GI tract, mucosal retention, size/ligand effects; for CNS candidates consider BBB penetration, bioavailability (10 = most efficient delivery).

Candidates:
{part_text}

Output in the same pipe-separated format: append a semicolon and a JSON object with the delivery score (REQUIRED on every line), e.g.:
...original line...; {{"delivery_efficiency": 8}}
The JSON object is MANDATORY — every line MUST contain exactly one JSON object."""
        return f"""Review and validate the following candidate list. For each candidate:
1. Verify the NADH activity prediction (YES/NO) with reasoning
2. Score TARGET-TISSUE DELIVERY EFFICIENCY (target-tissue delivery efficiency, 1-10): how efficiently the candidate reaches its intended target tissue — for gut-targeted candidates consider stability in GI tract, mucosal retention, size/ligand effects; for CNS candidates consider BBB penetration, bioavailability (10 = most efficient delivery).

Candidates:
{part_text}

Output in the same pipe-separated format: first append a semicolon and a JSON object with the delivery score (REQUIRED on every line), then optionally a semicolon and a short validation note, e.g.:
...original line...; {{"delivery_efficiency": 8}}; validation note
The JSON object is MANDATORY — every line MUST contain exactly one JSON object."""
    if agent == "safety":
        return f"""Assess the overall BIOSAFETY (biosafety) of each candidate below: cytotoxicity, organ damage (liver/kidney/spleen/brain), in-vivo reactions (hemolysis, inflammation, immunogenicity), environmental risk, and structural stability (ion leaching for nano candidates). Combine into ONE biosafety score 1-10 (10 = safest).

Candidates:
{part_text}

Output: ONE line per candidate with the original fields UNCHANGED, then append a semicolon and a JSON object with the biosafety score, e.g.:
...original line...; {{"biosafety": 8}}"""
    if agent == "mechanism":
        return f"""For the following candidates, explain:
1. The molecular mechanism behind the assigned AD_Mechanism and how it connects to Alzheimer's therapy
2. Score MULTI-TARGET SYNERGY POTENTIAL (multi-target synergy potential, 1-10): capacity of the candidate to engage multiple targets/pathways synergistically (10 = strong multi-target synergy)
3. Score EFFECT DURABILITY (effect durability, 1-10): expected persistence of the therapeutic effect — dosing frequency, resistance/tolerance risk, microbiome or epigenetic memory (10 = most durable)

Candidates:
{part_text}

Output: ONE line per candidate with the original fields, then append a semicolon and your mechanism explanation, then append another semicolon and a JSON object with BOTH scores, e.g.:
...original line...; mechanism explanation; {{"multi_target_synergy": 8, "durability": 7}}"""
    raise ValueError(f"unknown expert agent: {agent}")


# ---------------------------------------------------------------------------
# coordinator prompt
# ---------------------------------------------------------------------------

_AGENTS_ROSTER = """Available agents:
- designer: Creative material design — generates candidates (nanomaterials, small molecules, biologics) with all required fields
- manufacturing: Manufacturability assessment — scores production controllability, scalability, and precise dose control
- delivery: Target-tissue delivery scoring — scores how efficiently a candidate reaches its intended target tissue
- safety: Biosafety assessment — scores overall biosafety
- mechanism: Mechanism mining — explains mechanisms, scores multi-target synergy and effect durability
- ranker: Comparison & summary — ranks candidates and produces the final report"""

ROUTING_RULE = (
    'Routing rule: set "needs_pipeline": true ONLY when the user request asks '
    "to design, screen, rank, or evaluate candidate materials/drugs. For any "
    "other request (questions about the system itself, domain knowledge Q&A, "
    'explanations, casual chat), set "needs_pipeline": false and put the single '
    'best-suited agent to answer in "agents_needed" (use "ranker" when unsure).'
)


def coordinator_prompt(toa_goal: str, needs_pipeline: bool = False) -> str:
    """Coordinator (task orchestration) prompt.

    ``needs_pipeline=False`` is the CLI variant (the CLI always runs the full
    pipeline, so no routing decision is requested). ``needs_pipeline=True`` is
    the web-chat variant (adds the needs_pipeline field + routing rule).
    """
    plan = (
        "Output ONLY a JSON task plan:\n"
        "{\n"
        '  "intent": "brief analysis of what the workflow needs",\n'
        + ('  "needs_pipeline": true,\n' if needs_pipeline else '')
        + '  "agents_needed": ["..."],\n'
        '  "task_sequence": [{"agent": "...", "task": "..."}],\n'
        '  "data_flow": "how outputs move between agents"\n'
        "}"
    )
    routing = ("\n\n" + ROUTING_RULE) if needs_pipeline else ""
    return (
        "You are the Task Orchestration Agent (coordinator). Route the following "
        "workflow to the available agents.\n\n"
        f"Workflow goal: {toa_goal}\n\n"
        f"{_AGENTS_ROSTER}\n\n"
        f"{plan}{routing}"
    )


DIRECT_ANSWER_TEMPLATE = """You are an expert assistant of the Nano-Bio Evaluator multi-agent system (Alzheimer's gut-brain-axis intervention discovery spanning nanomaterials, small-molecule drugs, and biologics).

Answer the user's request directly and concisely, in the user's language. If the question is about the system's agents or workflow, answer accurately from this roster: coordinator (task orchestration/routing), designer (candidate design), manufacturing (manufacturability / production-QC scoring), delivery (target-tissue delivery efficiency), safety (biosafety), mechanism (mechanism mining), ranker (comparison & summary).

User request: {message}"""

VALID_ANSWER_AGENTS = (
    "ranker", "coordinator", "mechanism", "delivery", "safety",
    "manufacturing", "designer", "extractor",
)


# ---------------------------------------------------------------------------
# designer prompt
# ---------------------------------------------------------------------------

def designer_prompt(count: int, n: int, total_batches: int, focus: str,
                    format_block: str, exclusion: str = "") -> str:
    """Designer (candidate generation) prompt for one batch."""
    return (
        f"Design {count} candidates that have been REPORTED in peer-reviewed "
        "literature and achieve HIGH comprehensive ASA scores (combining "
        "antibacterial, enzyme-like activity, and biosafety).\n\n"
        f"This is batch {n} of {total_batches} — {focus}{exclusion}\n\n"
        f"{format_block}"
    )


# ---------------------------------------------------------------------------
# ranker prompt
# ---------------------------------------------------------------------------

def ca_structure(is_current: bool) -> str:
    if is_current:
        return """Report structure:
1. Total count by Drug_Type (nano_formulation/biologic/small_molecule/other)
2. Distribution of Target_Category (gut_targeted_regulation/CNS_intervention_neurorepair/signaling_pathway_modulation/peripheral_nerve_regulation/epigenetic_regulation)
3. Distribution of Action_Mode (microbiota_ratio_modulation/immune_inflammation_modulation/probiotic_prebiotic_supplementation/metabolite_modulation/active_substance_delivery)
4. Distribution of AD_Mechanism (gut_microbiome_axis/amyloid_tau_targeting/neuroprotection/neuroinflammation_modulation/synaptic_function_modulation)
5. Top 10 highest ASA score candidates with their full details
6. Key patterns: which drug types tend to have which AD mechanisms?
7. Recommendations for Alzheimer's therapy"""
    return """Report structure:
1. Total count by Modality (nanocluster/nanoparticle/single_atom/dual_atom/small_molecule/biologic)
2. Distribution of disease intervention methods
3. Distribution of mechanisms
4. NADH activity rate (YES count / total)
5. Top 10 highest ASA score candidates with their full details
6. Key patterns: which modalities tend to have which intervention types?
7. Recommendations for Alzheimer's therapy via gut-brain axis"""


def build_ca_prompt(designer_text: str, delivery_text: str, mechanism_text: str,
                    is_current: bool, trunc: dict) -> str:
    """Ranker (comparison & summary) prompt, with the configured truncations."""
    return (
        "Generate a comprehensive summary report from the 100 candidates below.\n\n"
        f"{ca_structure(is_current)}\n\n"
        "Candidates:\n"
        f"{designer_text[:trunc['designer']]}\n\n"
        "delivery validation:\n"
        f"{delivery_text[:trunc['delivery']]}\n\n"
        "mechanism analysis:\n"
        f"{mechanism_text[:trunc['mechanism']]}"
    )
