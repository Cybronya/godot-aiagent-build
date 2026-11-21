#!/usr/bin/env python3
"""Phase 1.75 Batch C — targeted evidence reanalysis (review-only).

Re-analyses a fixed set of existing External Analysis records with the hardened
parser (parser_version 1.75) and writes everything into an isolated, versioned
workspace:

    .ai/learning/external_code/reanalysis/parser_1.75/

Nothing in the official trees is written:

    .ai/learning/external_code/analysis/          (read only)
    .ai/learning/external_code/feature_links/     (read only)
    .ai/learning/candidate_workspace/             (read only)
    Features/**                                   (read only)

A reanalysis record is *evidence input for human review*, never a qualified
feature, link or candidate. Linkage classifications produced here are written to
`linkage_evaluation/` and are never promoted into the official record set.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DOTAI = PROJECT_ROOT / ".ai"
for _path in (str(DOTAI / "tools" / "learning"),
              str(DOTAI / "tools" / "external_code"),
              str(DOTAI / "tools" / "feature_registry"),
              str(DOTAI / "skills" / "foundation" / "godot-gdscript" / "tools")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import external_code_understanding as ext  # noqa: E402
import feature_linkage as linkage  # noqa: E402

ANALYSIS_DIR = DOTAI / "learning" / "external_code" / "analysis"
LINKAGE_DIR = DOTAI / "learning" / "external_code" / "feature_links"
CANDIDATE_DIR = DOTAI / "learning" / "candidate_workspace" / "candidates"
WORKSPACE_DIR = DOTAI / "learning" / "external_code" / "reanalysis" / "parser_1.75"

TARGETS = {
    "ext-73c80a3db6d71e48": "HealthResource.gd",
    "ext-ab693f3d6ef9439c": "HealthBar.gd (godot-open-rts)",
    "ext-1d204b35464cf388": "Stats.gd",
    "ext-23949c1378c49203": "blackboard.gd",
}

PROVENANCE_KEYS = ("repo", "source_path", "commit_sha", "commit_sha_full",
                   "source_url", "input_digest", "source_digest", "license",
                   "license_status", "license_text_present", "license_source",
                   "provenance_status", "file_type")

SYMBOL_GROUPS = ("functions", "signals", "exports", "variables", "constants",
                 "properties")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
                    + "\n", encoding="utf-8")


def digest_file(path: Path) -> str:
    return ext._digest(path.read_bytes())


def snapshot() -> dict:
    """Read-only digest snapshot of every official artefact this phase must not change."""
    items = {}
    for directory, pattern in ((ANALYSIS_DIR, "*.json"), (LINKAGE_DIR, "*.json"),
                               (CANDIDATE_DIR, "*.json")):
        for path in sorted(directory.glob(pattern)):
            items[str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")] = digest_file(path)
    for extra in (DOTAI / "learning" / "candidate_workspace" / "WORKSPACE.json",
                  DOTAI / "learning" / "external_code" / "index.json"):
        if extra.is_file():
            items[str(extra.relative_to(PROJECT_ROOT)).replace("\\", "/")] = \
                digest_file(extra)
    return {"file_count": len(items), "files": items}


def metadata_from_record(record: dict) -> dict:
    """Rebuild the collector metadata from the record so provenance is identical."""
    repo = str(record.get("repo") or "")
    return {
        "repo": repo,
        "full_name": repo,
        "repo_slug": repo.replace("/", "__"),
        "repo_path": record.get("source_path"),
        "source_path": record.get("source_path"),
        "snippet_id": record.get("snippet_id"),
        "domain": record.get("domain"),
        "commit_sha": record.get("commit_sha"),
        "commit_sha_full": record.get("commit_sha_full"),
        "source_url": record.get("source_url"),
        "license": record.get("license"),
        "license_status": record.get("license_status"),
        "license_text_present": record.get("license_text_present"),
        "license_source": record.get("license_source"),
    }


def symbol_index(record: dict) -> dict:
    index: dict[str, dict] = {}
    symbols = record.get("symbols") or {}
    for group in SYMBOL_GROUPS:
        for item in symbols.get(group) or []:
            name = str(item.get("name") or "")
            if not name:
                continue
            index["%s:%s" % (group, name)] = dict(item, _group=group)
    return index


def diff_records(old: dict, new: dict) -> dict:
    before, after = symbol_index(old), symbol_index(new)
    added = [after[key] for key in sorted(set(after) - set(before))]
    removed = [before[key] for key in sorted(set(before) - set(after))]
    changed = []
    for key in sorted(set(before) & set(after)):
        previous, current = before[key], dict(after[key], _group=before[key]["_group"])
        fields = {}
        for field in ("type", "value", "line", "end_line", "params", "returns",
                      "declaration_kind", "has_initializer", "initializer_kind",
                      "has_getter", "has_setter", "is_exported", "is_onready",
                      "is_static"):
            if previous.get(field) != current.get(field):
                fields[field] = {"old": previous.get(field), "new": current.get(field)}
        annotations_old = [a.get("name") for a in previous.get("annotations") or []]
        annotations_new = [a.get("name") for a in current.get("annotations") or []]
        if annotations_old != annotations_new:
            fields["annotations"] = {"old": annotations_old, "new": annotations_new}
        accessors_old = [(a.get("kind"), a.get("line"))
                         for a in previous.get("accessors") or []]
        accessors_new = [(a.get("kind"), a.get("line"))
                         for a in current.get("accessors") or []]
        if accessors_old != accessors_new:
            fields["accessors"] = {"old": accessors_old, "new": accessors_new}
        if fields:
            changed.append({"symbol": key, "fields": fields})
    coverage_before = old.get("syntax_coverage_status", "(absent: pre-1.75 record)")
    coverage_after = new.get("syntax_coverage_status", "(absent)")
    return {
        "symbols_added": added,
        "symbols_removed": removed,
        "symbols_changed": changed,
        "counts": {
            "before": {group: len((old.get("symbols") or {}).get(group) or [])
                       for group in SYMBOL_GROUPS},
            "after": {group: len((new.get("symbols") or {}).get(group) or [])
                      for group in SYMBOL_GROUPS},
        },
        "status": {
            "analysis_status": {"old": old.get("analysis_status"),
                                "new": new.get("analysis_status")},
            "parse_status": {"old": old.get("parse_status"),
                             "new": new.get("parse_status")},
            "syntax_coverage_status": {"old": coverage_before, "new": coverage_after},
            "analysis_completeness": {
                "old": old.get("analysis_completeness", "(absent: pre-1.75 record)"),
                "new": new.get("analysis_completeness")},
        },
        "unsupported_constructs": new.get("unsupported_constructs") or [],
        "unrecognized_declarations": new.get("unrecognized_declarations") or [],
        "new_limitations": [item for item in (new.get("limitations") or [])
                            if item not in (old.get("limitations") or [])],
        "dropped_limitations": [item for item in (old.get("limitations") or [])
                                if item not in (new.get("limitations") or [])],
    }


def verify_locations(new: dict, reference_text: str) -> list[dict]:
    """Every reported declaration line must really contain that declaration."""
    lines = reference_text.splitlines()
    problems = []
    for group in SYMBOL_GROUPS:
        for item in (new.get("symbols") or {}).get(group) or []:
            number = int(item.get("line") or 0)
            name = str(item.get("name") or "")
            if group == "functions":
                start = int(item.get("start_line") or number)
                number = start
            if not (1 <= number <= len(lines)):
                problems.append({"symbol": name, "group": group, "line": number,
                                 "problem": "line out of range"})
                continue
            text = lines[number - 1]
            if not text.strip():
                problems.append({"symbol": name, "group": group, "line": number,
                                 "problem": "reported line is blank"})
            elif name not in text:
                problems.append({"symbol": name, "group": group, "line": number,
                                 "problem": "reported line does not contain the symbol",
                                 "text": text.strip()[:80]})
    return problems


def reanalyse_one(analysis_id: str) -> dict:
    old = load_json(ANALYSIS_DIR / ("%s.json" % analysis_id))
    result = {"analysis_id": analysis_id, "source_path": old.get("source_path"),
              "label": TARGETS.get(analysis_id, str(old.get("source_path") or "")),
              "original_analysis_status":
              old.get("analysis_status")}
    reference = Path(str(old.get("reference_path") or ""))
    if not reference.is_file():
        result["stopped"] = "reference copy is missing"
        return result
    reference_bytes = reference.read_bytes()
    if ext._digest(reference_bytes) != old.get("input_digest"):
        result["stopped"] = "reference copy digest differs from the recorded input_digest"
        return result
    source_file = Path(str(old.get("source_file_path") or ""))
    if not source_file.is_file():
        result["stopped"] = "pinned source file is missing"
        return result
    if digest_file(source_file) != old.get("source_digest"):
        result["stopped"] = "source digest changed; reanalysis stopped"
        return result

    new = ext.analyze_external_code(reference, metadata_from_record(old))
    mismatches = [key for key in PROVENANCE_KEYS
                  if old.get(key) != new.get(key)]
    if mismatches:
        result["stopped"] = "provenance differs: %s" % ", ".join(mismatches)
        result["provenance_mismatches"] = {key: {"old": old.get(key), "new": new.get(key)}
                                           for key in mismatches}
        return result

    diff = diff_records(old, new)
    problems = verify_locations(new, reference_bytes.decode("utf-8", errors="replace"))
    result.update({
        "reanalysis_id": new["analysis_id"],
        "parser_version": {"old": old.get("parser_version"),
                           "new": new.get("parser_version")},
        "provenance_verified": True,
        "source_digest": {"old": old.get("source_digest"),
                          "new": new.get("source_digest"),
                          "same": old.get("source_digest") == new.get("source_digest")},
        "analysis_status": {"old": old.get("analysis_status"),
                            "new": new.get("analysis_status")},
        "coverage": new.get("symbols", {}).get("coverage") or {},
        "diff": diff,
        "location_problems": problems,
        "location_checks": sum(len((new.get("symbols") or {}).get(group) or [])
                               for group in SYMBOL_GROUPS),
        "new_record": new,
    })
    return result


def linkage_review(reanalysis: list[dict]) -> dict:
    """Re-evaluate linkage for the reanalysed records into a scratch directory."""
    ready = [item for item in reanalysis if item.get("new_record")]
    if not ready:
        return {"evaluated": 0, "pairs": []}
    scratch = Path(tempfile.mkdtemp(prefix="phase175-linkage-"))
    analysis_dir = WORKSPACE_DIR / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    for item in ready:
        dump_json(analysis_dir / ("%s.json" % item["reanalysis_id"]), item["new_record"])
    summary = linkage.build_linkages([item["reanalysis_id"] for item in ready],
                                     analysis_dir=analysis_dir, out_dir=scratch)
    old_to_new = {item["analysis_id"]: item["reanalysis_id"] for item in ready}
    pairs = []
    for item in ready:
        for feature_id in linkage.PILOT_FEATURES:
            old_path = LINKAGE_DIR / ("%s__%s.json" % (item["analysis_id"], feature_id))
            new_path = scratch / ("%s__%s.json" % (item["reanalysis_id"], feature_id))
            old_record = load_json(old_path) if old_path.is_file() else None
            new_record = load_json(new_path) if new_path.is_file() else None
            pairs.append({
                "analysis_id": item["analysis_id"],
                "reanalysis_id": item["reanalysis_id"],
                "feature_id": feature_id,
                "label": item["label"],
                "original_classification": (old_record or {}).get("linkage_classification",
                                                                  "NO_RECORD"),
                "reevaluated_classification": (new_record or {}).get(
                    "linkage_classification", "NOT_EVALUABLE"),
                "original_linkage_id": (old_record or {}).get("linkage_id"),
                "changed": (old_record or {}).get("linkage_classification")
                != (new_record or {}).get("linkage_classification"),
                "reevaluated_symbols": (new_record or {}).get("pair_evaluation", {}).get(
                    "matched_symbols")
                or (new_record or {}).get("pair_evaluation", {}).get("shared_symbols")
                or [],
                "original_symbols": (old_record or {}).get("pair_evaluation", {}).get(
                    "matched_symbols")
                or (old_record or {}).get("pair_evaluation", {}).get("shared_symbols")
                or [],
                "review_status": "REVIEW_ONLY_NOT_WRITTEN",
                "old_to_new": old_to_new,
            })
    return {"evaluated": len(ready), "scratch": str(scratch),
            "built": len(summary.get("built") or []), "pairs": pairs,
            "unevaluable": summary.get("unevaluable") or []}


def candidate_impact(reanalysis: list[dict], pairs: list[dict]) -> dict:
    changed_symbols = {}
    for item in reanalysis:
        if not item.get("diff"):
            continue
        names = [entry["name"] for entry in item["diff"]["symbols_added"]]
        changed_symbols[item["analysis_id"]] = names
    impact = []
    for path in sorted(CANDIDATE_DIR.glob("*.json")):
        candidate = load_json(path)
        refs = candidate.get("evidence_refs") or []
        touched = []
        for ref in refs:
            for key in ("analysis_id", "source_analysis_id"):
                if ref.get(key) in changed_symbols:
                    touched.append(ref)
        new_pairs = [pair for pair in pairs
                     if pair["analysis_id"] in changed_symbols
                     and pair["feature_id"] == candidate.get("feature_id")]
        impact.append({
            "candidate_id": candidate.get("candidate_id"),
            "feature_id": candidate.get("feature_id"),
            "candidate_status": candidate.get("candidate_status"),
            "policy_version": candidate.get("policy_version"),
            "content_digest": candidate.get("content_digest"),
            "evidence_refs": refs,
            "refs_touched_by_reanalysis": touched,
            "new_symbols_in_referenced_sources": {
                analysis_id: changed_symbols[analysis_id]
                for analysis_id in changed_symbols
                if any(ref.get("analysis_id") == analysis_id for ref in refs)},
            "reevaluated_pairs": [
                {key: pair[key] for key in ("analysis_id", "feature_id",
                                            "original_classification",
                                            "reevaluated_classification", "changed")}
                for pair in new_pairs],
            "candidate_mutated": False,
            "review_required": bool(touched) or any(pair["changed"] for pair in new_pairs),
        })
    return {"candidates": impact, "candidate_count": len(impact)}


def main() -> int:
    global WORKSPACE_DIR
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids", nargs="*", default=sorted(TARGETS),
                        help="analysis ids to reanalyse (default: the Batch C scope)")
    parser.add_argument("--out", default=str(WORKSPACE_DIR))
    args = parser.parse_args()
    WORKSPACE_DIR = Path(args.out)

    baseline = snapshot()
    reanalysis = [reanalyse_one(analysis_id) for analysis_id in args.ids]
    stopped = [item for item in reanalysis if item.get("stopped")]

    review = linkage_review(reanalysis)
    candidates = candidate_impact(reanalysis, review["pairs"])

    for item in reanalysis:
        record = item.pop("new_record", None)
        if record:
            dump_json(WORKSPACE_DIR / "analysis" / ("%s.json" % item["reanalysis_id"]),
                      record)
            dump_json(WORKSPACE_DIR / "diff" / ("%s.json" % item["analysis_id"]),
                      {"analysis_id": item["analysis_id"],
                       "reanalysis_id": item["reanalysis_id"],
                       "label": item["label"], **item["diff"]})
    for pair in review["pairs"]:
        dump_json(WORKSPACE_DIR / "linkage_evaluation"
                  / ("%s__%s.json" % (pair["analysis_id"], pair["feature_id"])), pair)

    manifest = {
        "schema": "external_code_reanalysis_workspace",
        "schema_version": 1,
        "phase": "1.75-C",
        "generated_with_parser": ext.PARSER_VERSION,
        "review_only": True,
        "official_analysis_overwritten": False,
        "official_linkage_overwritten": False,
        "candidate_mutated": False,
        "baseline_snapshot": baseline,
        "targets": {item["analysis_id"]: {"label": item["label"],
                                          "stopped": item.get("stopped")}
                    for item in reanalysis},
        "reanalysis": reanalysis,
        "linkage_review": review,
        "candidate_impact": candidates,
    }
    dump_json(WORKSPACE_DIR / "WORKSPACE.json", manifest)
    print(json.dumps({
        "workspace": str(WORKSPACE_DIR),
        "stopped": [item["analysis_id"] for item in stopped],
        "added_symbols": {item["analysis_id"]: [entry["name"] for entry
                                                in item["diff"]["symbols_added"]]
                          for item in reanalysis if item.get("diff")},
        "location_problems": {item["analysis_id"]: item["location_problems"]
                              for item in reanalysis if item.get("location_problems")},
        "status_changes": {item["analysis_id"]: item["diff"]["status"]
                           for item in reanalysis if item.get("diff")},
        "linkage_changes": [pair for pair in review["pairs"] if pair["changed"]],
        "candidates": candidates["candidates"],
        "baseline_files": baseline["file_count"],
    }, ensure_ascii=False, indent=2))
    return 1 if stopped else 0


if __name__ == "__main__":
    raise SystemExit(main())
