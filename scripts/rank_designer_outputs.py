#!/usr/bin/env python3
"""
Rank designer-designed materials by self-reported score into a Markdown document.

Mechanical compilation only: fields are preserved VERBATIM from the raw designer
output files (task100_designer_<TS>_part*.txt). Both output eras are parsed:
the current 13-field AD100 contract (Drug_Type/Target_Category/Action_Mode/
AD_Mechanism) and the retired legacy layouts (9/10/11/13 fields, NADH era).
Current records are re-keyed onto the shared legacy key set (Modality <-
Drug_Type, Disease_Intervention <- Target_Category, Mechanism <- AD_Mechanism,
NADH = NA) so scoring, sorting, and table layout stay era-independent.
The only operations are:
  - splitting pipe-separated fields
  - repairing physically fused lines (two records emitted without a newline,
    detected as 2F-1 fields; split point logged in the MD appendix)
  - normalizing legacy 9-field lines (no Chemical_Formula) to 10 fields
  - sorting (deterministic Score_Adj when subscores exist, else self-report)
No content is rewritten, cleaned, translated, or curated.

Usage: python scripts/rank_designer_outputs.py [timestamp] [--rubric path]

Deterministic scoring: when the run directory contains subscores_<TS>.json (from
extract_subscores.py), the PRIMARY sort key is Score_Adj — the deterministic
score from scoring_engine.py + the rubric (default scripts/scoring_rubric.json,
--rubric to re-rank historical subscores with a different rubric WITHOUT
re-running any agent). The designer self-reported score column is kept for
display, renamed SelfReport. Without subscores the self-report ranking is used.
"""

import argparse, json, re, sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from output_utils import find_run_dir, OUTPUT_ROOT
import output_schema
import scoring_engine

OUTPUT = OUTPUT_ROOT

FIELDS = output_schema.FIELDS_LEGACY               # legacy 11-field format
LEGACY_FIELDS = output_schema.LEGACY_LENGTHS   # runs before Ligand (10) / before Chemical_Formula+Ligand (9)
RECORD_LENGTHS = (*LEGACY_FIELDS, len(output_schema.FIELDS_LEGACY), 12, len(output_schema.FIELDS_LEGACY_MODALITY))  # 9/10/11/12(legacy-modality minus Ligand)/13

# Ranking drops only Size_nm; SMILES / Target_UniProt are shown right after
# Chemical_Formula (Phase 4 three-modality extension). Modality (legacy records:
# Material_Category, relocated verbatim by output_schema) is shown right after
# Material_Name per project requirement.
TABLE_FIELDS = ["Material_Name", "Modality", "Chemical_Formula", "SMILES", "Target_UniProt",
                "Ligand", "Core_Elements",
                "Self_Score(1-10)", "Disease_Intervention", "Mechanism",
                "NADH_Activity(YES/NO)", "Key_Features"]
SELF_SCORE = output_schema.SELF_SCORE  # canonical self-score key (legacy "ASA_Score(1-10)" accepted)
NAME = "Material_Name"
MODALITY = "Modality"
SMILES = "SMILES"
UNIPROT = "Target_UniProt"
ELEMENTS = "Core_Elements"
INTERVENTION = "Disease_Intervention"
MECHANISM = "Mechanism"
NADH = "NADH_Activity(YES/NO)"

NAME_RE = re.compile(r"[A-Z][A-Za-z0-9]*_[A-Za-z0-9_\-]*")

# Display-only column names for the deterministic-scoring ranking mode.
SELF_REPORT = "SelfReport"
SCORE_ADJ = "Score_Adj"


def _normalize(cells):
    """Legacy records -> FIELDS_LEGACY_MODALITY dict (output_schema.normalize_record);
    None for unrecognized column counts."""
    return output_schema.normalize_record(cells)


def _detect_era(text: str):
    """Run era of one designer output file, from its header line: the field
    spec emitted by the designer prompt starts with 'Material_Name'; the second
    cell is 'Drug_Type' for current (AD100) files and 'Modality' /
    'Material_Category' for legacy files. None when no header is found."""
    for line in text.split("\n")[:10]:
        if "|" not in line:
            continue
        cells = [c.strip() for c in line.split("|")]
        if cells[0] != "Material_Name" or len(cells) < 2:
            continue
        if cells[1] == "Drug_Type":
            return "current"
        if cells[1] in ("Modality", "Material_Category"):
            return "legacy"
    return None


def _looks_current(cells) -> bool:
    """Per-line vote for headerless files: a current record carries valid enum
    values in ALL THREE classification slots (Drug_Type/Target_Category/
    AD_Mechanism are mandated verbatim by the designer format block)."""
    return (len(cells) >= 5
            and cells[1] in output_schema.DRUG_TYPES
            and cells[2] in output_schema.TARGET_CATEGORIES
            and cells[4] in output_schema.AD_MECHANISMS)


def _normalize_any(cells, file_era: "str | None" = None):
    """Parse one record line of either era.

    Returns (record_dict_or_None, is_current). Current-schema lines are
    re-keyed onto the shared legacy key set; legacy lines go through
    output_schema.normalize_record unchanged. file_era (from _detect_era)
    resolves the 13-cell ambiguity: Modality and Drug_Type overlap on
    'small_molecule'/'biologic', so cells[1] alone cannot discriminate.
    Without a header, lines passing the full three-enum vote parse as current
    and everything else falls back to legacy (the historical behavior).
    """
    if file_era == "legacy":
        return output_schema.normalize_record(cells), False
    if file_era == "current" or _looks_current(cells):
        cur = output_schema.parse_record_current(cells)
        if cur is not None:
            return {
                "Material_Name": cur["Material_Name"],
                "Modality": cur["Drug_Type"],
                "Chemical_Formula": cur["Chemical_Formula"],
                "SMILES": cur["SMILES"],
                "Target_UniProt": cur["Target_UniProt"],
                "Ligand": cur["Ligand"],
                "Core_Elements": cur["Core_Elements"],
                SELF_SCORE: cur[SELF_SCORE],
                "Disease_Intervention": cur["Target_Category"],
                "Mechanism": cur["AD_Mechanism"],
                NADH: "NA",
                "Key_Features": cur["Key_Features"],
            }, True
        if file_era == "current":
            return None, True  # era known: a non-conforming line is an anomaly
    return output_schema.normalize_record(cells), False


# Display headers per era: current runs re-label the classification columns and
# drop the legacy-only NADH column. Internal keys stay era-independent.
_CURRENT_HEADERS = {MODALITY: "Drug_Type", INTERVENTION: "Target_Category",
                    MECHANISM: "AD_Mechanism", NADH: None}


def display_pairs(is_current: bool):
    """[(header, key), ...] table columns for the run's era."""
    pairs = []
    for f in TABLE_FIELDS:
        h = _CURRENT_HEADERS.get(f, f) if is_current else f
        if h is None:
            continue
        pairs.append((h, f))
    return pairs


def load_subscores(ts: str):
    """Return the extract_subscores payload for this run, or None."""
    f = find_run_dir(ts) / f"subscores_{ts}.json"
    if not f.exists():
        return None
    return json.loads(f.read_text(encoding="utf-8"))


def compute_score_map(payload: dict, rubric_path=None):
    """(rubric, {material_name: compute_score result}) from a subscores payload."""
    rubric = scoring_engine.load_rubric(rubric_path or scoring_engine.DEFAULT_RUBRIC)
    return rubric, {name: scoring_engine.compute_score(axes, rubric)
                    for name, axes in payload.get("materials", {}).items()}


def parse_records(ts: str):
    """Returns (src_files, records, fused, bad, is_current)."""
    parts = sorted(find_run_dir(ts).glob(f"task100_designer_{ts}_part*.txt"))
    if not parts:
        raise SystemExit(f"No task100_designer_{ts}_part*.txt found in {find_run_dir(ts)}")

    records, fused, bad = [], [], []
    saw_current = False
    for p in parts:
        text = p.read_text(encoding="utf-8")
        file_era = _detect_era(text)
        for line in text.split("\n"):
            line = line.strip()
            if not line or "|" not in line:
                continue
            cells = [c.strip() for c in line.split("|")]
            if cells[0] == "Material_Name":
                continue  # field-spec header line emitted by the designer prompt
            if len(cells) in RECORD_LENGTHS:
                rec, is_cur = _normalize_any(cells, file_era)
                saw_current = saw_current or is_cur
                if rec is not None:
                    records.append(rec)
                else:
                    bad.append((p.name, line))
            elif len(cells) in (2 * len(FIELDS) - 1, 2 * len(output_schema.FIELDS_LEGACY_MODALITY) - 1, 19, 17):
                # Two records fused on one physical line: the glue cell holds
                # "<featuresA><nameB>". Split at the last name-like token.
                glue_idx = (len(cells) + 1) // 2 - 1
                m = list(NAME_RE.finditer(cells[glue_idx]))
                if m:
                    cut = m[-1].start()
                    rec_a = cells[:glue_idx] + [cells[glue_idx][:cut].strip()]
                    rec_b = [cells[glue_idx][cut:].strip()] + cells[glue_idx + 1:]
                    for cells_i in (rec_a, rec_b):
                        rec, is_cur = _normalize_any(cells_i, file_era)
                        saw_current = saw_current or is_cur
                        if rec is not None:
                            records.append(rec)
                        else:
                            bad.append((p.name, line))
                    fused.append((p.name, cells[glue_idx]))
                else:
                    bad.append((p.name, line))
            else:
                bad.append((p.name, line))
    return [p.name for p in parts], records, fused, bad, saw_current


def main():
    parser = argparse.ArgumentParser(description="Rank designer outputs (deterministic scoring when subscores exist)")
    parser.add_argument("ts", nargs="?", help="run timestamp (default: latest)")
    parser.add_argument("--rubric", default=None,
                        help="scoring rubric JSON (default: scripts/scoring_rubric.json); "
                             "re-ranks historical subscores without re-running agents")
    args = parser.parse_args()
    ts = args.ts
    if ts is None:
        candidates = (list(OUTPUT.glob("task100_designer_*_part1.txt"))
                      + list(OUTPUT.glob("run_*/task100_designer_*_part1.txt")))
        if not candidates:
            raise SystemExit("No task100_designer_*_part1.txt found under outputs/ — run the pipeline first")
        latest = max(candidates, key=lambda p: p.stat().st_mtime)
        ts = re.search(r"task100_designer_(\d+)_part1", latest.name).group(1)

    src_files, records, fused, bad, is_current = parse_records(ts)

    # Phase 3: deterministic score from extracted subscores, if present.
    sub_payload = load_subscores(ts)
    rubric, score_map = (None, {})
    if sub_payload is not None:
        rubric, score_map = compute_score_map(sub_payload, args.rubric)

    def score(rec):
        try:
            return float(rec[SELF_SCORE])
        except ValueError:
            return float("nan")

    valid = [r for r in records if score(r) == score(r)]  # drop NaN scores
    nan_score = [r for r in records if score(r) != score(r)]
    if score_map:
        # Primary key: deterministic Score_Adj; materials without extracted
        # subscores sink to the bottom (nothing is invented for them).
        valid.sort(key=lambda r: (-score_map[r[NAME]]["total_adj"], r[NAME])
                   if r[NAME] in score_map else (float("inf"), r[NAME]))
    else:
        valid.sort(key=lambda r: (-score(r), r[NAME]))

    def esc(s):
        return s.replace("|", "\\|")

    out = []
    # Database-verified formulas (tool data, NOT agent output) — present when
    # scripts/formula_lookup.py has been run for this timestamp. formula_lookup
    # writes the map into the run directory; the flat outputs/ root is only a
    # fallback for legacy runs saved before the run-directory convention.
    db_map, db_source = {}, None
    map_file = find_run_dir(ts) / f"task100_formula_map_{ts}.json"
    if not map_file.exists():
        map_file = OUTPUT / f"task100_formula_map_{ts}.json"
    if map_file.exists():
        import json as _json
        payload = _json.loads(map_file.read_text(encoding="utf-8"))
        db_map = payload.get("materials", {})
        db_source = payload.get("source")

    out.append(f"# Material score ranking summary (run {ts})\n")
    out.append("> This document was mechanically generated by `scripts/rank_designer_outputs.py`.")
    if score_map:
        out.append(f"> **Primary sort key: Score_Adj (deterministically computed, scoring_rubric, scripts/scoring_engine.py; `--rubric` re-computes historical subscores with a different rubric without re-running any agent).**")
        out.append("> SelfReport is the designer self-reported score, shown for display only and not used for sorting. Subscores come from the JSON tail of the raw manufacturing/delivery/safety/mechanism outputs (mechanically extracted by scripts/extract_subscores.py).")
    else:
        out.append("> All fields are preserved **verbatim** from the raw designer agent output, sorted only by self-reported score descending, with no content rewriting, cleaning, or curation.")
    out.append("> Per project goals, the ranking drops only the size value (Size_nm). The classification column shows Modality for legacy runs and Drug_Type for current (AD100) runs; legacy Material_Category is relocated verbatim.")
    if db_map:
        out.append(f"> The DB_Formula column is the database-tool verification result (source: {db_source}, scripts/formula_lookup.py), not agent output; the Chemical_Formula column remains the raw agent output.")
    out.append(f"> Source files: {', '.join(src_files)}\n")

    out.append(f"- Total materials: **{len(valid)}**")
    out.append(f"- Score range: {score(valid[-1])} - {score(valid[0])}" if valid else "")
    if score_map:
        adj = [score_map[r[NAME]]["total_adj"] for r in valid if r[NAME] in score_map]
        out.append(f"\n- Score_Adj range: {min(adj):.3f} - {max(adj):.3f} (scoring_rubric)" if adj else "")
    out.append("")

    mod_freq = Counter(r[MODALITY].strip() for r in valid)
    cat_freq = Counter(r[INTERVENTION].strip() for r in valid)
    mech_freq = Counter(r[MECHANISM].strip() for r in valid)
    smiles_ok = sum(1 for r in valid if r[SMILES].strip() not in ("", "NA"))
    uniprot_ok = sum(1 for r in valid if r[UNIPROT].strip() not in ("", "NA"))

    era = "current (AD100)" if is_current else "legacy-modality"
    type_label = "Drug_Type" if is_current else "Modality"
    type_enums = output_schema.DRUG_TYPES if is_current else output_schema.MODALITIES
    out.append(f"## Classification statistics ({era} run)\n")
    out.append("| Metric | Value |")
    out.append("|---|---|")
    out.append(f"| {type_label} distribution | " + ", ".join(f"{m}x{mod_freq.get(m, 0)}" for m in type_enums) + " |")
    out.append("| " + ("Target_Category" if is_current else "Disease_Intervention") + " distribution | " + ", ".join(f"{k}x{v}" for k, v in cat_freq.most_common()) + " |")
    out.append("| " + ("AD_Mechanism" if is_current else "Mechanism") + " distribution | " + ", ".join(f"{k}x{v}" for k, v in mech_freq.most_common()) + " |")
    out.append(f"| SMILES not NA | **{smiles_ok}** |")
    out.append(f"| Target_UniProt not NA | **{uniprot_ok}** |")

    # Neutral element composition statistics (no element-level goal attached)
    all_elem = Counter()
    for r in valid:
        for e in r[ELEMENTS].split(","):
            e = e.strip()
            if e and e not in ("O", "N", "C"):
                all_elem[e] += 1
    out.append(f"| Element frequency Top8 (excl. O/N/C, per material) | {', '.join(f'{e}x{n}' for e, n in all_elem.most_common(8))} |\n")

    out.append("## Full ranking\n")
    pairs = display_pairs(is_current)
    # In deterministic-scoring mode the self-report column is renamed and the
    # computed Score_Adj column is inserted right before it.
    base_pairs = []
    for h, k in pairs:
        if score_map and k == SELF_SCORE:
            base_pairs += [(SCORE_ADJ, "__adj__"), (SELF_REPORT, SELF_SCORE)]
        else:
            base_pairs.append((h, k))
    db_pos = next(i for i, (h, k) in enumerate(base_pairs) if k == "Chemical_Formula") + 1
    final_pairs = base_pairs[:db_pos] + ([("DB_Formula", "__db__")] if db_map else []) + base_pairs[db_pos:]
    out.append("| Rank | " + " | ".join(h for h, k in final_pairs) + " |")
    out.append("|" + "---|" * (len(final_pairs) + 1))
    for i, r in enumerate(valid, 1):
        cells = []
        for h, k in final_pairs:
            if k == "__db__":
                cells.append((db_map.get(r[NAME]) or {}).get("combined_formula") or "—")
            elif k == "__adj__":
                res = score_map.get(r[NAME])
                cells.append(f"{res['total_adj']:.3f}" if res else "—")
            elif score_map and k == SELF_SCORE:
                cells.append(esc(r[SELF_SCORE]))
            else:
                cells.append(esc(r[k]))
        out.append(f"| {i} | " + " | ".join(cells) + " |")

    # ---- Top-5 per type (primary sort key — `valid` is already sorted) ----
    out.append(f"\n## Top5 grouped by {type_label} (primary sort key)\n")
    observed = list(type_enums) + sorted(
        {r[MODALITY].strip() for r in valid} - set(type_enums))
    for m in observed:
        group = [r for r in valid if r[MODALITY].strip() == m][:5]
        if not group:
            continue
        out.append(f"### {m}\n")
        out.append("| # | Material_Name | " + (SCORE_ADJ if score_map else SELF_SCORE) + " |")
        out.append("|---|---|---|")
        for j, r in enumerate(group, 1):
            if score_map:
                res = score_map.get(r[NAME])
                score = f"{res['total_adj']:.3f}" if res else "—"
            else:
                score = esc(r[SELF_SCORE])
            out.append(f"| {j} | {esc(r[NAME])} | {score} |")
        out.append("")

    if score_map:
        no_sub = [r[NAME] for r in valid if r[NAME] not in score_map]
        partial = [(n, score_map[n]["missing"]) for n in dict.fromkeys(r[NAME] for r in valid)
                   if n in score_map and score_map[n]["missing"]]
        n_extract_missing = len(sub_payload.get("missing", []))
        if no_sub or partial or n_extract_missing:
            out.append("\n---\n\n## Appendix: missing score subscores (counted as 0, never fabricated)\n")
            if no_sub:
                out.append(f"### Materials with no extracted subscores ({len(no_sub)}, listed at the bottom)\n")
                for n in no_sub:
                    out.append(f"- {esc(n)}")
            if partial:
                out.append(f"\n### Partial subscore coverage ({len(partial)} materials, missing dims counted as 0)\n")
                for n, miss in partial:
                    out.append(f"- {esc(n)}: {', '.join(miss)}")
            if n_extract_missing:
                out.append(f"\n### Extraction-failed lines ({n_extract_missing}, see the missing field in subscores_{ts}.json)")

    if fused or bad or nan_score:
        out.append("\n---\n\n## Appendix: format anomalies\n")
        if fused:
            out.append(f"### Fused-line repairs ({len(fused)})\n")
            out.append("Two materials were fused onto one line in the raw output; they were mechanically split at the last material-name marker without changing content. Original fused fields:\n")
            for fname, cell in fused:
                out.append(f"- `{fname}`: …{esc(cell)}")
        if nan_score:
            out.append(f"\n### Unparseable scores ({len(nan_score)}, excluded from ranking)\n")
            for r in nan_score:
                out.append("- " + esc(" | ".join(r[k] for _, k in display_pairs(is_current))))
        if bad:
            out.append(f"\n### Unparseable lines ({len(bad)}, preserved verbatim)\n")
            for fname, line in bad:
                out.append(f"- `{fname}`: {esc(line)}")

    md_path = find_run_dir(ts) / f"ranking_{ts}.md"
    md_path.write_text("\n".join(out) + "\n", encoding="utf-8")
    mode = "Score_Adj (scoring_rubric)" if score_map else "self-report fallback (no subscores)"
    print(f"Wrote {md_path} ({len(valid)} ranked materials, {len(fused)} fused repairs, {len(bad)} unparsed; mode: {mode})")


if __name__ == "__main__":
    main()
