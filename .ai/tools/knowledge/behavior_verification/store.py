"""Behavior Verification Knowledge Store（Phase 1.64）。

目的：把「一个 Behavior 被验证过什么、结论从哪来」记成**可追溯、可累积**的结构化知识，
为 Phase 1.65 Learning Engine 提供数据。这里是**存储与校验**，不做推理、不自动改结论。

硬规则（都由本模块强制）：

1. **每条事实必须带来源类型**：`CONTRACT_FACT` / `SOURCE_OBSERVATION` /
   `TEST_OBSERVATION` / `MUTATION_OBSERVATION` / `INFERENCE` / `UNKNOWN`。
   未知来源类型直接拒绝——推测不能伪装成已验证事实。
2. **历史不覆盖**：每次写入把旧记录整条追加到 `<feature>__<behavior>.history.jsonl`，
   当前文件只保留最新；历史事实因此永远可回溯。
3. **契约版本绑定**：记录里带 `contract_version`；契约变化后旧记录不会被静默升级
   （校验时比对，不一致就要求重新验证，而不是改个数字）。
4. **只记录真实产物引用**：evidence / mutation / run 引用由调用方给出，store 不生成
   任何虚构 ID 或摘要。

目录结构：

    .ai/knowledge/behavior_verification/<feature>/<behavior>.json          # 最新
    .ai/knowledge/behavior_verification/<feature>/<behavior>.history.jsonl # 历史版本
"""

from __future__ import annotations

import json
import os
import time

def _project_root() -> str:
    """向上找含 project.godot 的目录（不靠层数硬算）。"""
    current = os.path.dirname(os.path.abspath(__file__))
    while True:
        if os.path.isfile(os.path.join(current, "project.godot")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return os.getcwd()
        current = parent


ROOT = _project_root()
DEFAULT_ROOT = os.path.join(ROOT, ".ai", "knowledge", "behavior_verification")

SCHEMA = "behavior_verification_knowledge"
SCHEMA_VERSION = 1

SOURCE_TYPES = ("CONTRACT_FACT", "SOURCE_OBSERVATION", "TEST_OBSERVATION",
                "MUTATION_OBSERVATION", "INFERENCE", "UNKNOWN")

# updated_at 由 save() 统一写入，不由调用方提供（validate 不要求它）
REQUIRED_FIELDS = (
    "feature_id", "behavior_id", "contract_version", "behavior_category",
    "implementation_references", "dependency_references", "facts",
    "last_verified_run_id",
)


class KnowledgeError(ValueError):
    """记录不合法（缺来源、非法来源类型、契约版本为空等）。"""


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def record_path(feature_id: str, behavior_id: str, root: str = "") -> str:
    base = root or DEFAULT_ROOT
    return os.path.join(base, feature_id, "%s.json" % behavior_id)


def history_path(feature_id: str, behavior_id: str, root: str = "") -> str:
    base = root or DEFAULT_ROOT
    return os.path.join(base, feature_id, "%s.history.jsonl" % behavior_id)


def validate(record: dict) -> list[str]:
    """返回问题列表；空列表表示合法。"""
    problems: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in record:
            problems.append("missing field: %s" % field)
    if not str(record.get("feature_id") or "").strip():
        problems.append("feature_id empty")
    if not str(record.get("behavior_id") or "").strip():
        problems.append("behavior_id empty")
    if not str(record.get("contract_version") or "").strip():
        problems.append("contract_version empty")
    category = str(record.get("behavior_category") or "")
    if not category:
        problems.append("behavior_category empty")
    elif category not in ("A", "B", "C", "D", "E", "F"):
        problems.append("behavior_category not in A..F: %r" % category)
    for ref_field in ("implementation_references", "dependency_references"):
        value = record.get(ref_field)
        if not isinstance(value, list):
            problems.append("%s must be a list" % ref_field)
    facts = record.get("facts")
    if not isinstance(facts, list) or not facts:
        problems.append("facts must be a non-empty list")
        facts = []
    for index, fact in enumerate(facts):
        if not isinstance(fact, dict):
            problems.append("facts[%d] not an object" % index)
            continue
        if not str(fact.get("claim") or "").strip():
            problems.append("facts[%d].claim empty" % index)
        source = str(fact.get("source_type") or "")
        if source not in SOURCE_TYPES:
            problems.append("facts[%d].source_type invalid: %r" % (index, source))
        if not str(fact.get("source_ref") or "").strip():
            problems.append("facts[%d].source_ref empty" % index)
        if source == "CONTRACT_FACT" and not str(fact.get("source_ref") or "").startswith(
                ("Features/", "binding:")):
            problems.append("facts[%d] CONTRACT_FACT must reference Features/ or binding:" % index)
    return problems


def load(feature_id: str, behavior_id: str, root: str = "") -> dict | None:
    path = record_path(feature_id, behavior_id, root)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save(record: dict, *, change_reason: str, root: str = "") -> dict:
    """写入最新记录；旧记录（若存在）先追加进 history，绝不覆盖历史。"""
    problems = validate(record)
    if problems:
        raise KnowledgeError("invalid knowledge record: %s" % "; ".join(problems))
    feature_id = str(record["feature_id"])
    behavior_id = str(record["behavior_id"])
    target = record_path(feature_id, behavior_id, root)
    os.makedirs(os.path.dirname(target), exist_ok=True)

    previous = load(feature_id, behavior_id, root)
    if previous is not None:
        if str(previous.get("contract_version")) != str(record.get("contract_version")):
            raise KnowledgeError(
                "contract_version changed for %s/%s (%r -> %r): record a new version "
                "explicitly instead of silently upgrading"
                % (feature_id, behavior_id, previous.get("contract_version"),
                   record.get("contract_version")))
        if previous.get("facts") and record.get("facts"):
            old = {json.dumps(f, sort_keys=True, ensure_ascii=False)
                   for f in previous["facts"]}
            new = {json.dumps(f, sort_keys=True, ensure_ascii=False)
                   for f in record["facts"]}
            dropped = old - new
            if dropped:
                raise KnowledgeError(
                    "facts would be silently dropped: %d (append instead of rewrite)"
                    % len(dropped))
        with open(history_path(feature_id, behavior_id, root), "a",
                  encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps({"archived_at": _now(),
                                     "change_reason": change_reason,
                                     "record": previous},
                                    ensure_ascii=False, sort_keys=True))
            handle.write("\n")

    document = dict(record)
    document.setdefault("schema", SCHEMA)
    document["schema_version"] = SCHEMA_VERSION
    document["updated_at"] = _now()
    document["change_reason"] = change_reason
    with open(target, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return document


def summary(root: str = "") -> dict:
    """统计：记录数、来源分布、未解决问题数、失败案例数。"""
    base = root or DEFAULT_ROOT
    records = []
    for feature in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        directory = os.path.join(base, feature)
        if not os.path.isdir(directory):
            continue
        for name in sorted(os.listdir(directory)):
            if not name.endswith(".json"):
                continue
            with open(os.path.join(directory, name), encoding="utf-8") as handle:
                records.append(json.load(handle))
    sources: dict[str, int] = {}
    for record in records:
        for fact in record.get("facts") or []:
            key = str(fact.get("source_type"))
            sources[key] = sources.get(key, 0) + 1
    return {
        "records": len(records),
        "source_distribution": sources,
        "with_unresolved_questions": sum(
            1 for r in records if r.get("unresolved_questions")),
        "with_failure_knowledge": sum(1 for r in records if r.get("failure_modes")),
        "confidence": {c: sum(1 for r in records if r.get("confidence") == c)
                       for c in sorted({str(r.get("confidence")) for r in records})},
    }
