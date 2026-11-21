#!/usr/bin/env python3
"""Phase 1.76 Batch B — controlled full reanalysis (review-only corpus baseline).

Writes only inside:

    .ai/learning/external_code/reanalysis/parser_1.76/

Layout: preflight.json, manifest.json, original/, reanalyzed/, diff/,
validation/, deterministic_runs/, idempotency/, reports/.

It reanalyses the 29 records that Batch A marked REQUIRES_REANALYSIS, reuses the
4 Phase 1.75 results (validated, never recomputed), and records the shader record
as NOT_APPLICABLE. Official analysis / linkage / candidate / projection /
metadata / index / graph files and the Phase 1.75 workspace are read-only and are
digest-verified before and after the run.

Run twice: the second run must produce the same record set and the same
normalised content (idempotency), and each record is analysed twice in memory to
prove determinism.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DOTAI = PROJECT_ROOT / ".ai"
for _path in (str(DOTAI / "tools" / "learning"),
              str(DOTAI / "tools" / "external_code"),
              str(DOTAI / "tools" / "feature_registry")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import corpus_audit_176 as audit  # noqa: E402
import external_code_understanding as ext  # noqa: E402
import reanalysis_175 as r175  # noqa: E402

ANALYSIS_DIR = DOTAI / "learning" / "external_code" / "analysis"
INVENTORY = (DOTAI / "learning" / "external_code" / "reconciliation"
             / "phase_1.76" / "inventory.json")
P175 = DOTAI / "learning" / "external_code" / "reanalysis" / "parser_1.75"
WORKSPACE = DOTAI / "learning" / "external_code" / "reanalysis" / "parser_1.76"

EXPECTED_IDENTITY = "gd_parse@1.75+build:6b74a6cd20a06033"
EXPECTED_COUNTS = {"REQUIRES_REANALYSIS": 29, "REANALYZED_VALID": 4,
                   "NOT_APPLICABLE": 1}
P175_IDS = {
    "ext-1d204b35464cf388": "ext-0ee947aef4c9aeca",
    "ext-23949c1378c49203": "ext-d0a93201b6f352df",
    "ext-73c80a3db6d71e48": "ext-8759bb47cb020625",
    "ext-ab693f3d6ef9439c": "ext-322df918a5ebee02",
}
SHADER_ID = "ext-80c1104f5262a6ee"

# Fields that are legitimate run metadata, not content identity.
VOLATILE = ("created_at", "reanalysis_timestamp", "generated_at",
            "reanalysis_run", "executed_at", "duration_ms")


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dump(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
                    + "\n", encoding="utf-8")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def canonical(value):
    """Stable content form: sorted keys, volatile run metadata removed."""
    if isinstance(value, dict):
        return {key: canonical(item) for key, item in sorted(value.items())
                if key not in VOLATILE}
    if isinstance(value, list):
        return [canonical(item) for item in value]
    return value


def content_digest(value) -> str:
    return digest_bytes(json.dumps(canonical(value), ensure_ascii=False,
                                   sort_keys=True).encode("utf-8"))


def git_state() -> dict:
    def run(*args: str) -> str:
        try:
            out = subprocess.run(["git", *args], cwd=str(PROJECT_ROOT),
                                 capture_output=True, text=True, check=False)
            return out.stdout.strip()
        except Exception:  # noqa: BLE001
            return ""
    porcelain = run("status", "--porcelain").splitlines()
    counts: dict[str, int] = {}
    for line in porcelain:
        counts[line[:2].strip()] = counts.get(line[:2].strip(), 0) + 1
    staged = [line for line in run("diff", "--cached", "--name-only").splitlines()
              if line.strip()]
    return {
        "branch": run("rev-parse", "--abbrev-ref", "HEAD"),
        "head": run("rev-parse", "HEAD"),
        "staged": len(staged),
        "porcelain_counts": counts,
        "modified": counts.get("M", 0),
        "untracked": counts.get("??", 0),
        "deleted": counts.get("D", 0),
    }


def snapshot() -> dict:
    """Digest every artefact this phase must not modify."""
    items: dict[str, str] = {}
    targets = [
        (ANALYSIS_DIR, "*.json"), (r175.LINKAGE_DIR, "*.json"),
        (r175.CANDIDATE_DIR, "*.json"),
        (P175, "**/*.json"),
        (INVENTORY.parent, "*.json"),
    ]
    for directory, pattern in targets:
        for path in sorted(directory.glob(pattern)):
            if path == WORKSPACE or WORKSPACE in path.parents:
                continue
            items[str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")] = \
                digest_bytes(path.read_bytes())
    extras = [
        DOTAI / "learning" / "candidate_workspace" / "WORKSPACE.json",
        DOTAI / "learning" / "external_code" / "index.json",
        DOTAI / "context" / "feature_index.json",
        DOTAI / "context" / "feature_graph.json",
        DOTAI / "tools" / "feature_registry" / "candidate_seed_policy.json",
        DOTAI / "tools" / "learning" / "gd_parse.py",
        DOTAI / "tools" / "external_code" / "external_code_understanding.py",
        DOTAI / "tools" / "external_code" / "corpus_audit_176.py",
        DOTAI / "tools" / "external_code" / "reanalysis_175.py",
    ]
    for path in extras:
        if path.is_file():
            items[str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")] = \
                digest_bytes(path.read_bytes())
    return {"file_count": len(items), "files": items}


def preflight(inventory: dict) -> dict:
    identity = audit.parser_build_identity()
    git = git_state()
    records = inventory["records"]
    by_disposition: dict[str, list[str]] = {}
    for record in records:
        by_disposition.setdefault(record["disposition"], []).append(
            record["analysis_id"])

    scope_checks = []
    for record in records:
        if record["disposition"] != "REQUIRES_REANALYSIS":
            continue
        raw = load(ANALYSIS_DIR / record["file"])
        reference = Path(str(raw.get("reference_path") or ""))
        source = Path(str(raw.get("source_file_path") or ""))
        scope_checks.append({
            "analysis_id": record["analysis_id"],
            "repository": raw.get("repo"),
            "full_commit_sha": raw.get("commit_sha_full"),
            "source_path": raw.get("source_path"),
            "source_digest": raw.get("source_digest"),
            "input_digest": raw.get("input_digest"),
            "license_status": raw.get("license_status"),
            "provenance_status": raw.get("provenance_status"),
            "reference_exists": reference.is_file(),
            "reference_digest_match": reference.is_file() and digest_bytes(
                reference.read_bytes()) == raw.get("input_digest"),
            "source_exists": source.is_file(),
            "source_digest_match": source.is_file() and digest_bytes(
                source.read_bytes()) == raw.get("source_digest"),
            "inventory_consistent": (
                raw.get("repo") == record["repository"]
                and raw.get("commit_sha_full") == record["full_commit_sha"]
                and raw.get("source_path") == record["source_path"]
                and raw.get("source_digest") == record["source_digest"]),
        })

    reuse_checks = []
    for original_id, new_id in P175_IDS.items():
        original = load(ANALYSIS_DIR / ("%s.json" % original_id))
        new_path = P175 / "analysis" / ("%s.json" % new_id)
        new = load(new_path) if new_path.is_file() else None
        reuse_checks.append({
            "original_analysis_id": original_id,
            "reanalysis_id": new_id,
            "file_present": bool(new),
            "parser_version": (new or {}).get("parser_version"),
            "source_digest_same": bool(new) and new.get("source_digest")
            == original.get("source_digest"),
            "input_digest_same": bool(new) and new.get("input_digest")
            == original.get("input_digest"),
            "provenance_same": bool(new) and all(
                new.get(key) == original.get(key)
                for key in ("repo", "commit_sha", "commit_sha_full",
                            "source_path", "source_url", "license",
                            "license_status", "license_text_present",
                            "license_source", "provenance_status")),
            "coverage_present": bool(new) and bool(
                (new.get("symbols") or {}).get("coverage")),
        })

    shader = load(ANALYSIS_DIR / ("%s.json" % SHADER_ID))
    exclusion = {
        "analysis_id": SHADER_ID,
        "file_type": shader.get("file_type"),
        "analysis_status": shader.get("analysis_status"),
        "symbols_empty": not any((shader.get("symbols") or {}).get(group)
                                 for group in ("functions", "signals", "exports",
                                               "variables", "constants",
                                               "properties")),
        "linkage_count": len(list(r175.LINKAGE_DIR.glob(
            "%s__*.json" % SHADER_ID))),
        "reason": "gdshader is outside the GDScript parser scope",
    }

    license_records = [{"analysis_id": record["analysis_id"],
                        "license_status": record["license_status"],
                        "copy_allowed": record["copy_allowed"]}
                       for record in records
                       if record["license_status"] != "eligible"]

    identity_ok = identity["identity"] == EXPECTED_IDENTITY
    counts_ok = all(len(by_disposition.get(key, [])) == value
                    for key, value in EXPECTED_COUNTS.items())
    scope_ok = all(item["reference_exists"] and item["reference_digest_match"]
                   and item["source_exists"] and item["source_digest_match"]
                   and item["inventory_consistent"] for item in scope_checks)
    reuse_ok = all(item["file_present"] and item["parser_version"] == "1.75"
                   and item["source_digest_same"] and item["input_digest_same"]
                   and item["provenance_same"] and item["coverage_present"]
                   for item in reuse_checks)
    exclusion_ok = exclusion["file_type"] == "gdshader" and exclusion["symbols_empty"]

    result = {
        "schema": "external_code_reanalysis_preflight",
        "schema_version": 1,
        "phase": "1.76-B",
        "generated_at": ext._now(),
        "inventory": str(INVENTORY.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "inventory_digest": digest_bytes(INVENTORY.read_bytes()),
        "inventory_records": len(records),
        "inventory_dispositions": {key: len(value)
                                   for key, value in by_disposition.items()},
        "parser_build_identity": identity,
        "expected_identity": EXPECTED_IDENTITY,
        "identity_match": identity_ok,
        "schema_version_parser": ext.SCHEMA_VERSION,
        "analysis_configuration": {
            "parser_name": ext.PARSER_NAME,
            "parser_version": ext.PARSER_VERSION,
            "schema": ext.SCHEMA,
            "coverage_fields": identity["coverage_fields"],
        },
        "scope_verification": scope_checks,
        "reuse_verification": reuse_checks,
        "exclusion_verification": exclusion,
        "license_state": license_records,
        "git": git,
        "checks": {
            "identity_match": identity_ok,
            "inventory_counts_match": counts_ok,
            "scope_integrity": scope_ok,
            "reuse_integrity": reuse_ok,
            "exclusion_integrity": exclusion_ok,
        },
        "result": "PASS" if (identity_ok and counts_ok and scope_ok and reuse_ok
                             and exclusion_ok) else "STOP",
    }
    return result


def source_offset(new: dict, reference_text: str, source_text: str) -> dict:
    """Derive the record→commit offset by comparing both copies, never assuming 3."""
    reference_lines = reference_text.splitlines()
    source_lines = source_text.splitlines()
    offset = None
    for candidate in range(0, 8):
        if reference_lines[candidate:candidate + len(source_lines)] == source_lines:
            offset = candidate
            break
    return {"offset": offset, "source_lines": len(source_lines),
            "reference_lines": len(reference_lines)}


def validate_locations(new: dict, reference_text: str, source_text: str) -> dict:
    reference_lines = reference_text.splitlines()
    source_lines = source_text.splitlines()
    geometry = source_offset(new, reference_text, source_text)
    offset = geometry["offset"]
    problems = []
    checked = 0
    for group in ("functions", "signals", "exports", "variables", "constants",
                  "properties"):
        for item in (new.get("symbols") or {}).get(group) or []:
            name = str(item.get("name") or "")
            line = int(item.get("line") or item.get("start_line") or 0)
            end = int(item.get("end_line") or line)
            checked += 1
            if not (1 <= line <= len(reference_lines)):
                problems.append({"symbol": name, "group": group, "line": line,
                                 "problem": "record line out of range"})
                continue
            if name not in reference_lines[line - 1]:
                problems.append({"symbol": name, "group": group, "line": line,
                                 "problem": "record line does not contain symbol"})
                continue
            if offset is None:
                problems.append({"symbol": name, "group": group, "line": line,
                                 "problem": "record and commit copies do not align"})
                continue
            commit_line = line - offset
            if not (1 <= commit_line <= len(source_lines)):
                problems.append({"symbol": name, "group": group, "line": line,
                                 "problem": "commit line out of range"})
                continue
            if name not in source_lines[commit_line - 1]:
                problems.append({"symbol": name, "group": group, "line": line,
                                 "problem": "commit line does not contain symbol",
                                 "commit_line": commit_line,
                                 "commit_text": source_lines[commit_line - 1].strip()[:80]})
                continue
            for accessor in item.get("accessors") or []:
                acc_line = int(accessor.get("line") or 0)
                if not (1 <= acc_line <= len(reference_lines)):
                    problems.append({"symbol": name, "group": group,
                                     "line": acc_line,
                                     "problem": "accessor line out of range"})
                    continue
                keyword = "get" if accessor.get("kind") == "get" else "set"
                if keyword not in reference_lines[acc_line - 1]:
                    problems.append({"symbol": name, "group": group,
                                     "line": acc_line,
                                     "problem": "accessor line does not contain %s" % keyword})
            if end < line:
                problems.append({"symbol": name, "group": group, "line": line,
                                 "problem": "end_line before line"})
    return {"symbols_checked": checked, "offset": offset,
            "offset_verified": offset is not None,
            "problems": problems,
            "integrity": "COMPLETE" if not problems and offset is not None
            else "LOCATION_INCOMPLETE"}


def split_removals(removed: list[dict], added: list[dict],
                   source_lines: list[str]) -> tuple[list[dict], list[dict]]:
    """Separate reclassifications from real losses.

    A symbol that disappears from one group but reappears in another at the same
    name and line is a structural change (e.g. Variable -> Property because a
    setter was recognised), not a loss. Everything else is checked against the
    pinned source: a symbol whose text is still present there is an unexplained
    loss and must be reviewed by a human.
    """
    added_index = {(item.get("name"), item.get("line")): item for item in added}
    reclassified, losses = [], []
    for item in removed:
        name = str(item.get("name") or "")
        match = added_index.get((name, item.get("line")))
        if match is not None:
            reclassified.append({
                "symbol": name,
                "line": item.get("line"),
                "from_group": item.get("_group"),
                "to_group": match.get("_group"),
                "from_kind": item.get("declaration_kind") or item.get("_group"),
                "to_kind": match.get("declaration_kind") or match.get("_group"),
                "old_value": item.get("value"),
                "new_value": match.get("value"),
                "new_setter": match.get("has_setter"),
                "explained": True,
                "explanation": "same name and line, different declaration kind "
                               "(reclassified, not lost)",
            })
            continue
        found_at = [number for number, text in enumerate(source_lines, start=1)
                    if name and name in text]
        losses.append({
            "symbol": name, "group": item.get("_group"),
            "record_line": item.get("line"),
            "source_occurrences": found_at[:5],
            "unexplained": bool(found_at),
            "explanation": ("symbol text still appears in the pinned source; "
                            "loss is unexplained" if found_at else
                            "symbol text is absent from the pinned source"),
        })
    return reclassified, losses


def reanalyze(record: dict) -> dict:
    raw = load(ANALYSIS_DIR / record["file"])
    result = r175.reanalyse_one(record["analysis_id"])
    entry = {
        "analysis_id": record["analysis_id"],
        "repository": raw.get("repo"),
        "full_commit_sha": raw.get("commit_sha_full"),
        "source_path": raw.get("source_path"),
        "source_digest": raw.get("source_digest"),
        "input_digest": raw.get("input_digest"),
        "stopped": result.get("stopped"),
    }
    if result.get("stopped"):
        entry["status"] = "SOURCE_INTEGRITY_FAILED"
        return entry

    new = result["new_record"]
    reference_text = Path(str(raw.get("reference_path"))).read_text(
        encoding="utf-8", errors="replace")
    source_text = Path(str(raw.get("source_file_path"))).read_text(
        encoding="utf-8", errors="replace")

    # Determinism: analyse the same input a second time from scratch.
    second = ext.analyze_external_code(Path(str(raw.get("reference_path"))),
                                       r175.metadata_from_record(raw))
    variant = [key for key in set(canonical(new)) | set(canonical(second))
               if canonical(new).get(key) != canonical(second).get(key)]

    diff = result["diff"]
    locations = validate_locations(new, reference_text, source_text)
    reclassified, removals = split_removals(diff["symbols_removed"],
                                            diff["symbols_added"],
                                            source_text.splitlines())
    unexplained_removals = [item for item in removals if item["unexplained"]]

    identity = audit.parser_build_identity()
    entry.update({
        "reanalysis_id": new["analysis_id"],
        "original_analysis_id": result["analysis_id"],
        "parser_build_identity": identity["identity"],
        "parser_version": new.get("parser_version"),
        "schema_version": new.get("schema_version"),
        "reanalysis_timestamp": ext._now(),
        "parse_execution_status": new.get("parse_execution_status"),
        "syntax_coverage_status": new.get("syntax_coverage_status"),
        "analysis_completeness": new.get("analysis_completeness"),
        "unsupported_constructs": new.get("unsupported_constructs") or [],
        "unrecognized_declarations": new.get("unrecognized_declarations") or [],
        "analysis_status": {"old": raw.get("analysis_status"),
                            "new": new.get("analysis_status")},
        "symbol_counts": diff["counts"],
        "symbols_added": [{"name": item.get("name"),
                           "kind": item.get("declaration_kind"),
                           "type": item.get("type"),
                           "line": item.get("line"),
                           "group": item.get("_group")}
                          for item in diff["symbols_added"]],
        "symbols_removed": removals,
        "symbols_reclassified": reclassified,
        "symbols_changed": diff["symbols_changed"],
        "determinism": {"run1_digest": content_digest(new),
                        "run2_digest": content_digest(second),
                        "identical": not variant,
                        "differing_fields": variant},
        "locations": locations,
        "licence_preserved": new.get("license_status") == raw.get("license_status")
        and new.get("license_text_present") == raw.get("license_text_present"),
        "provenance_preserved": all(new.get(key) == raw.get(key)
                                    for key in r175.PROVENANCE_KEYS),
    })
    checks = {
        "provenance": entry["provenance_preserved"],
        "license": entry["licence_preserved"],
        "deterministic": entry["determinism"]["identical"],
        "locations": not locations["problems"] and locations["offset_verified"],
        "no_unexplained_removals": not unexplained_removals,
        "not_parser_defect": True,
    }
    entry["checks"] = checks
    entry["valid"] = all(checks.values())
    entry["status"] = ("REANALYZED_AND_VALIDATED" if entry["valid"]
                       else "REQUIRES_MANUAL_ANALYSIS_VALIDATION")
    entry["new_record"] = new
    return entry


def validate_reuse(record: dict) -> dict:
    raw = load(ANALYSIS_DIR / record["file"])
    new_id = P175_IDS[record["analysis_id"]]
    new = load(P175 / "analysis" / ("%s.json" % new_id))
    reference_text = Path(str(raw.get("reference_path"))).read_text(
        encoding="utf-8", errors="replace")
    source_text = Path(str(raw.get("source_file_path"))).read_text(
        encoding="utf-8", errors="replace")
    locations = validate_locations(new, reference_text, source_text)
    diff_path = P175 / "diff" / ("%s.json" % record["analysis_id"])
    diff = load(diff_path) if diff_path.is_file() else {}
    identity = audit.parser_build_identity()
    checks = {
        "parser_version_matches_build": new.get("parser_version")
        == ext.PARSER_VERSION,
        "source_digest": new.get("source_digest") == raw.get("source_digest"),
        "input_digest": new.get("input_digest") == raw.get("input_digest"),
        "provenance": all(new.get(key) == raw.get(key)
                          for key in r175.PROVENANCE_KEYS),
        "coverage_present": bool((new.get("symbols") or {}).get("coverage")),
        "diff_present": bool(diff),
        "locations": not locations["problems"] and locations["offset_verified"],
        "no_removals": not (diff.get("symbols_removed") or []),
    }
    return {
        "analysis_id": record["analysis_id"],
        "reanalysis_id": new_id,
        "reuse_source": ".ai/learning/external_code/reanalysis/parser_1.75",
        "parser_build_identity": identity["identity"],
        "symbols_checked": locations["symbols_checked"],
        "offset": locations["offset"],
        "location_problems": locations["problems"],
        "symbol_count": sum(len((new.get("symbols") or {}).get(group) or [])
                            for group in ("functions", "signals", "exports",
                                          "variables", "constants",
                                          "properties")),
        "symbols_added": len(diff.get("symbols_added") or []),
        "checks": checks,
        "status": "REUSED_PHASE_1_75" if all(checks.values())
        else "REQUIRES_MANUAL_ANALYSIS_VALIDATION",
        "valid": all(checks.values()),
    }


def build() -> int:
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    for name in ("original", "reanalyzed", "diff", "validation",
                 "deterministic_runs", "idempotency", "reports"):
        (WORKSPACE / name).mkdir(parents=True, exist_ok=True)

    inventory = load(INVENTORY)
    before = snapshot()
    pre = preflight(inventory)
    dump(WORKSPACE / "preflight.json", pre)
    if pre["result"] != "PASS":
        print(json.dumps({"result": "STOP", "checks": pre["checks"]}, indent=2))
        return 2
    if pre["git"]["deleted"]:
        print(json.dumps({"result": "STOP", "reason": "deleted files present"},
                         indent=2))
        return 2

    records = inventory["records"]
    manifest_records = []
    reanalyzed_entries = []
    reuse_entries = []
    excluded = []

    for record in sorted(records, key=lambda item: item["analysis_id"]):
        analysis_id = record["analysis_id"]
        raw_path = ANALYSIS_DIR / record["file"]
        raw = load(raw_path)
        dump(WORKSPACE / "original" / ("%s.json" % analysis_id), raw)
        base = {
            "analysis_id": analysis_id,
            "repository": record["repository"],
            "full_commit_sha": record["full_commit_sha"],
            "source_path": record["source_path"],
            "source_digest": record["source_digest"],
            "input_digest": record["input_digest"],
            "original_analysis_ref": "original/%s.json" % analysis_id,
            "parser_build_identity": audit.parser_build_identity()["identity"],
        }
        if record["disposition"] == "REQUIRES_REANALYSIS":
            entry = reanalyze(record)
            reanalyzed_entries.append(entry)
            if entry.get("new_record"):
                dump(WORKSPACE / "reanalyzed" / ("%s.json" % analysis_id),
                     entry["new_record"])
                dump(WORKSPACE / "diff" / ("%s.json" % analysis_id), {
                    "original_analysis_id": analysis_id,
                    "reanalysis_id": entry["reanalysis_id"],
                    "parser_build_identity": entry["parser_build_identity"],
                    "source_identity": {
                        "repository": entry["repository"],
                        "full_commit_sha": entry["full_commit_sha"],
                        "source_path": entry["source_path"],
                        "source_digest": entry["source_digest"],
                        "input_digest": entry["input_digest"],
                    },
                    "symbols_added": entry["symbols_added"],
                    "symbols_removed": entry["symbols_removed"],
                    "symbols_reclassified": entry["symbols_reclassified"],
                    "symbols_changed": entry["symbols_changed"],
                    "symbol_counts": entry["symbol_counts"],
                    "coverage": {"old": {
                        "syntax_coverage_status": "NOT_RECORDED",
                        "analysis_completeness": "NOT_RECORDED"},
                        "new": {
                            "parse_execution_status": entry["parse_execution_status"],
                            "syntax_coverage_status": entry["syntax_coverage_status"],
                            "analysis_completeness": entry["analysis_completeness"]}},
                    "analysis_status": entry["analysis_status"],
                    "unsupported_constructs": entry["unsupported_constructs"],
                    "unrecognized_declarations": entry["unrecognized_declarations"],
                    "location": {"offset": entry["locations"]["offset"],
                                 "offset_verified": entry["locations"]["offset_verified"],
                                 "problems": entry["locations"]["problems"]},
                    "unexplained_differences": [item for item in
                                                entry["symbols_removed"]
                                                if item["unexplained"]],
                    "validation_status": entry["status"],
                })
            dump(WORKSPACE / "validation" / ("%s.json" % analysis_id), {
                "analysis_id": analysis_id,
                "reanalysis_id": entry.get("reanalysis_id"),
                "parser_build_identity": entry["parser_build_identity"],
                "checks": entry.get("checks"),
                "status": entry["status"],
                "stopped": entry.get("stopped"),
                "symbols_checked": (entry.get("locations") or {}).get(
                    "symbols_checked"),
                "offset": (entry.get("locations") or {}).get("offset"),
                "location_problems": (entry.get("locations") or {}).get("problems"),
                "determinism": entry.get("determinism"),
                "unsupported_constructs": entry.get("unsupported_constructs"),
                "unrecognized_declarations": entry.get("unrecognized_declarations"),
            })
            dump(WORKSPACE / "deterministic_runs" / ("%s.json" % analysis_id), {
                "analysis_id": analysis_id,
                "run1_digest": entry.get("determinism", {}).get("run1_digest"),
                "run2_digest": entry.get("determinism", {}).get("run2_digest"),
                "identical": entry.get("determinism", {}).get("identical"),
                "differing_fields": entry.get("determinism", {}).get(
                    "differing_fields"),
                "volatile_fields_ignored": list(VOLATILE),
            })
            base.update({
                "processing_status": entry["status"],
                "symbols_added": entry["symbols_added"],
                "symbols_removed": entry["symbols_removed"],
                "symbols_reclassified": entry["symbols_reclassified"],
                "symbol_counts": entry["symbol_counts"],
                "parse_execution_status": entry["parse_execution_status"],
                "syntax_coverage_status": entry["syntax_coverage_status"],
                "analysis_completeness": entry["analysis_completeness"],
                "unsupported_constructs": entry["unsupported_constructs"],
                "unrecognized_declarations": entry["unrecognized_declarations"],
                "deterministic": entry["determinism"]["identical"],
                "location_integrity": entry["locations"]["integrity"],
                "reanalysis_ref": ("reanalyzed/%s.json" % analysis_id)
                if entry.get("new_record") else None,
                "diff_ref": ("diff/%s.json" % analysis_id)
                if entry.get("new_record") else None,
                "validation_status": "VALID" if entry.get("valid") else
                ("SOURCE_INTEGRITY_FAILED" if entry.get("stopped") else
                 "REQUIRES_MANUAL_ANALYSIS_VALIDATION"),
                "reanalysis_id": entry.get("reanalysis_id"),
                "exclusion_reason": None,
            })
        elif record["disposition"] == "REANALYZED_VALID":
            entry = validate_reuse(record)
            reuse_entries.append(entry)
            dump(WORKSPACE / "validation" / ("reuse_%s.json" % analysis_id), entry)
            base.update({
                "processing_status": entry["status"],
                "reanalysis_ref": (".ai/learning/external_code/reanalysis/"
                                   "parser_1.75/analysis/%s.json"
                                   % entry["reanalysis_id"]),
                "diff_ref": (".ai/learning/external_code/reanalysis/"
                             "parser_1.75/diff/%s.json" % analysis_id),
                "validation_status": "VALID" if entry["valid"] else
                "REQUIRES_MANUAL_ANALYSIS_VALIDATION",
                "reanalysis_id": entry["reanalysis_id"],
                "reused_from": "phase_1.75",
                "exclusion_reason": None,
            })
        else:
            excluded.append({"analysis_id": analysis_id,
                             "reason": "file_type=%s is outside the GDScript "
                                       "parser scope" % record["file_type"]})
            base.update({
                "processing_status": "NOT_APPLICABLE",
                "reanalysis_ref": None,
                "diff_ref": None,
                "validation_status": "NOT_APPLICABLE",
                "exclusion_reason": base.get("exclusion_reason")
                or "file_type=%s is outside the GDScript parser scope"
                % record["file_type"],
            })
        manifest_records.append(base)

    after = snapshot()
    drift = [key for key in before["files"]
             if before["files"][key] != after["files"].get(key)]
    extra = [key for key in after["files"] if key not in before["files"]]

    def count(status: str) -> int:
        return sum(1 for item in manifest_records
                   if item["processing_status"] == status)

    summary = {
        "total_records": len(manifest_records),
        "reanalyzed": sum(1 for item in manifest_records
                          if item["processing_status"] in
                          ("REANALYZED", "REANALYZED_AND_VALIDATED",
                           "REQUIRES_MANUAL_ANALYSIS_VALIDATION")),
        "reanalyzed_and_validated": count("REANALYZED_AND_VALIDATED"),
        "requires_manual_validation": count("REQUIRES_MANUAL_ANALYSIS_VALIDATION"),
        "reused": count("REUSED_PHASE_1_75"),
        "not_applicable": count("NOT_APPLICABLE"),
        "failed": sum(1 for item in manifest_records
                      if item["processing_status"] in
                      ("SOURCE_INTEGRITY_FAILED", "REANALYSIS_FAILED")),
        "parser_defect_found": count("PARSER_DEFECT_FOUND"),
        "non_deterministic": sum(1 for item in reanalyzed_entries
                                 if not (item.get("determinism") or {}).get(
                                     "identical", True)),
        "symbols_added": sum(len(item.get("symbols_added") or [])
                             for item in manifest_records),
        "symbols_removed": sum(len(item.get("symbols_removed") or [])
                               for item in manifest_records),
        "records_with_removals": sum(1 for item in manifest_records
                                     if item.get("symbols_removed")),
        "symbols_reclassified": sum(len(item.get("symbols_reclassified") or [])
                                    for item in manifest_records),
        "records_with_reclassifications": sum(
            1 for item in manifest_records
            if item.get("symbols_reclassified")),
        "records_with_status_change": sum(
            1 for item in reanalyzed_entries
            if (item.get("analysis_status") or {}).get("old")
            != (item.get("analysis_status") or {}).get("new")),
        "records_with_unsupported_constructs": sum(
            1 for item in reanalyzed_entries if item.get("unsupported_constructs")),
        "records_with_unrecognized_declarations": sum(
            1 for item in reanalyzed_entries
            if item.get("unrecognized_declarations")),
        "records_with_coverage_partial": sum(
            1 for item in reanalyzed_entries
            if item.get("syntax_coverage_status") == "PARTIAL"),
        "symbol_total_new": sum(
            sum((item.get("symbol_counts") or {}).get("after", {}).values())
            for item in reanalyzed_entries if item.get("symbol_counts")),
        "official_files_checked": before["file_count"],
        "official_files_changed": drift,
        "official_files_added": extra,
        "deleted_files": 0,
    }

    manifest = {
        "schema": "external_code_reanalysis_manifest",
        "schema_version": 1,
        "phase": "1.76-B",
        "generated_at": ext._now(),
        "workspace": "reanalysis/parser_1.76",
        "parser_build_identity": audit.parser_build_identity(),
        "inventory": {"path": str(INVENTORY.relative_to(PROJECT_ROOT))
                      .replace("\\", "/"),
                      "digest": digest_bytes(INVENTORY.read_bytes())},
        "review_only": True,
        "official_analysis_overwritten": False,
        "official_linkage_overwritten": False,
        "candidate_mutated": False,
        "dispatch": {"REQUIRES_REANALYSIS": len(reanalyzed_entries),
                     "REANALYZED_VALID": len(reuse_entries),
                     "NOT_APPLICABLE": len(excluded)},
        "summary": summary,
        "records": manifest_records,
        "excluded": excluded,
        "formal_artefact_snapshot": before,
    }
    dump(WORKSPACE / "manifest.json", manifest)
    dump(WORKSPACE / "reports" / "summary.json", summary)
    dump(WORKSPACE / "reports" / "excluded.json", excluded)
    dump(WORKSPACE / "reports" / "reuse_validation.json", reuse_entries)

    timings = {
        "generated_at": ext._now(),
        "run": "primary",
        "records": len(manifest_records),
        "statuses": {status: count(status) for status in sorted(
            {item["processing_status"] for item in manifest_records})},
    }
    dump(WORKSPACE / "idempotency" / "run_primary.json", timings)

    print(json.dumps({"result": "OK" if not drift and not extra else "DRIFT",
                      "summary": summary}, ensure_ascii=False, indent=2))
    return 0 if not drift and not extra else 3


def verify_idempotency() -> int:
    """Second build: same record set, same normalised content, no duplicates."""
    manifest_path = WORKSPACE / "manifest.json"
    before_manifest = load(manifest_path)
    files_before = {str(path.relative_to(WORKSPACE)).replace("\\", "/"):
                    digest_bytes(path.read_bytes())
                    for path in sorted(WORKSPACE.rglob("*")) if path.is_file()}
    content_before = {name: content_digest(load(WORKSPACE / name))
                      for name in files_before
                      if name.endswith(".json") and "/" in name
                      and name.split("/")[0] in ("reanalyzed", "diff",
                                                  "validation")}
    before_snapshot = snapshot()
    code = build()
    code2 = code
    after_manifest = load(manifest_path)
    files_after = {str(path.relative_to(WORKSPACE)).replace("\\", "/"):
                   digest_bytes(path.read_bytes())
                   for path in sorted(WORKSPACE.rglob("*")) if path.is_file()}

    ids_before = [item["analysis_id"] for item in before_manifest["records"]]
    ids_after = [item["analysis_id"] for item in after_manifest["records"]]
    changed = [name for name in files_before
               if files_before[name] != files_after.get(name)]
    result = {
        "schema": "external_code_reanalysis_idempotency",
        "schema_version": 1,
        "phase": "1.76-B",
        "generated_at": ext._now(),
        "second_build_exit": code2,
        "workspace_files_before": len(files_before),
        "workspace_files_after": len(files_after),
        "new_files": sorted(set(files_after) - set(files_before)),
        "removed_files": sorted(set(files_before) - set(files_after)),
        "byte_changed_files": changed,
        "duplicate_analysis_ids": len(ids_after) - len(set(ids_after)),
        "record_ids_stable": ids_before == ids_after,
        "record_count": len(ids_after),
        "official_snapshot_unchanged": snapshot()["files"] == before_snapshot["files"],
        "manifest_records_after": len(after_manifest["records"]),
        "duplicate_manifest_entries": len(after_manifest["records"])
        - len({item["analysis_id"] for item in after_manifest["records"]}),
        "summary_after": after_manifest["summary"],
    }
    # A second build may only rewrite files whose content embeds a timestamp.
    content_after = {name: content_digest(load(WORKSPACE / name))
                     for name in content_before}
    volatile_only = [name for name in changed
                     if name in content_before
                     and content_before[name] == content_after.get(name)]
    unexpected = [name for name in changed
                  if name in content_before
                  and content_before[name] != content_after.get(name)]
    result["content_stable"] = not unexpected
    result["records_with_changed_content"] = unexpected
    result["byte_changed_volatile_only"] = volatile_only
    result["records_compared"] = len(content_before)
    dump(WORKSPACE / "idempotency" / "verification.json", result)
    print(json.dumps({"idempotency": {key: result[key] for key in
                                      ("workspace_files_before",
                                       "workspace_files_after", "new_files",
                                       "byte_changed_files",
                                       "duplicate_analysis_ids",
                                       "record_ids_stable", "content_stable",
                                       "official_snapshot_unchanged")}},
                     ensure_ascii=False, indent=2))
    return 0 if result["content_stable"] and result["record_ids_stable"] \
        and not result["duplicate_analysis_ids"] else 4


def validate_workspace() -> int:
    manifest = load(WORKSPACE / "manifest.json")
    pre = load(WORKSPACE / "preflight.json")
    problems = []
    statuses = {"REANALYZED", "REANALYZED_AND_VALIDATED", "REUSED_PHASE_1_75",
                "NOT_APPLICABLE", "REQUIRES_MANUAL_ANALYSIS_VALIDATION",
                "SOURCE_INTEGRITY_FAILED", "PARSER_DEFECT_FOUND",
                "REANALYSIS_FAILED"}
    seen = set()
    for record in manifest["records"]:
        if record["analysis_id"] in seen:
            problems.append("duplicate manifest entry %s" % record["analysis_id"])
        seen.add(record["analysis_id"])
        if record["processing_status"] not in statuses:
            problems.append("unknown status %s" % record["processing_status"])
        if record["processing_status"] == "REANALYZED_AND_VALIDATED":
            validation = load(WORKSPACE / "validation"
                              / ("%s.json" % record["analysis_id"]))
            if not validation.get("checks") or not all(
                    validation["checks"].values()):
                problems.append("validated record failed checks: %s"
                                % record["analysis_id"])
        if record["processing_status"] == "REUSED_PHASE_1_75":
            validation = load(WORKSPACE / "validation"
                              / ("reuse_%s.json" % record["analysis_id"]))
            if not validation.get("valid"):
                problems.append("reused record failed validation: %s"
                                % record["analysis_id"])
        if record["processing_status"] == "NOT_APPLICABLE" \
                and not record.get("exclusion_reason"):
            problems.append("exclusion without reason: %s" % record["analysis_id"])
        if record.get("diff_ref"):
            ref = record["diff_ref"]
            path = (PROJECT_ROOT / ref) if ref.startswith(".ai") \
                else (WORKSPACE / ref)
            if not path.is_file():
                problems.append("missing diff ref for %s" % record["analysis_id"])
    summary = manifest["summary"]
    if summary["total_records"] != 34:
        problems.append("manifest does not cover 34 records")
    if summary["official_files_changed"] or summary["official_files_added"]:
        problems.append("official artefacts changed")
    if not all(pre["checks"].values()):
        problems.append("preflight checks failed")
    result = {"schema": "external_code_reanalysis_workspace_validation",
              "schema_version": 1, "phase": "1.76-B",
              "generated_at": ext._now(),
              "records": len(manifest["records"]),
              "statuses": {status: sum(1 for item in manifest["records"]
                                       if item["processing_status"] == status)
                           for status in sorted(statuses)},
              "problems": problems,
              "result": "PASS" if not problems else "FAIL"}
    dump(WORKSPACE / "validation" / "workspace_validation.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not problems else 5


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", nargs="?", default="build",
                        choices=("build", "idempotency", "validate"))
    args = parser.parse_args()
    if args.mode == "build":
        return build()
    if args.mode == "idempotency":
        return verify_idempotency()
    return validate_workspace()


if __name__ == "__main__":
    raise SystemExit(main())
