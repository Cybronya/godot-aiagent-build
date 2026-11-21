#!/usr/bin/env python3
"""Phase 1.76 Batch A — corpus reconciliation audit (read only).

Builds a per-record inventory of the External Analysis corpus, matches it
against the Phase 1.75 reanalysis workspace, derives a repeatable Parser Build
Identity, and runs the provenance / source-digest preflight that decides which
records may enter Batch B.

Writes exactly one artefact:

    .ai/learning/external_code/reconciliation/phase_1.76/inventory.json

It never writes an analysis record, a linkage record, a candidate or a Feature.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DOTAI = PROJECT_ROOT / ".ai"
for _path in (str(DOTAI / "tools" / "learning"),
              str(DOTAI / "tools" / "external_code"),
              str(DOTAI / "tools" / "feature_registry")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import external_code_understanding as ext  # noqa: E402
import gd_parse  # noqa: E402

ANALYSIS_DIR = DOTAI / "learning" / "external_code" / "analysis"
LINKAGE_DIR = DOTAI / "learning" / "external_code" / "feature_links"
P175 = DOTAI / "learning" / "external_code" / "reanalysis" / "parser_1.75"
OUT_DIR = DOTAI / "learning" / "external_code" / "reconciliation" / "phase_1.76"

SYMBOL_GROUPS = ("functions", "signals", "exports", "variables", "constants",
                 "properties", "declarations")


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parser_build_identity() -> dict:
    parser = (DOTAI / "tools" / "learning" / "gd_parse.py").read_bytes()
    adapter = (DOTAI / "tools" / "external_code"
               / "external_code_understanding.py").read_bytes()
    combined = digest_bytes(parser + b"\0" + adapter)
    return {
        "kind": "content-digest",
        "parser_name": ext.PARSER_NAME,
        "declared_parser_version": ext.PARSER_VERSION,
        "schema_version": ext.SCHEMA_VERSION,
        "gd_parse_sha256": digest_bytes(parser),
        "adapter_sha256": digest_bytes(adapter),
        "identity": "%s@%s+build:%s" % (ext.PARSER_NAME, ext.PARSER_VERSION,
                                        combined[:16]),
        "identity_sha256": combined,
        "identity_source": "sha256(gd_parse.py bytes || 0x00 || "
                           "external_code_understanding.py bytes)",
        "known_annotations": len(gd_parse.KNOWN_ANNOTATIONS),
        "declaration_kinds": ["VARIABLE", "PROPERTY", "FUNCTION", "CONSTANT",
                              "SIGNAL"],
        "coverage_fields": ["parse_execution_status", "syntax_coverage_status",
                            "analysis_completeness", "unsupported_constructs",
                            "unrecognized_declarations", "source_coordinates"],
    }


def symbol_items(record: dict, group: str) -> list[dict]:
    return list((record.get("symbols") or {}).get(group) or [])


def symbol_count(record: dict) -> int:
    return sum(len(symbol_items(record, group))
               for group in ("functions", "signals", "exports", "variables",
                             "constants", "properties"))


def location_check(record: dict, reference_lines: list[str]) -> dict:
    """Verify every reported symbol line really contains that symbol."""
    checked = 0
    problems = []
    for group in ("functions", "signals", "exports", "variables", "constants",
                  "properties"):
        for item in symbol_items(record, group):
            name = str(item.get("name") or "")
            line = int(item.get("line") or item.get("start_line") or 0)
            if not name or not line:
                problems.append({"symbol": name, "group": group, "line": line,
                                 "problem": "missing name or line"})
                continue
            checked += 1
            if not (1 <= line <= len(reference_lines)):
                problems.append({"symbol": name, "group": group, "line": line,
                                 "problem": "line out of range"})
                continue
            text = reference_lines[line - 1]
            if name not in text:
                problems.append({"symbol": name, "group": group, "line": line,
                                 "problem": "line does not contain the symbol"})
    return {"checked": checked, "problems": problems,
            "integrity": "COMPLETE" if not problems else "LOCATION_INCOMPLETE"}


def load_workspace() -> dict:
    path = P175 / "WORKSPACE.json"
    if not path.is_file():
        return {"present": False}
    manifest = json.loads(path.read_text(encoding="utf-8"))
    matched = {}
    for item in manifest.get("reanalysis") or []:
        matched[item["analysis_id"]] = {
            "workspace": str(P175.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "reanalysis_id": item.get("reanalysis_id"),
            "parser_version": (item.get("parser_version") or {}).get("new"),
            "source_digest_same": (item.get("source_digest") or {}).get("same"),
            "provenance_verified": item.get("provenance_verified"),
            "location_problems": len(item.get("location_problems") or []),
            "location_checks": item.get("location_checks"),
            "symbols_added": len((item.get("diff") or {}).get("symbols_added") or []),
            "symbols_removed": len((item.get("diff") or {}).get("symbols_removed") or []),
            "status_change": (item.get("diff") or {}).get("status", {}),
            "stopped": item.get("stopped"),
        }
    return {"present": True, "generated_with_parser": manifest.get(
        "generated_with_parser"), "records": matched,
        "official_analysis_overwritten": manifest.get(
            "official_analysis_overwritten"),
        "baseline_file_count": (manifest.get("baseline_snapshot") or {}).get(
            "file_count")}


def main() -> int:
    identity = parser_build_identity()
    workspace = load_workspace()
    linkage_index = {}
    for path in LINKAGE_DIR.glob("*.json"):
        analysis_id = path.name.split("__")[0]
        linkage_index.setdefault(analysis_id, []).append(path.name)

    records = []
    for path in sorted(ANALYSIS_DIR.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        reference = Path(str(raw.get("reference_path") or ""))
        source_file = Path(str(raw.get("source_file_path") or ""))
        ref_bytes = reference.read_bytes() if reference.is_file() else b""
        src_bytes = source_file.read_bytes() if source_file.is_file() else b""
        ref_digest = digest_bytes(ref_bytes) if ref_bytes else ""
        src_digest = digest_bytes(src_bytes) if src_bytes else ""
        lines = ref_bytes.decode("utf-8", errors="replace").splitlines() \
            if ref_bytes else []
        location = location_check(raw, lines)
        coverage = {
            key: raw.get(key, "NOT_RECORDED")
            for key in ("parse_execution_status", "syntax_coverage_status",
                        "analysis_completeness", "unsupported_constructs",
                        "unrecognized_declarations")
        }
        record = {
            "analysis_id": raw.get("analysis_id") or path.stem,
            "file": path.name,
            "repository": raw.get("repo"),
            "full_commit_sha": raw.get("commit_sha_full"),
            "short_commit_sha": raw.get("commit_sha"),
            "source_path": raw.get("source_path"),
            "source_url": raw.get("source_url"),
            "source_digest": raw.get("source_digest"),
            "input_digest": raw.get("input_digest"),
            "file_type": raw.get("file_type"),
            "license_status": raw.get("license_status"),
            "copy_allowed": raw.get("copy_allowed"),
            "provenance_status": raw.get("provenance_status"),
            "parser_name": raw.get("parser_name", "NOT_RECORDED"),
            "parser_version": raw.get("parser_version", "NOT_RECORDED"),
            "schema": raw.get("schema"),
            "schema_version": raw.get("schema_version"),
            "analysis_status": raw.get("analysis_status"),
            "parse_status": raw.get("parse_status"),
            "coverage": coverage,
            "symbol_counts": {group: len(symbol_items(raw, group))
                              for group in ("functions", "signals", "exports",
                                            "variables", "constants",
                                            "properties")},
            "symbol_count": symbol_count(raw),
            "existing_linkage_count": len(linkage_index.get(
                raw.get("analysis_id") or path.stem, [])),
            "existing_linkage_files": sorted(linkage_index.get(
                raw.get("analysis_id") or path.stem, [])),
            "location": location,
            "checks": {
                "reference_exists": reference.is_file(),
                "reference_digest_match": bool(ref_digest)
                and ref_digest == raw.get("input_digest"),
                "source_exists": source_file.is_file(),
                "source_digest_match": bool(src_digest)
                and src_digest == raw.get("source_digest"),
                "commit_full_present": bool(raw.get("commit_sha_full")),
                "provenance_complete": bool(raw.get("repo")
                                            and raw.get("commit_sha_full")
                                            and raw.get("source_path")
                                            and raw.get("source_url")),
            },
            "source_analysis_status": raw.get("source_analysis_status"),
        }

        # Disposition against the Phase 1.75 workspace, matched on stable identity
        # (repo + full commit + source path + source digest), never on filename.
        new = (workspace.get("records") or {}).get(record["analysis_id"])
        record["phase_1_75"] = new
        if not record["checks"]["provenance_complete"]:
            disposition = "PROVENANCE_INCOMPLETE"
        elif not (record["checks"]["reference_exists"]
                  and record["checks"]["source_exists"]):
            disposition = "SOURCE_MISSING"
        elif not record["checks"]["source_digest_match"]:
            disposition = "SOURCE_CHANGED"
        elif record["file_type"] != "gdscript":
            disposition = "NOT_APPLICABLE"
        elif new and new.get("stopped") is None \
                and new.get("provenance_verified") \
                and new.get("source_digest_same") \
                and new.get("parser_version") == ext.PARSER_VERSION:
            disposition = "REANALYZED_VALID"
        else:
            disposition = "REQUIRES_REANALYSIS"
        record["disposition"] = disposition
        record["reanalysis_candidate"] = disposition == "REQUIRES_REANALYSIS"
        records.append(record)

    # Duplicate / ambiguity detection on the identity tuple.
    groups: dict[tuple, list[str]] = {}
    for record in records:
        key = (record["repository"], record["full_commit_sha"],
               record["source_path"], record["source_digest"])
        groups.setdefault(key, []).append(record["analysis_id"])
    duplicates = {str(key): ids for key, ids in groups.items() if len(ids) > 1}
    near: dict[tuple, list[str]] = {}
    for record in records:
        near.setdefault((record["repository"], record["full_commit_sha"],
                         record["source_path"]), []).append(
                             record["source_digest"])
    ambiguous = {str(key): values for key, values in near.items()
                 if len(set(values)) > 1}
    for record in records:
        for ids in duplicates.values():
            if record["analysis_id"] in ids:
                record["duplicate_of"] = [item for item in ids
                                          if item != record["analysis_id"]]

    summary = {
        "records": len(records),
        "unique_repositories": len({r["repository"] for r in records}),
        "unique_commits": len({r["full_commit_sha"] for r in records}),
        "unique_source_paths": len({r["source_path"] for r in records}),
        "unique_identity_tuples": len(groups),
        "duplicates": duplicates,
        "ambiguous_identities": ambiguous,
        "missing_provenance": [r["analysis_id"] for r in records
                               if not r["checks"]["provenance_complete"]],
        "missing_source_digest": [r["analysis_id"] for r in records
                                  if not r["source_digest"]],
        "missing_input_digest": [r["analysis_id"] for r in records
                                 if not r["input_digest"]],
        "missing_parser_version": [r["analysis_id"] for r in records
                                   if r["parser_version"] == "NOT_RECORDED"],
        "missing_coverage_metadata": [r["analysis_id"] for r in records
                                      if r["coverage"]["syntax_coverage_status"]
                                      == "NOT_RECORDED"],
        "dispositions": {},
        "symbol_total": sum(r["symbol_count"] for r in records),
        "linkage_total": sum(r["existing_linkage_count"] for r in records),
        "location_incomplete": [r["analysis_id"] for r in records
                                if r["location"]["integrity"] != "COMPLETE"],
        "parser_versions_recorded": sorted({r["parser_version"] for r in records}),
        "schema_versions_recorded": sorted({str(r["schema_version"])
                                            for r in records}),
        "file_types": {},
    }
    for record in records:
        summary["dispositions"][record["disposition"]] = \
            summary["dispositions"].get(record["disposition"], 0) + 1
    for record in records:
        summary["file_types"][record["file_type"]] = \
            summary["file_types"].get(record["file_type"], 0) + 1

    payload = {
        "schema": "external_analysis_corpus_audit",
        "schema_version": 1,
        "phase": "1.76-A",
        "generated_at": ext._now(),
        "parser_build_identity": identity,
        "phase_1_75_workspace": workspace,
        "summary": summary,
        "records": records,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "inventory.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(json.dumps({"identity": identity["identity"],
                      "workspace_present": workspace.get("present"),
                      "summary": summary}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
