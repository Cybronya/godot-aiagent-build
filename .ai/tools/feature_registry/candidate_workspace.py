#!/usr/bin/env python3
"""Phase 1.74 Batch C - restricted Candidate Workspace foundation.

A candidate draft is a *restricted* record: it groups the evidence that may seed
a later comparison stage for one Feature.  It is not a Feature, it is not a
promotion, and it does not verify anything.

Everything that decides whether a linkage record may enter a draft lives in
``candidate_eligibility``.  This module only assembles, validates, persists and
inspects drafts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
AI_ROOT = TOOLS_DIR.parents[1]
PROJECT_ROOT = TOOLS_DIR.parents[2]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(AI_ROOT / "tools" / "external_code") not in sys.path:
    sys.path.insert(0, str(AI_ROOT / "tools" / "external_code"))

import candidate_eligibility as eligibility  # noqa: E402
import feature_linkage as linkage  # noqa: E402

CANDIDATE_SCHEMA = "candidate_workspace_draft"
WORKSPACE_SCHEMA = "candidate_workspace"
SCHEMA_VERSION = 1

WORKSPACE_DIR = AI_ROOT / "learning" / "candidate_workspace"
CANDIDATE_DIRNAME = "candidates"

STATUS_DRAFT = "DRAFT"
STATUS_NEEDS_REVIEW = "NEEDS_REVIEW"
STATUS_BLOCKED = "BLOCKED"
CANDIDATE_STATUSES = (STATUS_DRAFT, STATUS_NEEDS_REVIEW, STATUS_BLOCKED)
# Statuses that would imply a decision this stage is forbidden to make.
FORBIDDEN_STATUSES = ("ADMITTED", "PROMOTED", "VERIFIED", "ACCEPTED", "APPROVED")

DIGEST_EXCLUDED = ("content_digest", "created_at", "updated_at")

VERIFICATION_TEMPLATE = {
    "eligibility_status": "INELIGIBLE",
    "test_execution_status": "NOT_RUN",
    "runtime_verification_status": "NOT_VERIFIED",
    "behavior_verification_status": "NOT_VERIFIED",
    "feature_verification_status": "NOT_VERIFIED",
    "basis": "NO_EXECUTION_EVIDENCE",
}

REQUIRED_CANDIDATE_FIELDS = (
    "schema", "schema_version", "candidate_id", "feature_id", "feature_name",
    "candidate_status", "workspace_id", "created_at", "updated_at",
    "policy_version", "evidence_refs", "context_refs", "excluded_evidence",
    "eligibility_summary", "verification_status", "limitations",
    "source_snapshot", "content_digest",
)

REQUIRED_EVIDENCE_FIELDS = (
    "linkage_id", "feature_id", "classification", "evidence_role",
    "seed_eligibility", "independence", "derivation_type", "source_repository",
    "source_commit", "source_digest", "immutable_source_url", "source_consistent",
    "evidence_location", "evidence_item_refs",
)

REQUIRED_LOCATION_FIELDS = (
    "record_line", "commit_line", "source_path", "source_commit", "location_basis",
)

REQUIRED_CONTEXT_FIELDS = (
    "linkage_id", "feature_id", "context_kind", "derivation_type",
    "intermediate_feature_ids", "counts_as_seed",
)

# Keys that would turn a draft into a decision record.
FORBIDDEN_KEYS = frozenset({
    "admission", "admission_decision", "admission_gate", "promoted", "promotion",
    "promotion_decision", "similarity", "similarity_score", "ranking", "rank",
    "cluster", "deduplicated", "feature_candidate", "verified", "accepted",
    "feature_created", "feature_registry_write",
})


class CandidateError(RuntimeError):
    """A candidate could not be built, read or validated."""


class CandidateValidationError(CandidateError):
    """A draft does not satisfy the schema or the evidence rules."""


# --- helpers -------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: str | Path) -> str:
    return _sha256_bytes(Path(path).read_bytes())


def _canonical(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def candidate_content_digest(candidate: dict) -> str:
    """Reproducible digest of a draft, ignoring volatile fields."""
    # ``__path__`` is injected by the loader and must never enter the digest.
    body = {key: value for key, value in candidate.items()
            if key not in DIGEST_EXCLUDED and not key.startswith("__")}
    snapshot = dict(body.get("source_snapshot") or {})
    snapshot.pop("observed_at", None)
    body["source_snapshot"] = snapshot
    return _sha256_bytes(_canonical(body).encode("utf-8"))


def candidate_identity(feature_id: str, linkage_ids, policy_version: str) -> str:
    """Content identity: same feature + same seed set + same policy = same id."""
    joined = ",".join(sorted(str(value) for value in linkage_ids))
    return "cand-" + _sha256_bytes(
        ("%s|%s|%s" % (feature_id, joined, policy_version)).encode("utf-8"))[:16]


def workspace_identity(policy: dict) -> str:
    scope = ",".join(sorted(policy.get("feature_scope", [])))
    return "ws-" + _sha256_bytes(
        ("%s|%s" % (policy.get("policy_version"), scope)).encode("utf-8"))[:12]


def _atomic_write(path: Path, payload: str, *, replace_func=os.replace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=".candidate-", suffix=".tmp",
                                         dir=str(path.parent))
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        replace_func(temporary, str(path))
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise


def _relative(path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(PROJECT_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


# --- validation ----------------------------------------------------------------

def _check_forbidden_keys(payload, trail: str, errors: list[str]) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in FORBIDDEN_KEYS and value:
                errors.append("%s.%s is a forbidden decision key" % (trail, key))
            _check_forbidden_keys(value, "%s.%s" % (trail, key), errors)
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            _check_forbidden_keys(value, "%s[%d]" % (trail, index), errors)


def validate_candidate_evidence(candidate: dict) -> list[str]:
    """Structural rules for the evidence and context reference lists."""
    errors: list[str] = []
    seeds = candidate.get("evidence_refs")
    contexts = candidate.get("context_refs")
    if not isinstance(seeds, list) or not isinstance(contexts, list):
        return ["evidence_refs and context_refs must be lists"]

    seed_ids = []
    for index, ref in enumerate(seeds):
        trail = "evidence_refs[%d]" % index
        if not isinstance(ref, dict):
            errors.append("%s must be an object" % trail)
            continue
        for field in REQUIRED_EVIDENCE_FIELDS:
            if field not in ref:
                errors.append("%s missing %s" % (trail, field))
        if ref.get("classification") != linkage.DIRECT_EVIDENCE:
            errors.append("%s classification must be DIRECT_EVIDENCE, got %r"
                          % (trail, ref.get("classification")))
        if ref.get("evidence_role") != linkage.LINKAGE_EVIDENCE_ROLE:
            errors.append("%s evidence_role must be LINKAGE_EVIDENCE" % trail)
        if ref.get("seed_eligibility") not in eligibility.SEED_ELIGIBLE_QUALIFICATIONS:
            errors.append("%s seed_eligibility %r is not seed-grade"
                          % (trail, ref.get("seed_eligibility")))
        if ref.get("independence") not in ("INDEPENDENT", "NOT_INDEPENDENT"):
            errors.append("%s independence must be explicit, got %r"
                          % (trail, ref.get("independence")))
        if ref.get("derivation_type") is not None:
            errors.append("%s seed evidence must not carry a derivation_type" % trail)
        if ref.get("evidence_kind") != eligibility.EXTERNAL_DIRECT:
            errors.append("%s evidence_kind must be %s"
                          % (trail, eligibility.EXTERNAL_DIRECT))
        if ref.get("feature_id") != candidate.get("feature_id"):
            errors.append("%s feature_id %r does not match the candidate feature %r"
                          % (trail, ref.get("feature_id"), candidate.get("feature_id")))
        location = ref.get("evidence_location")
        if not isinstance(location, dict):
            errors.append("%s evidence_location must be an object" % trail)
        else:
            for field in REQUIRED_LOCATION_FIELDS:
                if field not in location:
                    errors.append("%s.evidence_location missing %s" % (trail, field))
            if location.get("commit_line") is not None:
                if not isinstance(location.get("commit_line"), int):
                    errors.append("%s.evidence_location.commit_line must be int or null"
                                  % trail)
                if location.get("record_line") is not None \
                        and location.get("commit_line") == location.get("record_line") \
                        and location.get("offset_applied"):
                    errors.append("%s.evidence_location silently offsets the record line"
                                  % trail)
            if location.get("location_integrity") not in (
                    eligibility.LOCATION_COMPLETE, eligibility.LOCATION_PARTIAL,
                    eligibility.LOCATION_INCOMPLETE):
                errors.append("%s.evidence_location.location_integrity invalid" % trail)
            if location.get("location_integrity") != eligibility.LOCATION_COMPLETE \
                    and location.get("source_lookup_allowed"):
                errors.append("%s.evidence_location allows source lookup while incomplete"
                              % trail)
        if not isinstance(ref.get("evidence_item_refs"), list) or not ref["evidence_item_refs"]:
            errors.append("%s evidence_item_refs must be a non-empty list" % trail)
        seed_ids.append(ref.get("linkage_id"))

    for index, ref in enumerate(contexts):
        trail = "context_refs[%d]" % index
        if not isinstance(ref, dict):
            errors.append("%s must be an object" % trail)
            continue
        for field in REQUIRED_CONTEXT_FIELDS:
            if field not in ref:
                errors.append("%s missing %s" % (trail, field))
        if ref.get("counts_as_seed") is not False:
            errors.append("%s must declare counts_as_seed=false" % trail)
        if ref.get("context_kind") != eligibility.GRAPH_DERIVED:
            errors.append("%s context_kind must be %s"
                          % (trail, eligibility.GRAPH_DERIVED))
        if ref.get("derivation_type") != "FEATURE_GRAPH_NEIGHBOUR":
            errors.append("%s derivation_type must be FEATURE_GRAPH_NEIGHBOUR" % trail)
        if ref.get("linkage_id") in seed_ids:
            errors.append("%s linkage_id is also listed as seed evidence" % trail)
        if ref.get("classification") != linkage.INDIRECT_EVIDENCE:
            errors.append("%s classification must be INDIRECT_EVIDENCE" % trail)

    for excluded in candidate.get("excluded_evidence") or []:
        if excluded.get("linkage_id") in seed_ids:
            errors.append("excluded evidence %r is also a seed" % excluded.get("linkage_id"))

    summary = candidate.get("eligibility_summary") or {}
    if summary.get("seed_count") != len(seeds):
        errors.append("eligibility_summary.seed_count %r != %d evidence refs"
                      % (summary.get("seed_count"), len(seeds)))
    if summary.get("context_count") != len(contexts):
        errors.append("eligibility_summary.context_count %r != %d context refs"
                      % (summary.get("context_count"), len(contexts)))
    return errors


def validate_candidate_draft(candidate: dict) -> None:
    """Validate a draft; raises with every problem found."""
    errors: list[str] = []
    if not isinstance(candidate, dict):
        raise CandidateValidationError("candidate must be an object")
    for field in REQUIRED_CANDIDATE_FIELDS:
        if field not in candidate:
            errors.append("missing required field %s" % field)
    if errors:
        raise CandidateValidationError("; ".join(errors))

    if candidate.get("schema") != CANDIDATE_SCHEMA:
        errors.append("schema must be %s" % CANDIDATE_SCHEMA)
    if candidate.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version must be %d" % SCHEMA_VERSION)

    status = candidate.get("candidate_status")
    if status in FORBIDDEN_STATUSES:
        errors.append("candidate_status %r is a decision this stage must not make" % status)
    elif status not in CANDIDATE_STATUSES:
        errors.append("candidate_status %r is not one of %s"
                      % (status, list(CANDIDATE_STATUSES)))

    if not str(candidate.get("candidate_id") or "").startswith("cand-"):
        errors.append("candidate_id must be a content identity")
    if not str(candidate.get("workspace_id") or "").startswith("ws-"):
        errors.append("workspace_id must be a workspace identity")

    expected_id = candidate_identity(
        candidate.get("feature_id"),
        [ref.get("linkage_id") for ref in candidate.get("evidence_refs") or []],
        candidate.get("policy_version"))
    if candidate.get("candidate_id") != expected_id:
        errors.append("candidate_id %r is not the content identity %r"
                      % (candidate.get("candidate_id"), expected_id))

    verification = candidate.get("verification_status")
    if not isinstance(verification, dict):
        errors.append("verification_status must be an object")
    else:
        for field in ("eligibility_status", "test_execution_status",
                      "runtime_verification_status", "behavior_verification_status",
                      "feature_verification_status"):
            if field not in verification:
                errors.append("verification_status missing %s" % field)
        if verification.get("feature_verification_status") != "NOT_VERIFIED":
            errors.append("feature_verification_status must be NOT_VERIFIED")
        if verification.get("runtime_verification_status") != "NOT_VERIFIED":
            errors.append("runtime_verification_status must be NOT_VERIFIED")
        if verification.get("behavior_verification_status") != "NOT_VERIFIED":
            errors.append("behavior_verification_status must be NOT_VERIFIED")
        if verification.get("test_execution_status") != "NOT_RUN":
            errors.append("test_execution_status must be NOT_RUN")

    snapshot = candidate.get("source_snapshot")
    if not isinstance(snapshot, dict) or not snapshot.get("repositories"):
        errors.append("source_snapshot.repositories must be a non-empty list")
    if not isinstance(candidate.get("limitations"), list):
        errors.append("limitations must be a list")

    errors.extend(validate_candidate_evidence(candidate))
    _check_forbidden_keys(candidate, "candidate", errors)

    digest = candidate.get("content_digest")
    if not isinstance(digest, str) or not digest:
        errors.append("content_digest must be a sha256 string")
    elif digest != candidate_content_digest(candidate):
        errors.append("content_digest does not match the draft content")

    if errors:
        raise CandidateValidationError("; ".join(errors))


def validate_against_store(candidate: dict, records: dict[str, dict]) -> list[str]:
    """Cross-check a draft against the live linkage records."""
    problems: list[str] = []
    for ref in candidate.get("evidence_refs") or []:
        link_id = ref.get("linkage_id")
        record = records.get(link_id)
        if record is None:
            problems.append("evidence %s has no linkage record" % link_id)
            continue
        if record.get("linkage_classification") != linkage.DIRECT_EVIDENCE:
            problems.append("evidence %s is no longer DIRECT_EVIDENCE" % link_id)
        if record.get("feature_id") != ref.get("feature_id"):
            problems.append("evidence %s feature_id changed" % link_id)
        digest = _sha256_file(record["__path__"]) if record.get("__path__") else None
        if digest != ref.get("linkage_record_digest"):
            problems.append("evidence %s linkage record digest changed" % link_id)
        source = (record.get("external_analysis") or {}).get("source_digest")
        if source != ref.get("source_digest"):
            problems.append("evidence %s source digest changed" % link_id)
        if eligibility.linkage.is_graph_derived_relation(record):
            problems.append("evidence %s became graph-derived" % link_id)
    for ref in candidate.get("context_refs") or []:
        link_id = ref.get("linkage_id")
        record = records.get(link_id)
        if record is None:
            problems.append("context %s has no linkage record" % link_id)
            continue
        if record.get("linkage_classification") != linkage.INDIRECT_EVIDENCE:
            problems.append("context %s is no longer INDIRECT_EVIDENCE" % link_id)
        if not eligibility.linkage.is_graph_derived_relation(record):
            problems.append("context %s is no longer graph-derived" % link_id)
        if record.get("feature_id") in [seed.get("feature_id")
                                        for seed in candidate.get("evidence_refs") or []]:
            problems.append("context %s targets the candidate feature as a seed feature"
                            % link_id)
    return problems


# --- build ---------------------------------------------------------------------

def _evidence_snapshot(ref: dict) -> dict:
    return {
        "linkage_id": ref["linkage_id"],
        "analysis_id": ref.get("analysis_id"),
        "repository": ref.get("source_repository"),
        "commit_sha": ref.get("source_commit"),
        "source_path": (ref.get("evidence_location") or {}).get("source_path"),
        "source_digest": ref.get("source_digest"),
        "immutable_source_url": ref.get("immutable_source_url"),
        "analysis_record_digest": ref.get("analysis_record_digest"),
        "linkage_record_digest": ref.get("linkage_record_digest"),
    }


def _candidate_status(refs: list[dict]) -> str:
    if not refs:
        return STATUS_BLOCKED
    for ref in refs:
        location = ref.get("evidence_location") or {}
        if ref.get("seed_eligibility") != "QUALIFIED_DIRECT":
            return STATUS_NEEDS_REVIEW
        if ref.get("independence") == "NOT_INDEPENDENT":
            return STATUS_NEEDS_REVIEW
        if location.get("location_integrity") != eligibility.LOCATION_COMPLETE:
            return STATUS_NEEDS_REVIEW
    return STATUS_DRAFT


def _feature_limitations(refs: list[dict], contexts: list[dict]) -> list[str]:
    limitations = [
        "a candidate draft is evidence grouping, not Feature verification, "
        "admission, promotion or similarity",
        "every referenced evidence keeps its original linkage record as the source of truth",
    ]
    if len(refs) > 1:
        limitations.append(
            "%d evidences are kept as separate sources and are not merged into one "
            "implementation" % len(refs))
    for ref in refs:
        if ref.get("seed_eligibility") == "QUALIFIED_DIRECT_WITH_LIMITATIONS":
            limitations.append(
                "evidence %s is restricted: %s"
                % (ref["linkage_id"], ref.get("qualification_reason", "")))
        if ref.get("independence") == "NOT_INDEPENDENT":
            limitations.append(
                "evidence %s is NOT_INDEPENDENT: %s"
                % (ref["linkage_id"], ref.get("independence_reason", "")))
        location = ref.get("evidence_location") or {}
        if location.get("location_integrity") != eligibility.LOCATION_COMPLETE:
            limitations.append(
                "evidence %s has location_integrity=%s; source line lookup is disabled "
                "for at least one item" % (ref["linkage_id"],
                                           location.get("location_integrity")))
    for context in contexts:
        limitations.append(
            "context %s is graph-derived for %s and is not implementation evidence"
            % (context["linkage_id"], context.get("feature_id")))
    return limitations


def build_candidate(feature_id: str, policy: dict, records: dict[str, dict], *,
                    workspace_id: str, now: str | None = None) -> dict:
    """Assemble one draft for a Feature from the reviewed policy."""
    timestamp = now or _now()
    refs: list[dict] = []
    excluded: list[dict] = []
    for entry in eligibility.seed_entries(policy, feature_id):
        record = records.get(entry["linkage_id"])
        if record is None:
            excluded.append({"linkage_id": entry["linkage_id"],
                             "feature_id": feature_id,
                             "codes": ["LINKAGE_NOT_FOUND"],
                             "reason": "reviewed seed has no linkage record"})
            continue
        evaluation = eligibility.evaluate_seed_eligibility(record, policy)
        if not evaluation["eligible"]:
            excluded.append({"linkage_id": entry["linkage_id"],
                             "feature_id": feature_id,
                             "codes": evaluation["codes"],
                             "reason": evaluation["reason"]})
            continue
        refs.append(eligibility.build_evidence_reference(record, policy))

    contexts: list[dict] = []
    for entry in eligibility.context_entries(policy, feature_id):
        record = records.get(entry["linkage_id"])
        if record is None:
            excluded.append({"linkage_id": entry["linkage_id"],
                             "feature_id": entry.get("feature_id"),
                             "codes": ["LINKAGE_NOT_FOUND"],
                             "reason": "reviewed context relation has no linkage record"})
            continue
        try:
            contexts.append(eligibility.build_context_reference(record, policy))
        except eligibility.EligibilityError as exc:
            excluded.append({"linkage_id": entry["linkage_id"],
                             "feature_id": entry.get("feature_id"),
                             "codes": ["CONTEXT_NOT_SAFE"],
                             "reason": str(exc)})

    refs.sort(key=lambda ref: ref["linkage_id"])
    contexts.sort(key=lambda ref: ref["linkage_id"])

    qualification_counts: dict[str, int] = {}
    integrity_counts: dict[str, int] = {}
    for ref in refs:
        qualification = ref["seed_eligibility"]
        qualification_counts[qualification] = qualification_counts.get(qualification, 0) + 1
        integrity = (ref["evidence_location"] or {}).get("location_integrity")
        integrity_counts[integrity] = integrity_counts.get(integrity, 0) + 1

    status = _candidate_status(refs)
    eligibility_status = ("ELIGIBLE" if refs and status == STATUS_DRAFT
                          else "CONDITIONAL" if refs else "INELIGIBLE")
    verification = dict(VERIFICATION_TEMPLATE)
    verification["eligibility_status"] = eligibility_status

    candidate = {
        "schema": CANDIDATE_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "candidate_id": candidate_identity(feature_id, [ref["linkage_id"] for ref in refs],
                                           policy["policy_version"]),
        "feature_id": feature_id,
        "feature_name": feature_id,
        "candidate_status": status,
        "workspace_id": workspace_id,
        "created_at": timestamp,
        "updated_at": timestamp,
        "policy_version": policy["policy_version"],
        "evidence_refs": refs,
        "context_refs": contexts,
        "excluded_evidence": excluded,
        "eligibility_summary": {
            "seed_count": len(refs),
            "seed_eligibility_counts": qualification_counts,
            "independent_seed_count": sum(1 for ref in refs
                                          if ref["independence"] == "INDEPENDENT"),
            "not_independent_seed_count": sum(1 for ref in refs
                                              if ref["independence"] == "NOT_INDEPENDENT"),
            "location_integrity_counts": integrity_counts,
            "context_count": len(contexts),
            "excluded_count": len(excluded),
            "feature_scope": list(policy.get("feature_scope", [])),
            "excluded_features": sorted(policy.get("excluded_features", {})),
        },
        "verification_status": verification,
        "limitations": _feature_limitations(refs, contexts),
        "source_snapshot": {
            "observed_at": timestamp,
            "policy_version": policy["policy_version"],
            "policy_source": policy.get("review_source"),
            "repositories": [_evidence_snapshot(ref) for ref in refs],
            "context_sources": [
                {"linkage_id": context["linkage_id"],
                 "analysis_id": context.get("analysis_id"),
                 "repository": context.get("source_repository"),
                 "commit_sha": context.get("source_commit"),
                 "source_digest": context.get("source_digest"),
                 "graph_edge_reference": context.get("graph_edge_reference")}
                for context in contexts],
        },
    }
    candidate["content_digest"] = candidate_content_digest(candidate)
    return candidate


def _workspace_payload(policy: dict, candidates: list[dict], now: str) -> dict:
    return {
        "schema": WORKSPACE_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "workspace_id": workspace_identity(policy),
        "policy_version": policy["policy_version"],
        "policy_source": policy.get("review_source"),
        "generated_at": now,
        "candidates": [
            {"candidate_id": candidate["candidate_id"],
             "feature_id": candidate["feature_id"],
             "candidate_status": candidate["candidate_status"],
             "seed_count": candidate["eligibility_summary"]["seed_count"],
             "context_count": candidate["eligibility_summary"]["context_count"],
             "content_digest": candidate["content_digest"]}
            for candidate in candidates],
        "excluded_features": [
            {"feature_id": feature_id, **detail}
            for feature_id, detail in sorted(policy.get("excluded_features", {}).items())],
        "not_in_scope": {
            "graph_derived_seeds": "graph-derived relations are context only",
            "similarity": "not implemented in this stage",
            "admission": "not implemented in this stage",
            "promotion": "not implemented in this stage",
        },
    }


def build_workspace(policy: dict | None = None, *,
                    out_dir: str | Path = WORKSPACE_DIR,
                    linkage_dir: str | Path | None = None,
                    allow_refresh: bool = False,
                    records: dict[str, dict] | None = None,
                    now: str | None = None) -> dict:
    """Build or refresh every in-scope candidate draft."""
    policy_data = policy or eligibility.load_policy()
    timestamp = now or _now()
    directory = Path(out_dir)
    candidate_dir = directory / CANDIDATE_DIRNAME
    if records is None:
        store = linkage.load_linkage_records(linkage_dir) if linkage_dir \
            else linkage.load_linkage_records()
        records = {record.get("linkage_id"): record for record in store
                   if isinstance(record, dict) and record.get("linkage_id")}

    built: list[dict] = []
    unchanged: list[str] = []
    candidates: list[dict] = []
    for feature_id in sorted(policy_data.get("feature_scope", [])):
        candidate = build_candidate(feature_id, policy_data, records,
                                    workspace_id=workspace_identity(policy_data),
                                    now=timestamp)
        validate_candidate_draft(candidate)
        path = candidate_dir / ("%s.json" % candidate["candidate_id"])
        previous = None
        if path.is_file():
            try:
                previous = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                previous = None
        if previous is not None and not allow_refresh:
            for ref in previous.get("evidence_refs") or []:
                current = records.get(ref.get("linkage_id"))
                current_digest = (_sha256_file(current["__path__"])
                                  if current and current.get("__path__") else None)
                if current_digest != ref.get("linkage_record_digest"):
                    raise CandidateError(
                        "candidate %s references %s whose record changed; "
                        "rerun with --allow-refresh after review"
                        % (candidate["candidate_id"], ref.get("linkage_id")))
        if previous is not None and previous.get("content_digest") == \
                candidate["content_digest"] and previous.get("candidate_id") == \
                candidate["candidate_id"]:
            candidate = previous
            unchanged.append(candidate["candidate_id"])
        else:
            if previous is not None and previous.get("created_at"):
                candidate["created_at"] = previous["created_at"]
            _atomic_write(path, json.dumps(candidate, ensure_ascii=False, indent=2) + "\n")
            built.append({"candidate_id": candidate["candidate_id"],
                          "feature_id": feature_id,
                          "path": _relative(path)})
        candidates.append(candidate)

    summary = _workspace_payload(policy_data, candidates, timestamp)
    summary_path = directory / "WORKSPACE.json"
    if summary_path.is_file():
        try:
            previous_summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except ValueError:
            previous_summary = None
        if isinstance(previous_summary, dict) \
                and previous_summary.get("generated_at") \
                and previous_summary.get("candidates") == summary["candidates"] \
                and previous_summary.get("workspace_id") == summary["workspace_id"]:
            summary["generated_at"] = previous_summary["generated_at"]
    _atomic_write(summary_path,
                  json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    return {"workspace": summary, "built": built, "unchanged": unchanged,
            "candidates": candidates, "out_dir": _relative(directory)}


# --- read side -----------------------------------------------------------------

def candidate_paths(out_dir: str | Path = WORKSPACE_DIR) -> list[Path]:
    directory = Path(out_dir) / CANDIDATE_DIRNAME
    return sorted(directory.glob("*.json")) if directory.is_dir() else []


def load_candidates(out_dir: str | Path = WORKSPACE_DIR) -> list[dict]:
    loaded = []
    for path in candidate_paths(out_dir):
        try:
            candidate = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise CandidateError("candidate %s is not valid JSON: %s"
                                 % (_relative(path), exc)) from exc
        candidate["__path__"] = _relative(path)
        loaded.append(candidate)
    return loaded


def find_candidate(out_dir: str | Path = WORKSPACE_DIR, *,
                   candidate_id: str | None = None,
                   feature_id: str | None = None) -> dict:
    matches = [candidate for candidate in load_candidates(out_dir)
               if (candidate_id is None or candidate.get("candidate_id") == candidate_id)
               and (feature_id is None or candidate.get("feature_id") == feature_id)]
    if not matches:
        raise CandidateError("no candidate matches the request")
    if len(matches) > 1:
        raise CandidateError("ambiguous request: %d candidates match"
                             % len(matches))
    return matches[0]


def validate_workspace(out_dir: str | Path = WORKSPACE_DIR, *,
                       policy: dict | None = None,
                       linkage_dir: str | Path | None = None) -> dict:
    policy_data = policy or eligibility.load_policy()
    store = linkage.load_linkage_records(linkage_dir) if linkage_dir \
        else linkage.load_linkage_records()
    records = {record.get("linkage_id"): record for record in store
               if isinstance(record, dict) and record.get("linkage_id")}
    results = []
    for candidate in load_candidates(out_dir):
        problems: list[str] = []
        try:
            validate_candidate_draft(candidate)
        except CandidateValidationError as exc:
            problems.append(str(exc))
        problems.extend(validate_against_store(candidate, records))
        if candidate.get("policy_version") != policy_data["policy_version"]:
            problems.append("candidate policy_version differs from the current policy")
        results.append({"candidate_id": candidate.get("candidate_id"),
                        "feature_id": candidate.get("feature_id"),
                        "status": "VALID" if not problems else "INVALID",
                        "problems": problems})
    return {"validated": len(results), "results": results,
            "policy_version": policy_data["policy_version"]}


def check_candidate_freshness(out_dir: str | Path = WORKSPACE_DIR, *,
                              policy: dict | None = None,
                              linkage_dir: str | Path | None = None) -> dict:
    policy_data = policy or eligibility.load_policy()
    store = linkage.load_linkage_records(linkage_dir) if linkage_dir \
        else linkage.load_linkage_records()
    records = {record.get("linkage_id"): record for record in store
               if isinstance(record, dict) and record.get("linkage_id")}
    results = []
    for candidate in load_candidates(out_dir):
        issues: list[dict] = []
        if candidate.get("policy_version") != policy_data["policy_version"]:
            issues.append({"target": "policy", "status": "POLICY_CHANGED",
                           "reason": "stored %r vs current %r"
                           % (candidate.get("policy_version"),
                              policy_data["policy_version"])})
        for ref in candidate.get("evidence_refs") or []:
            record = records.get(ref.get("linkage_id"))
            if record is None:
                issues.append({"target": ref.get("linkage_id"),
                               "status": "MISSING_LINKAGE",
                               "reason": "referenced linkage record is absent"})
                continue
            digest = _sha256_file(record["__path__"]) if record.get("__path__") else None
            if digest != ref.get("linkage_record_digest"):
                issues.append({"target": ref.get("linkage_id"),
                               "status": "STALE_LINKAGE",
                               "reason": "linkage record content changed"})
            upstream = linkage.evaluate_freshness(record)
            if upstream["status"] != "FRESH":
                issues.append({"target": ref.get("linkage_id"),
                               "status": "STALE_SOURCE",
                               "reason": "; ".join(upstream["reasons"]) or upstream["status"]})
        for ref in candidate.get("context_refs") or []:
            record = records.get(ref.get("linkage_id"))
            if record is None:
                issues.append({"target": ref.get("linkage_id"),
                               "status": "MISSING_LINKAGE",
                               "reason": "referenced context record is absent"})
                continue
            digest = _sha256_file(record["__path__"]) if record.get("__path__") else None
            if digest != ref.get("linkage_record_digest"):
                issues.append({"target": ref.get("linkage_id"),
                               "status": "STALE_LINKAGE",
                               "reason": "context linkage record content changed"})
        status = "FRESH" if not issues else (
            "STALE" if any(issue["status"].startswith("STALE") for issue in issues)
            else "INCOMPLETE")
        results.append({"candidate_id": candidate.get("candidate_id"),
                        "feature_id": candidate.get("feature_id"),
                        "status": status, "issues": issues})
    counts = {"FRESH": 0, "STALE": 0, "INCOMPLETE": 0}
    for result in results:
        counts[result["status"]] += 1
    return {"checked": len(results), "status_counts": counts, "results": results}


# --- report formatting ---------------------------------------------------------

def print_build(result: dict) -> None:
    print("workspace: %s (%s)" % (result["workspace"]["workspace_id"],
                                  result["out_dir"]))
    print("policy: %s" % result["workspace"]["policy_version"])
    for candidate in result["candidates"]:
        print("CANDIDATE | %s | %s | %s | seeds=%d contexts=%d"
              % (candidate["candidate_id"], candidate["feature_id"],
                 candidate["candidate_status"],
                 candidate["eligibility_summary"]["seed_count"],
                 candidate["eligibility_summary"]["context_count"]))
    print("built: %d, unchanged: %d" % (len(result["built"]), len(result["unchanged"])))
    for detail in result["workspace"]["excluded_features"]:
        print("EXCLUDED | %s | %s" % (detail["feature_id"], detail["code"]
                                      if "code" in detail else detail["reason_code"]))


def print_list(out_dir: str | Path = WORKSPACE_DIR) -> None:
    for candidate in load_candidates(out_dir):
        print("%s | %s | %s | seeds=%d | independence=%s"
              % (candidate["candidate_id"], candidate["feature_id"],
                 candidate["candidate_status"],
                 candidate["eligibility_summary"]["seed_count"],
                 ",".join(sorted({ref["independence"]
                                  for ref in candidate["evidence_refs"]})) or "-"))
        for ref in candidate["evidence_refs"]:
            location = ref["evidence_location"]
            print("    SEED    %s | %s | %s | %s | record_line=%s commit_line=%s (%s)"
                  % (ref["linkage_id"], ref["seed_eligibility"], ref["independence"],
                     ref["source_repository"], location["record_line"],
                     location["commit_line"], location["location_integrity"]))
        for ref in candidate["context_refs"]:
            print("    CONTEXT %s | %s | %s | target=%s | counts_as_seed=False"
                  % (ref["linkage_id"], ref["context_kind"], ref["derivation_type"],
                     ref["feature_id"]))
        for excluded in candidate["excluded_evidence"]:
            print("    EXCLUDED %s | %s" % (excluded["linkage_id"],
                                            ",".join(excluded["codes"])))


def print_candidate(candidate: dict) -> None:
    print(json.dumps(candidate, ensure_ascii=False, indent=2))


def print_validation(result: dict) -> None:
    for item in result["results"]:
        print("%s | %s | %s" % (item["candidate_id"], item["feature_id"], item["status"]))
        for problem in item["problems"]:
            print("    %s" % problem)
    print("validated: %d, policy: %s" % (result["validated"], result["policy_version"]))


def print_freshness(result: dict) -> None:
    for item in result["results"]:
        print("%s | %s | %s" % (item["candidate_id"], item["feature_id"], item["status"]))
        for issue in item["issues"]:
            print("    %s | %s | %s" % (issue["target"], issue["status"], issue["reason"]))
    print("checked: %d | %s" % (result["checked"], result["status_counts"]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Restricted Candidate Workspace (Phase 1.74 Batch C)")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "list", "show", "validate", "check-freshness"):
        command = sub.add_parser(name)
        command.add_argument("--out", default=str(WORKSPACE_DIR))
        command.add_argument("--policy", default=str(eligibility.POLICY_PATH))
        command.add_argument("--json", action="store_true")
        if name == "build":
            command.add_argument("--allow-refresh", action="store_true")
        if name == "show":
            command.add_argument("--candidate")
            command.add_argument("--feature")
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            policy = eligibility.load_policy(args.policy)
            result = build_workspace(policy, out_dir=args.out,
                                     allow_refresh=args.allow_refresh)
            if args.json:
                print(json.dumps({"workspace": result["workspace"],
                                  "built": result["built"],
                                  "unchanged": result["unchanged"]},
                                 ensure_ascii=False, indent=2))
            else:
                print_build(result)
            return 0
        if args.command == "list":
            if args.json:
                print(json.dumps(load_candidates(args.out), ensure_ascii=False, indent=2))
            else:
                print_list(args.out)
            return 0
        if args.command == "show":
            candidate = find_candidate(args.out, candidate_id=args.candidate,
                                       feature_id=args.feature)
            print_candidate(candidate)
            return 0
        if args.command == "validate":
            result = validate_workspace(args.out, policy=eligibility.load_policy(args.policy))
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print_validation(result)
            return 0 if all(item["status"] == "VALID" for item in result["results"]) else 1
        result = check_candidate_freshness(args.out,
                                           policy=eligibility.load_policy(args.policy))
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_freshness(result)
        return 0 if result["status_counts"]["FRESH"] == result["checked"] else 1
    except (CandidateError, eligibility.EligibilityError) as exc:
        print("FAIL: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
