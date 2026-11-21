#!/usr/bin/env python3
"""External Analysis <-> Feature Evidence Linkage (Phase 1.73, Batch B).

Builds a read-only, independently rebuildable linkage layer between existing
External Analysis Records and existing Feature Evidence Projections.

The linkage only answers: which Analysis Records have traceable evidence
connecting them to which Features, on what basis, and is that basis still
current?  It never answers similarity, quality, admission or promotion
questions, and it never writes to its inputs.

Reused building blocks (no second parser / registry / store):
  * feature_evidence.py  -> path normalization, sha256/canonical helpers,
    evidence/projection/verification status vocabularies, pilot Feature list.
  * .ai/learning/external_code/analysis/*.json -> Analysis Records (read only).
  * .ai/learning/feature_evidence/*.json       -> Projections (read only).
  * .ai/context/feature_graph.json             -> declared composition edges.

Semantics kept strictly apart:
  * projection_status : completeness of the derived projection only.
  * verification_status: Batch A.1 marker; copied verbatim, never upgraded.
  * evidence_status    : status of a single evidence record.
  * linkage_classification: type of the evidence connecting the two sides.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TOOLS_DIR = HERE.parent
DOTAI = TOOLS_DIR.parent
PROJECT_ROOT = DOTAI.parent

for _path in (str(DOTAI / "tools" / "learning"), str(HERE),
              str(DOTAI / "tools" / "feature_registry")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import feature_evidence as projection_schema  # noqa: E402

_sha256_file = projection_schema._sha256_file
_sha256_text = projection_schema._sha256_text
_canonical = projection_schema._canonical
normalize_path = projection_schema.normalize_path
EVIDENCE_STATUSES = projection_schema.EVIDENCE_STATUSES
PROJECTION_STATUSES = projection_schema.PROJECTION_STATUSES
VERIFICATION_STATUSES = projection_schema.VERIFICATION_STATUSES
PILOT_FEATURES = projection_schema.PILOT_FEATURES

SCHEMA = "external_analysis_feature_linkage"
SCHEMA_VERSION = 1
GENERATOR_NAME = "feature_linkage"
GENERATOR_VERSION = "phase-1.73-b/1"
CLASSIFIER = "deterministic_symbol_and_declaration_matching"

EXTERNAL_ANALYSIS_SCHEMA = "external_code_analysis"
PROJECTION_SCHEMA = "feature_evidence_projection"

ANALYSIS_DIR = DOTAI / "learning" / "external_code" / "analysis"
ANALYSIS_INDEX_PATH = DOTAI / "learning" / "external_code" / "index.json"
PROJECTION_DIR = DOTAI / "learning" / "feature_evidence"
LINKAGE_DIR = DOTAI / "learning" / "external_code" / "feature_links"
FEATURES_DIR = PROJECT_ROOT / "Features"
GRAPH_PATH = DOTAI / "context" / "feature_graph.json"

# --- classification vocabulary -------------------------------------------------

DIRECT_EVIDENCE = "DIRECT_EVIDENCE"
INDIRECT_EVIDENCE = "INDIRECT_EVIDENCE"
DECLARED_CONTEXT = "DECLARED_CONTEXT"
POTENTIAL_RELEVANCE = "POTENTIAL_RELEVANCE"
AMBIGUOUS = "AMBIGUOUS"
NO_SUPPORTED_LINK = "NO_SUPPORTED_LINK"

CLASSIFICATIONS = (DIRECT_EVIDENCE, INDIRECT_EVIDENCE, DECLARED_CONTEXT,
                   POTENTIAL_RELEVANCE, AMBIGUOUS, NO_SUPPORTED_LINK)
LINKED_CLASSIFICATIONS = frozenset({DIRECT_EVIDENCE, INDIRECT_EVIDENCE,
                                    DECLARED_CONTEXT, POTENTIAL_RELEVANCE,
                                    AMBIGUOUS})

DIRECT_EVIDENCE_TYPES = frozenset({"SYMBOL_EXACT_MATCH"})
DECLARED_EVIDENCE_TYPES = frozenset({"DECLARED_SYMBOL_MATCH", "DECLARED_SOURCE_SNIPPET"})
GRAPH_EVIDENCE_TYPES = frozenset({"GRAPH_RELATION"})
CLUE_EVIDENCE_TYPES = frozenset({"SYMBOL_TOKEN_OVERLAP"})
NONE_EVIDENCE_TYPES = frozenset({"NONE"})
EVIDENCE_TYPES = (DIRECT_EVIDENCE_TYPES | DECLARED_EVIDENCE_TYPES
                  | GRAPH_EVIDENCE_TYPES | CLUE_EVIDENCE_TYPES | NONE_EVIDENCE_TYPES)

SOURCE_SIDES = frozenset({"EXTERNAL_ANALYSIS", "FEATURE_PROJECTION",
                          "FEATURE_METADATA", "FEATURE_GRAPH", "BOTH"})

# Batch B.1: an item is either positive linkage evidence or the record of a pair
# evaluation that found nothing.  The field is optional so Batch B records, which
# predate it, stay valid and readable unchanged.
LINKAGE_EVIDENCE_ROLE = "LINKAGE_EVIDENCE"
PAIR_EVALUATION_ROLE = "PAIR_EVALUATION"
EVIDENCE_ROLES = frozenset({LINKAGE_EVIDENCE_ROLE, PAIR_EVALUATION_ROLE})

GRAPH_RELATION_TYPES = frozenset({"works_with", "commonly_used_with",
                                  "requires", "composes_with"})

# Keys that would turn a linkage record into a similarity / admission decision.
FORBIDDEN_KEYS = frozenset({
    "similarity", "similarity_score", "similarity_scores",
    "similarity_classification", "similarity_engine", "candidate",
    "candidate_id", "feature_candidate", "admission", "admission_decision",
    "admission_gate", "promoted", "promotion", "promotion_decision",
    "feature_verified", "verified",
})

# Engine / lifecycle identifiers never count as distinctive evidence.
BUILTIN_SYMBOLS = frozenset({
    "_init", "_ready", "_process", "_physics_process", "_input", "_unhandled_input",
    "_draw", "_notification", "_enter_tree", "_exit_tree", "_get", "_set",
    "_get_property_list", "_to_string", "queue_free", "new", "print",
    "connect", "disconnect", "emit", "emit_signal", "call", "call_deferred",
    "get_node", "get_parent", "get_children", "instantiate", "duplicate",
    "get", "set", "has", "is", "add", "remove", "erase", "clear",
})

STOP_TOKENS = frozenset({
    "this", "that", "with", "from", "into", "when", "then", "than", "true",
    "false", "null", "none", "void", "bool", "int", "float", "string", "self",
    "node", "node2d", "node3d", "data", "item", "items", "list", "array",
    "dict", "dictionary", "value", "values", "name", "names", "kind", "type",
    "file", "path", "main", "test", "tests", "func", "function", "return",
    "else", "elif", "while", "update", "ready", "init", "enter", "exit",
    "process", "physics", "input", "draw", "tick", "apply", "reset", "clear",
    "default", "current", "get", "set", "has", "add", "remove", "load",
    "save", "call", "called", "using", "used", "base", "left", "right",
    "width", "height", "size", "count", "index", "text", "label", "button",
    "color", "colour", "visual", "state", "changed", "signal", "event",
})

REQUIRED_RECORD_FIELDS = (
    "schema", "schema_version", "linkage_id", "analysis_id", "snippet_id",
    "feature_id", "feature_name", "generated_at", "generator",
    "linkage_classification", "linkage_outcome", "external_analysis",
    "feature_projection", "evidence_items", "evidence_limitations",
    "pair_evaluation", "source_verification", "limitations",
)

REQUIRED_EVIDENCE_FIELDS = (
    "evidence_id", "evidence_type", "evidence_status", "source_side",
    "source_path", "symbol_name", "line_reference", "matched_value",
    "explanation", "provenance_reference",
)

LIMITATION_FIELDS = (
    "analysis_status", "projection_status", "verification_status",
    "parser_limitations", "missing_evidence", "ambiguity_reasons",
    "unsupported_content", "provenance_limitations",
)


class LinkageError(RuntimeError):
    """Raised when a linkage cannot be built from the available sources."""


class LinkageValidationError(LinkageError):
    """Raised when a linkage record does not satisfy the Batch B schema."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _rel(path: Any) -> str:
    text = str(path or "")
    if not text:
        return ""
    try:
        return Path(text).resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return Path(text).as_posix()


def _is_hex64(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


def _linkage_id(analysis_id: str, feature_id: str) -> str:
    """Stable id: derived from the identity pair only, never from file mtime."""
    return "lnk-" + _sha256_text("phase-1.73-b|%s|%s" % (analysis_id, feature_id))[:16]


def _tokenize(raw: Any) -> list[str]:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(raw or ""))
    parts = re.split(r"[^A-Za-z0-9]+", text)
    return [part.lower() for part in parts if part]


def _significant_tokens(raw: Any) -> set[str]:
    return {token for token in _tokenize(raw)
            if len(token) >= 4 and token not in STOP_TOKENS}


def _one_item_per_identifier(symbols: list[dict]) -> list[dict]:
    """One evidence item per identifier, even if a parser lists it twice.

    The external parser records a name both as a function and as an entry point.
    The same identifier is one piece of evidence, so the first occurrence wins and
    duplicated symbol-table rows never inflate the evidence count.
    """
    seen: set[str] = set()
    unique: list[dict] = []
    for symbol in symbols:
        name = str(symbol.get("name") or "")
        if name in seen:
            continue
        seen.add(name)
        unique.append(symbol)
    return unique


def _distinctive(name: Any) -> bool:
    text = str(name or "").strip()
    if not text or text.startswith("_"):
        return False
    return text not in BUILTIN_SYMBOLS


# --- source loading ------------------------------------------------------------


def load_external_analyses(analysis_dir: str | Path = ANALYSIS_DIR) -> dict[str, dict]:
    """Load every Analysis Record. Invalid sources raise, they are never skipped."""
    directory = Path(analysis_dir)
    if not directory.is_dir():
        raise LinkageError("external analysis directory not found: %s" % directory)
    records: dict[str, dict] = {}
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise LinkageError("cannot read analysis record %s: %s" % (path, exc))
        if not isinstance(data, dict) or data.get("schema") != EXTERNAL_ANALYSIS_SCHEMA:
            raise LinkageError("not an external analysis record: %s" % path)
        analysis_id = str(data.get("analysis_id") or "")
        if not analysis_id:
            raise LinkageError("analysis record without analysis_id: %s" % path)
        if analysis_id in records:
            raise LinkageError("duplicate analysis_id: %s" % analysis_id)
        if not str(data.get("analysis_status") or ""):
            raise LinkageError("analysis record without analysis_status: %s" % path)
        records[analysis_id] = {
            "analysis_id": analysis_id,
            "record": data,
            "path": _rel(path),
            "digest": _sha256_file(path),
        }
    if not records:
        raise LinkageError("no external analysis records found in %s" % directory)
    return records


def load_analysis_index(index_path: str | Path = ANALYSIS_INDEX_PATH) -> dict[str, dict]:
    """Load the External Analysis Index for cross-checking (optional file)."""
    path = Path(index_path)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LinkageError("cannot read analysis index %s: %s" % (path, exc))
    if not isinstance(data, dict) or data.get("schema") != "external_code_analysis_index":
        raise LinkageError("not an external analysis index: %s" % path)
    entries = data.get("analyses") or []
    if not isinstance(entries, list):
        raise LinkageError("external analysis index entries must be a list")
    result: dict[str, dict] = {}
    for entry in entries:
        if not isinstance(entry, dict) or not str(entry.get("analysis_id") or ""):
            raise LinkageError("external analysis index entry without analysis_id")
        result[str(entry["analysis_id"])] = entry
    return result


def cross_check_index(analyses: dict[str, dict], index: dict[str, dict]) -> dict:
    """Compare Analysis Records against the index without repairing anything."""
    if not index:
        return {"status": "INDEX_ABSENT", "missing_in_index": [], "missing_records": []}
    missing_in_index = sorted(set(analyses) - set(index))
    missing_records = sorted(set(index) - set(analyses))
    status = "MATCHED" if not missing_in_index and not missing_records else "MISMATCH"
    return {"status": status, "missing_in_index": missing_in_index,
            "missing_records": missing_records}


def load_feature_projections(projection_dir: str | Path = PROJECTION_DIR,
                             feature_ids: list[str] | None = None) -> dict[str, dict]:
    """Load Feature Evidence Projections. Read-only; contents are never rebuilt."""
    directory = Path(projection_dir)
    if not directory.is_dir():
        raise LinkageError("feature projection directory not found: %s" % directory)
    selected = list(feature_ids or PILOT_FEATURES)
    projections: dict[str, dict] = {}
    for feature_id in selected:
        path = directory / ("%s.json" % feature_id)
        if not path.is_file():
            raise LinkageError("feature projection missing: %s" % path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise LinkageError("cannot read projection %s: %s" % (path, exc))
        _check_projection_input(data, feature_id, path)
        projections[feature_id] = {
            "feature_id": feature_id,
            "record": data,
            "path": _rel(path),
            "digest": _sha256_file(path),
        }
    return projections


def _check_projection_input(projection: Any, feature_id: str, path: Path) -> None:
    if not isinstance(projection, dict):
        raise LinkageError("projection is not an object: %s" % path)
    if projection.get("schema") != PROJECTION_SCHEMA:
        raise LinkageError("not a feature evidence projection: %s" % path)
    if str(projection.get("feature_id") or "") != feature_id:
        raise LinkageError("projection feature_id mismatch for %s" % path)
    if projection.get("projection_status") not in PROJECTION_STATUSES:
        raise LinkageError("invalid projection_status in %s" % path)
    verification = projection.get("verification_status")
    if not isinstance(verification, dict):
        raise LinkageError("projection without verification_status: %s" % path)
    for field in ("feature_verification_status", "test_execution_status",
                  "runtime_verification_status", "behavior_verification_status"):
        if verification.get(field) not in VERIFICATION_STATUSES:
            raise LinkageError("invalid verification_status.%s in %s" % (field, path))
    if not str(verification.get("basis") or ""):
        raise LinkageError("verification_status.basis missing in %s" % path)
    for section in ("symbol_evidence", "interface_evidence", "capability_evidence",
                    "source_references", "analysis_references"):
        if not isinstance(projection.get(section), list):
            raise LinkageError("projection.%s must be a list in %s" % (section, path))


def load_declared_feature_snippets(features_dir: str | Path = FEATURES_DIR,
                                   feature_ids: list[str] | None = None) -> dict[str, set[str]]:
    """Collect `snippet_id:` values declared in Feature metadata comments."""
    directory = Path(features_dir)
    declared: dict[str, set[str]] = {}
    for feature_id in (feature_ids or PILOT_FEATURES):
        path = directory / feature_id / "feature.yaml"
        snippets: set[str] = set()
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            for match in re.finditer(r"snippet_id:\s*([A-Za-z0-9_.\-/]+)", text):
                snippets.add(match.group(1).strip())
        declared[feature_id] = snippets
    return declared


def load_graph_edges(graph_path: str | Path = GRAPH_PATH) -> list[dict]:
    path = Path(graph_path)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LinkageError("cannot read feature graph %s: %s" % (path, exc))
    edges = data.get("edges") if isinstance(data, dict) else None
    if not isinstance(edges, list):
        return []
    result = []
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        if edge.get("type") not in GRAPH_RELATION_TYPES:
            continue
        if not edge.get("from") or not edge.get("to"):
            continue
        result.append({"from": str(edge["from"]), "to": str(edge["to"]),
                       "type": str(edge["type"])})
    return result


# --- evidence extraction -------------------------------------------------------


def external_symbols(record: dict) -> list[dict]:
    """Distinctive, locatable identifiers extracted by the external analysis."""
    symbols = record.get("symbols") or {}
    items: list[dict] = []

    def add(name: Any, kind: str, line: Any = None) -> None:
        text = str(name or "").strip()
        if not _distinctive(text):
            return
        number = line if isinstance(line, int) else None
        items.append({"name": text, "kind": kind, "line": number})

    add(symbols.get("class_name"), "class_name")
    for entry, kind in ((symbols.get("functions"), "function"),
                        (symbols.get("signals"), "signal"),
                        (symbols.get("variables"), "variable"),
                        (symbols.get("exports"), "export")):
        for value in entry or []:
            if isinstance(value, dict):
                add(value.get("name"), kind, value.get("line"))
    for value in record.get("entry_points") or []:
        if isinstance(value, dict):
            add(value.get("name"), "entry_point", value.get("line"))

    seen: set[tuple[str, str]] = set()
    unique: list[dict] = []
    for item in items:
        key = (item["name"], item["kind"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def feature_symbol_index(projection: dict) -> tuple[dict[str, dict], dict[str, dict]]:
    """Return (source-extracted symbols, human-declared symbols) for a Feature."""
    source: dict[str, dict] = {}
    for item in projection.get("symbol_evidence") or []:
        if not isinstance(item, dict):
            continue
        if item.get("extraction_status") != "EXTRACTED":
            continue
        if item.get("source_type") != "GDSCRIPT_SOURCE":
            continue
        name = str((item.get("value") or {}).get("name") or "")
        if _distinctive(name):
            source.setdefault(name, item)
    declared: dict[str, dict] = {}
    for item in projection.get("interface_evidence") or []:
        if not isinstance(item, dict):
            continue
        name = str((item.get("value") or {}).get("name") or "")
        if _distinctive(name):
            declared.setdefault(name, item)
    for item in projection.get("capability_evidence") or []:
        if not isinstance(item, dict):
            continue
        name = str((item.get("value") or {}).get("capability") or "")
        if _distinctive(name):
            declared.setdefault(name, item)
    return source, declared


def _feature_identity_names(projection: dict) -> list[str]:
    names = [str(projection.get("feature_id") or ""), str(projection.get("feature_name") or "")]
    return [name for name in names if name]


def _evidence_item(evidence_type: str, evidence_status: str, source_side: str,
                   source_path: str, symbol_name: str, line_reference: Any,
                   matched_value: str, explanation: str, provenance_reference: str,
                   *, evidence_role: str = LINKAGE_EVIDENCE_ROLE, **extra: Any) -> dict:
    if evidence_type not in EVIDENCE_TYPES:
        raise LinkageValidationError("invalid evidence_type: %s" % evidence_type)
    if evidence_role not in EVIDENCE_ROLES:
        raise LinkageValidationError("invalid evidence_role: %s" % evidence_role)
    if evidence_status not in EVIDENCE_STATUSES:
        raise LinkageValidationError("invalid evidence_status: %s" % evidence_status)
    if source_side not in SOURCE_SIDES:
        raise LinkageValidationError("invalid source_side: %s" % source_side)
    item = {
        "evidence_type": evidence_type,
        "evidence_role": evidence_role,
        "evidence_status": evidence_status,
        "source_side": source_side,
        "source_path": source_path,
        "symbol_name": symbol_name,
        "line_reference": line_reference if isinstance(line_reference, int) else None,
        "matched_value": matched_value,
        "explanation": explanation,
        "provenance_reference": provenance_reference,
    }
    for key, value in extra.items():
        if key in FORBIDDEN_KEYS:
            raise LinkageValidationError("forbidden evidence key: %s" % key)
        item[key] = value
    return item


def _external_locator(record: dict) -> str:
    provenance = record.get("provenance") or {}
    return str(record.get("source_path") or provenance.get("source_path") or "")


def _evidence_source_path(record: dict) -> str:
    """Project-relative reference file when the mirror exists, else repo path."""
    reference = str(record.get("reference_path") or "")
    if reference:
        relative = _rel(reference)
        if relative:
            return relative
    return _external_locator(record)


def _declared_snippet_match(record: dict, snippets: set[str]) -> str:
    snippet_id = str(record.get("snippet_id") or "").strip()
    if not snippet_id or not snippets:
        return ""
    for declared in snippets:
        normalized = str(declared).strip()
        if normalized == snippet_id:
            return normalized
        if normalized.replace("/", "__") == snippet_id.replace("/", "__"):
            return normalized
    return ""


def _parser_limitations(record: dict) -> list[str]:
    values = [str(item) for item in record.get("limitations") or []]
    for question in record.get("unresolved_questions") or []:
        values.append("unresolved: %s" % question)
    return values


def _provenance_limitations(record: dict) -> list[str]:
    provenance = record.get("provenance") or {}
    status = str(record.get("provenance_status") or "UNKNOWN")
    values = ["provenance_status=%s" % status]
    reason = str(provenance.get("reason") or "")
    if reason:
        values.append(reason)
    if not str(record.get("commit_sha_full") or ""):
        values.append("no full commit SHA recorded")
    return values


def _unsupported_content(record: dict) -> list[str]:
    values: list[str] = []
    file_type = str(record.get("file_type") or "")
    parse_status = str(record.get("parse_status") or "")
    if file_type and file_type != "gdscript":
        values.append("file_type=%s is outside the GDScript evidence path" % file_type)
    if parse_status and parse_status != "parsed":
        values.append("parse_status=%s: the source was not fully parsed" % parse_status)
    if str(record.get("analysis_status") or "") == "unsupported_shader":
        values.append("shader analysis is unsupported; no symbols are available")
    return values


def evaluate_pair(analysis: dict, projection: dict,
                  declared_snippets: set[str] | None = None) -> dict:
    """Evaluate one Analysis <-> Feature pair using traceable evidence only."""
    record = analysis["record"]
    feature_id = projection["feature_id"]
    feature_record = projection["record"]
    external = external_symbols(record)
    source_symbols, declared_symbols = feature_symbol_index(feature_record)

    base = {
        "feature_id": feature_id,
        "feature_name": str(feature_record.get("feature_name") or feature_id),
        "evaluable": True,
        "tier": 0,
        "classification": NO_SUPPORTED_LINK,
        "evidence_items": [],
        "missing_evidence": [],
        "ambiguity_reasons": [],
        "pair_evaluation": {
            "external_symbol_count": len(external),
            "external_symbols": sorted({item["name"] for item in external}),
            "feature_source_symbol_count": len(source_symbols),
            "feature_declared_symbol_count": len(declared_symbols),
            "matched_symbols": [],
            "shared_tokens": [],
            "declared_relation": "",
        },
    }

    if not external:
        base["evaluable"] = False
        base["reason"] = (
            "no distinctive parseable symbols (analysis_status=%s, parse_status=%s, file_type=%s)"
            % (record.get("analysis_status"), record.get("parse_status"),
               record.get("file_type")))
        return base

    analysis_path = analysis["path"]
    source_path = _evidence_source_path(record)

    direct = _one_item_per_identifier(
        [symbol for symbol in external if symbol["name"] in source_symbols])
    declared_names = _one_item_per_identifier(
        [symbol for symbol in external if symbol["name"] in declared_symbols])
    snippet = _declared_snippet_match(record, declared_snippets or set())

    external_tokens: dict[str, str] = {}
    for symbol in external:
        for token in _significant_tokens(symbol["name"]):
            external_tokens.setdefault(token, symbol["name"])
    feature_tokens: dict[str, str] = {}
    for name in list(source_symbols) + list(declared_symbols) + _feature_identity_names(feature_record):
        for token in _significant_tokens(name):
            feature_tokens.setdefault(token, name)
    shared = sorted(set(external_tokens) & set(feature_tokens))

    items: list[dict] = []
    if direct:
        base["tier"] = 3
        base["classification"] = DIRECT_EVIDENCE
        for index, symbol in enumerate(direct, start=1):
            feature_item = source_symbols[symbol["name"]]
            items.append(_evidence_item(
                "SYMBOL_EXACT_MATCH", "EXTRACTED", "BOTH", source_path,
                symbol["name"], symbol["line"], symbol["name"],
                ("external %s '%s' at %s%s is the same identifier as the "
                 "Feature source-extracted symbol in %s"
                 % (symbol["kind"], symbol["name"], source_path,
                    (":%d" % symbol["line"]) if symbol["line"] else "",
                    feature_item.get("source_file") or "")),
                "%s#%s" % (analysis_path, symbol["name"]),
                evidence_id="ev-%d" % index,
                feature_evidence_id=str(feature_item.get("evidence_id") or ""),
                feature_source_path=str(feature_item.get("source_file") or ""),
                feature_source_line=feature_item.get("source_line")))
        base["pair_evaluation"]["matched_symbols"] = [s["name"] for s in direct]
    elif snippet or declared_names:
        base["tier"] = 2
        base["classification"] = DECLARED_CONTEXT
        if snippet:
            items.append(_evidence_item(
                "DECLARED_SOURCE_SNIPPET", "DECLARED", "FEATURE_METADATA",
                "Features/%s/feature.yaml" % feature_id, "", None, snippet,
                ("Feature metadata declares the source snippet '%s', which is the "
                 "same snippet_id as this external analysis record; the relation is "
                 "a human declaration, not a source-level identifier match" % snippet),
                "Features/%s/feature.yaml#snippet_id" % feature_id,
                evidence_id="ev-%d" % (len(items) + 1),
                external_snippet_id=str(record.get("snippet_id") or "")))
            base["pair_evaluation"]["declared_relation"] = "snippet_id:%s" % snippet
        for symbol in declared_names:
            declared_item = declared_symbols[symbol["name"]]
            value = declared_item.get("value") or {}
            items.append(_evidence_item(
                "DECLARED_SYMBOL_MATCH", "DECLARED", "BOTH", source_path,
                symbol["name"], symbol["line"], symbol["name"],
                ("Feature metadata declares '%s' (%s), matching the external %s '%s' "
                 "at %s; the Feature side is human-declared, not source-extracted"
                 % (symbol["name"], value.get("kind") or "interface", symbol["kind"],
                    symbol["name"], source_path)),
                "%s#%s" % (analysis_path, symbol["name"]),
                evidence_id="ev-%d" % (len(items) + 1),
                feature_evidence_id=str(declared_item.get("evidence_id") or ""),
                feature_source_check=str((declared_item.get("value") or {}).get("source_check") or "")))
        base["pair_evaluation"]["matched_symbols"] = [s["name"] for s in declared_names]
        base["missing_evidence"] = [
            "association rests on a human declaration; no source-level identifier "
            "match exists across both sides"]
    elif shared:
        base["tier"] = 1
        base["classification"] = POTENTIAL_RELEVANCE
        for index, token in enumerate(shared, start=1):
            items.append(_evidence_item(
                "SYMBOL_TOKEN_OVERLAP", "PARTIAL", "BOTH", source_path,
                external_tokens[token], None, token,
                ("external symbol '%s' shares the significant token '%s' with Feature "
                 "symbol '%s'; this is a clue only, not an exact identifier, shared "
                 "class or declared relation"
                 % (external_tokens[token], token, feature_tokens[token])),
                "%s#token:%s" % (analysis_path, token),
                evidence_id="ev-%d" % index,
                feature_symbol=str(feature_tokens[token])))
        base["pair_evaluation"]["shared_tokens"] = shared
        base["missing_evidence"] = [
            "no exact shared identifier between external symbols and Feature symbols",
            "no shared class, signal or export identifier",
            "no declared external-source relation in Feature metadata"]
    else:
        items.append(_evidence_item(
            "NONE", "MISSING", "BOTH", source_path, "", None, "",
            ("compared %d external symbols (%s) against %d Feature source symbols and "
             "%d Feature declared symbols; no exact identifier match, no declared "
             "external-source relation and no shared significant token were found"
             % (len(external), ", ".join(sorted({s["name"] for s in external})),
                len(source_symbols), len(declared_symbols))),
            analysis_path,
            evidence_id="ev-1", evidence_role=PAIR_EVALUATION_ROLE))
        base["missing_evidence"] = [
            "no exact shared identifier between external symbols and Feature symbols",
            "no declared external-source relation in Feature metadata",
            "no shared significant token between the two symbol sets"]

    base["evidence_items"] = items
    return base


def resolve_ambiguity(evaluations: list[dict]) -> list[dict]:
    """Multiple Features matching at the same strongest tier are AMBIGUOUS."""
    evaluable = [item for item in evaluations if item.get("evaluable")]
    if not evaluable:
        return evaluations
    top = max(item["tier"] for item in evaluable)
    if top <= 0:
        return evaluations
    contenders = [item for item in evaluable if item["tier"] == top]
    if len(contenders) < 2:
        return evaluations
    feature_ids = sorted(item["feature_id"] for item in contenders)
    reason = ("single external analysis matches multiple Features at the same "
              "evidence tier (%s): %s" % (top, ", ".join(feature_ids)))
    for item in contenders:
        item["classification"] = AMBIGUOUS
        item["ambiguity_reasons"] = [reason]
        item["missing_evidence"] = ["the target Feature cannot be determined "
                                    "without disambiguating evidence"]
    return evaluations


# --- record construction -------------------------------------------------------


def build_linkage_record(analysis: dict, projection: dict, evaluation: dict) -> dict:
    """Assemble and validate one linkage record from an evaluated pair."""
    record = analysis["record"]
    feature_record = projection["record"]
    feature_id = projection["feature_id"]
    classification = evaluation["classification"]
    linkage_id = _linkage_id(analysis["analysis_id"], feature_id)
    verification = json.loads(json.dumps(feature_record.get("verification_status") or {}))

    items = []
    for index, item in enumerate(evaluation["evidence_items"], start=1):
        copy = dict(item)
        copy["evidence_id"] = "%s:%s:%02d" % (linkage_id, "ev", index)
        items.append(copy)

    limitations = [
        "evidence type only; not a similarity, quality, admission or promotion judgement",
        "analysis_status=%s" % record.get("analysis_status"),
        "projection_status=%s" % feature_record.get("projection_status"),
    ]
    if str(record.get("analysis_status") or "") != "analysis_complete":
        limitations.append("external analysis is not complete; its symbols are partial evidence")
    if feature_record.get("projection_status") != "COMPLETE":
        limitations.append("feature projection is not complete; coverage of Feature evidence is partial")

    external_source = {
        "analysis_record_path": analysis["path"],
        "analysis_record_digest": analysis["digest"],
        "source_repository": str(record.get("repo") or ""),
        "source_commit": str(record.get("commit_sha_full") or record.get("commit_sha") or ""),
        "source_path": _external_locator(record),
        "source_digest": str(record.get("source_digest") or ""),
        "analysis_status": str(record.get("analysis_status") or ""),
        "parse_status": str(record.get("parse_status") or ""),
        "provenance_status": str(record.get("provenance_status") or ""),
        "file_type": str(record.get("file_type") or ""),
        "source_url": str(record.get("source_url") or ""),
    }

    feature_block = {
        "feature_projection_path": projection["path"],
        "feature_projection_digest": projection["digest"],
        "feature_path": str(feature_record.get("feature_path") or ""),
        "feature_source_references": json.loads(json.dumps(
            feature_record.get("source_references") or [])),
        "feature_analysis_references": json.loads(json.dumps(
            feature_record.get("analysis_references") or [])),
        "projection_status": str(feature_record.get("projection_status") or ""),
        "verification_status": verification,
    }

    limitations_block = {
        "analysis_status": str(record.get("analysis_status") or ""),
        "projection_status": str(feature_record.get("projection_status") or ""),
        "verification_status": verification,
        "parser_limitations": _parser_limitations(record),
        "missing_evidence": list(evaluation.get("missing_evidence") or []),
        "ambiguity_reasons": list(evaluation.get("ambiguity_reasons") or []),
        "unsupported_content": _unsupported_content(record),
        "provenance_limitations": _provenance_limitations(record),
    }

    source_verification = {
        "analysis_record": {"path": analysis["path"], "digest": analysis["digest"],
                            "digest_status": "MATCHED"},
        "feature_projection": {"path": projection["path"], "digest": projection["digest"],
                               "digest_status": "MATCHED"},
        "external_source_file": _external_source_check(record),
        "feature_sources": [
            {"path": str(ref.get("source_path") or ""),
             "source_status": str(ref.get("source_status") or ""),
             "source_digest": str(ref.get("source_digest") or "")}
            for ref in feature_record.get("source_references") or []
            if isinstance(ref, dict)
        ],
    }

    built = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "linkage_id": linkage_id,
        "analysis_id": str(analysis["analysis_id"]),
        "snippet_id": str(record.get("snippet_id") or ""),
        "feature_id": feature_id,
        "feature_name": str(feature_record.get("feature_name") or feature_id),
        "generated_at": _now(),
        "generator": {"name": GENERATOR_NAME, "version": GENERATOR_VERSION,
                      "classifier": CLASSIFIER},
        "linkage_classification": classification,
        "linkage_outcome": "LINKED" if classification in LINKED_CLASSIFICATIONS else "NOT_LINKED",
        "external_analysis": external_source,
        "feature_projection": feature_block,
        "evidence_items": items,
        "evidence_limitations": limitations_block,
        "pair_evaluation": dict(evaluation.get("pair_evaluation") or {}),
        "source_verification": source_verification,
        "limitations": limitations,
    }
    if evaluation.get("ambiguous_from"):
        built["supersedes_classification"] = str(evaluation["ambiguous_from"])
    validate_linkage(built)
    return built


def _external_source_check(record: dict) -> dict:
    raw = record.get("source_file_path") or record.get("reference_path") or ""
    path = Path(str(raw)) if raw else None
    recorded = str(record.get("source_digest") or "")
    block = {"path": _rel(path) if path else "", "recorded_digest": recorded,
             "digest_status": "NOT_RECORDED"}
    if not recorded:
        return block
    if path is None or not path.is_file():
        block["digest_status"] = "NOT_FOUND"
        return block
    block["digest_status"] = "MATCHED" if _sha256_file(path) == recorded else "MISMATCH"
    return block


def validate_linkage(record: Any) -> None:
    """Validate one linkage record; raise on the first structural problem found."""
    if not isinstance(record, dict):
        raise LinkageValidationError("linkage record must be an object")
    errors: list[str] = []
    for field in REQUIRED_RECORD_FIELDS:
        if field not in record:
            errors.append("missing field: %s" % field)
    if errors:
        raise LinkageValidationError("; ".join(errors))
    if record.get("schema") != SCHEMA:
        errors.append("invalid schema")
    if record.get("schema_version") != SCHEMA_VERSION:
        errors.append("invalid schema_version")
    analysis_id = str(record.get("analysis_id") or "")
    feature_id = str(record.get("feature_id") or "")
    if not analysis_id:
        errors.append("analysis_id must be non-empty")
    if not feature_id:
        errors.append("feature_id must be non-empty")
    linkage_id = str(record.get("linkage_id") or "")
    if not re.match(r"^lnk-[0-9a-f]{16}$", linkage_id):
        errors.append("linkage_id must look like lnk-<16 hex>")
    elif analysis_id and feature_id and linkage_id != _linkage_id(analysis_id, feature_id):
        errors.append("linkage_id is not the stable id of this analysis/feature pair")
    if not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", str(record.get("generated_at") or "")):
        errors.append("generated_at must be an ISO-8601 UTC timestamp")

    generator = record.get("generator")
    if not isinstance(generator, dict) or not str(generator.get("version") or ""):
        errors.append("generator.version must be recorded")

    classification = record.get("linkage_classification")
    if classification not in CLASSIFICATIONS:
        errors.append("invalid linkage_classification: %s" % classification)
    outcome = record.get("linkage_outcome")
    expected_outcome = "LINKED" if classification in LINKED_CLASSIFICATIONS else "NOT_LINKED"
    if outcome != expected_outcome:
        errors.append("linkage_outcome must be %s for %s" % (expected_outcome, classification))

    external = record.get("external_analysis")
    if not isinstance(external, dict):
        errors.append("external_analysis must be an object")
    else:
        for field in ("analysis_record_path", "analysis_record_digest", "source_repository",
                      "source_commit", "source_path", "source_digest", "analysis_status",
                      "parse_status", "provenance_status"):
            if field not in external:
                errors.append("external_analysis missing %s" % field)
        if not _is_hex64(external.get("analysis_record_digest")):
            errors.append("analysis_record_digest must be 64 hex characters")
        if str(external.get("source_digest") or "") and not _is_hex64(external.get("source_digest")):
            errors.append("source_digest must be empty or 64 hex characters")
        if not str(external.get("analysis_record_path") or ""):
            errors.append("analysis_record_path must be non-empty")
        if not str(external.get("analysis_status") or ""):
            errors.append("analysis_status must be preserved")

    feature_block = record.get("feature_projection")
    if not isinstance(feature_block, dict):
        errors.append("feature_projection must be an object")
    else:
        for field in ("feature_projection_path", "feature_projection_digest",
                      "feature_source_references", "feature_analysis_references",
                      "projection_status", "verification_status"):
            if field not in feature_block:
                errors.append("feature_projection missing %s" % field)
        if not _is_hex64(feature_block.get("feature_projection_digest")):
            errors.append("feature_projection_digest must be 64 hex characters")
        if feature_block.get("projection_status") not in PROJECTION_STATUSES:
            errors.append("invalid projection_status in feature_projection")
        if not isinstance(feature_block.get("feature_source_references"), list):
            errors.append("feature_source_references must be a list")
        if not isinstance(feature_block.get("feature_analysis_references"), list):
            errors.append("feature_analysis_references must be a list")
        verification = feature_block.get("verification_status")
        if not isinstance(verification, dict):
            errors.append("verification_status must be copied from the projection")
        else:
            for field in ("feature_verification_status", "test_execution_status",
                          "runtime_verification_status", "behavior_verification_status"):
                if verification.get(field) not in VERIFICATION_STATUSES:
                    errors.append("invalid verification_status.%s" % field)
            if not str(verification.get("basis") or ""):
                errors.append("verification_status.basis must be non-empty")

    items = record.get("evidence_items")
    if not isinstance(items, list) or not items:
        errors.append("evidence_items must be a non-empty list")
        items = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append("evidence_items[%d] must be an object" % index)
            continue
        for field in REQUIRED_EVIDENCE_FIELDS:
            if field not in item:
                errors.append("evidence_items[%d] missing %s" % (index, field))
        if item.get("evidence_type") not in EVIDENCE_TYPES:
            errors.append("evidence_items[%d] invalid evidence_type: %s"
                          % (index, item.get("evidence_type")))
        if item.get("evidence_status") not in EVIDENCE_STATUSES:
            errors.append("evidence_items[%d] invalid evidence_status: %s"
                          % (index, item.get("evidence_status")))
        if item.get("source_side") not in SOURCE_SIDES:
            errors.append("evidence_items[%d] invalid source_side: %s"
                          % (index, item.get("source_side")))
        if not str(item.get("source_path") or ""):
            errors.append("evidence_items[%d] requires a source_path" % index)
        if not str(item.get("explanation") or "").strip():
            errors.append("evidence_items[%d] requires an explanation" % index)
        if not str(item.get("provenance_reference") or ""):
            errors.append("evidence_items[%d] requires a provenance_reference" % index)
        line = item.get("line_reference")
        if line is not None and not isinstance(line, int):
            errors.append("evidence_items[%d] line_reference must be an integer or null" % index)
        role = item.get("evidence_role")
        if role is not None and role not in EVIDENCE_ROLES:
            errors.append("evidence_items[%d] invalid evidence_role: %s" % (index, role))

    types = {item.get("evidence_type") for item in items if isinstance(item, dict)}

    if classification == DIRECT_EVIDENCE:
        supporting = [item for item in items
                      if isinstance(item, dict)
                      and item.get("evidence_type") in DIRECT_EVIDENCE_TYPES
                      and item.get("evidence_status") == "EXTRACTED"
                      and str(item.get("symbol_name") or "")]
        if not supporting:
            errors.append("DIRECT_EVIDENCE requires an EXTRACTED exact symbol match")
        for item in supporting:
            if not str(item.get("feature_evidence_id") or ""):
                errors.append("DIRECT_EVIDENCE items must reference the Feature evidence_id")
    if classification == INDIRECT_EVIDENCE:
        indirect = [item for item in items if isinstance(item, dict)
                    and item.get("evidence_type") in GRAPH_EVIDENCE_TYPES
                    and item.get("intermediate_path")]
        if not indirect:
            errors.append("INDIRECT_EVIDENCE requires a graph relation with intermediate_path")
    if classification == DECLARED_CONTEXT:
        if types & DIRECT_EVIDENCE_TYPES:
            errors.append("DECLARED_CONTEXT must not claim source-level direct evidence")
        if not (types & DECLARED_EVIDENCE_TYPES):
            errors.append("DECLARED_CONTEXT requires a declared evidence item")
    if classification == POTENTIAL_RELEVANCE:
        if types & (DIRECT_EVIDENCE_TYPES | DECLARED_EVIDENCE_TYPES | GRAPH_EVIDENCE_TYPES):
            errors.append("POTENTIAL_RELEVANCE must not carry direct or declared evidence")
        if not (types & CLUE_EVIDENCE_TYPES):
            errors.append("POTENTIAL_RELEVANCE requires a documented clue item")
    if classification == NO_SUPPORTED_LINK:
        if types & (DIRECT_EVIDENCE_TYPES | DECLARED_EVIDENCE_TYPES | GRAPH_EVIDENCE_TYPES
                    | CLUE_EVIDENCE_TYPES):
            errors.append("NO_SUPPORTED_LINK must not carry supporting evidence")
        if not (types & NONE_EVIDENCE_TYPES):
            errors.append("NO_SUPPORTED_LINK requires an item documenting the comparison")

    if classification == NO_SUPPORTED_LINK:
        for index, item in enumerate(items):
            if isinstance(item, dict) and item.get("evidence_role") == LINKAGE_EVIDENCE_ROLE:
                errors.append("evidence_items[%d] of a NO_SUPPORTED_LINK record must be "
                              "PAIR_EVALUATION, not linkage evidence" % index)
    elif classification in LINKED_CLASSIFICATIONS:
        for index, item in enumerate(items):
            if isinstance(item, dict) and item.get("evidence_role") == PAIR_EVALUATION_ROLE:
                errors.append("evidence_items[%d] of a linked record must not be a "
                              "PAIR_EVALUATION marker" % index)

    limitations_block = record.get("evidence_limitations")
    if not isinstance(limitations_block, dict):
        errors.append("evidence_limitations must be an object")
    else:
        for field in LIMITATION_FIELDS:
            if field not in limitations_block:
                errors.append("evidence_limitations missing %s" % field)
        for field in ("parser_limitations", "missing_evidence", "ambiguity_reasons",
                      "unsupported_content", "provenance_limitations"):
            if not isinstance(limitations_block.get(field), list):
                errors.append("evidence_limitations.%s must be a list" % field)
        if isinstance(external, dict) and limitations_block.get("analysis_status") != external.get("analysis_status"):
            errors.append("evidence_limitations.analysis_status must match the analysis record")
        if isinstance(feature_block, dict):
            if limitations_block.get("projection_status") != feature_block.get("projection_status"):
                errors.append("evidence_limitations.projection_status must match the projection")
            if limitations_block.get("verification_status") != feature_block.get("verification_status"):
                errors.append("evidence_limitations.verification_status must match the projection")
        if classification == AMBIGUOUS and not limitations_block.get("ambiguity_reasons"):
            errors.append("AMBIGUOUS requires recorded ambiguity_reasons")

    if not isinstance(record.get("pair_evaluation"), dict):
        errors.append("pair_evaluation must be an object")
    if not isinstance(record.get("source_verification"), dict):
        errors.append("source_verification must be an object")
    if not isinstance(record.get("limitations"), list) or not record.get("limitations"):
        errors.append("limitations must be a non-empty list")

    for path in _forbidden_key_paths(record):
        errors.append("forbidden decision key present: %s" % path)

    if errors:
        raise LinkageValidationError("; ".join(errors))


def _forbidden_key_paths(value: Any, prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = "%s.%s" % (prefix, key) if prefix else str(key)
            if str(key).lower() in FORBIDDEN_KEYS:
                found.append(path)
            found.extend(_forbidden_key_paths(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_forbidden_key_paths(child, "%s[%d]" % (prefix, index)))
    return found


# --- writing and freshness -----------------------------------------------------


def verify_record_sources(record: dict) -> None:
    """Verify that the digests recorded in a linkage still describe the files."""
    external = record["external_analysis"]
    analysis_path = _path_for(external["analysis_record_path"])
    if not analysis_path.is_file():
        raise LinkageValidationError("analysis record missing: %s" % external["analysis_record_path"])
    if _sha256_file(analysis_path) != external["analysis_record_digest"]:
        raise LinkageValidationError(
            "analysis record digest changed: %s" % external["analysis_record_path"])
    feature_block = record["feature_projection"]
    projection_path = _path_for(feature_block["feature_projection_path"])
    if not projection_path.is_file():
        raise LinkageValidationError(
            "feature projection missing: %s" % feature_block["feature_projection_path"])
    if _sha256_file(projection_path) != feature_block["feature_projection_digest"]:
        raise LinkageValidationError(
            "feature projection digest changed: %s" % feature_block["feature_projection_path"])


def _path_for(raw: Any) -> Path:
    path = Path(str(raw))
    return path if path.is_absolute() else (PROJECT_ROOT / path)


def write_linkage(record: dict, out_dir: str | Path = LINKAGE_DIR, *,
                  replace_func=os.replace, verify_sources: bool = True) -> str:
    """Atomic single-file write: validate, verify, re-read, then replace."""
    validate_linkage(record)
    if verify_sources:
        verify_record_sources(record)
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / ("%s__%s.json" % (record["analysis_id"], record["feature_id"]))
    fd, temporary = tempfile.mkstemp(prefix=".feature-link-", suffix=".tmp", dir=str(directory))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(record, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        loaded = json.loads(Path(temporary).read_text(encoding="utf-8"))
        validate_linkage(loaded)
        if verify_sources:
            verify_record_sources(loaded)
        replace_func(temporary, str(target))
        return str(target)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def evaluate_freshness(record: dict, *,
                       generator_version: str = GENERATOR_VERSION) -> dict:
    """Decide whether a stored linkage still rests on its current sources."""
    try:
        validate_linkage(record)
    except LinkageValidationError as exc:
        return {"status": "INVALID", "reasons": [str(exc)], "changed_sources": []}
    reasons: list[str] = []
    changed: list[str] = []
    stored_version = str((record.get("generator") or {}).get("version") or "")
    if stored_version != generator_version:
        reasons.append("LINKAGE_GENERATOR_VERSION_CHANGED: %s -> %s"
                       % (stored_version, generator_version))
    external = record["external_analysis"]
    feature_block = record["feature_projection"]
    analysis_path = _path_for(external.get("analysis_record_path"))
    projection_path = _path_for(feature_block.get("feature_projection_path"))
    missing = False
    if not analysis_path.is_file():
        reasons.append("ANALYSIS_RECORD_MISSING: %s" % external.get("analysis_record_path"))
        missing = True
    elif _sha256_file(analysis_path) != external.get("analysis_record_digest"):
        changed.append("analysis_record:%s" % external.get("analysis_record_path"))
    if not projection_path.is_file():
        reasons.append("FEATURE_PROJECTION_MISSING: %s"
                       % feature_block.get("feature_projection_path"))
        missing = True
    elif _sha256_file(projection_path) != feature_block.get("feature_projection_digest"):
        changed.append("feature_projection:%s" % feature_block.get("feature_projection_path"))
    if changed:
        reasons.append("SOURCE_DIGEST_CHANGED: %s" % ", ".join(changed))
    if missing:
        return {"status": "MISSING_SOURCE", "reasons": reasons, "changed_sources": changed}
    if reasons:
        return {"status": "STALE", "reasons": reasons, "changed_sources": changed}
    return {"status": "FRESH", "reasons": [], "changed_sources": []}


# --- pilot build ---------------------------------------------------------------


def _apply_indirect(evaluations: dict[tuple[str, str], dict],
                    edges: list[dict]) -> None:
    """Promote unevidenced pairs to INDIRECT_EVIDENCE through a graph relation."""
    direct_by_feature: dict[str, list[tuple[str, str]]] = {}
    for (analysis_id, feature_id), evaluation in evaluations.items():
        if evaluation.get("evaluable") and evaluation["classification"] == DIRECT_EVIDENCE:
            direct_by_feature.setdefault(feature_id, []).append(
                (analysis_id, feature_id))
    if not direct_by_feature:
        return
    neighbours: dict[str, list[dict]] = {}
    for edge in edges:
        neighbours.setdefault(edge["from"], []).append(edge)
        neighbours.setdefault(edge["to"], []).append(
            {"from": edge["to"], "to": edge["from"], "type": edge["type"]})
    for (analysis_id, feature_id), evaluation in evaluations.items():
        if not evaluation.get("evaluable"):
            continue
        if evaluation["classification"] != NO_SUPPORTED_LINK:
            continue
        for edge in neighbours.get(feature_id, []):
            sources = direct_by_feature.get(edge["to"]) or []
            matching = [pair for pair in sources if pair[0] == analysis_id]
            if not matching:
                continue
            path = [feature_id, edge["type"], edge["to"]]
            evaluation["classification"] = INDIRECT_EVIDENCE
            evaluation["evidence_items"] = [_evidence_item(
                "GRAPH_RELATION", "DECLARED", "FEATURE_GRAPH",
                ".ai/context/feature_graph.json", edge["to"], None, edge["type"],
                ("Feature '%s' is connected to '%s' by the declared '%s' relation, and "
                 "this analysis has a direct link to '%s'; the relation to '%s' is "
                 "indirect and has no direct identifier match"
                 % (feature_id, edge["to"], edge["type"], edge["to"], feature_id)),
                "feature_graph.json#%s-%s-%s" % (feature_id, edge["type"], edge["to"]),
                evidence_id="ev-1", intermediate_path=path)]
            evaluation["missing_evidence"] = [
                "evidence is indirect: no direct identifier match between this "
                "analysis and this Feature"]
            evaluation["pair_evaluation"]["declared_relation"] = "graph:%s" % edge["type"]
            break


def build_linkages(analysis_ids: list[str] | None = None, *, pilot: bool = True,
                   analysis_dir: str | Path = ANALYSIS_DIR,
                   projection_dir: str | Path = PROJECTION_DIR,
                   features_dir: str | Path = FEATURES_DIR,
                   graph_path: str | Path = GRAPH_PATH,
                   out_dir: str | Path = LINKAGE_DIR,
                   replace_func=os.replace,
                   feature_ids: list[str] | None = None) -> dict:
    """Build linkage records for the selected analyses; one file per pair."""
    selected_features = list(feature_ids or PILOT_FEATURES)
    analyses = load_external_analyses(analysis_dir)
    projections = load_feature_projections(projection_dir, selected_features)
    declared = load_declared_feature_snippets(features_dir, selected_features)
    edges = load_graph_edges(graph_path)

    if analysis_ids:
        unknown = [value for value in analysis_ids if value not in analyses]
        if unknown:
            raise LinkageError("unknown analysis_id: %s" % ", ".join(sorted(unknown)))
        targets = [value for value in sorted(analyses) if value in set(analysis_ids)]
    elif pilot:
        targets = sorted(analyses)
    else:
        raise LinkageError("choose --pilot or --analysis")

    evaluations: dict[tuple[str, str], dict] = {}
    unevaluable: list[dict] = []
    for analysis_id in targets:
        per_feature = [evaluate_pair(analyses[analysis_id], projections[feature_id],
                                     declared.get(feature_id, set()))
                       for feature_id in selected_features]
        per_feature = resolve_ambiguity(per_feature)
        for evaluation in per_feature:
            if evaluation.get("evaluable"):
                evaluations[(analysis_id, evaluation["feature_id"])] = evaluation
            else:
                unevaluable.append({
                    "analysis_id": analysis_id,
                    "feature_id": evaluation["feature_id"],
                    "reason": evaluation.get("reason", ""),
                })

    _apply_indirect(evaluations, edges)

    built: list[dict] = []
    failed: list[dict] = []
    for (analysis_id, feature_id) in sorted(evaluations):
        evaluation = evaluations[(analysis_id, feature_id)]
        try:
            record = build_linkage_record(analyses[analysis_id], projections[feature_id],
                                          evaluation)
            path = write_linkage(record, out_dir, replace_func=replace_func)
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            failed.append({"analysis_id": analysis_id, "feature_id": feature_id,
                           "error": "%s: %s" % (type(exc).__name__, exc)})
            continue
        built.append({"linkage_id": record["linkage_id"], "analysis_id": analysis_id,
                      "feature_id": feature_id,
                      "classification": record["linkage_classification"],
                      "outcome": record["linkage_outcome"],
                      "evidence_count": len(record["evidence_items"]),
                      "path": _rel(path)})

    counts = {name: 0 for name in CLASSIFICATIONS}
    for item in built:
        counts[item["classification"]] += 1
    total_pairs = len(targets) * len(selected_features)
    summary = {
        "analyses": len(targets),
        "features": len(selected_features),
        "total_pairs": total_pairs,
        "evaluated_pairs": len(evaluations),
        "unevaluable_pairs": len(unevaluable),
        "built": len(built),
        "failed": len(failed),
        "classifications": counts,
    }
    return {"built": built, "failed": failed, "unevaluable": unevaluable,
            "summary": summary}


def load_linkage_records(out_dir: str | Path = LINKAGE_DIR) -> list[dict]:
    directory = Path(out_dir)
    if not directory.is_dir():
        return []
    records: list[dict] = []
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            records.append({"__invalid__": str(exc), "__path__": _rel(path)})
            continue
        if isinstance(data, dict):
            data["__path__"] = _rel(path)
        records.append(data)
    return records


# --- Batch B.2: read-side seed qualification -----------------------------------

def linkage_evidence_items(record: dict) -> list[dict]:
    """Return the stored items that may support this record's linkage.

    Downstream stages must use this instead of reading ``evidence_items``
    directly.  An item marked ``PAIR_EVALUATION`` only records that the pair was
    compared and found nothing, so it is never returned.  Batch B records
    predate ``evidence_role``; for those the classification decides: a linked
    record contributes its non-``NONE`` items, ``NO_SUPPORTED_LINK`` contributes
    none.
    """
    items = record.get("evidence_items") or []
    classification = record.get("linkage_classification")
    selected: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if not str(item.get("evidence_type") or ""):
            continue
        role = item.get("evidence_role")
        if role is not None:
            if role != LINKAGE_EVIDENCE_ROLE:
                continue
        elif (classification not in LINKED_CLASSIFICATIONS
              or item.get("evidence_type") in NONE_EVIDENCE_TYPES):
            continue
        selected.append(item)
    return selected


def is_graph_derived_relation(record: dict) -> bool:
    """True when a record's support comes only from an internal Feature-graph edge.

    Such a relation does not show that the external code implements the Feature;
    it shows only that this analysis is directly linked to a neighbouring
    Feature and that the graph declares a relation to this one.
    """
    if record.get("linkage_classification") != INDIRECT_EVIDENCE:
        return False
    items = linkage_evidence_items(record)
    if not items:
        return False
    return all(item.get("evidence_type") in GRAPH_EVIDENCE_TYPES
               and item.get("source_side") == "FEATURE_GRAPH"
               and item.get("intermediate_path") for item in items)


def check_linkages(analysis_ids: list[str] | None = None, *, pilot: bool = True,
                   analysis_dir: str | Path = ANALYSIS_DIR,
                   projection_dir: str | Path = PROJECTION_DIR,
                   features_dir: str | Path = FEATURES_DIR,
                   graph_path: str | Path = GRAPH_PATH,
                   out_dir: str | Path = LINKAGE_DIR,
                   feature_ids: list[str] | None = None) -> dict:
    """Check freshness of stored linkages against the current sources."""
    selected_features = list(feature_ids or PILOT_FEATURES)
    analyses = load_external_analyses(analysis_dir)
    load_feature_projections(projection_dir, selected_features)
    if analysis_ids:
        unknown = [value for value in analysis_ids if value not in analyses]
        if unknown:
            raise LinkageError("unknown analysis_id: %s" % ", ".join(sorted(unknown)))
        target_ids = set(analysis_ids)
    elif pilot:
        target_ids = set(analyses)
    else:
        raise LinkageError("choose --pilot or --analysis")

    stored = load_linkage_records(out_dir)
    checked: list[dict] = []
    counts = {"FRESH": 0, "STALE": 0, "MISSING_SOURCE": 0, "INVALID": 0}
    for record in stored:
        if "__invalid__" in record:
            counts["INVALID"] += 1
            checked.append({"path": record.get("__path__", ""), "status": "INVALID",
                            "reasons": [record["__invalid__"]], "changed_sources": []})
            continue
        analysis_id = str(record.get("analysis_id") or "")
        if analysis_id not in target_ids:
            continue
        result = evaluate_freshness(record)
        counts[result["status"]] += 1
        checked.append({
            "path": record.get("__path__", ""),
            "linkage_id": str(record.get("linkage_id") or ""),
            "analysis_id": analysis_id,
            "feature_id": str(record.get("feature_id") or ""),
            "classification": str(record.get("linkage_classification") or ""),
            "status": result["status"],
            "reasons": result["reasons"],
            "changed_sources": result["changed_sources"],
        })

    expected: set[tuple[str, str]] = set()
    for analysis_id in sorted(target_ids):
        for feature_id in selected_features:
            if external_symbols(analyses[analysis_id]["record"]):
                expected.add((analysis_id, feature_id))
    present = {(item["analysis_id"], item["feature_id"]) for item in checked
               if item.get("analysis_id")}
    missing_records = sorted("%s__%s" % pair for pair in expected - present)
    unexpected_records = sorted("%s__%s" % pair for pair in present - expected)
    return {
        "checked": checked,
        "status_counts": counts,
        "coverage": {
            "expected_records": len(expected),
            "checked_records": len(present),
            "missing_records": missing_records,
            "unexpected_records": unexpected_records,
        },
        "generator_version": GENERATOR_VERSION,
    }


# --- reporting -----------------------------------------------------------------


def print_build_report(result: dict) -> None:
    summary = result["summary"]
    print("pairs: total=%d evaluated=%d unevaluable=%d built=%d failed=%d"
          % (summary["total_pairs"], summary["evaluated_pairs"],
             summary["unevaluable_pairs"], summary["built"], summary["failed"]))
    for name in CLASSIFICATIONS:
        print("  %-20s %d" % (name, summary["classifications"][name]))
    print("")
    for item in result["built"]:
        print("%s | %s | %s | evidence=%d | %s"
              % (item["analysis_id"], item["feature_id"], item["classification"],
                 item["evidence_count"], item["linkage_id"]))
    for item in result["unevaluable"]:
        print("UNEVALUABLE | %s | %s | %s"
              % (item["analysis_id"], item["feature_id"], item["reason"]))
    for item in result["failed"]:
        print("FAILED | %s | %s | %s"
              % (item["analysis_id"], item["feature_id"], item["error"]))


def print_check_report(result: dict) -> None:
    counts = result["status_counts"]
    print("freshness: FRESH=%d STALE=%d MISSING_SOURCE=%d INVALID=%d"
          % (counts["FRESH"], counts["STALE"], counts["MISSING_SOURCE"], counts["INVALID"]))
    coverage = result["coverage"]
    print("coverage: expected=%d checked=%d missing=%d unexpected=%d"
          % (coverage["expected_records"], coverage["checked_records"],
             len(coverage["missing_records"]), len(coverage["unexpected_records"])))
    for item in result["checked"]:
        print("%s | %s | %s | %s"
              % (item.get("analysis_id", "?"), item.get("feature_id", "?"),
                 item.get("classification", "?"), item["status"]))
        for reason in item["reasons"]:
            print("    %s" % reason)
    for name in coverage["missing_records"]:
        print("MISSING | %s" % name)
    for name in coverage["unexpected_records"]:
        print("UNEXPECTED | %s" % name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="External Analysis <-> Feature Evidence Linkage (Phase 1.73 Batch B)")
    sub = parser.add_subparsers(dest="command", required=True)

    for name, help_text in (("build", "build linkage records"),
                            ("check", "check linkage freshness")):
        command = sub.add_parser(name, help=help_text)
        command.add_argument("--pilot", action="store_true")
        command.add_argument("--analysis", action="append", default=[],
                             help="analysis_id (repeatable)")
        command.add_argument("--feature", action="append", default=[],
                             help="restrict to these Feature ids (repeatable)")
        command.add_argument("--analysis-dir", default=str(ANALYSIS_DIR))
        command.add_argument("--projection-dir", default=str(PROJECTION_DIR))
        command.add_argument("--features-dir", default=str(FEATURES_DIR))
        command.add_argument("--graph", default=str(GRAPH_PATH))
        command.add_argument("--out", default=str(LINKAGE_DIR))
        command.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    common = dict(analysis_dir=args.analysis_dir, projection_dir=args.projection_dir,
                  features_dir=args.features_dir, graph_path=args.graph,
                  out_dir=args.out, feature_ids=args.feature or None)
    try:
        if args.command == "build":
            result = build_linkages(args.analysis or None, pilot=args.pilot, **common)
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print_build_report(result)
            return 0 if not result["failed"] else 1
        result = check_linkages(args.analysis or None, pilot=args.pilot, **common)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_check_report(result)
        counts = result["status_counts"]
        coverage = result["coverage"]
        clean = (counts["STALE"] == 0 and counts["MISSING_SOURCE"] == 0
                 and counts["INVALID"] == 0 and not coverage["missing_records"]
                 and not coverage["unexpected_records"])
        return 0 if clean else 1
    except Exception as exc:  # noqa: BLE001 - reported with a failing exit code
        print("FAIL: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
