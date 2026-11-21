#!/usr/bin/env python3
"""External Code Understanding adapter (Phase 1.71 Batch B).

The adapter reuses the existing regex parser (`gd_parse.py`) and the shared
source-analysis helpers (`source_analysis.py`). It does not create a second
parser, knowledge store, Feature registry or Feature.

An Analysis Record is evidence, not approved Knowledge and not a Feature.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DOTAI = PROJECT_ROOT / ".ai"
LEARNING = DOTAI / "tools" / "learning"
COLLECTOR_TOOLS = DOTAI / "skills" / "foundation" / "godot-gdscript" / "tools"
for _path in (str(LEARNING), str(DOTAI / "tools" / "external_code"), str(COLLECTOR_TOOLS)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import gd_parse  # noqa: E402
import source_analysis  # noqa: E402
from provenance import assess_license, assess_provenance, has_license_text  # noqa: E402

SCHEMA = "external_code_analysis"
SCHEMA_VERSION = 1
PARSER_NAME = "gd_parse"
PARSER_VERSION = "1.75"
ANALYSIS_DIR = DOTAI / "learning" / "external_code" / "analysis"
INDEX_PATH = DOTAI / "learning" / "external_code" / "index.json"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _digest(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _analysis_id(repo: str, commit: str, source_path: str, input_digest: str) -> str:
    return "ext-" + _digest("|".join((repo, commit, source_path, input_digest,
                                      PARSER_NAME, PARSER_VERSION)))[:16]


def _limit_lines(lines: list[str], limit: int = 200) -> list[str]:
    return lines[:limit]


def _syntax_limitations(text: str) -> list[str]:
    limits = ["regex_parser_without_ast_or_type_inference"]
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("class ") and not stripped.startswith("class_name "):
            limits.append("inner_class_not_interpreted:line=%d" % number)
        if "lambda" in stripped:
            limits.append("lambda_not_semantically_analyzed:line=%d" % number)
        if stripped.startswith("@"):
            match = re.match(r"@([A-Za-z_]\w*)", stripped)
            name = match.group(1) if match else ""
            if name not in gd_parse.KNOWN_ANNOTATIONS:
                limits.append("annotation_not_fully_interpreted:line=%d" % number)
    return limits


def _reference_offset(reference_text: str, source_text: str) -> int | None:
    """Leading lines the Reference copy has that the pinned Source copy lacks.

    Phase 1.71 references carry a header the pinned source does not, so the same
    text lives at different line numbers in the two files. Batch E derives that
    offset instead of assuming it.
    """
    reference = reference_text.splitlines()
    source = source_text.splitlines()
    if not source:
        return None
    for candidate in range(0, 13):
        if reference[candidate:candidate + len(source)] == source:
            return candidate
    return None


def _coverage_with_coordinates(coverage: dict, reference_text: str,
                               source_text: str) -> dict:
    """State every coverage coordinate space explicitly.

    Batch D found `unsupported_constructs[].line` being consumed as a commit line
    while it was a Reference-copy line. `line` keeps its meaning (the analysed
    file) and the projected spaces are added next to it.
    """
    offset = _reference_offset(reference_text, source_text)
    projected = dict(coverage)
    for key in ("unsupported_constructs", "unrecognized_declarations"):
        projected[key] = gd_parse.project_construct_lines(
            coverage.get(key) or [], source_offset=offset, record_offset=offset)
    coordinates = dict(coverage.get("line_coordinates") or {})
    coordinates.update({
        "line": gd_parse.LINE_SPACE_ANALYSIS,
        "analysis_line": gd_parse.LINE_SPACE_ANALYSIS,
        "source_line": "PINNED_SOURCE" if offset is not None else "UNMAPPED",
        "record_line": "ANALYSIS_REFERENCE" if offset is not None else "UNMAPPED",
        "reference_offset": offset,
        "mapping_status": "ALIGNED" if offset is not None else "UNALIGNED",
    })
    projected["line_coordinates"] = coordinates
    return projected


def _file_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".gd":
        return "gdscript"
    if suffix == ".gdshader":
        return "gdshader"
    return "unsupported"


def _symbols(script: gd_parse.Script) -> dict:
    calls, connects = [], []
    for function in script.functions:
        for call in gd_parse.calls(function):
            item = {"function": function.name, **call}
            if item not in calls:
                calls.append(item)
        for connection in gd_parse.connects(function):
            item = {"function": function.name, **connection}
            if item not in connects:
                connects.append(item)
    return {
        "class_name": script.class_name,
        "extends": script.extends,
        "functions": [{"name": f.name, "params": f.params, "returns": f.returns,
                       "line": f.start_line, "end_line": f.end_line,
                       "declaration_kind": "FUNCTION"}
                      for f in script.functions],
        "signals": list(script.signals),
        "exports": list(script.exports),
        "variables": list(script.variables),
        "constants": list(script.constants),
        "properties": list(script.properties),
        "declarations": list(script.declarations),
        "coverage": dict(script.coverage),
        "calls": _limit_lines(calls),
        "connections": _limit_lines(connects),
    }


def _base_record(reference_path: Path, metadata: dict, file_type: str,
                 input_digest: str) -> dict:
    repo = str(metadata.get("repo") or metadata.get("full_name") or "")
    source_path = str(metadata.get("repo_path") or metadata.get("source_path") or "")
    commit_short = str(metadata.get("commit_sha") or "")
    commit_full = str(metadata.get("commit_sha_full") or "")
    source_url = str(metadata.get("source_url") or "")
    provenance = assess_provenance(
        full_name=repo, commit_sha=commit_short, commit_sha_full=commit_full,
        source_path=source_path, source_url=source_url,
    )
    return {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "analysis_id": _analysis_id(repo, commit_full or commit_short,
                                    source_path, input_digest),
        "snippet_id": str(metadata.get("snippet_id") or metadata.get("id") or ""),
        "repo": repo,
        "source_path": source_path,
        "reference_path": str(reference_path),
        "domain": str(metadata.get("domain") or ""),
        "commit_sha": commit_short or commit_full,
        "commit_sha_full": commit_full,
        "source_url": source_url,
        "provenance_status": provenance["provenance_status"],
        "provenance": provenance,
        "file_type": file_type,
        "license": str(metadata.get("license") or "unknown"),
        "license_status": str(metadata.get("license_status") or "unknown"),
        "license_text_present": metadata.get("license_text_present"),
        "license_source": str(metadata.get("license_source") or "unknown"),
        "parser_name": PARSER_NAME,
        "parser_version": PARSER_VERSION,
        "input_digest": input_digest,
        "created_at": _now(),
        "knowledge_status": "NOT_KNOWLEDGE",
        "approved_knowledge": False,
        "feature_created": False,
        "limitations": [],
        "unresolved_questions": [],
    }


def analyze_external_code(reference_path: str | Path, metadata: dict,
                          options: dict | None = None) -> dict:
    """Analyze one Reference and return a structured, non-knowledge record."""
    options = options or {}
    path = Path(reference_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    file_type = _file_type(path)
    if not path.is_file():
        record = _base_record(path, metadata, file_type, "")
        record.update({
            "parse_status": "parse_failed",
            "analysis_status": "analysis_failed",
            "source_analysis_status": "failed",
            "error": "reference file not found",
        })
        return record
    raw = path.read_bytes()
    input_digest = _digest(raw)
    record = _base_record(path, metadata, file_type, input_digest)

    source_root = Path(options.get("source_root")) if options.get("source_root") \
        else (PROJECT_ROOT / ".ai" / "skills" / "foundation" / "godot-gdscript"
              / "code_library" / "sources")
    source_dir = source_root / str(metadata.get("repo_slug") or "")
    license_gate = assess_license(
        metadata.get("license"),
        license_text_present=metadata.get("license_text_present",
                                          has_license_text(source_dir)),
        license_source=metadata.get("license_source") or "github_api_spdx",
        declared_status=(metadata.get("license_status")
                         if metadata.get("license_status") in ("blocked", "pending_review")
                         else None),
        allow_missing_text=True,
    )
    record.update({
        "license_status": license_gate["license_status"],
        "license_text_present": license_gate["license_text_present"],
        "license_source": license_gate["license_source"],
        "license_basis": license_gate["license_basis"],
        "license_risk": license_gate["license_risk"],
        "copy_allowed": license_gate["copy_allowed"],
    })
    if record["provenance_status"] == "unknown":
        record.update({"parse_status": "not_run", "analysis_status": "blocked_provenance",
                       "source_analysis_status": "skipped"})
        record["unresolved_questions"].append(record["provenance"]["reason"])
        return record
    text = raw.decode("utf-8", errors="replace")
    source_file = (source_dir / "gd" / str(metadata.get("repo_path") or "")) \
        if source_dir.is_dir() else None
    source_text = ""
    record["source_file_path"] = str(source_file) if source_file else ""
    record["source_exists"] = bool(source_file and source_file.is_file())
    if source_file and source_file.is_file():
        source_text = source_file.read_text(encoding="utf-8", errors="replace")
        record["source_digest"] = _digest(source_file.read_bytes())
        offset = _reference_offset(text, source_text)
        record["reference_offset"] = offset
        record["source_consistent"] = (
            offset is not None and
            source_text.replace("\r\n", "\n").strip("\n")
            == "\n".join(text.splitlines()[offset:]).strip("\n"))
        if not record["source_consistent"]:
            record["unresolved_questions"].append(
                "reference body does not match the recorded source file")
    else:
        record["source_digest"] = ""
        record["source_consistent"] = False
        record["unresolved_questions"].append("source file is missing")
    if file_type == "gdshader":
        record.update({
            "parse_status": "unsupported_shader",
            "analysis_status": "unsupported_shader",
            "source_analysis_status": "skipped",
            "symbols": {}, "entry_points": [], "state_changes": [],
            "signals_events": [], "side_effects": [], "failure_paths": [],
        })
        record["limitations"].append("shader parsing is outside Phase 1.71")
        return record
    if file_type != "gdscript":
        record.update({
            "parse_status": "unsupported_file_type",
            "analysis_status": "unsupported_file_type",
            "source_analysis_status": "skipped",
            "symbols": {}, "entry_points": [], "state_changes": [],
            "signals_events": [], "side_effects": [], "failure_paths": [],
        })
        record["limitations"].append("unsupported external file type")
        return record
    if not license_gate["copy_allowed"]:
        # The read-only analysis is still useful, but it can never become a
        # copyable candidate or approved knowledge.
        record["unresolved_questions"].append(license_gate["reason"])

    limitations = _syntax_limitations(text)
    record["limitations"].extend(limitations)
    try:
        script = gd_parse.parse_text(str(path), text)
    except Exception as exc:  # noqa: BLE001
        record.update({
            "parse_status": "parse_failed",
            "analysis_status": "analysis_failed",
            "source_analysis_status": "failed",
            "error": str(exc),
            "symbols": {}, "entry_points": [], "state_changes": [],
            "signals_events": [], "side_effects": [], "failure_paths": [],
        })
        return record

    record["symbols"] = _symbols(script)
    coverage = _coverage_with_coordinates(script.coverage, text, source_text)
    record["symbols"]["coverage"] = coverage
    record.update({
        "parse_execution_status": coverage.get("parse_execution_status", "PARSED"),
        "syntax_coverage_status": coverage.get("syntax_coverage_status", "PARTIAL"),
        "analysis_completeness": coverage.get("analysis_completeness", "DECLARATION_GAPS"),
        "unsupported_constructs": coverage.get("unsupported_constructs", []),
        "unrecognized_declarations": coverage.get("unrecognized_declarations", []),
        "source_coordinates": coverage.get("source_coordinates", "ANALYZED_FILE"),
    })
    if not script.functions:
        record["parse_status"] = "partial"
        record["analysis_status"] = "analysis_partial"
        record["source_analysis_status"] = "partial"
        record["unresolved_questions"].append("no functions found by the regex parser")
        record.update({"entry_points": [], "state_changes": [], "signals_events": [],
                       "side_effects": [], "failure_paths": []})
        return record
    try:
        analysis = source_analysis.analyze_external_scripts(
            [script], entry_names=options.get("entry_names"))
    except Exception as exc:  # noqa: BLE001
        record.update({
            "parse_status": "parsed",
            "analysis_status": "analysis_failed",
            "source_analysis_status": "failed",
            "error": str(exc),
            "entry_points": [], "state_changes": [], "signals_events": [],
            "side_effects": [], "failure_paths": [],
        })
        return record
    unresolved = (record["unresolved_questions"]
                  + analysis["unresolved_questions"])
    record.update({
        "entry_points": analysis["entry_points"],
        "functions_analyzed": analysis["functions_analyzed"],
        "state_changes": analysis["state_variables"],
        "conditions": analysis["conditions"],
        "signals_events": analysis["events"],
        "side_effects": analysis["side_effects"],
        "failure_paths": analysis["failure_paths"],
        "unresolved_questions": unresolved,
    })
    hard_limitations = [x for x in limitations
                        if not x.startswith("regex_parser_without")]
    # Phase 1.75: parser execution success is not coverage. A record whose
    # declaration grammar could not account for every declaration in the file
    # is never reported as complete.
    coverage_partial = (coverage.get("syntax_coverage_status") != "COMPLETE"
                        or bool(coverage.get("unrecognized_declarations")))
    syntax_partial = bool(hard_limitations) or coverage_partial
    if not license_gate["copy_allowed"]:
        record["parse_status"] = "partial" if syntax_partial else "parsed"
        record["analysis_status"] = "blocked_license"
        record["source_analysis_status"] = "complete" if not unresolved else "partial"
    elif unresolved or hard_limitations:
        record["parse_status"] = "partial" if syntax_partial else "parsed"
        record["analysis_status"] = "analysis_partial"
        record["source_analysis_status"] = "partial"
    else:
        record["parse_status"] = "parsed"
        record["analysis_status"] = "analysis_complete"
        record["source_analysis_status"] = "complete"
    return record


def write_record(record: dict, out_dir: str | Path | None = None) -> str:
    directory = Path(out_dir) if out_dir else ANALYSIS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ("%s.json" % record["analysis_id"])
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True)
                    + "\n", encoding="utf-8")
    return str(path)


def build_index(out_dir: str | Path | None = None,
                index_path: str | Path | None = None) -> dict:
    directory = Path(out_dir) if out_dir else ANALYSIS_DIR
    target = Path(index_path) if index_path else INDEX_PATH
    records = []
    if directory.is_dir():
        for path in sorted(directory.glob("*.json")):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
            if record.get("schema") != SCHEMA:
                continue
            records.append({
                "analysis_id": record.get("analysis_id"),
                "snippet_id": record.get("snippet_id"),
                "repo": record.get("repo"),
                "source_path": record.get("source_path"),
                "reference_path": record.get("reference_path"),
                "commit_sha": record.get("commit_sha"),
                "commit_sha_full": record.get("commit_sha_full"),
                "provenance_status": record.get("provenance_status"),
                "license_status": record.get("license_status"),
                "file_type": record.get("file_type"),
                "parse_status": record.get("parse_status"),
                "analysis_status": record.get("analysis_status"),
                "symbols": record.get("symbols") or {},
                "entry_points": record.get("entry_points") or [],
                "unresolved_questions": record.get("unresolved_questions") or [],
            })
    payload = {"schema": "external_code_analysis_index", "schema_version": 1,
               "generated_at": _now(), "analyses": records}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
                      + "\n", encoding="utf-8")
    return payload


def _catalog_entry(snippet_id: str, catalog_path: str | Path | None = None) -> dict:
    sys.path.insert(0, str(DOTAI / "skills" / "foundation" / "godot-gdscript" / "tools"))
    import github_collector as collector
    entries = {e["id"]: e for e in collector._read_catalog_entries(
        Path(catalog_path) if catalog_path else collector.CATALOG_YAML)}
    if snippet_id not in entries:
        raise KeyError("catalog does not contain snippet: %s" % snippet_id)
    entry = dict(entries[snippet_id])
    entry["snippet_id"] = entry["id"]
    entry["license_text_present"] = entry.get("license_text_present",
                                               has_license_text(
                                                   collector.SOURCES_DIR /
                                                   str(entry.get("repo_slug") or "")))
    entry["license_source"] = entry.get("license_source") or "github_api_spdx"
    entry["source_url"] = entry.get("source_url") or ""
    return entry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="External Code Understanding")
    parser.add_argument("--snippet", action="append", default=[],
                        help="catalog snippet id (repeatable)")
    parser.add_argument("--reference", default="", help="standalone reference path")
    parser.add_argument("--metadata", default="", help="JSON metadata for --reference")
    parser.add_argument("--catalog", default="", help="catalog path override")
    parser.add_argument("--out-dir", default="", help="analysis record directory")
    parser.add_argument("--index-path", default="", help="analysis index path")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--reindex", action="store_true")
    args = parser.parse_args(argv)

    if args.reindex:
        payload = build_index(args.out_dir or None, args.index_path or None)
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json
              else "indexed %d analysis record(s)" % len(payload["analyses"]))
        return 0

    records = []
    if args.reference:
        metadata = {}
        if args.metadata:
            metadata = json.loads(Path(args.metadata).read_text(encoding="utf-8"))
        records.append(analyze_external_code(args.reference, metadata))
    elif args.snippet:
        for snippet_id in args.snippet:
            records.append(analyze_external_code(
                _reference_for_snippet(snippet_id, args.catalog or None),
                _catalog_entry(snippet_id, args.catalog or None),
            ))
    else:
        parser.error("one of --snippet, --reference or --reindex is required")

    paths = []
    for record in records:
        paths.append(write_record(record, args.out_dir or None))
    if args.json:
        print(json.dumps({"paths": paths, "records": records},
                         ensure_ascii=False, indent=2))
    else:
        for record, path in zip(records, paths):
            print("%s -> %s" % (record.get("analysis_status"), path))
    return 0


def _reference_for_snippet(snippet_id: str, catalog_path: str | Path | None = None) -> Path:
    entry = _catalog_entry(snippet_id, catalog_path)
    return (DOTAI / "skills" / "foundation" / "godot-gdscript" / "code_library"
            / "references" / str(entry.get("domain") or "") / snippet_id)


if __name__ == "__main__":
    sys.exit(main())
