"""Typed Behavior Knowledge Store（Phase 1.65）。

这是 Phase 1.64 `knowledge/behavior_verification/store.py` 的**扩展**，不是平行数据库：

- 复用它的 `SOURCE_TYPES` 语义与「历史不覆盖」纪律（这里用 `lifecycle_events` + 独立记录文件实现）。
- 1.64 的 7 条汇总记录保持原样，不迁移、不改写；本模块只新增**按知识类型**的记录层。
- 目录仍在同一个知识根下：`.ai/knowledge/behavior_learning/`。

生命周期：`PENDING_REVIEW → APPROVED → SUPERSEDED / REVOKED / ARCHIVED`。
硬规则：

1. 自动生成的知识一律 `PENDING_REVIEW`，`approve()` 必须带 reviewer + reason。
2. 来源门禁按类型强制（见 `REQUIRED_REFERENCE_KINDS`）；`MUTATION_OBSERVATION` 只接受
   `MUTANT_KILLED`，`INVALID_MUTANT` 一律拒绝。
3. 冲突保留双方，不自动选最新；有未解决冲突时拒绝审批。
4. 撤销/归档不删除文件；被撤销的 id 不能重新审批。
5. `INFERENCE` 必须带 `derivations`（指向已存在的 knowledge_id），且不能标 `VERIFIED`。
"""

from __future__ import annotations

import hashlib
import json
import os
import time

import paths

BASE = os.path.join(paths.ROOT, ".ai", "knowledge", "behavior_learning")
RECORDS = os.path.join(BASE, "records")
CANDIDATES = os.path.join(BASE, "candidates")
CONFLICTS = os.path.join(BASE, "conflicts")

SCHEMA = "behavior_learning_knowledge"
SCHEMA_VERSION = 1

KNOWLEDGE_TYPES = ("CONTRACT_FACT", "SOURCE_OBSERVATION", "TEST_OBSERVATION",
                   "RUNTIME_OBSERVATION", "MUTATION_OBSERVATION", "FAILURE_KNOWLEDGE",
                   "DEPENDENCY_KNOWLEDGE", "SCENARIO_OBSERVATION",
                   "EXECUTION_OBSERVATION", "BEHAVIOR_OBSERVATION",
                   "TEST_DESIGN_KNOWLEDGE", "INFERENCE", "UNKNOWN")

CONFIDENCE_LEVELS = ("VERIFIED", "HIGH", "MEDIUM", "LOW", "UNKNOWN")

STATUSES = ("PENDING_REVIEW", "APPROVED", "SUPERSEDED", "REVOKED", "ARCHIVED")

REQUIRED_REFERENCE_KINDS = {
    "CONTRACT_FACT": ("CONTRACT_REFERENCE",),
    "SOURCE_OBSERVATION": ("SOURCE_REFERENCE",),
    "TEST_OBSERVATION": ("EVIDENCE_REFERENCE",),
    "RUNTIME_OBSERVATION": ("ATTESTATION_REFERENCE",),
    "MUTATION_OBSERVATION": ("MUTATION_REFERENCE",),
    "FAILURE_KNOWLEDGE": ("MUTATION_REFERENCE", "TEST_REFERENCE", "EVIDENCE_REFERENCE"),
    "DEPENDENCY_KNOWLEDGE": ("SOURCE_REFERENCE", "CONTRACT_REFERENCE"),
    # Phase 1.66：执行结果回流。场景/执行/行为观察都必须带真实 Run；
    # 「可信执行」额外要 Attestation，测试设计错误允许用 TEST_REFERENCE。
    "SCENARIO_OBSERVATION": ("EVIDENCE_REFERENCE",),
    "EXECUTION_OBSERVATION": ("EVIDENCE_REFERENCE", "ATTESTATION_REFERENCE"),
    "BEHAVIOR_OBSERVATION": ("EVIDENCE_REFERENCE",),
    "TEST_DESIGN_KNOWLEDGE": ("EVIDENCE_REFERENCE", "TEST_REFERENCE"),
    "INFERENCE": (),
    "UNKNOWN": (),
}


class KnowledgeError(ValueError):
    """记录不合法、来源不足、状态不允许。"""


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _path_for(status: str, knowledge_id: str) -> str:
    directory = RECORDS if status != "PENDING_REVIEW" else CANDIDATES
    return os.path.join(directory, "%s.json" % knowledge_id)


def _write(path: str, record: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _read(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def all_records() -> list[dict]:
    records = []
    for directory in (RECORDS, CANDIDATES):
        if not os.path.isdir(directory):
            continue
        for name in sorted(os.listdir(directory)):
            if name.endswith(".json"):
                records.append(_read(os.path.join(directory, name)))
    return records


def get(knowledge_id: str) -> dict | None:
    for directory in (RECORDS, CANDIDATES):
        path = os.path.join(directory, "%s.json" % knowledge_id)
        if os.path.isfile(path):
            return _read(path)
    return None


def _file_digest(reference: str) -> str | None:
    path = reference.split("#")[0]
    head, _, tail = path.rpartition(":")
    if head and tail.isdigit():
        path = head
    path = os.path.join(paths.ROOT, path)
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def validate(record: dict) -> list[str]:
    problems: list[str] = []
    for field in ("feature_id", "behavior_id", "behavior_category", "knowledge_type",
                  "key", "content", "source_references", "contract_version",
                  "confidence", "verification_status"):
        if field not in record:
            problems.append("missing field: %s" % field)
    if record.get("knowledge_type") not in KNOWLEDGE_TYPES:
        problems.append("knowledge_type invalid: %r" % record.get("knowledge_type"))
    if record.get("confidence") not in CONFIDENCE_LEVELS:
        problems.append("confidence invalid: %r" % record.get("confidence"))
    if record.get("verification_status") not in STATUSES:
        problems.append("verification_status invalid: %r" % record.get("verification_status"))
    if not str(record.get("contract_version") or "").strip():
        problems.append("contract_version empty")
    references = record.get("source_references")
    if not isinstance(references, list) or not references:
        problems.append("source_references must be a non-empty list")
        references = []
    for index, reference in enumerate(references):
        if not isinstance(reference, dict):
            problems.append("source_references[%d] not an object" % index)
            continue
        if not str(reference.get("kind") or ""):
            problems.append("source_references[%d].kind empty" % index)
        if not str(reference.get("reference") or ""):
            problems.append("source_references[%d].reference empty" % index)

    kinds = {str(reference.get("kind")) for reference in references if isinstance(reference, dict)}
    required = REQUIRED_REFERENCE_KINDS.get(str(record.get("knowledge_type")), ())
    if required and not (kinds & set(required)):
        problems.append("%s requires one of %s" % (record.get("knowledge_type"), required))

    if record.get("knowledge_type") == "CONTRACT_FACT":
        if not any(str(reference.get("reference", "")).startswith("Features/")
                   for reference in references):
            problems.append("CONTRACT_FACT must reference Features/")
    if record.get("knowledge_type") == "SOURCE_OBSERVATION":
        for reference in references:
            if reference.get("kind") != "SOURCE_REFERENCE":
                continue
            expected = reference.get("digest")
            actual = _file_digest(str(reference.get("reference")))
            if actual is None:
                problems.append("SOURCE_OBSERVATION reference file missing: %s"
                                % reference.get("reference"))
            elif expected and expected != actual:
                problems.append("SOURCE_OBSERVATION digest mismatch for %s"
                                % reference.get("reference"))
    if record.get("knowledge_type") == "MUTATION_OBSERVATION":
        verdict = str(record.get("mutation_verdict") or "")
        if verdict != "MUTANT_KILLED":
            problems.append("MUTATION_OBSERVATION requires MUTANT_KILLED (got %r)" % verdict)
        if not str(record.get("run_id") or "").strip():
            problems.append("MUTATION_OBSERVATION requires run_id")
    if record.get("knowledge_type") in ("TEST_OBSERVATION", "RUNTIME_OBSERVATION",
                                        "SCENARIO_OBSERVATION", "EXECUTION_OBSERVATION",
                                        "BEHAVIOR_OBSERVATION"):
        if not str(record.get("run_id") or "").strip():
            problems.append("%s requires run_id" % record.get("knowledge_type"))
    if record.get("knowledge_type") == "EXECUTION_OBSERVATION":
        # 「可信执行」：Attestation 缺席就不能入库成执行事实（仍可存 TEST_OBSERVATION）
        if not any(reference.get("kind") == "ATTESTATION_REFERENCE"
                   for reference in references if isinstance(reference, dict)):
            problems.append("EXECUTION_OBSERVATION requires ATTESTATION_REFERENCE")
    for reference in references:
        if not isinstance(reference, dict):
            continue
        if reference.get("kind") not in ("EVIDENCE_REFERENCE", "ATTESTATION_REFERENCE",
                                         "TEST_REFERENCE"):
            continue
        target = str(reference.get("reference") or "")
        if not (target.startswith(".ai/") or target.startswith("Features/")):
            continue
        actual = _file_digest(target)
        expected = reference.get("digest")
        if actual is None:
            problems.append("%s reference file missing: %s"
                            % (record.get("knowledge_type"), target))
        elif expected and expected != actual:
            problems.append("%s digest mismatch for %s"
                            % (record.get("knowledge_type"), target))
    if record.get("knowledge_type") == "INFERENCE":
        derivations = record.get("derivations")
        if not isinstance(derivations, list) or not derivations:
            problems.append("INFERENCE requires derivations")
        else:
            for knowledge_id in derivations:
                if get(str(knowledge_id)) is None:
                    problems.append("INFERENCE derivation missing: %s" % knowledge_id)
        if record.get("confidence") == "VERIFIED":
            problems.append("INFERENCE cannot be VERIFIED")
    if record.get("knowledge_type") == "UNKNOWN" and not str(record.get("reason") or "").strip():
        problems.append("UNKNOWN requires reason")
    return problems


def make_record(*, feature_id: str, behavior_id: str, knowledge_type: str, key: str,
                content, source_references: list[dict], contract_version: str,
                confidence: str, implementation_digest: str = "", evidence_digest: str = "",
                run_id: str = "", mutation_verdict: str = "", derivations: list[str] | None = None,
                unresolved_questions: list[str] | None = None, reason: str = "",
                supersedes: str = "") -> dict:
    record = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "feature_id": feature_id,
        "behavior_id": behavior_id,
        "behavior_category": paths.category_of(feature_id, behavior_id),
        "knowledge_type": knowledge_type,
        "key": key,
        "content": content,
        "content_digest": _digest(content),
        "source_references": source_references,
        "contract_version": contract_version,
        "implementation_digest": implementation_digest,
        "evidence_digest": evidence_digest,
        "run_id": run_id,
        "mutation_verdict": mutation_verdict,
        "derivations": derivations or [],
        "confidence": confidence,
        "verification_status": "PENDING_REVIEW",
        "created_at": _now(),
        "updated_at": _now(),
        "supersedes": supersedes,
        "superseded_by": "",
        "unresolved_questions": unresolved_questions or [],
        "reason": reason,
        "review": None,
        "conflict_ids": [],
        "lifecycle_events": [{"at": _now(), "event": "CREATE",
                              "detail": "generated by learning pipeline"}],
    }
    record["knowledge_id"] = "k-" + _digest({k: record[k] for k in
                                             ("feature_id", "behavior_id", "knowledge_type",
                                              "key", "content_digest")})[:16]
    return record


def _same_slot(record: dict, other: dict) -> bool:
    return (record["feature_id"] == other["feature_id"]
            and record["behavior_id"] == other["behavior_id"]
            and record["knowledge_type"] == other["knowledge_type"]
            and record["key"] == other["key"])


def add_candidate(record: dict) -> dict:
    """写入候选区。重复内容直接返回既有记录；同槽不同内容 → 建冲突并保持待审。"""
    problems = validate(record)
    if problems:
        raise KnowledgeError("invalid knowledge record: %s" % "; ".join(problems))
    existing = get(record["knowledge_id"])
    if existing is not None:
        return existing
    for other in all_records():
        if not _same_slot(record, other):
            continue
        if other["content_digest"] == record["content_digest"]:
            return other
        if other["verification_status"] in ("APPROVED", "PENDING_REVIEW"):
            conflict = _record_conflict(record, other)
            record["conflict_ids"].append(conflict["conflict_id"])
    _write(_path_for("PENDING_REVIEW", record["knowledge_id"]), record)
    return record


def _record_conflict(new: dict, old: dict) -> dict:
    conflict_id = "c-" + _digest({"new": new["knowledge_id"], "old": old["knowledge_id"]})[:16]
    path = os.path.join(CONFLICTS, "%s.json" % conflict_id)
    if os.path.isfile(path):
        return _read(path)
    conflict = {
        "schema": "behavior_learning_conflict",
        "schema_version": SCHEMA_VERSION,
        "conflict_id": conflict_id,
        "feature_id": new["feature_id"],
        "behavior_id": new["behavior_id"],
        "knowledge_type": new["knowledge_type"],
        "key": new["key"],
        "parties": [
            {"knowledge_id": old["knowledge_id"], "content": old["content"],
             "content_digest": old["content_digest"],
             "verification_status": old["verification_status"],
             "source_references": old["source_references"]},
            {"knowledge_id": new["knowledge_id"], "content": new["content"],
             "content_digest": new["content_digest"],
             "verification_status": new["verification_status"],
             "source_references": new["source_references"]},
        ],
        "detected_at": _now(),
        "status": "OPEN",
        "resolution": "",
        "note": "双方都保留；不自动选择最新记录作为正确答案",
    }
    _write(path, conflict)
    return conflict


def conflicts(status: str = "") -> list[dict]:
    if not os.path.isdir(CONFLICTS):
        return []
    items = [_read(os.path.join(CONFLICTS, name))
             for name in sorted(os.listdir(CONFLICTS)) if name.endswith(".json")]
    return [item for item in items if not status or item["status"] == status]


def resolve_conflict(conflict_id: str, *, resolution: str, reviewer: str) -> dict:
    path = os.path.join(CONFLICTS, "%s.json" % conflict_id)
    if not os.path.isfile(path):
        raise KnowledgeError("unknown conflict: %s" % conflict_id)
    conflict = _read(path)
    if conflict["status"] != "OPEN":
        raise KnowledgeError("conflict %s already %s" % (conflict_id, conflict["status"]))
    if not resolution.strip() or not reviewer.strip():
        raise KnowledgeError("resolution and reviewer are required")
    conflict["status"] = "RESOLVED"
    conflict["resolution"] = resolution
    conflict["resolved_by"] = reviewer
    conflict["resolved_at"] = _now()
    _write(path, conflict)
    return conflict


def approve(knowledge_id: str, *, reviewer: str, reason: str) -> dict:
    record = get(knowledge_id)
    if record is None:
        raise KnowledgeError("unknown knowledge: %s" % knowledge_id)
    if record["verification_status"] in ("REVOKED", "ARCHIVED"):
        raise KnowledgeError("cannot approve %s record %s" % (record["verification_status"],
                                                             knowledge_id))
    if record["verification_status"] == "APPROVED":
        return record
    if not reviewer.strip() or not reason.strip():
        raise KnowledgeError("reviewer and reason are required")
    open_conflicts = [item for item in conflicts("OPEN")
                      if knowledge_id in {party["knowledge_id"] for party in item["parties"]}]
    if open_conflicts:
        raise KnowledgeError("unresolved conflict blocks approval: %s"
                             % ", ".join(item["conflict_id"] for item in open_conflicts))
    problems = validate(record)
    if problems:
        raise KnowledgeError("invalid knowledge record: %s" % "; ".join(problems))

    previous = [other for other in all_records()
                if other["verification_status"] == "APPROVED" and _same_slot(record, other)]
    for old in previous:
        old["verification_status"] = "SUPERSEDED"
        old["superseded_by"] = knowledge_id
        old["updated_at"] = _now()
        old["lifecycle_events"].append({"at": _now(), "event": "SUPERSEDE",
                                        "detail": "superseded by %s" % knowledge_id})
        _write(_path_for("APPROVED", old["knowledge_id"]), old)
        record["supersedes"] = old["knowledge_id"]

    record["verification_status"] = "APPROVED"
    record["review"] = {"reviewer": reviewer, "reason": reason, "at": _now(),
                        "scope": "LOCAL_REVIEW",
                        "note": "本地审批，不代表人类审批者身份已验证"}
    record["updated_at"] = _now()
    record["lifecycle_events"].append({"at": _now(), "event": "APPROVE",
                                       "detail": reason})
    _write(_path_for("APPROVED", knowledge_id), record)
    candidate_path = _path_for("PENDING_REVIEW", knowledge_id)
    if os.path.isfile(candidate_path):
        os.remove(candidate_path)
    return record


def revoke(knowledge_id: str, *, reviewer: str, reason: str) -> dict:
    record = get(knowledge_id)
    if record is None:
        raise KnowledgeError("unknown knowledge: %s" % knowledge_id)
    if not reviewer.strip() or not reason.strip():
        raise KnowledgeError("reviewer and reason are required")
    record["verification_status"] = "REVOKED"
    record["updated_at"] = _now()
    record["lifecycle_events"].append({"at": _now(), "event": "REVOKE",
                                       "detail": "%s: %s" % (reviewer, reason)})
    _write(_path_for("REVOKED", knowledge_id), record)
    for directory in (CANDIDATES, RECORDS):
        path = os.path.join(directory, "%s.json" % knowledge_id)
        if os.path.isfile(path) and directory != RECORDS:
            os.remove(path)
    return record


def archive(knowledge_id: str, *, reviewer: str, reason: str) -> dict:
    record = get(knowledge_id)
    if record is None:
        raise KnowledgeError("unknown knowledge: %s" % knowledge_id)
    record["verification_status"] = "ARCHIVED"
    record["updated_at"] = _now()
    record["lifecycle_events"].append({"at": _now(), "event": "ARCHIVE",
                                       "detail": "%s: %s" % (reviewer, reason)})
    _write(_path_for("ARCHIVED", knowledge_id), record)
    return record


def revive(knowledge_id: str, *, reviewer: str, reason: str,
           source_references: list[dict] | None = None, run_id: str = "") -> dict:
    """把已归档/已替代的记录重新放回候选区（不改内容，不自动批准）。

    场景：同一内容的新观察在 add_candidate 里会命中已归档的同槽记录，
    此时不能把归档记录当作「本次写入」——要么重开，要么拒绝。本函数选择重开，
    保留完整 lifecycle（ARCHIVE 之后追加 REOPEN），审批仍需显式 approve。
    """
    record = get(knowledge_id)
    if record is None:
        raise KnowledgeError("unknown knowledge: %s" % knowledge_id)
    if record["verification_status"] not in ("ARCHIVED", "SUPERSEDED", "PENDING_REVIEW"):
        raise KnowledgeError("cannot revive %s record %s"
                             % (record["verification_status"], knowledge_id))
    if not reviewer.strip() or not reason.strip():
        raise KnowledgeError("reviewer and reason are required")
    previous_status = record["verification_status"]
    if previous_status == "PENDING_REVIEW":
        # 已在候选区，只是同一结论的新一次观察换了证据文件：只刷新引用。
        if source_references and source_references != record["source_references"]:
            record["lifecycle_events"].append(
                {"at": _now(), "event": "REFRESH_REFERENCES",
                 "detail": "%s: %d -> %d reference(s); run %s -> %s"
                           % (reviewer, len(record["source_references"]),
                              len(source_references), record.get("run_id") or "-",
                              run_id or "-")})
            record["source_references"] = source_references
            record["run_id"] = run_id
            record["updated_at"] = _now()
            _write(_path_for("PENDING_REVIEW", knowledge_id), record)
        return record
    if source_references and source_references != record["source_references"]:
        # 结论相同但证据文件换了（旧 Run 已被清理）：刷新引用，并在历史里留痕，
        # 不能带着指向已消失文件的引用复活。
        record["lifecycle_events"].append(
            {"at": _now(), "event": "REFRESH_REFERENCES",
             "detail": "%s: %d -> %d reference(s); run %s -> %s"
                       % (reviewer, len(record["source_references"]),
                          len(source_references), record.get("run_id") or "-", run_id or "-")})
        record["source_references"] = source_references
        record["run_id"] = run_id
        record["evidence_digest"] = _digest(source_references)
    record["verification_status"] = "PENDING_REVIEW"
    record["superseded_by"] = ""
    record["updated_at"] = _now()
    record["lifecycle_events"].append(
        {"at": _now(), "event": "REOPEN", "from": previous_status,
         "detail": "%s: %s" % (reviewer, reason)})
    _write(_path_for("PENDING_REVIEW", knowledge_id), record)
    for status in ("ARCHIVED", "RECORDS"):
        path = _path_for(status, knowledge_id) if status == "ARCHIVED" else \
            os.path.join(RECORDS, "%s.json" % knowledge_id)
        if os.path.isfile(path):
            os.remove(path)
    return record


def staleness(record: dict, *, current_contract_version: str = "",
              current_implementation_digest: str = "") -> list[str]:
    """返回过期原因；空列表表示未发现过期。"""
    reasons = []
    if current_contract_version and record.get("contract_version") != current_contract_version:
        reasons.append("contract_version %r != current %r"
                       % (record.get("contract_version"), current_contract_version))
    if current_implementation_digest and record.get("implementation_digest") \
            and record["implementation_digest"] != current_implementation_digest:
        reasons.append("implementation_digest changed")
    return reasons


def summary() -> dict:
    records = all_records()
    by_type: dict[str, int] = {}
    by_status: dict[str, int] = {}
    by_confidence: dict[str, int] = {}
    for record in records:
        by_type[record["knowledge_type"]] = by_type.get(record["knowledge_type"], 0) + 1
        by_status[record["verification_status"]] = \
            by_status.get(record["verification_status"], 0) + 1
        by_confidence[record["confidence"]] = by_confidence.get(record["confidence"], 0) + 1
    return {
        "records": len(records),
        "by_type": by_type,
        "by_status": by_status,
        "by_confidence": by_confidence,
        "conflicts_open": len(conflicts("OPEN")),
        "conflicts_total": len(conflicts()),
        "behaviors_with_knowledge": len({(r["feature_id"], r["behavior_id"]) for r in records}),
    }
