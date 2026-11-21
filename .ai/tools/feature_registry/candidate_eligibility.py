#!/usr/bin/env python3
"""Phase 1.74 Batch C - centralized Candidate seed eligibility guard.

Every candidate draft obtains its evidence through this module.  No other module
is allowed to decide whether a linkage record may seed a candidate: the rules
live here once, and both the builder and the validators call them.

Two dimensions are deliberately separate:

* ``seed_eligibility`` - the reviewed qualification from Phase 1.73 Batch B.2,
  carried by ``candidate_seed_policy.json`` (never inferred from counts, file
  names or record contents).
* ``location_integrity`` - whether the evidence location can be expressed in both
  coordinate systems (record line on the references copy, commit line on the
  immutable source).  A seed that passed review but cannot be dual-coordinated
  stays eligible and is marked incomplete; it is never rejected for it.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
AI_ROOT = TOOLS_DIR.parents[1]
PROJECT_ROOT = TOOLS_DIR.parents[2]
EXTERNAL_CODE_DIR = AI_ROOT / "tools" / "external_code"

if str(EXTERNAL_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(EXTERNAL_CODE_DIR))

import feature_linkage as linkage  # noqa: E402

POLICY_PATH = TOOLS_DIR / "candidate_seed_policy.json"

SEED_ELIGIBLE_QUALIFICATIONS = frozenset({
    "QUALIFIED_DIRECT",
    "QUALIFIED_DIRECT_WITH_LIMITATIONS",
})
INDEPENDENCE_VALUES = ("INDEPENDENT", "NOT_INDEPENDENT", "UNKNOWN")
GRAPH_DERIVED = "GRAPH_DERIVED_RELATION"
EXTERNAL_DIRECT = "EXTERNAL_DIRECT_IMPLEMENTATION"

LOCATION_COMPLETE = "COMPLETE"
LOCATION_PARTIAL = "PARTIAL"
LOCATION_INCOMPLETE = "INCOMPLETE"

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")


class EligibilityError(RuntimeError):
    """The policy or a guard input is structurally unusable."""


def _sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# --- policy -------------------------------------------------------------------

POLICY_REQUIRED = ("schema", "schema_version", "policy_version", "feature_scope",
                   "excluded_features", "seeds", "context_relations")


def load_policy(path: str | Path = POLICY_PATH) -> dict:
    target = Path(path)
    if not target.is_file():
        raise EligibilityError("policy not found: %s" % target)
    try:
        policy = json.loads(target.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise EligibilityError("policy is not valid JSON: %s" % exc) from exc
    if not isinstance(policy, dict):
        raise EligibilityError("policy must be an object")
    for field in POLICY_REQUIRED:
        if field not in policy:
            raise EligibilityError("policy missing %s" % field)
    if policy["schema"] != "candidate_seed_policy":
        raise EligibilityError("unexpected policy schema: %s" % policy["schema"])
    if policy["schema_version"] != 1:
        raise EligibilityError("unsupported policy schema_version: %s"
                               % policy["schema_version"])
    seen: set[str] = set()
    for entry in policy["seeds"]:
        for field in ("linkage_id", "feature_id", "qualification_status", "independence"):
            if not entry.get(field):
                raise EligibilityError("seed entry missing %s" % field)
        if entry["linkage_id"] in seen:
            raise EligibilityError("duplicate seed linkage_id: %s" % entry["linkage_id"])
        seen.add(entry["linkage_id"])
        if entry["qualification_status"] not in SEED_ELIGIBLE_QUALIFICATIONS:
            raise EligibilityError("seed %s has non-seed qualification %s"
                                   % (entry["linkage_id"], entry["qualification_status"]))
        if entry["independence"] not in INDEPENDENCE_VALUES:
            raise EligibilityError("seed %s has invalid independence %s"
                                   % (entry["linkage_id"], entry["independence"]))
    for entry in policy["context_relations"]:
        for field in ("linkage_id", "feature_id", "evidence_kind", "derivation_type"):
            if not entry.get(field):
                raise EligibilityError("context relation missing %s" % field)
        if entry["linkage_id"] in seen:
            raise EligibilityError("linkage %s is both seed and context"
                                   % entry["linkage_id"])
    return policy


def seed_entries(policy: dict, feature_id: str) -> list[dict]:
    return [entry for entry in policy["seeds"] if entry["feature_id"] == feature_id]


def seed_entry(policy: dict, linkage_id: str) -> dict | None:
    for entry in policy["seeds"]:
        if entry["linkage_id"] == linkage_id:
            return entry
    return None


def context_entries(policy: dict, feature_id: str) -> list[dict]:
    return [entry for entry in policy["context_relations"]
            if entry.get("attach_to_feature") == feature_id]


# --- dual coordinate resolution -----------------------------------------------

def _read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def resolve_line_offset(reference_path: str | Path, source_path: str | Path) -> dict:
    """Derive the reference-copy line offset WITHOUT assuming a value.

    The references copy is the analysed file; the sources copy is the immutable
    commit file.  Only a pure prefix difference is accepted, so the offset is
    provable from the two files rather than hard-coded.
    """
    reference = Path(reference_path)
    source = Path(source_path)
    if not reference.is_file() or not source.is_file():
        return {"offset": None, "verified": False,
                "basis": "either the references copy or the commit copy is missing"}
    ref_lines = _read_lines(reference)
    src_lines = _read_lines(source)
    if ref_lines == src_lines:
        return {"offset": 0, "verified": True,
                "basis": "references copy and commit copy are line-identical"}
    limit = len(ref_lines) - len(src_lines)
    if limit > 0 and ref_lines[limit:] == src_lines:
        return {"offset": limit, "verified": True,
                "basis": ("references copy = commit copy plus %d prepended line(s); "
                          "verified by comparing both files line-for-line" % limit)}
    return {"offset": None, "verified": False,
            "basis": "references copy is not a pure prefix extension of the commit copy "
                     "(content differs beyond a header), so no offset can be derived"}


def _commit_source_path(record: dict) -> str | None:
    path = ((record.get("source_verification") or {}).get("external_source_file") or {}).get("path")
    return str(path) if path else None


def build_evidence_location(record: dict, item: dict) -> dict:
    """Express one evidence item's location in both coordinate systems."""
    analysis = record.get("external_analysis") or {}
    commit = analysis.get("source_commit") or ""
    record_line = item.get("line_reference")
    symbol = item.get("symbol_name") or ""
    reference_path = item.get("source_path") or ""
    source_path = _commit_source_path(record) or ""
    offset = resolve_line_offset(reference_path, source_path) if reference_path and source_path \
        else {"offset": None, "verified": False, "basis": "source paths missing"}

    commit_line = None
    symbol_status = "UNKNOWN"
    if item.get("source_side") == "FEATURE_GRAPH":
        integrity = LOCATION_INCOMPLETE
        basis = ("graph-derived item: the location is a Feature-graph reference, "
                 "not a source line")
    elif record_line is None:
        integrity = LOCATION_INCOMPLETE
        basis = ("record carries no line for this item; no commit line can be derived "
                 "without guessing")
    elif not offset["verified"] or offset["offset"] is None:
        integrity = LOCATION_INCOMPLETE
        basis = "line offset unverified: %s" % offset["basis"]
    else:
        candidate_line = record_line - offset["offset"]
        lines = _read_lines(Path(source_path))
        if 1 <= candidate_line <= len(lines):
            commit_line = candidate_line
            if symbol and symbol in lines[candidate_line - 1]:
                symbol_status = "VERIFIED"
                integrity = LOCATION_COMPLETE
            else:
                symbol_status = "SYMBOL_NOT_AT_LINE"
                integrity = LOCATION_PARTIAL
            basis = ("%s; commit_line = record_line - %d; symbol '%s' checked against the "
                     "commit copy" % (offset["basis"], offset["offset"], symbol))
        else:
            integrity = LOCATION_PARTIAL
            basis = ("commit line %d is outside the commit copy (%d lines)"
                     % (candidate_line, len(lines)))

    return {
        "record_line": record_line,
        "commit_line": commit_line,
        "source_path": analysis.get("source_path") or "",
        "source_commit": commit,
        "location_basis": basis,
        "offset_applied": offset["offset"],
        "offset_verified": bool(offset["verified"]),
        "symbol_at_commit_line": symbol_status,
        "location_integrity": integrity,
        "source_lookup_allowed": integrity == LOCATION_COMPLETE,
        "references_path": reference_path,
        "commit_file_path": source_path,
        "commit_relative_path": analysis.get("source_path") or "",
    }


# --- evidence health -----------------------------------------------------------

def _digest_matched(record: dict) -> bool:
    verification = record.get("source_verification") or {}
    analysis = (verification.get("analysis_record") or {})
    source_file = (verification.get("external_source_file") or {})
    return (analysis.get("digest_status") == "MATCHED"
            and source_file.get("digest_status") == "MATCHED")


def _identity_problems(record: dict) -> list[tuple[str, object, str]]:
    analysis = record.get("external_analysis") or {}
    problems: list[tuple[str, object, str]] = []
    repository = analysis.get("source_repository") or ""
    commit = analysis.get("source_commit") or ""
    digest = analysis.get("source_digest") or ""
    url = analysis.get("source_url") or ""
    if repository.count("/") != 1:
        problems.append(("source_repository", repository, "one owner/repo segment"))
    if not _SHA40.match(str(commit)):
        problems.append(("source_commit", commit, "40 hex characters"))
    if not _SHA64.match(str(digest)):
        problems.append(("source_digest", digest, "64 hex characters"))
    if commit and str(commit) not in url:
        problems.append(("source_url", url, "immutable URL containing the commit"))
    return problems


def _check(name: str, ok: bool, field: str, value, expected: str,
           code: str, recoverable: bool) -> dict:
    return {"check": name, "status": "PASS" if ok else "FAIL", "field": field,
            "value": value, "expected": expected, "code": None if ok else code,
            "recoverable": recoverable}


def evaluate_seed_eligibility(record: dict, policy: dict, *, location: bool = True) -> dict:
    """Decide whether one linkage record may seed a candidate.

    Returns a fully explained result; ``eligible`` is the only boolean and it is
    never the whole answer.
    """
    if not isinstance(record, dict):
        raise EligibilityError("record must be an object")

    link_id = str(record.get("linkage_id") or "")
    feature_id = str(record.get("feature_id") or "")
    classification = record.get("linkage_classification") or ""
    entry = seed_entry(policy, link_id)
    items = linkage.linkage_evidence_items(record)
    analysis = record.get("external_analysis") or {}
    location_result = None

    checks: list[dict] = []

    in_scope = feature_id in policy.get("feature_scope", [])
    checks.append(_check(
        "feature_scope", in_scope, "feature_id", feature_id,
        "one of %s" % list(policy.get("feature_scope", [])),
        "FEATURE_OUT_OF_SCOPE", False))

    if feature_id in policy.get("excluded_features", {}):
        checks.append(_check(
            "excluded_feature", False, "feature_id", feature_id,
            "a Feature with a qualified seed (excluded by policy)",
            "FEATURE_EXCLUDED", False))

    reviewed = entry is not None
    qualification = (entry or {}).get("qualification_status") or ""
    checks.append(_check(
        "reviewed_qualification", reviewed, "linkage_id", link_id,
        "a linkage_id reviewed in the Batch B.2 policy",
        "QUALIFICATION_NOT_REVIEWED", True))

    policy_feature_ok = reviewed and (entry or {}).get("feature_id") == feature_id
    checks.append(_check(
        "policy_feature_match", policy_feature_ok, "feature_id", feature_id,
        "the feature_id the reviewed qualification was recorded for",
        "POLICY_FEATURE_CONFLICT", False))

    classification_ok = (reviewed
                         and classification == linkage.DIRECT_EVIDENCE
                         and qualification in SEED_ELIGIBLE_QUALIFICATIONS)
    checks.append(_check(
        "linkage_classification", classification_ok, "linkage_classification",
        classification, "DIRECT_EVIDENCE with a QUALIFIED_DIRECT* review",
        "CLASSIFICATION_NOT_ELIGIBLE", False))

    roles_ok = bool(items) and all(
        item.get("evidence_role") == linkage.LINKAGE_EVIDENCE_ROLE for item in items)
    checks.append(_check(
        "evidence_role", roles_ok, "evidence_items[].evidence_role",
        sorted({item.get("evidence_role") for item in items}) or None,
        "every item LINKAGE_EVIDENCE and at least one item",
        "EVIDENCE_ROLE_NOT_LINKAGE", False))

    graph_only = bool(items) and all(
        item.get("evidence_type") in linkage.GRAPH_EVIDENCE_TYPES for item in items)
    checks.append(_check(
        "not_graph_derived", not (graph_only or linkage.is_graph_derived_relation(record)),
        "evidence_items[].evidence_type",
        sorted({item.get("evidence_type") for item in items}) or None,
        "no GRAPH_RELATION support",
        "GRAPH_DERIVED_NOT_SEED", False))

    provenance_ok = analysis.get("provenance_status") == "complete"
    checks.append(_check(
        "provenance_status", provenance_ok, "external_analysis.provenance_status",
        analysis.get("provenance_status"), "complete",
        "PROVENANCE_INCOMPLETE", True))

    digest_ok = _digest_matched(record)
    checks.append(_check(
        "source_digest", digest_ok, "source_verification.*.digest_status",
        {"analysis_record": ((record.get("source_verification") or {})
                             .get("analysis_record") or {}).get("digest_status"),
         "external_source_file": ((record.get("source_verification") or {})
                                  .get("external_source_file") or {}).get("digest_status")},
        "both MATCHED", "SOURCE_DIGEST_UNVERIFIED", True))

    identity_problems = _identity_problems(record)
    checks.append(_check(
        "source_identity", not identity_problems, "external_analysis.*",
        [{"field": f, "value": v} for f, v, _ in identity_problems] or "complete",
        "owner/repo, 40-hex commit, 64-hex digest, commit inside the URL",
        "SOURCE_IDENTITY_MISSING", False))

    independence = (entry or {}).get("independence") or "UNKNOWN"
    independence_ok = reviewed and independence in ("INDEPENDENT", "NOT_INDEPENDENT")
    checks.append(_check(
        "independence", independence_ok, "independence", independence,
        "INDEPENDENT or NOT_INDEPENDENT recorded in the reviewed policy",
        "INDEPENDENCE_UNKNOWN", True))

    if location:
        locations = [build_evidence_location(record, item) for item in items]
        integrity = LOCATION_COMPLETE
        if any(loc["location_integrity"] == LOCATION_INCOMPLETE for loc in locations):
            integrity = LOCATION_INCOMPLETE
        elif any(loc["location_integrity"] == LOCATION_PARTIAL for loc in locations):
            integrity = LOCATION_PARTIAL
        location_result = {
            "location_integrity": integrity,
            "items": locations,
            "source_lookup_allowed": bool(locations) and all(
                loc["source_lookup_allowed"] for loc in locations),
        }

    failures = [check for check in checks if check["status"] == "FAIL"]
    eligible = not failures
    first = failures[0] if failures else None
    result = {
        "linkage_id": link_id,
        "feature_id": feature_id,
        "analysis_id": record.get("analysis_id"),
        "eligible": eligible,
        "seed_eligibility": qualification if eligible else None,
        "independence": independence,
        "evidence_kind": EXTERNAL_DIRECT if eligible else None,
        "derivation_type": None,
        "codes": [check["code"] for check in failures],
        "checks": checks,
        "reason": (first["code"] + ": " + str(first["field"]) + "=" + str(first["value"])
                   if first else "all eligibility checks passed"),
        "recoverable": bool(first and first["recoverable"]) if first else True,
        "location_integrity": (location_result or {}).get("location_integrity"),
        "source_lookup_allowed": (location_result or {}).get("source_lookup_allowed"),
        "locations": (location_result or {}).get("items", []),
        "policy_entry": entry,
    }
    return result


def build_evidence_reference(record: dict, policy: dict) -> dict:
    """Build one candidate evidence reference from a reviewed linkage record."""
    evaluation = evaluate_seed_eligibility(record, policy)
    if not evaluation["eligible"]:
        raise EligibilityError("linkage %s is not seed-eligible: %s"
                               % (evaluation["linkage_id"], evaluation["reason"]))
    entry = evaluation["policy_entry"]
    analysis = record.get("external_analysis") or {}
    item_refs = []
    for item in linkage.linkage_evidence_items(record):
        loc = build_evidence_location(record, item)
        item_refs.append({
            "evidence_id": item.get("evidence_id"),
            "symbol_name": item.get("symbol_name"),
            "evidence_type": item.get("evidence_type"),
            "evidence_status": item.get("evidence_status"),
            "evidence_role": item.get("evidence_role"),
            "matched_value": item.get("matched_value"),
            "feature_evidence_id": item.get("feature_evidence_id"),
            "feature_source_path": item.get("feature_source_path"),
            "feature_source_line": item.get("feature_source_line"),
            "record_line": loc["record_line"],
            "commit_line": loc["commit_line"],
            "location_integrity": loc["location_integrity"],
            "symbol_at_commit_line": loc["symbol_at_commit_line"],
            "provenance_reference": item.get("provenance_reference"),
        })
    record_path = record.get("__path__") or ""
    located = next((ref for ref in item_refs if ref["record_line"] is not None), None)
    return {
        "linkage_id": record["linkage_id"],
        "feature_id": record["feature_id"],
        "classification": record.get("linkage_classification"),
        "evidence_role": "LINKAGE_EVIDENCE",
        "seed_eligibility": evaluation["seed_eligibility"],
        "evidence_kind": evaluation["evidence_kind"],
        "independence": evaluation["independence"],
        "independence_reason": entry.get("independence_reason", ""),
        "derivation_type": None,
        "architecture": entry.get("architecture", ""),
        "qualification_reason": entry.get("qualification_reason", ""),
        "source_repository": analysis.get("source_repository"),
        "source_commit": analysis.get("source_commit"),
        "source_digest": analysis.get("source_digest"),
        "immutable_source_url": analysis.get("source_url"),
        "source_consistent": (record.get("source_verification") or {})
                             .get("external_source_file", {}).get("digest_status") == "MATCHED",
        "analysis_id": record.get("analysis_id"),
        "analysis_record_path": (record.get("external_analysis") or {})
                                .get("analysis_record_path"),
        "analysis_record_digest": (record.get("external_analysis") or {})
                                  .get("analysis_record_digest"),
        "linkage_record_path": record_path,
        "linkage_record_digest": _sha256_file(record_path) if record_path else None,
        "evidence_location": {
            "record_line": (located or {}).get("record_line"),
            "commit_line": (located or {}).get("commit_line"),
            "source_path": analysis.get("source_path"),
            "source_commit": analysis.get("source_commit"),
            "location_basis": (evaluation["locations"][0]["location_basis"]
                               if evaluation["locations"] else ""),
            "offset_applied": (evaluation["locations"][0]["offset_applied"]
                               if evaluation["locations"] else None),
            "offset_verified": bool(evaluation["locations"]) and all(
                loc["offset_verified"] for loc in evaluation["locations"]),
            "location_integrity": evaluation["location_integrity"],
            "source_lookup_allowed": evaluation["source_lookup_allowed"],
        },
        "evidence_item_refs": item_refs,
        "limitations": list(entry.get("limitations", [])),
        "symbol_notes": list(entry.get("symbol_notes", [])),
        "verification_status": {
            "eligibility_status": evaluation["seed_eligibility"],
            "test_execution_status": "NOT_RUN",
            "runtime_verification_status": "NOT_VERIFIED",
            "behavior_verification_status": "NOT_VERIFIED",
            "feature_verification_status": "NOT_VERIFIED",
        },
    }


def build_context_reference(record: dict, policy: dict) -> dict:
    """Build a graph-derived context reference; never seed-eligible."""
    link_id = str(record.get("linkage_id") or "")
    entry = None
    for candidate in policy.get("context_relations", []):
        if candidate["linkage_id"] == link_id:
            entry = candidate
            break
    if entry is None:
        raise EligibilityError("linkage %s is not a reviewed context relation" % link_id)

    problems = []
    if record.get("linkage_classification") != linkage.INDIRECT_EVIDENCE:
        problems.append(("linkage_classification", record.get("linkage_classification"),
                         "INDIRECT_EVIDENCE"))
    if not linkage.is_graph_derived_relation(record):
        problems.append(("evidence_kind", "not graph-derived", "GRAPH_DERIVED_RELATION"))
    items = linkage.linkage_evidence_items(record)
    path = next((item.get("intermediate_path") for item in items
                 if item.get("intermediate_path")), None)
    declared_path = entry.get("derivation_path") or []
    expected_relation = declared_path[1] if len(declared_path) > 1 else None
    if not path:
        problems.append(("intermediate_path", path, "a graph relation path"))
    elif expected_relation is not None and path[1:2] != [expected_relation]:
        problems.append(("intermediate_path", path,
                         "path with relation type '%s'" % expected_relation))
    if entry.get("intermediate_feature_ids") and path is not None:
        for needed in entry["intermediate_feature_ids"]:
            if needed not in path:
                problems.append(("intermediate_feature_ids", path,
                                 "contains %s" % needed))
    if entry["feature_id"] != record.get("feature_id"):
        problems.append(("feature_id", record.get("feature_id"), entry["feature_id"]))
    if problems:
        raise EligibilityError("linkage %s is not a safe context relation: %s"
                               % (link_id, problems))

    analysis = record.get("external_analysis") or {}
    return {
        "linkage_id": link_id,
        "feature_id": record.get("feature_id"),
        "attached_to_feature": entry.get("attach_to_feature"),
        "context_kind": entry["evidence_kind"],
        "evidence_kind": GRAPH_DERIVED,
        "derivation_type": entry["derivation_type"],
        "intermediate_feature_ids": list(entry["intermediate_feature_ids"]),
        "derivation_path": list(path),
        "graph_edge_reference": entry.get("graph_edge_reference"),
        "graph_declaration_origin": entry.get("graph_declaration_origin"),
        "counts_as_seed": False,
        "counts_as_implementation_evidence": False,
        "classification": record.get("linkage_classification"),
        "evidence_role": "LINKAGE_EVIDENCE",
        "source_repository": analysis.get("source_repository"),
        "source_commit": analysis.get("source_commit"),
        "source_digest": analysis.get("source_digest"),
        "immutable_source_url": analysis.get("source_url"),
        "linkage_record_path": record.get("__path__"),
        "linkage_record_digest": (_sha256_file(record["__path__"])
                                  if record.get("__path__") else None),
        "analysis_id": record.get("analysis_id"),
        "reason": entry.get("reason", ""),
        "limitations": [
            "graph-derived relation: derived from the internal Feature graph, "
            "not from external attack-emission code",
            "must never be counted as a direct seed, a DIRECT classification, "
            "or a QUALIFIED_DIRECT qualification",
            "the graph edge itself is a human-declared metadata relation without "
            "a recorded rationale",
        ],
    }


if __name__ == "__main__":  # pragma: no cover - thin inspection helper
    import argparse

    parser = argparse.ArgumentParser(description="Inspect seed eligibility policy")
    parser.add_argument("--policy", default=str(POLICY_PATH))
    parser.add_argument("--linkage", action="append", default=[])
    args = parser.parse_args()
    policy_data = load_policy(args.policy)
    records = {record.get("linkage_id"): record
               for record in linkage.load_linkage_records()}
    targets = args.linkage or [entry["linkage_id"] for entry in policy_data["seeds"]]
    for target in targets:
        record = records.get(target)
        if record is None:
            print("MISSING %s" % target)
            continue
        result = evaluate_seed_eligibility(record, policy_data)
        print(json.dumps({key: result[key] for key in
                          ("linkage_id", "feature_id", "eligible", "seed_eligibility",
                           "independence", "location_integrity", "codes", "reason")},
                         ensure_ascii=False, indent=2))
