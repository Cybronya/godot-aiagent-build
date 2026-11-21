#!/usr/bin/env python3
"""Feature Evidence Projection (Phase 1.73, Batch A).

Builds a read-only, traceable projection from existing Feature metadata,
Feature Index/Graph, existing behavior source analysis, and targeted GDScript
symbol extraction.  It never writes Feature metadata, the Feature Index/Graph,
Source Analysis records, or External Analysis records.

The projection is derived evidence, not a new Feature Registry and not a
similarity/candidate/admission decision.

Semantics are intentionally split:
  * projection_status: completeness of the derived projection data only.
  * extraction_status: status of one evidence record only.
  * verification_status: conservative feature/test/runtime marker.  Batch A
    never executes tests or runtime code, so it never emits VERIFIED.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import ntpath
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TOOLS_DIR = HERE.parent
DOTAI = TOOLS_DIR.parent
PROJECT_ROOT = DOTAI.parent

FEATURES_DIR = PROJECT_ROOT / "Features"
INDEX_PATH = DOTAI / "context" / "feature_index.json"
GRAPH_PATH = DOTAI / "context" / "feature_graph.json"
SOURCE_ANALYSIS_DIR = DOTAI / "learning" / "source_analysis"
COVERAGE_PATH = DOTAI / "context" / "coverage_matrix.json"
DEFAULT_OUT = DOTAI / "learning" / "feature_evidence"

LEARNING_DIR = TOOLS_DIR / "learning"
if str(LEARNING_DIR) not in sys.path:
    sys.path.insert(0, str(LEARNING_DIR))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import gd_parse  # noqa: E402
import build_feature_index as feature_index_builder  # noqa: E402

SCHEMA = "feature_evidence_projection"
SCHEMA_VERSION = 1
EXTRACTOR_VERSION = "phase-1.73-a1/1"
PILOT_FEATURES = ("health", "health_bar", "openable_door", "attack_emitter", "blackboard")

EVIDENCE_STATUSES = {
    "DECLARED",
    "EXTRACTED",
    "PARTIAL",
    "MISSING",
    "NOT_APPLICABLE",
    "UNSUPPORTED",
    "CONFLICTED",
}
PROJECTION_STATUSES = {"COMPLETE", "PARTIAL", "MISSING", "UNSUPPORTED", "CONFLICTED"}
VERIFICATION_STATUSES = {"NOT_RUN", "NOT_VERIFIED", "VERIFIED", "FAILED"}
RELIABILITY_VALUES = {"HIGH", "MEDIUM", "LOW", "NONE"}

EVIDENCE_SECTIONS = (
    "descriptive_evidence",
    "capability_evidence",
    "interface_evidence",
    "symbol_evidence",
    "dependency_evidence",
    "behavior_evidence",
    "test_evidence",
    "validation_evidence",
    "provenance_evidence",
)

REQUIRED_PROJECTION_FIELDS = (
    "schema",
    "schema_version",
    "projection_id",
    "content_digest",
    "feature_id",
    "feature_name",
    "feature_path",
    "generated_at",
    "extractor_version",
    "source_identity",
    "source_references",
    "analysis_references",
    "descriptive_evidence",
    "capability_evidence",
    "interface_evidence",
    "symbol_evidence",
    "dependency_evidence",
    "behavior_evidence",
    "test_evidence",
    "validation_evidence",
    "provenance_evidence",
    "declared_evidence",
    "extracted_evidence",
    "evidence_counts",
    "path_normalization",
    "projection_status",
    "limitations",
)


class ProjectionError(RuntimeError):
    """Raised when a projection cannot be built or validated."""


class ProjectionValidationError(ProjectionError):
    """Raised when a projection does not satisfy the Phase 1.73 schema."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def normalize_path(raw: Any, project_root: str | Path = PROJECT_ROOT) -> dict:
    """Return an original path plus a portable project-relative path when possible.

    The original spelling is never discarded.  A path outside the project is
    explicitly marked OUTSIDE_PROJECT rather than silently rewritten.
    """
    original = str(raw or "")
    root = Path(project_root).resolve()
    if not original:
        return {
            "original_path": "",
            "normalized_path": "",
            "normalization_status": "MISSING",
        }

    if os.name != "nt" and ntpath.isabs(original):
        # 记录里可能带 Windows 绝对路径（例如别的机器写下的 F:\...）；
        # POSIX 上 Path("F:\\...") 会被当成单个文件名的相对路径，必须单独识别。
        parts = [part for part in original.replace("\\", "/").split("/") if part]
        # 仓库在另一台机器/云端上的目录层数不同（F:\...\game 对 /workspaces/xxx），
        # 所以按「在项目里真实存在的最长尾段」定位，而不是比目录名。
        for index in range(len(parts)):
            candidate = "/".join(parts[index:])
            if candidate and os.path.exists(os.path.join(root, candidate)):
                return {
                    "original_path": original,
                    "normalized_path": candidate,
                    "normalization_status": "CONVERTED",
                }
        return {
            "original_path": original,
            "normalized_path": "",
            "normalization_status": "OUTSIDE_PROJECT",
        }

    path = Path(original)
    try:
        absolute = path.resolve() if path.is_absolute() else (root / path).resolve()
    except (OSError, ValueError):
        return {
            "original_path": original,
            "normalized_path": "",
            "normalization_status": "UNRESOLVED",
        }

    try:
        relative = absolute.relative_to(root).as_posix()
    except ValueError:
        return {
            "original_path": original,
            "normalized_path": "",
            "normalization_status": "OUTSIDE_PROJECT",
        }

    status = "RELATIVE" if not path.is_absolute() else "CONVERTED"
    if not path.is_absolute() and relative != path.as_posix().lstrip("./"):
        status = "RELATIVE_NORMALIZED"
    return {
        "original_path": original,
        "normalized_path": relative,
        "normalization_status": status,
    }


def _path_for(raw: Any, project_root: str | Path = PROJECT_ROOT) -> Path:
    path = Path(str(raw))
    return path if path.is_absolute() else (Path(project_root) / path)


def source_reference(source_type: str, raw_path: Any, project_root: str | Path = PROJECT_ROOT,
                     *, status: str = "") -> dict:
    desc = normalize_path(raw_path, project_root)
    path = _path_for(raw_path, project_root) if str(raw_path or "") else None
    if status:
        source_status = status
    elif path is None:
        source_status = "MISSING"
    elif path.is_file():
        source_status = "FOUND"
    else:
        source_status = "MISSING"
    digest = _sha256_file(path) if path is not None and path.is_file() else ""
    return {
        "source_type": source_type,
        "source_path": desc["normalized_path"] or desc["original_path"],
        "source_digest": digest,
        "source_status": source_status,
        "original_path": desc["original_path"],
        "normalized_path": desc["normalized_path"],
        "normalization_status": desc["normalization_status"],
    }


def _evidence(feature_id: str, evidence_type: str, evidence_id: str, value: Any,
              source_type: str, source_record_id: str, source_file: str = "",
              source_symbol: str = "", source_line: int | None = None,
              extraction_method: str = "", extraction_status: str = "DECLARED",
              reliability: str = "MEDIUM", provenance: dict | None = None,
              limitations: list[str] | None = None,
              applicability: str = "APPLICABLE", **extra: Any) -> dict:
    if extraction_status not in EVIDENCE_STATUSES:
        raise ProjectionValidationError("invalid evidence status: %s" % extraction_status)
    if reliability not in RELIABILITY_VALUES:
        raise ProjectionValidationError("invalid reliability: %s" % reliability)
    record = {
        "evidence_id": evidence_id,
        "evidence_type": evidence_type,
        "value": value,
        "source_type": source_type,
        "source_record_id": source_record_id,
        "source_file": source_file,
        "source_symbol": source_symbol,
        "source_line": source_line,
        "extraction_method": extraction_method,
        "extraction_status": extraction_status,
        "reliability": reliability,
        "applicability": applicability,
        "provenance": dict(provenance or {}),
        "limitations": list(limitations or []),
    }
    record.update(extra)
    return record


def _load_yaml(path: Path) -> dict:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - project already depends on PyYAML
        raise ProjectionError("PyYAML is required: %s" % exc) from exc
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ProjectionError("cannot read YAML %s: %s" % (path, exc)) from exc
    if not isinstance(value, dict):
        raise ProjectionError("YAML root is not a mapping: %s" % path)
    return value


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ProjectionError("cannot read JSON %s: %s" % (path, exc)) from exc


def _feature_files(feature_id: str, features_dir: str | Path = FEATURES_DIR) -> tuple[Path, Path]:
    feature_dir = Path(features_dir) / feature_id
    return feature_dir, feature_dir / "feature.yaml"


def _source_records(feature_id: str, source_dir: str | Path = SOURCE_ANALYSIS_DIR,
                    project_root: str | Path = PROJECT_ROOT) -> tuple[list[dict], list[dict]]:
    directory = Path(source_dir) / feature_id
    records: list[dict] = []
    references: list[dict] = []
    if not directory.is_dir():
        return records, references
    for path in sorted(directory.glob("*.json")):
        ref = source_reference("FEATURE_SOURCE_ANALYSIS", path, project_root)
        references.append(ref)
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(record, dict) or record.get("feature_id") != feature_id:
            continue
        record = dict(record)
        record["_record_path"] = str(path)
        record["_record_digest"] = _sha256_file(path)
        records.append(record)
    return records, references


def _source_files(feature_id: str, feature_dir: Path, records: list[dict],
                  project_root: str | Path = PROJECT_ROOT) -> list[dict]:
    files: list[dict] = []
    seen: set[str] = set()
    for record in records:
        for script in record.get("scripts") or []:
            raw = str(script.get("path") or "")
            if not raw:
                continue
            desc = normalize_path(raw, project_root)
            key = desc["normalized_path"] or desc["original_path"]
            if key in seen:
                continue
            seen.add(key)
            path = _path_for(raw, project_root)
            files.append({
                "raw_path": raw,
                "path": path,
                "normalized_path": desc["normalized_path"],
                "original_path": desc["original_path"],
                "normalization_status": desc["normalization_status"],
                "source": "SOURCE_ANALYSIS",
                "recorded_digest": str(script.get("digest") or ""),
                "source_status": "FOUND" if path.is_file() else "MISSING",
            })
    if not files:
        # A Feature without behavior contracts (for example blackboard) has no
        # source-analysis record.  Parse only this Feature's own non-test .gd
        # files; never scan the whole project.
        for path in sorted(feature_dir.glob("*.gd")):
            if path.name.startswith("test_"):
                continue
            desc = normalize_path(path, project_root)
            key = desc["normalized_path"] or desc["original_path"]
            if key in seen:
                continue
            seen.add(key)
            files.append({
                "raw_path": str(path),
                "path": path,
                "normalized_path": desc["normalized_path"],
                "original_path": desc["original_path"],
                "normalization_status": desc["normalization_status"],
                "source": "FEATURE_DIRECTORY",
                "recorded_digest": "",
                "source_status": "FOUND" if path.is_file() else "MISSING",
            })
    return files


def _parse_symbols(feature_id: str, source_files: list[dict], metadata_path: str,
                   project_root: str | Path) -> tuple[list[dict], dict[str, set], list[dict]]:
    evidence: list[dict] = []
    names: dict[str, set] = {"method": set(), "signal": set(), "export": set()}
    references: list[dict] = []
    for source in source_files:
        raw = source["raw_path"]
        path = source["path"]
        desc = normalize_path(raw, project_root)
        ref = source_reference("GDSCRIPT_SOURCE", raw, project_root)
        references.append(ref)
        evidence_id_prefix = "symbol:%s:%s" % (feature_id, desc["normalized_path"] or raw)
        if not path.is_file():
            evidence.append(_evidence(
                feature_id, "SYMBOL", evidence_id_prefix + ":missing",
                {"path": desc["normalized_path"] or raw},
                "GDSCRIPT_SOURCE", desc["normalized_path"] or raw,
                source_file=desc["normalized_path"] or raw,
                extraction_method="gd_parse.parse_file",
                extraction_status="MISSING",
                reliability="NONE",
                limitations=["source file is missing or unreadable"],
            ))
            continue
        if path.suffix.lower() != ".gd":
            evidence.append(_evidence(
                feature_id, "SYMBOL", evidence_id_prefix + ":unsupported",
                {"path": desc["normalized_path"] or raw, "file_type": path.suffix.lower()},
                "GDSCRIPT_SOURCE", desc["normalized_path"] or raw,
                source_file=desc["normalized_path"] or raw,
                extraction_method="gd_parse.parse_file",
                extraction_status="UNSUPPORTED",
                reliability="NONE",
                limitations=["only .gd files are supported by gd_parse"],
            ))
            continue
        try:
            script = gd_parse.parse_file(str(path))
        except Exception as exc:  # noqa: BLE001
            evidence.append(_evidence(
                feature_id, "SYMBOL", evidence_id_prefix + ":parse_error",
                {"path": desc["normalized_path"] or raw, "error": str(exc)},
                "GDSCRIPT_SOURCE", desc["normalized_path"] or raw,
                source_file=desc["normalized_path"] or raw,
                extraction_method="gd_parse.parse_file",
                extraction_status="UNSUPPORTED",
                reliability="NONE",
                limitations=["gd_parse failed: %s" % exc],
            ))
            continue
        source_file = desc["normalized_path"] or raw
        digest = _sha256_file(path)
        provenance = {
            "source_digest": digest,
            "parser": "gd_parse",
            "parser_version": "regex-v1",
            "recorded_source_digest": source.get("recorded_digest") or "",
        }
        limitations = ["regex_parser_without_ast_or_type_inference"]
        if source.get("recorded_digest") and source["recorded_digest"] != digest:
            limitations.append("source_digest differs from source-analysis record")
        if script.class_name:
            evidence.append(_evidence(
                feature_id, "SYMBOL", evidence_id_prefix + ":class",
                {"kind": "class_name", "name": script.class_name},
                "GDSCRIPT_SOURCE", source_file, source_file=source_file,
                source_symbol=script.class_name,
                extraction_method="gd_parse.parse_text",
                extraction_status="EXTRACTED", reliability="MEDIUM",
                provenance=provenance, limitations=list(limitations),
            ))
        if script.extends:
            evidence.append(_evidence(
                feature_id, "SYMBOL", evidence_id_prefix + ":extends",
                {"kind": "extends", "name": script.extends},
                "GDSCRIPT_SOURCE", source_file, source_file=source_file,
                source_symbol=script.extends,
                extraction_method="gd_parse.parse_text",
                extraction_status="EXTRACTED", reliability="MEDIUM",
                provenance=provenance, limitations=list(limitations),
            ))
        for function in script.functions:
            names["method"].add(function.name)
            evidence.append(_evidence(
                feature_id, "SYMBOL", evidence_id_prefix + ":func:%s:%d" % (function.name, function.start_line),
                {"kind": "function", "name": function.name, "params": function.params,
                 "returns": function.returns, "public": not function.name.startswith("_")},
                "GDSCRIPT_SOURCE", source_file, source_file=source_file,
                source_symbol=function.name, source_line=function.start_line,
                extraction_method="gd_parse.parse_text",
                extraction_status="EXTRACTED", reliability="MEDIUM",
                provenance=dict(provenance, source_line=function.start_line,
                                end_line=function.end_line),
                limitations=list(limitations),
            ))
        for signal in script.signals:
            names["signal"].add(signal["name"])
            evidence.append(_evidence(
                feature_id, "SYMBOL", evidence_id_prefix + ":signal:%s:%s" % (signal["name"], signal.get("line")),
                {"kind": "signal", "name": signal["name"], "params": signal.get("params", "")},
                "GDSCRIPT_SOURCE", source_file, source_file=source_file,
                source_symbol=signal["name"], source_line=signal.get("line"),
                extraction_method="gd_parse.parse_text",
                extraction_status="EXTRACTED", reliability="MEDIUM",
                provenance=dict(provenance, source_line=signal.get("line")),
                limitations=list(limitations),
            ))
        for export in script.exports:
            names["export"].add(export["name"])
            evidence.append(_evidence(
                feature_id, "SYMBOL", evidence_id_prefix + ":export:%s:%s" % (export["name"], export.get("line")),
                {"kind": "export", "name": export["name"], "type": export.get("type", ""),
                 "value": export.get("value", "")},
                "GDSCRIPT_SOURCE", source_file, source_file=source_file,
                source_symbol=export["name"], source_line=export.get("line"),
                extraction_method="gd_parse.parse_text",
                extraction_status="EXTRACTED", reliability="MEDIUM",
                provenance=dict(provenance, source_line=export.get("line")),
                limitations=list(limitations),
            ))
        for variable in script.variables:
            evidence.append(_evidence(
                feature_id, "SYMBOL", evidence_id_prefix + ":var:%s:%s" % (variable["name"], variable.get("line")),
                {"kind": "variable", "name": variable["name"], "type": variable.get("type", ""),
                 "value": variable.get("value", "")},
                "GDSCRIPT_SOURCE", source_file, source_file=source_file,
                source_symbol=variable["name"], source_line=variable.get("line"),
                extraction_method="gd_parse.parse_text",
                extraction_status="EXTRACTED", reliability="MEDIUM",
                provenance=dict(provenance, source_line=variable.get("line")),
                limitations=list(limitations),
            ))
    return evidence, names, references


def _build_descriptive(feature_id: str, metadata: dict, metadata_path: str) -> list[dict]:
    result: list[dict] = []
    provenance = {"metadata_sha256": _sha256_text(_canonical(metadata))}
    result.append(_evidence(
        feature_id, "DESCRIPTIVE", "desc:%s:name" % feature_id,
        {"name": str(metadata.get("name") or feature_id)},
        "FEATURE_METADATA", metadata_path, source_file=metadata_path,
        extraction_method="yaml.safe_load", extraction_status="DECLARED",
        reliability="HIGH", provenance=provenance,
    ))
    summary = metadata.get("summary")
    if isinstance(summary, str) and summary.strip():
        result.append(_evidence(
            feature_id, "DESCRIPTIVE", "desc:%s:summary" % feature_id,
            {"summary": summary.strip()},
            "FEATURE_METADATA", metadata_path, source_file=metadata_path,
            extraction_method="yaml.safe_load", extraction_status="DECLARED",
            reliability="MEDIUM", provenance=provenance,
        ))
    else:
        result.append(_evidence(
            feature_id, "DESCRIPTIVE", "desc:%s:summary" % feature_id,
            {"summary": None},
            "FEATURE_METADATA", metadata_path, source_file=metadata_path,
            extraction_method="yaml.safe_load", extraction_status="MISSING",
            reliability="NONE", provenance=provenance,
            limitations=["summary is not declared in feature.yaml"],
        ))
    category = metadata.get("category")
    if category:
        result.append(_evidence(
            feature_id, "DESCRIPTIVE", "desc:%s:category" % feature_id,
            {"category": category},
            "FEATURE_METADATA", metadata_path, source_file=metadata_path,
            extraction_method="yaml.safe_load", extraction_status="DECLARED",
            reliability="MEDIUM", provenance=provenance,
        ))
    else:
        result.append(_evidence(
            feature_id, "DESCRIPTIVE", "desc:%s:category" % feature_id,
            {"category": None},
            "FEATURE_METADATA", metadata_path, source_file=metadata_path,
            extraction_method="yaml.safe_load", extraction_status="MISSING",
            reliability="NONE", provenance=provenance,
            limitations=["category is not declared in feature.yaml"],
        ))
    return result


def _build_capability(feature_id: str, metadata: dict, metadata_path: str) -> list[dict]:
    result: list[dict] = []
    provenance = {"metadata_sha256": _sha256_text(_canonical(metadata))}
    for index, name in enumerate(metadata.get("provides") or []):
        result.append(_evidence(
            feature_id, "CAPABILITY", "capability:%s:provides:%d:%s" % (feature_id, index, name),
            {"capability": name, "scope": "FEATURE_TAG", "validation": "HUMAN_DECLARED"},
            "FEATURE_METADATA", metadata_path, source_file=metadata_path,
            extraction_method="yaml.safe_load", extraction_status="DECLARED",
            reliability="MEDIUM", provenance=provenance,
            limitations=["provides is a human declaration, not source-verified capability"],
        ))
    required = ((metadata.get("capabilities") or {}).get("required") or [])
    if required:
        for index, name in enumerate(required):
            result.append(_evidence(
                feature_id, "CAPABILITY", "capability:%s:scene:%d:%s" % (feature_id, index, name),
                {"capability": name, "scope": "SCENE_REQUIREMENT", "validation": "HUMAN_DECLARED"},
                "FEATURE_METADATA", metadata_path, source_file=metadata_path,
                extraction_method="yaml.safe_load", extraction_status="DECLARED",
                reliability="MEDIUM", provenance=provenance,
                limitations=["Scene capability requirement; not a semantic capability extraction"],
            ))
    else:
        result.append(_evidence(
            feature_id, "CAPABILITY", "capability:%s:scene:none" % feature_id,
            {"capability": None, "scope": "SCENE_REQUIREMENT"},
            "FEATURE_METADATA", metadata_path, source_file=metadata_path,
            extraction_method="yaml.safe_load", extraction_status="NOT_APPLICABLE",
            reliability="NONE", provenance=provenance,
            applicability="NO_SCENE_CAPABILITY_DECLARED",
            limitations=["no Scene capability requirement is declared"],
        ))
    if not result:
        result.append(_evidence(
            feature_id, "CAPABILITY", "capability:%s:none" % feature_id,
            {"capability": None},
            "FEATURE_METADATA", metadata_path, source_file=metadata_path,
            extraction_method="yaml.safe_load", extraction_status="NOT_APPLICABLE",
            reliability="NONE", provenance=provenance,
            applicability="NO_CAPABILITY_DECLARED",
        ))
    return result


def _build_interfaces(feature_id: str, metadata: dict, metadata_path: str,
                      symbol_names: dict[str, set]) -> list[dict]:
    result: list[dict] = []
    block = metadata.get("interfaces") or {}
    provenance = {"metadata_sha256": _sha256_text(_canonical(metadata))}
    for kind, key in (("method", "methods"), ("signal", "signals"), ("export", "exports")):
        items = block.get(key) or []
        if not items:
            continue
        for index, item in enumerate(items):
            if isinstance(item, str):
                item = {"name": item}
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "")
            if not name:
                continue
            check = "NO_SOURCE"
            if symbol_names:
                check = "MATCHED" if name in symbol_names.get(kind, set()) else "NOT_FOUND"
            result.append(_evidence(
                feature_id, "INTERFACE", "interface:%s:%s:%d:%s" % (feature_id, kind, index, name),
                {"kind": kind, "name": name, "signature": item.get("signature", ""),
                 "description": item.get("description", ""), "type": item.get("type", ""),
                 "default": item.get("default", ""), "source_check": check},
                "FEATURE_METADATA", metadata_path, source_file=metadata_path,
                extraction_method="yaml.safe_load", extraction_status="DECLARED",
                reliability="MEDIUM", provenance=dict(provenance, source_check=check),
                limitations=([] if check == "MATCHED" else
                             ["declared interface was not confirmed by a parsed source symbol"]),
            ))
    if not result:
        result.append(_evidence(
            feature_id, "INTERFACE", "interface:%s:none" % feature_id,
            {"kind": None, "name": None},
            "FEATURE_METADATA", metadata_path, source_file=metadata_path,
            extraction_method="yaml.safe_load", extraction_status="NOT_APPLICABLE",
            reliability="NONE", provenance=provenance,
            applicability="NO_INTERFACE_DECLARED",
        ))
    return result


def _build_dependencies(feature_id: str, metadata: dict, metadata_path: str,
                        graph_path: str, graph: dict, feature_ids: set[str]) -> tuple[list[dict], list[dict]]:
    result: list[dict] = []
    conflicts: list[dict] = []
    relations = metadata.get("relations") or {}
    provenance = {"metadata_sha256": _sha256_text(_canonical(metadata))}
    seen: set[tuple] = set()

    def add_relation(kind: str, value: str, source_type: str = "FEATURE_METADATA",
                     source_record: str = metadata_path, source_file: str = metadata_path) -> None:
        key = (kind, value, source_type)
        if key in seen:
            return
        seen.add(key)
        result.append(_evidence(
            feature_id, "DEPENDENCY", "dependency:%s:%s:%s" % (feature_id, kind, value),
            {"relationship": kind, "target": value,
             "evidence_scope": "DECLARED_STRUCTURE" if source_type == "FEATURE_METADATA" else "GRAPH_STRUCTURE"},
            source_type, source_record, source_file=source_file,
            extraction_method="yaml.safe_load" if source_type == "FEATURE_METADATA" else "feature_graph",
            extraction_status="DECLARED", reliability="MEDIUM",
            provenance=dict(provenance, source_type=source_type),
            limitations=["relationship is declared metadata/graph evidence; it is not source-verified"],
        ))

    for value in metadata.get("requires") or []:
        add_relation("requires", str(value))
    for value in relations.get("requires") or []:
        add_relation("relations_requires", str(value))
    for key, kind in (("works_with", "works_with"), ("commonly_used_with", "commonly_used_with"),
                      ("conflicts", "conflicts")):
        for value in relations.get(key) or []:
            add_relation(kind, str(value))

    actual_edges: set[tuple] = set()
    for edge in graph.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        if edge.get("from") == feature_id:
            actual_edges.add((str(edge.get("to")), str(edge.get("type"))))
            add_relation("graph_" + str(edge.get("type") or "edge"), str(edge.get("to")),
                         "FEATURE_GRAPH", graph_path, graph_path)
    expected_edges = set()
    for key in ("works_with", "commonly_used_with"):
        for value in relations.get(key) or []:
            expected_edges.add((str(value), key))
    if feature_id not in set(graph.get("nodes") or []):
        conflicts.append(_evidence(
            feature_id, "DEPENDENCY", "dependency:%s:graph_missing_node" % feature_id,
            {"feature_id": feature_id},
            "FEATURE_GRAPH", graph_path, source_file=graph_path,
            extraction_method="feature_graph", extraction_status="CONFLICTED",
            reliability="NONE", limitations=["Feature is absent from feature_graph nodes"],
        ))
    for target, edge_type in sorted(expected_edges - actual_edges):
        conflicts.append(_evidence(
            feature_id, "DEPENDENCY", "dependency:%s:graph_missing_edge:%s:%s" % (feature_id, edge_type, target),
            {"target": target, "edge_type": edge_type},
            "FEATURE_GRAPH", graph_path, source_file=graph_path,
            extraction_method="feature_graph", extraction_status="CONFLICTED",
            reliability="NONE", limitations=["declared relation is absent from feature_graph edges"],
        ))
    for target, edge_type in sorted(actual_edges - expected_edges):
        conflicts.append(_evidence(
            feature_id, "DEPENDENCY", "dependency:%s:graph_extra_edge:%s:%s" % (feature_id, edge_type, target),
            {"target": target, "edge_type": edge_type},
            "FEATURE_GRAPH", graph_path, source_file=graph_path,
            extraction_method="feature_graph", extraction_status="CONFLICTED",
            reliability="NONE", limitations=["feature_graph edge is not declared in metadata"],
        ))
    if not result and not conflicts:
        result.append(_evidence(
            feature_id, "DEPENDENCY", "dependency:%s:none" % feature_id,
            {"relationship": None, "target": None},
            "FEATURE_METADATA", metadata_path, source_file=metadata_path,
            extraction_method="yaml.safe_load", extraction_status="NOT_APPLICABLE",
            reliability="NONE", provenance=provenance,
            applicability="NO_DEPENDENCY_DECLARED",
        ))
    return result, conflicts


def _build_behavior(feature_id: str, metadata_path: str, template: dict | None,
                    template_path: str, records: list[dict], coverage: dict,
                    project_root: str | Path = PROJECT_ROOT) -> tuple[list[dict], list[dict]]:
    result: list[dict] = []
    refs: list[dict] = []
    behavior_block = (template or {}).get("behavior")
    contracts = behavior_block if isinstance(behavior_block, list) else []
    by_behavior = {str(record.get("behavior_id")): record for record in records}
    coverage_by = {}
    for row in coverage.get("rows") or []:
        if isinstance(row, dict) and row.get("feature_id") == feature_id:
            coverage_by[str(row.get("behavior_id"))] = row

    for record in records:
        refs.append({
            "analysis_record_path": source_reference(
                "FEATURE_SOURCE_ANALYSIS", record.get("_record_path", ""), project_root)["source_path"],
            "analysis_status": record.get("analysis_status"),
            "analysis_digest": record.get("_record_digest", ""),
            "analyzed_source_files": [str(item.get("path")) for item in record.get("scripts") or []],
            "limitations": list(record.get("unresolved_questions") or []),
        })

    if not contracts:
        result.append(_evidence(
            feature_id, "BEHAVIOR", "behavior:%s:no_contract" % feature_id,
            {"behavior_contract": None},
            "FEATURE_TEMPLATE", template_path or metadata_path,
            source_file=template_path or metadata_path,
            extraction_method="yaml.safe_load", extraction_status="NOT_APPLICABLE",
            reliability="NONE", applicability="NO_BEHAVIOR_CONTRACT",
            limitations=["Feature has no template.yaml#behavior contract"],
        ))
        if records:
            result.append(_evidence(
                feature_id, "BEHAVIOR", "behavior:%s:records_without_contract" % feature_id,
                {"record_count": len(records)},
                "FEATURE_SOURCE_ANALYSIS", records[0].get("_record_path", metadata_path),
                extraction_method="source_analysis", extraction_status="CONFLICTED",
                reliability="NONE", limitations=["source-analysis records exist without a behavior contract"],
            ))
        return result, refs

    for index, contract in enumerate(contracts):
        if not isinstance(contract, dict):
            continue
        behavior_id = str(contract.get("id") or contract.get("name") or "")
        if not behavior_id:
            continue
        record = by_behavior.get(behavior_id)
        coverage_row = coverage_by.get(behavior_id) or {}
        contract_version = coverage_row.get("contract_version")
        if record is None:
            result.append(_evidence(
                feature_id, "BEHAVIOR", "behavior:%s:%s:missing" % (feature_id, behavior_id),
                {"behavior_id": behavior_id, "contract_version": contract_version},
                "FEATURE_TEMPLATE", template_path, source_file=template_path,
                extraction_method="yaml.safe_load", extraction_status="MISSING",
                reliability="NONE", limitations=["behavior contract has no source-analysis record"],
            ))
            continue
        analysis_status = str(record.get("analysis_status") or "UNKNOWN")
        record_version = record.get("contract_version")
        status = "EXTRACTED" if analysis_status == "COMPLETE" else "PARTIAL"
        if analysis_status in ("FAILED", "UNSUPPORTED", "UNKNOWN"):
            status = "UNSUPPORTED"
        limitations = list(record.get("unresolved_questions") or [])
        if record_version and contract_version and record_version != contract_version:
            status = "CONFLICTED"
            limitations.append("contract_version differs between source analysis and coverage matrix")
        source_path = record.get("_record_path", "")
        source_desc = normalize_path(source_path, project_root)
        result.append(_evidence(
            feature_id, "BEHAVIOR", "behavior:%s:%s" % (feature_id, behavior_id),
            {"behavior_id": behavior_id, "analysis_status": analysis_status,
             "contract_version": record_version,
             "coverage_contract_version": contract_version,
             "static_only": bool(record.get("static_only"))},
            "FEATURE_SOURCE_ANALYSIS", source_desc["normalized_path"] or source_path,
            source_file=source_desc["normalized_path"] or source_path,
            extraction_method="existing_source_analysis",
            extraction_status=status, reliability="MEDIUM" if status == "EXTRACTED" else "LOW",
            provenance={"analysis_record_digest": record.get("_record_digest", ""),
                        "analyzed_source_files": [str(item.get("path")) for item in record.get("scripts") or []]},
            limitations=limitations,
        ))
    for behavior_id, record in by_behavior.items():
        if behavior_id not in {str(c.get("id") or c.get("name") or "") for c in contracts if isinstance(c, dict)}:
            result.append(_evidence(
                feature_id, "BEHAVIOR", "behavior:%s:%s:no_contract" % (feature_id, behavior_id),
                {"behavior_id": behavior_id, "analysis_status": record.get("analysis_status")},
                "FEATURE_SOURCE_ANALYSIS", record.get("_record_path", metadata_path),
                extraction_method="existing_source_analysis", extraction_status="CONFLICTED",
                reliability="NONE", limitations=["source-analysis record has no matching behavior contract"],
            ))
    if not result:
        result.append(_evidence(
            feature_id, "BEHAVIOR", "behavior:%s:no_records" % feature_id,
            {"behavior_contract": True},
            "FEATURE_TEMPLATE", template_path, source_file=template_path,
            extraction_method="yaml.safe_load", extraction_status="MISSING",
            reliability="NONE", limitations=["behavior contract exists but no behavior evidence was found"],
        ))
    return result, refs


def _test_path(metadata: dict, feature_dir: Path, project_root: str | Path) -> str:
    validation = metadata.get("validation") or {}
    if isinstance(validation, dict):
        raw = str(validation.get("test_path") or "")
        if raw:
            return raw
        self_test = str(validation.get("self_test") or "")
        if self_test:
            return str(feature_dir / self_test)
    return ""


def _build_test(feature_id: str, metadata: dict, metadata_path: str,
                feature_dir: Path, project_root: str | Path) -> tuple[list[dict], list[dict], list[dict]]:
    # project_root is threaded through explicitly for temporary fixtures.
    test_evidence: list[dict] = []
    validation_evidence: list[dict] = []
    references: list[dict] = []
    raw = _test_path(metadata, feature_dir, project_root)
    if not raw:
        test_evidence.append(_evidence(
            feature_id, "TEST", "test:%s:missing_path" % feature_id,
            {"test_path": None},
            "FEATURE_METADATA", metadata_path, source_file=metadata_path,
            extraction_method="yaml.safe_load", extraction_status="MISSING",
            reliability="NONE", limitations=["no test_path/self_test is declared"],
        ))
        return test_evidence, validation_evidence, references
    desc = normalize_path(raw, project_root)
    path = _path_for(raw, project_root)
    exists = path.is_file()
    ref = source_reference("FEATURE_TEST", raw, project_root)
    references.append(ref)
    test_evidence.append(_evidence(
        feature_id, "TEST", "test:%s:file" % feature_id,
        {"test_path": desc["normalized_path"] or desc["original_path"],
         "path_form": desc["normalization_status"], "file_exists": exists,
         "execution_status": "NOT_RUN"},
        "FEATURE_METADATA", metadata_path, source_file=desc["normalized_path"] or desc["original_path"],
        extraction_method="yaml.safe_load", extraction_status="DECLARED" if exists else "MISSING",
        reliability="MEDIUM" if exists else "NONE", provenance={"test_sha256": _sha256_file(path) if exists else ""},
        limitations=["test file existence is not test execution; test status is NOT_RUN"],
        original_path=desc["original_path"], normalized_path=desc["normalized_path"],
        normalization_status=desc["normalization_status"],
    ))
    validation = metadata.get("validation") or {}
    if isinstance(validation, dict) and validation.get("command"):
        validation_evidence.append(_evidence(
            feature_id, "VALIDATION", "validation:%s:test_command" % feature_id,
            {"validation_type": "TEST_CONTRACT", "command": validation.get("command"),
             "execution_status": "NOT_RUN"},
            "FEATURE_METADATA", metadata_path, source_file=metadata_path,
            extraction_method="yaml.safe_load", extraction_status="DECLARED",
            reliability="LOW", limitations=["validation command was not executed in Batch A"],
        ))
    return test_evidence, validation_evidence, references


def _build_provenance(feature_id: str, metadata_path: str,
                      project_root: str | Path = PROJECT_ROOT) -> list[dict]:
    raw = _path_for(metadata_path, project_root)
    digest = _sha256_file(raw) if raw.is_file() else ""
    return [_evidence(
        feature_id, "PROVENANCE", "provenance:%s:metadata_digest" % feature_id,
        {"metadata_path": normalize_path(metadata_path, project_root)["normalized_path"],
         "metadata_sha256": digest},
        "FEATURE_METADATA", metadata_path, source_file=metadata_path,
        extraction_method="sha256", extraction_status="EXTRACTED",
        reliability="HIGH", provenance={"metadata_sha256": digest},
        limitations=["Feature metadata does not define structured upstream provenance"],
    )]


def _index_consistency(feature_id: str, metadata: dict, metadata_path: str,
                       index_record: dict | None, index_path: str,
                       feature_dir: Path, features_dir: Path,
                       project_root: str | Path = PROJECT_ROOT) -> list[dict]:
    if not index_record:
        return [_evidence(
            feature_id, "PROVENANCE", "index:%s:missing" % feature_id,
            {"index_record": None},
            "FEATURE_INDEX", index_path, source_file=index_path,
            extraction_method="json", extraction_status="MISSING",
            reliability="NONE", limitations=["Feature Index has no record for this Feature"],
        )]
    try:
        interfaces, signals = feature_index_builder.collect_interfaces(metadata)
    except Exception:  # noqa: BLE001
        interfaces, signals = [], []
    expected = {
        "id": metadata.get("id"),
        "version": str(metadata.get("version")),
        "category": metadata.get("category"),
        "provides": list(metadata.get("provides") or []),
        "requires": list(metadata.get("requires") or []),
        "interfaces": interfaces,
        "signals": signals,
        "relations": feature_index_builder.normalize_relations(metadata.get("relations")),
    }
    actual = {key: index_record.get(key) for key in expected}
    actual_validation = index_record.get("validation") or {}
    expected_test = _test_path(metadata, feature_dir, features_dir)
    actual_test = str(actual_validation.get("test_path") or "")
    path_form = "SAME"
    if normalize_path(expected_test, project_root)["normalized_path"] != \
            normalize_path(actual_test, project_root)["normalized_path"]:
        path_form = "DIFFERENT"
    actual["validation"] = {"test_path_normalized": normalize_path(actual_test, project_root)["normalized_path"]}
    expected["validation"] = {"test_path_normalized": normalize_path(expected_test, project_root)["normalized_path"]}
    if expected == actual:
        status = "EXTRACTED"
        limitations = []
        if path_form == "DIFFERENT":
            limitations.append("Feature Index test path uses a different path form; normalized paths match")
        return [_evidence(
            feature_id, "PROVENANCE", "index:%s:consistency" % feature_id,
            {"consistent": True, "path_form": path_form},
            "FEATURE_INDEX", index_path, source_file=index_path,
            extraction_method="build_feature_index projection comparison",
            extraction_status=status, reliability="HIGH",
            limitations=limitations,
        )]
    return [_evidence(
        feature_id, "PROVENANCE", "index:%s:conflict" % feature_id,
        {"expected": expected, "actual": actual, "path_form": path_form},
        "FEATURE_INDEX", index_path, source_file=index_path,
        extraction_method="build_feature_index projection comparison",
        extraction_status="CONFLICTED", reliability="NONE",
        limitations=["Feature metadata and Feature Index disagree beyond path normalization"],
    )]


def _build_source_identity(metadata_path: str, index_path: str, graph_path: str,
                           source_records: list[dict], source_files: list[dict],
                           source_references: list[dict],
                           project_root: str | Path = PROJECT_ROOT) -> dict:
    def digest(path: str) -> str:
        return source_reference("SOURCE", path, project_root)["source_digest"]

    return {
        "metadata_path": normalize_path(metadata_path)["normalized_path"] or metadata_path,
        "metadata_sha256": digest(metadata_path),
        "index_path": normalize_path(index_path)["normalized_path"] or index_path,
        "index_sha256": digest(index_path),
        "graph_path": normalize_path(graph_path)["normalized_path"] or graph_path,
        "graph_sha256": digest(graph_path),
        "source_analysis_records": [
            {
                "path": normalize_path(record.get("_record_path", ""), project_root)["normalized_path"]
                        or record.get("_record_path", ""),
                "analysis_status": record.get("analysis_status"),
                "analysis_digest": record.get("_record_digest", ""),
                "contract_version": record.get("contract_version"),
                "script_digests": [
                    {"path": script.get("path"), "digest": script.get("digest")}
                    for script in record.get("scripts") or []
                ],
            }
            for record in source_records
        ],
        "source_files": [
            {
                "path": item.get("normalized_path") or item.get("original_path"),
                "source_digest": source_reference(
                    "GDSCRIPT_SOURCE", item.get("raw_path", ""), project_root)["source_digest"],
                "source_status": item.get("source_status"),
            }
            for item in source_files
        ],
        "source_reference_count": len(source_references),
    }


def _evidence_counts(evidence_sections: dict[str, list[dict]]) -> dict:
    counts = {status: 0 for status in sorted(EVIDENCE_STATUSES)}
    for section in evidence_sections.values():
        for item in section:
            status = item.get("extraction_status")
            counts[status] = counts.get(status, 0) + 1
    return counts


def _path_counts(references: list[dict]) -> dict:
    counts = {"CONVERTED": 0, "RELATIVE": 0, "RELATIVE_NORMALIZED": 0,
              "OUTSIDE_PROJECT": 0, "UNRESOLVED": 0, "MISSING": 0}
    for ref in references:
        status = ref.get("normalization_status") or "MISSING"
        counts[status] = counts.get(status, 0) + 1
    return counts


def _projection_status(evidence_counts: dict, limitations: list[str]) -> str:
    if evidence_counts.get("CONFLICTED", 0):
        return "CONFLICTED"
    if evidence_counts.get("UNSUPPORTED", 0):
        return "UNSUPPORTED"
    if evidence_counts.get("PARTIAL", 0) or evidence_counts.get("MISSING", 0):
        return "PARTIAL"
    return "COMPLETE"


def _build_verification_status() -> dict:
    """Return conservative verification markers for a static projection.

    Projection COMPLETE and Source Analysis COMPLETE are not test or runtime
    execution evidence.  Batch A has no execution step, so these values are
    explicit constants rather than inferred from evidence completeness.
    """
    return {
        "feature_verification_status": "NOT_VERIFIED",
        "test_execution_status": "NOT_RUN",
        "runtime_verification_status": "NOT_VERIFIED",
        "behavior_verification_status": "NOT_VERIFIED",
        "basis": "NO_EXECUTION_EVIDENCE",
    }


def _compute_content_digest(projection: dict) -> str:
    payload = json.loads(json.dumps(projection, ensure_ascii=False))
    payload.pop("generated_at", None)
    payload.pop("projection_id", None)
    payload.pop("content_digest", None)
    return _sha256_text(_canonical(payload))


def build_projection(feature_id: str, *, features_dir: str | Path = FEATURES_DIR,
                     index_path: str | Path = INDEX_PATH,
                     graph_path: str | Path = GRAPH_PATH,
                     source_analysis_dir: str | Path = SOURCE_ANALYSIS_DIR,
                     coverage_path: str | Path = COVERAGE_PATH,
                     project_root: str | Path = PROJECT_ROOT) -> dict:
    project_root = Path(project_root)
    features_dir = Path(features_dir)
    feature_dir, metadata_file = _feature_files(feature_id, features_dir)
    if not metadata_file.is_file():
        raise ProjectionError("Feature metadata not found: %s" % metadata_file)
    metadata = _load_yaml(metadata_file)
    if metadata.get("id") != feature_id:
        raise ProjectionError("Feature id mismatch: folder=%s metadata=%s" % (feature_id, metadata.get("id")))

    metadata_desc = normalize_path(metadata_file, project_root)
    metadata_path = metadata_desc["normalized_path"] or str(metadata_file)
    index_doc = _load_json(Path(index_path), {"features": []}) or {"features": []}
    index_record = next((item for item in index_doc.get("features", [])
                        if isinstance(item, dict) and item.get("id") == feature_id), None)
    graph = _load_json(Path(graph_path), {"nodes": [], "edges": []}) or {"nodes": [], "edges": []}
    coverage = _load_json(Path(coverage_path), {"rows": []}) or {"rows": []}
    template_path = feature_dir / "template.yaml"
    template = _load_yaml(template_path) if template_path.is_file() else None
    template_path_str = normalize_path(template_path, project_root)["normalized_path"] if template_path.is_file() else ""

    source_records, analysis_refs = _source_records(feature_id, source_analysis_dir, project_root)
    source_files = _source_files(feature_id, feature_dir, source_records, project_root)
    source_symbols, symbol_names, source_file_refs = _parse_symbols(
        feature_id, source_files, metadata_path, project_root)

    declared_sections = {
        "descriptive_evidence": _build_descriptive(feature_id, metadata, metadata_path),
        "capability_evidence": _build_capability(feature_id, metadata, metadata_path),
        "interface_evidence": _build_interfaces(feature_id, metadata, metadata_path, symbol_names),
        "symbol_evidence": source_symbols,
        "test_evidence": [],
        "validation_evidence": [],
        "provenance_evidence": _build_provenance(feature_id, metadata_path, project_root),
    }
    dependencies, dependency_conflicts = _build_dependencies(
        feature_id, metadata, metadata_path, str(graph_path), graph,
        {item.get("id") for item in index_doc.get("features", []) if isinstance(item, dict)})
    behavior, behavior_refs = _build_behavior(
        feature_id, metadata_path, template, template_path_str, source_records, coverage,
        project_root)
    test_evidence, validation_evidence, test_refs = _build_test(
        feature_id, metadata, metadata_path, feature_dir, project_root)
    declared_sections["dependency_evidence"] = dependencies + dependency_conflicts
    declared_sections["behavior_evidence"] = behavior
    declared_sections["test_evidence"] = test_evidence
    declared_sections["validation_evidence"] = validation_evidence

    source_refs = [
        source_reference("FEATURE_METADATA", metadata_file, project_root),
        source_reference("FEATURE_INDEX", index_path, project_root),
        source_reference("FEATURE_GRAPH", graph_path, project_root),
        source_reference("COVERAGE_MATRIX", coverage_path, project_root),
    ]
    if template_path.is_file():
        source_refs.append(source_reference("FEATURE_TEMPLATE", template_path, project_root))
    source_refs.extend(analysis_refs)
    source_refs.extend(source_file_refs)
    source_refs.extend(test_refs)
    index_consistency = _index_consistency(
        feature_id, metadata, metadata_path, index_record, str(index_path),
        feature_dir, features_dir, project_root)
    declared_sections["provenance_evidence"].extend(index_consistency)

    projection = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "projection_id": "",
        "content_digest": "",
        "feature_id": feature_id,
        "feature_name": str(metadata.get("name") or feature_id),
        "feature_path": metadata_path,
        "generated_at": _now(),
        "extractor_version": EXTRACTOR_VERSION,
        "source_identity": {},
        "source_references": source_refs,
        "analysis_references": behavior_refs,
        "declared_evidence": [],
        "extracted_evidence": [],
        "evidence_counts": {},
        "path_normalization": {},
        "projection_status": "PARTIAL",
        "verification_status": _build_verification_status(),
        "limitations": [],
    }
    projection.update(declared_sections)
    # Attach behavior references to the top-level analysis reference list without
    # duplicating the raw source-reference descriptors.
    projection["source_identity"] = _build_source_identity(
        metadata_path, str(index_path), str(graph_path), source_records, source_files, source_refs,
        project_root)
    all_evidence = [item for section in EVIDENCE_SECTIONS for item in projection[section]]
    projection["declared_evidence"] = [item for item in all_evidence if item["extraction_status"] == "DECLARED"]
    projection["extracted_evidence"] = [item for item in all_evidence if item["extraction_status"] == "EXTRACTED"]
    projection["evidence_counts"] = _evidence_counts({name: projection[name] for name in EVIDENCE_SECTIONS})
    projection["path_normalization"] = _path_counts(source_refs)
    projection["limitations"] = sorted({
        limitation
        for item in all_evidence
        for limitation in item.get("limitations", [])
    })
    projection["projection_status"] = _projection_status(projection["evidence_counts"], projection["limitations"])
    projection["content_digest"] = _compute_content_digest(projection)
    projection["projection_id"] = "fep-" + projection["content_digest"][:16]
    validate_projection(projection)
    return projection


def validate_projection(projection: Any) -> None:
    errors: list[str] = []
    if not isinstance(projection, dict):
        raise ProjectionValidationError("projection must be a JSON object")
    for field in REQUIRED_PROJECTION_FIELDS:
        if field not in projection:
            errors.append("missing field: %s" % field)
    if errors:
        raise ProjectionValidationError("; ".join(errors))
    if projection.get("schema") != SCHEMA:
        errors.append("invalid schema")
    if projection.get("schema_version") != SCHEMA_VERSION:
        errors.append("invalid schema_version")
    if not str(projection.get("feature_id") or ""):
        errors.append("feature_id must be non-empty")
    if not str(projection.get("projection_id") or "").startswith("fep-"):
        errors.append("projection_id must start with fep-")
    digest = str(projection.get("content_digest") or "")
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        errors.append("content_digest must be 64 hex characters")
    if projection.get("projection_status") not in PROJECTION_STATUSES:
        errors.append("invalid projection_status")
    if "verification_status" in projection:
        verification = projection.get("verification_status")
        if not isinstance(verification, dict):
            errors.append("verification_status must be an object")
        else:
            for field in ("feature_verification_status", "test_execution_status",
                          "runtime_verification_status", "behavior_verification_status"):
                if verification.get(field) not in VERIFICATION_STATUSES:
                    errors.append("invalid verification_status.%s" % field)
            if not str(verification.get("basis") or ""):
                errors.append("verification_status.basis must be non-empty")
    if not isinstance(projection.get("source_identity"), dict):
        errors.append("source_identity must be an object")
    for section in EVIDENCE_SECTIONS:
        items = projection.get(section)
        if not isinstance(items, list):
            errors.append("%s must be a list" % section)
            continue
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append("%s[%d] must be an object" % (section, index))
                continue
            for field in ("evidence_id", "evidence_type", "value", "source_type",
                          "source_record_id", "extraction_status", "reliability",
                          "provenance", "limitations"):
                if field not in item:
                    errors.append("%s[%d] missing %s" % (section, index, field))
            if item.get("extraction_status") not in EVIDENCE_STATUSES:
                errors.append("%s[%d] invalid extraction_status: %s"
                              % (section, index, item.get("extraction_status")))
            if item.get("reliability") not in RELIABILITY_VALUES:
                errors.append("%s[%d] invalid reliability: %s"
                              % (section, index, item.get("reliability")))
            if not str(item.get("evidence_id") or ""):
                errors.append("%s[%d] empty evidence_id" % (section, index))
            if not isinstance(item.get("provenance"), dict):
                errors.append("%s[%d] provenance must be an object" % (section, index))
            if not isinstance(item.get("limitations"), list):
                errors.append("%s[%d] limitations must be a list" % (section, index))
    for field in ("declared_evidence", "extracted_evidence"):
        if not isinstance(projection.get(field), list):
            errors.append("%s must be a list" % field)
    for ref in projection.get("source_references") or []:
        if not isinstance(ref, dict):
            errors.append("source_references entries must be objects")
            break
        for field in ("source_type", "source_path", "source_digest", "source_status",
                      "original_path", "normalized_path", "normalization_status"):
            if field not in ref:
                errors.append("source_references entries missing %s" % field)
                break
        if not ref.get("source_type") or not ref.get("source_path"):
            errors.append("source_references entries require source_type/source_path")
            break
    for ref in projection.get("analysis_references") or []:
        if not isinstance(ref, dict):
            errors.append("analysis_references entries must be objects")
            break
        for field in ("analysis_record_path", "analysis_status", "analysis_digest",
                      "analyzed_source_files", "limitations"):
            if field not in ref:
                errors.append("analysis_references entries missing %s" % field)
                break
    counts = projection.get("evidence_counts")
    if not isinstance(counts, dict):
        errors.append("evidence_counts must be an object")
    else:
        total = sum(counts.values()) if all(isinstance(v, int) for v in counts.values()) else -1
        actual = sum(len(projection.get(section) or []) for section in EVIDENCE_SECTIONS)
        if total != actual:
            errors.append("evidence_counts total does not match evidence sections")
    if errors:
        raise ProjectionValidationError("; ".join(errors))


def write_projection(projection: dict, out_dir: str | Path = DEFAULT_OUT,
                     *, replace_func=os.replace) -> str:
    validate_projection(projection)
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / ("%s.json" % projection["feature_id"])
    fd, temporary = tempfile.mkstemp(prefix=".feature-evidence-", suffix=".tmp", dir=str(directory))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(projection, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        loaded = json.loads(Path(temporary).read_text(encoding="utf-8"))
        validate_projection(loaded)
        replace_func(temporary, str(target))
        return str(target)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def build_and_write(feature_id: str, out_dir: str | Path = DEFAULT_OUT, **kwargs) -> tuple[dict, str]:
    replace_func = kwargs.pop("replace_func", os.replace)
    projection = build_projection(feature_id, **kwargs)
    path = write_projection(projection, out_dir, replace_func=replace_func)
    return projection, path


def check_projection(feature_id: str, *, out_dir: str | Path = DEFAULT_OUT,
                     **kwargs) -> dict:
    target = Path(out_dir) / ("%s.json" % feature_id)
    if not target.is_file():
        return {"feature_id": feature_id, "status": "MISSING", "path": str(target),
                "reason": "no existing projection"}
    try:
        existing = json.loads(target.read_text(encoding="utf-8"))
        validate_projection(existing)
    except Exception as exc:  # noqa: BLE001
        return {"feature_id": feature_id, "status": "INVALID", "path": str(target),
                "reason": str(exc)}
    try:
        current = build_projection(feature_id, **kwargs)
    except Exception as exc:  # noqa: BLE001
        return {"feature_id": feature_id, "status": "INVALID", "path": str(target),
                "reason": "cannot build current projection: %s" % exc}
    changed: list[str] = []
    old_refs = {(item.get("source_type"), item.get("source_path")): item.get("source_digest")
                for item in existing.get("source_references") or []}
    new_refs = {(item.get("source_type"), item.get("source_path")): item.get("source_digest")
                for item in current.get("source_references") or []}
    for key in sorted(set(old_refs) | set(new_refs)):
        if old_refs.get(key) != new_refs.get(key):
            changed.append("%s:%s" % key)
    status = "FRESH" if existing.get("content_digest") == current.get("content_digest") else "STALE"
    return {"feature_id": feature_id, "status": status, "path": str(target),
            "changed_sources": changed,
            "existing_status": existing.get("projection_status"),
            "current_status": current.get("projection_status")}


def _resolve_features(feature: list[str] | None = None, pilot: bool = False,
                      all_features: bool = False, features_dir: str | Path = FEATURES_DIR) -> list[str]:
    if pilot:
        selected = list(PILOT_FEATURES)
    elif feature:
        selected = list(feature)
    elif all_features:
        selected = sorted(path.parent.name for path in Path(features_dir).glob("*/feature.yaml"))
    else:
        raise ProjectionError("choose --feature, --pilot, or --all")
    for value in selected:
        if not (Path(features_dir) / value / "feature.yaml").is_file():
            raise ProjectionError("unknown Feature: %s" % value)
    return selected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Feature Evidence Projection (Phase 1.73 Batch A)")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="build Feature Evidence Projection")
    build.add_argument("--feature", action="append", default=[])
    build.add_argument("--pilot", action="store_true")
    build.add_argument("--all", action="store_true")
    build.add_argument("--out", default=str(DEFAULT_OUT))
    build.add_argument("--json", action="store_true")

    check = sub.add_parser("check", help="check projection freshness")
    check.add_argument("--feature", action="append", default=[])
    check.add_argument("--pilot", action="store_true")
    check.add_argument("--all", action="store_true")
    check.add_argument("--out", default=str(DEFAULT_OUT))
    check.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    try:
        selected = _resolve_features(args.feature, args.pilot, args.all)
        if args.command == "build":
            results = []
            for feature_id in selected:
                projection, path = build_and_write(feature_id, args.out)
                results.append({"feature_id": feature_id, "status": projection["projection_status"],
                                "path": path, "evidence_counts": projection["evidence_counts"]})
            if args.json:
                print(json.dumps({"built": results}, ensure_ascii=False, indent=2))
            else:
                for item in results:
                    print("%s: %s -> %s" % (item["feature_id"], item["status"], item["path"]))
            return 0
        results = [check_projection(feature_id, out_dir=args.out) for feature_id in selected]
        if args.json:
            print(json.dumps({"checked": results}, ensure_ascii=False, indent=2))
        else:
            for item in results:
                print("%s: %s" % (item["feature_id"], item["status"]))
        return 0 if all(item["status"] == "FRESH" for item in results) else 1
    except Exception as exc:  # noqa: BLE001
        print("FAIL: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
