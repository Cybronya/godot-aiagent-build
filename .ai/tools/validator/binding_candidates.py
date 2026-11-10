#!/usr/bin/env python3
"""Binding 候选生成与显式审批（Phase 1.63）。

定位：**加法式**扩展 Phase 1.60 的逐行为 Binding 体系：

1. **候选生成（只读契约，绝不猜测）**：对正式支持集合的每个 (Feature, Behavior)
   从 `template.yaml#behavior` 契约逐项复制 expected。契约缺少可评估 expected 时
   产出 `BLOCKED_MISSING_EXPECTED` 占位候选——禁止按名称/测试名/Evidence 实测结果
   反推预期。候选生成器**永不自动批准**。
2. **显式审批流**：`DRAFT → PENDING_REVIEW → APPROVED`（保留 REJECTED /
   SUPERSEDED / REVOKED）。审批时**重新计算**当前契约摘要与候选摘要：
   契约在候选生成后发生变化 → 拒绝审批旧候选。审批记录写入独立登记表
   （`bindings/approval_registry.json`），可选接 Phase 1.61 独立信任根做 Ed25519
   签名（object_type=behavior_binding / scope=approve_binding）。
3. **晋升（promote）**：只有 APPROVED 的候选才允许写入正式绑定库
   `bindings/behavior_bindings.json`；同 (Feature, Behavior) 的旧绑定先被
   SUPERSEDED，不得双活。
4. **门禁状态**：`binding_gate_status()` 输出 NO_BINDING / DRAFT_BINDING /
   PENDING_REVIEW / APPROVED_BINDING / BINDING_REVOKED / CONTRACT_MISMATCH /
   BINDING_INVALID——不改变 Phase 1.58/1.60 的 Evaluation 状态语义，只把
   「为什么不能用于评估」表达得更精确。

信任边界：reviewer 是自报文本；Ed25519 签名证明「审批记录自签名后未被篡改」，
不证明审批者的人类身份（无 CI/KMS）。与 1.61 Baseline 审批同一边界。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
VALIDATOR_DIR = _HERE
_TOOLS = os.path.dirname(_HERE)
PROJECT_ROOT = os.path.dirname(os.path.dirname(_TOOLS))
for _p in (_HERE, os.path.join(_TOOLS, "scene_composer"),
           os.path.join(_TOOLS, "provenance")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import feature_behavior_evidence as fbe          # noqa: E402
import trace_bindings as tb                      # noqa: E402

CANDIDATES_PATH = os.path.join(_HERE, "bindings", "binding_candidates.json")
REGISTRY_PATH = os.path.join(_HERE, "bindings", "approval_registry.json")

CANDIDATE_SCHEMA = "binding_candidates"
CANDIDATE_SCHEMA_VERSION = 1
REGISTRY_SCHEMA = "binding_approval_registry"
REGISTRY_SCHEMA_VERSION = 1
DIGEST_SCHEME = "binding-candidate-digest-v1"

# ---------------------------------------------------------------- 状态词表
DRAFT = "DRAFT"
PENDING_REVIEW = "PENDING_REVIEW"
APPROVED = "APPROVED"
REJECTED = "REJECTED"
SUPERSEDED = "SUPERSEDED"
REVOKED = "REVOKED"
BLOCKED_MISSING_EXPECTED = "BLOCKED_MISSING_EXPECTED"
CANDIDATE_STATUSES = (DRAFT, PENDING_REVIEW, APPROVED, REJECTED, SUPERSEDED,
                      REVOKED, BLOCKED_MISSING_EXPECTED)

# 门禁状态（§3.4）
NO_BINDING = "NO_BINDING"
DRAFT_BINDING = "DRAFT_BINDING"
PENDING_REVIEW_BINDING = "PENDING_REVIEW"
APPROVED_BINDING = "APPROVED_BINDING"
BINDING_REVOKED = "BINDING_REVOKED"
BINDING_INVALID = "BINDING_INVALID"

# 允许的状态转换（显式状态机；终态只能到 REVOKED/SUPERSEDED 之外的原则性出口见 _TRANSITIONS）
_TRANSITIONS = {
    DRAFT: (PENDING_REVIEW, REJECTED),
    PENDING_REVIEW: (APPROVED, REJECTED, DRAFT),
    APPROVED: (REVOKED, SUPERSEDED),
    REJECTED: (DRAFT,),
    REVOKED: (),
    SUPERSEDED: (),
    BLOCKED_MISSING_EXPECTED: (),
}


class BindingCandidateError(ValueError):
    """候选/审批/晋升的前置条件不满足。"""


def now_iso() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- 摘要

def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def candidate_digest(candidate: dict) -> str:
    """候选内容摘要：覆盖一切影响评估结果的字段（不含可变的状态/时间戳）。"""
    core = {key: candidate.get(key) for key in
            ("binding_id", "feature_id", "behavior_id", "contract_version",
             "expected", "expected_source", "source_contract", "source_digest")}
    return hashlib.sha256(_canonical(core).encode("utf-8")).hexdigest()


def contract_digest(feature_id: str, behavior_id: str,
                    features_dir: str = "") -> tuple[str, list, str]:
    """返回 (contract_version, expected, digest)。版本规则与 1.60 绑定一致：
    契约核心内容（除 behavior/run_id 外）规范化 JSON 的 SHA256 前 12 位。"""
    directory = features_dir or os.path.join(PROJECT_ROOT, "Features")
    contracts, _reports = fbe.build_contracts(str(feature_id), directory)
    contract = next((c for c in contracts if str(c["behavior"]) == str(behavior_id)), None)
    if contract is None:
        raise BindingCandidateError(
            "behavior %r is not declared by Features/%s" % (behavior_id, feature_id))
    core = {key: contract[key] for key in contract if key not in ("behavior", "run_id")}
    version = hashlib.sha256(_canonical(core).encode("utf-8")).hexdigest()[:12]
    return version, list(contract.get("expected") or []), _canonical(core)


# ---------------------------------------------------------------- 候选生成

def _new_binding_id(feature_id: str, behavior_id: str, existing_ids: set) -> str:
    base = "BND-%s-%s" % (feature_id.upper()[:10], behavior_id.upper()[:18])
    candidate_id, index = base, 2
    while candidate_id in existing_ids:
        candidate_id = "%s-%d" % (base, index)
        index += 1
    return candidate_id


def build_candidate(feature_id: str, behavior_id: str, features_dir: str = "",
                    binding_id: str = "") -> dict:
    """从契约构造单条候选。契约缺 expected → BLOCKED_MISSING_EXPECTED（不得猜测填充）。"""
    record = {
        "binding_id": binding_id,
        "feature_id": str(feature_id),
        "behavior_id": str(behavior_id),
        "contract_version": "",
        "expected": [],
        "expected_source": "behavior_contract",
        "source_contract": "",
        "source_digest": "",
        "approval_status": DRAFT,
        "generated_at": now_iso(),
        "candidate_digest": "",
    }
    try:
        version, expected, _core = contract_digest(record["feature_id"],
                                                   record["behavior_id"], features_dir)
    except BindingCandidateError as exc:
        record["approval_status"] = BLOCKED_MISSING_EXPECTED
        record["blocked_reason"] = str(exc)
        return record
    if not expected:
        record["approval_status"] = BLOCKED_MISSING_EXPECTED
        record["blocked_reason"] = ("contract declares no evaluable expected; "
                                    "guessing is forbidden (Phase 1.63 §3.2)")
        record["contract_version"] = version
        record["source_contract"] = "Features/%s/template.yaml#behavior" % feature_id
        return record
    record.update({
        "contract_version": version,
        "expected": expected,
        "source_contract": "Features/%s/template.yaml#behavior" % feature_id,
    })
    return record


def load_candidates(path: str = "") -> dict:
    target = path or CANDIDATES_PATH
    if not os.path.isfile(target):
        return {"schema": CANDIDATE_SCHEMA, "schema_version": CANDIDATE_SCHEMA_VERSION,
                "generated_at": "", "candidates": []}
    with open(target, encoding="utf-8") as handle:
        return json.load(handle)


def save_candidates(document: dict, path: str = "") -> None:
    statuses = {str(c.get("approval_status")) for c in document.get("candidates", [])}
    unknown = statuses - set(CANDIDATE_STATUSES)
    if unknown:
        raise BindingCandidateError("unknown candidate statuses: %s" % sorted(unknown))
    target = path or CANDIDATES_PATH
    os.makedirs(os.path.dirname(target), exist_ok=True)
    tmp = target + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(tmp, target)


def generate_candidates(features_dir: str = "", out_path: str = "",
                        existing_bindings: dict | None = None) -> dict:
    """对正式支持集合全量生成/刷新候选（幂等）。

    - 已存在于正式绑定库的 (Feature, Behavior) 不生成新候选（保留既有审批历史）。
    - 既有候选在 binding_id + contract_version + 内容摘要 都未变时保留其审批状态
      与时间线；内容变化则退回 DRAFT（旧审批自然失效）。
    """
    sys.path.insert(0, os.path.join(_TOOLS, "evaluation"))
    import evidence_adapter as adapter                 # noqa: E402  动态支持集
    supported = adapter.supported_set(features_dir)
    official = existing_bindings or tb.load_bindings()
    bound_pairs = {(str(b.get("feature_id")), str(b.get("behavior_id")))
                   for b in official.get("bindings", [])}

    previous = {str(c.get("binding_id")): c
                for c in load_candidates(out_path).get("candidates", [])}
    used_ids = set(previous)
    candidates: list = []
    for feature_id in sorted(supported["features"]):
        for behavior_id in supported["features"][feature_id]:
            if (feature_id, behavior_id) in bound_pairs:
                continue                                    # 已绑定：不动历史
            reused = None
            for old in previous.values():
                if str(old.get("feature_id")) == feature_id and \
                        str(old.get("behavior_id")) == behavior_id and \
                        old.get("approval_status") != BLOCKED_MISSING_EXPECTED:
                    reused = old
                    break
            candidate = build_candidate(feature_id, behavior_id, features_dir,
                                        binding_id=str(reused.get("binding_id") or "")
                                        if reused else "")
            if candidate["approval_status"] == BLOCKED_MISSING_EXPECTED:
                candidates.append(candidate)
                continue
            if reused:
                candidate["binding_id"] = reused["binding_id"]
                if candidate_digest(candidate) == str(reused.get("candidate_digest") or ""):
                    candidate["approval_status"] = str(reused.get("approval_status") or DRAFT)
                    candidate["generated_at"] = str(reused.get("generated_at") or
                                                    candidate["generated_at"])
                else:
                    candidate["approval_status"] = DRAFT    # 内容漂移：审批作废重走
            if not candidate["binding_id"]:
                candidate["binding_id"] = _new_binding_id(
                    feature_id, behavior_id, used_ids)
            used_ids.add(candidate["binding_id"])
            candidate["candidate_digest"] = candidate_digest(candidate)
            candidates.append(candidate)

    document = {
        "schema": CANDIDATE_SCHEMA,
        "schema_version": CANDIDATE_SCHEMA_VERSION,
        "generated_at": now_iso(),
        "support_source": supported["source"],
        "note": ("Phase 1.63 candidates. expected is copied verbatim from the formal "
                 "behavior contract; approval is explicit and separate (never automatic)."),
        "candidates": candidates,
    }
    save_candidates(document, out_path)
    return document


# ---------------------------------------------------------------- 审批登记表

def load_registry(path: str = "") -> dict:
    target = path or REGISTRY_PATH
    if not os.path.isfile(target):
        return {"schema": REGISTRY_SCHEMA, "schema_version": REGISTRY_SCHEMA_VERSION,
                "records": []}
    with open(target, encoding="utf-8") as handle:
        return json.load(handle)


def save_registry(document: dict, path: str = "") -> None:
    target = path or REGISTRY_PATH
    os.makedirs(os.path.dirname(target), exist_ok=True)
    tmp = target + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(tmp, target)


def latest_record(registry: dict, binding_id: str) -> dict | None:
    records = [r for r in registry.get("records", [])
               if str(r.get("binding_id")) == str(binding_id)]
    return records[-1] if records else None


def _transition(candidates: dict, binding_id: str, target_status: str,
                expect_from: tuple = ()) -> dict:
    candidate = next((c for c in candidates.get("candidates", [])
                      if str(c.get("binding_id")) == str(binding_id)), None)
    if candidate is None:
        raise BindingCandidateError("candidate %r not found" % binding_id)
    current = str(candidate.get("approval_status"))
    if expect_from and current not in expect_from:
        raise BindingCandidateError("candidate %s is %s, expected one of %s"
                                    % (binding_id, current, expect_from))
    if target_status not in _TRANSITIONS.get(current, ()):
        raise BindingCandidateError("illegal transition %s -> %s for %s"
                                    % (current, target_status, binding_id))
    if candidate.get("approval_status") == BLOCKED_MISSING_EXPECTED or \
            target_status == APPROVED and candidate.get("approval_status") == \
            BLOCKED_MISSING_EXPECTED:
        raise BindingCandidateError(
            "candidate %s is BLOCKED_MISSING_EXPECTED and can never be approved"
            % binding_id)
    candidate["approval_status"] = target_status
    return candidate


def submit_for_review(candidates: dict, binding_id: str,
                      candidates_path: str = "") -> dict:
    """DRAFT → PENDING_REVIEW。"""
    candidate = _transition(candidates, binding_id, PENDING_REVIEW,
                            expect_from=(DRAFT,))
    save_candidates(candidates, candidates_path)
    return candidate


def approve_candidate(candidates: dict, binding_id: str, *, reviewer: str,
                      approval_reference: str, features_dir: str = "",
                      candidates_path: str = "", registry_path: str = "",
                      key_id: str = "", project_root: str = "",
                      trust_root: str = "") -> dict:
    """PENDING_REVIEW → APPROVED（显式审批；重核契约摘要 + 候选摘要 + 可选签名）。

    - 候选摘要与登记值不一致（候选内容在生成后被改动）→ 拒绝。
    - 当前契约摘要与候选 contract_version 不一致（契约在候选生成后漂移）→ 拒绝。
    - key_id 提供时对审批记录做 Ed25519 签名（1.61 信任根，scope=approve_binding）。
    """
    candidate = _transition(candidates, binding_id, APPROVED,
                            expect_from=(PENDING_REVIEW,))
    if candidate.get("approval_status") == BLOCKED_MISSING_EXPECTED:
        raise BindingCandidateError("blocked candidate can never be approved")
    stored_digest = str(candidate.get("candidate_digest") or "")
    current_digest = candidate_digest(candidate)
    if stored_digest != current_digest:
        candidate["approval_status"] = DRAFT
        save_candidates(candidates, candidates_path)
        raise BindingCandidateError(
            "candidate %s content changed after generation (stored %s != current %s); "
            "approval rejected, candidate reset to DRAFT"
            % (binding_id, stored_digest[:12], current_digest[:12]))
    version, _expected, _core = contract_digest(
        candidate["feature_id"], candidate["behavior_id"], features_dir)
    if version != str(candidate.get("contract_version")):
        candidate["approval_status"] = DRAFT
        save_candidates(candidates, candidates_path)
        raise BindingCandidateError(
            "contract drifted since candidate generation (%s != %s) for %s; "
            "regenerate the candidate first"
            % (version, candidate.get("contract_version"), binding_id))

    record = {
        "binding_id": binding_id,
        "candidate_digest": current_digest,
        "approved_digest": current_digest,
        "approved_contract_version": version,
        "reviewer": str(reviewer),
        "decision": APPROVED,
        "approval_reference": str(approval_reference),
        "approved_at": now_iso(),
    }
    if key_id:
        import provenance.signing as signing
        from provenance.trust_store import TrustStore
        store = TrustStore(project_root=project_root or PROJECT_ROOT,
                           trust_root_path=trust_root or "")
        envelope = signing.sign_object(
            object_type="behavior_binding", object_id=binding_id,
            object_version=version, content_digest=current_digest,
            digest_scheme=DIGEST_SCHEME, key_id=key_id, trust_store=store,
            project_root=project_root or PROJECT_ROOT)
        record["signature_envelope"] = envelope
    registry = load_registry(registry_path)
    registry.setdefault("records", []).append(record)
    save_registry(registry, registry_path)
    save_candidates(candidates, candidates_path)
    return record


def set_binding_lifecycle(binding_id: str, status: str, *, reason: str = "",
                          registry_path: str = "") -> dict:
    """APPROVED → REVOKED / SUPERSEDED（终态；不删除记录，只追加）。"""
    if status not in (REVOKED, SUPERSEDED, REJECTED):
        raise BindingCandidateError("lifecycle transition supports %s only"
                                    % ((REVOKED, SUPERSEDED, REJECTED),))
    record = {"binding_id": binding_id, "decision": status, "reason": str(reason),
              "decided_at": now_iso()}
    registry = load_registry(registry_path)
    registry.setdefault("records", []).append(record)
    save_registry(registry, registry_path)
    return record


# ---------------------------------------------------------------- 晋升与门禁

def promote_binding(candidates: dict, binding_id: str, *, registry_path: str = "",
                    bindings_path: str = "") -> dict:
    """把 APPROVED 候选写入正式绑定库；同 (Feature, Behavior) 旧绑定 SUPERSEDED。"""
    candidate = next((c for c in candidates.get("candidates", [])
                      if str(c.get("binding_id")) == str(binding_id)), None)
    if candidate is None:
        raise BindingCandidateError("candidate %r not found" % binding_id)
    if str(candidate.get("approval_status")) != APPROVED:
        raise BindingCandidateError("candidate %s is %s, only APPROVED can be promoted"
                                    % (binding_id, candidate.get("approval_status")))
    registry = load_registry(registry_path)
    latest = latest_record(registry, binding_id)
    if latest is None or str(latest.get("decision")) != APPROVED:
        raise BindingCandidateError("candidate %s has no APPROVED registry record"
                                    % binding_id)
    if str(latest.get("approved_digest")) != candidate_digest(candidate):
        raise BindingCandidateError(
            "candidate %s digest changed after approval" % binding_id)

    official = tb.load_bindings(bindings_path)
    superseded = []
    for existing in official.get("bindings", []):
        if str(existing.get("feature_id")) == candidate["feature_id"] and \
                str(existing.get("behavior_id")) == candidate["behavior_id"]:
            superseded.append(str(existing.get("binding_id")))
    official["bindings"] = [
        b for b in official.get("bindings", [])
        if not (str(b.get("feature_id")) == candidate["feature_id"] and
                str(b.get("behavior_id")) == candidate["behavior_id"])]
    official["bindings"].append({
        "binding_id": candidate["binding_id"],
        "feature_id": candidate["feature_id"],
        "behavior_id": candidate["behavior_id"],
        "scenario_id": "",
        "trace_id": "",
        "trace_version": "",
        "contract_version": candidate["contract_version"],
        "baseline_id": "",
        "baseline_version": "",
        "expected": candidate["expected"],
        "expected_source": candidate["expected_source"],
        "expected_source_ref": "%s (contract digest %s)" % (
            candidate["source_contract"], candidate["contract_version"]),
        "approved": True,
        "approval_reference": str(latest.get("approval_reference") or ""),
        "approval_registry_digest": str(latest.get("approved_digest") or ""),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    })
    tb.save_bindings(official, bindings_path)
    for old_id in superseded:
        set_binding_lifecycle(old_id, SUPERSEDED,
                              reason="superseded by %s (contract version %s)"
                                     % (binding_id, candidate["contract_version"]),
                              registry_path=registry_path)
    return {"promoted": candidate["binding_id"], "superseded": superseded,
            "contract_version": candidate["contract_version"]}


def binding_gate_status(feature_id: str, behavior_id: str, *,
                        candidates: dict | None = None,
                        registry: dict | None = None,
                        contract_version: str = "",
                        official_bindings: dict | None = None) -> dict:
    """§3.4 门禁状态：精确匹配，无子串；缺失不静默回退。"""
    result = {"feature_id": feature_id, "behavior_id": behavior_id,
              "status": NO_BINDING, "binding_id": None, "reason": ""}
    official = official_bindings or tb.load_bindings()
    binding = tb.get_binding(official, feature_id, behavior_id)
    if binding is None:
        # 正式库没有 → 看候选池（草稿/待审/被拒都要如实表达）
        doc = candidates if candidates is not None else load_candidates()
        candidate = next((c for c in doc.get("candidates", [])
                          if str(c.get("feature_id")) == str(feature_id) and
                          str(c.get("behavior_id")) == str(behavior_id)), None)
        if candidate is None:
            result["reason"] = "no official binding and no candidate for this behavior"
            return result
        result["binding_id"] = candidate.get("binding_id")
        status = str(candidate.get("approval_status"))
        if status == BLOCKED_MISSING_EXPECTED:
            result["status"] = BINDING_INVALID
            result["reason"] = str(candidate.get("blocked_reason") or "blocked candidate")
        elif status == DRAFT:
            result["status"] = DRAFT_BINDING
            result["reason"] = "candidate exists but is DRAFT (not approvable yet)"
        elif status == PENDING_REVIEW:
            result["status"] = PENDING_REVIEW_BINDING
            result["reason"] = "candidate awaits explicit review"
        elif status == REJECTED:
            result["status"] = BINDING_INVALID
            result["reason"] = "candidate was rejected"
        elif status in (REVOKED, SUPERSEDED):
            result["status"] = BINDING_REVOKED
            result["reason"] = "candidate lifecycle ended as %s" % status
        else:
            result["status"] = DRAFT_BINDING
            result["reason"] = "candidate is %s and not promoted yet" % status
        return result

    result["binding_id"] = binding.get("binding_id")
    registry_doc = registry if registry is not None else load_registry()
    lifecycle = latest_record(registry_doc, str(binding.get("binding_id")))
    if lifecycle and str(lifecycle.get("decision")) == REVOKED:
        result["status"] = BINDING_REVOKED
        result["reason"] = str(lifecycle.get("reason") or "binding was revoked")
        return result
    if lifecycle and str(lifecycle.get("decision")) == SUPERSEDED:
        result["status"] = BINDING_REVOKED
        result["reason"] = str(lifecycle.get("reason") or "binding was superseded")
        return result
    if contract_version and str(binding.get("contract_version")) and \
            str(binding.get("contract_version")) != str(contract_version):
        result["status"] = "CONTRACT_MISMATCH"
        result["reason"] = ("binding contract_version %r != current %r"
                            % (binding.get("contract_version"), contract_version))
        return result
    if not bool(binding.get("approved")):
        result["status"] = BINDING_INVALID
        result["reason"] = "official binding is not marked approved"
        return result
    result["status"] = APPROVED_BINDING
    result["reason"] = "approved official binding"
    return result


# ---------------------------------------------------------------- 支持清单

def build_support_inventory(features_dir: str = "") -> dict:
    """§2.3 动态支持清单（正式支持状态来自契约推导，不来自历史数量）。"""
    sys.path.insert(0, os.path.join(_TOOLS, "evaluation"))
    import evidence_adapter as adapter                 # noqa: E402
    supported = adapter.supported_set(features_dir)
    directory = features_dir or os.path.join(PROJECT_ROOT, "Features")
    entries = []
    for feature_id in sorted(supported["features"]):
        template_path = "Features/%s/template.yaml" % feature_id
        for behavior_id in supported["features"][feature_id]:
            version, _expected, _core = contract_digest(feature_id, behavior_id, directory)
            entries.append({
                "feature_id": feature_id,
                "behavior_id": behavior_id,
                "template_path": template_path,
                "contract_path": template_path + "#behavior",
                "contract_version": version,
                "support_status": "SUPPORTED",
                "support_source": supported["source"],
            })
    return {
        "schema": "phase_1_63_support_inventory",
        "schema_version": 1,
        "generated_at": now_iso(),
        "feature_count": supported["feature_count"],
        "behavior_count": supported["behavior_count"],
        "entries": entries,
    }


# ---------------------------------------------------------------- CLI

def _load_trust_key(trust_root: str, key_id: str) -> str:
    return key_id


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    gen = sub.add_parser("generate", help="generate/refresh binding candidates")
    gen.add_argument("--features-dir", default="")
    gen.add_argument("--out", default="")

    inv = sub.add_parser("inventory", help="dump support inventory json")
    inv.add_argument("--features-dir", default="")
    inv.add_argument("--out", required=True)

    st = sub.add_parser("submit", help="DRAFT -> PENDING_REVIEW")
    st.add_argument("--binding-id", required=True)

    ap = sub.add_parser("approve", help="PENDING_REVIEW -> APPROVED (explicit)")
    ap.add_argument("--binding-id", required=True)
    ap.add_argument("--reviewer", required=True)
    ap.add_argument("--reference", required=True)
    ap.add_argument("--key-id", default="", help="Ed25519 key with approve_binding scope")
    ap.add_argument("--trust-root", default="")

    pr = sub.add_parser("promote", help="merge APPROVED candidate into official bindings")
    pr.add_argument("--binding-id", required=True)

    gate = sub.add_parser("gate", help="binding gate status for a behavior")
    gate.add_argument("--feature", required=True)
    gate.add_argument("--behavior", required=True)

    args = parser.parse_args(argv)
    if args.cmd == "generate":
        doc = generate_candidates(args.features_dir, args.out)
        counts: dict = {}
        for c in doc["candidates"]:
            counts[c["approval_status"]] = counts.get(c["approval_status"], 0) + 1
        print("candidates:", len(doc["candidates"]), counts)
        return 0
    if args.cmd == "inventory":
        doc = build_support_inventory(args.features_dir)
        with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(doc, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        print("features:", doc["feature_count"], "behaviors:", doc["behavior_count"],
              "->", args.out)
        return 0
    if args.cmd == "submit":
        doc = load_candidates()
        submit_for_review(doc, args.binding_id)
        print("submitted:", args.binding_id)
        return 0
    if args.cmd == "approve":
        doc = load_candidates()
        record = approve_candidate(
            doc, args.binding_id, reviewer=args.reviewer,
            approval_reference=args.reference, key_id=args.key_id,
            trust_root=args.trust_root)
        print("approved:", record["binding_id"], "digest:",
              record["approved_digest"][:12],
              "signed=%s" % bool(record.get("signature_envelope")))
        return 0
    if args.cmd == "promote":
        doc = load_candidates()
        result = promote_binding(doc, args.binding_id)
        print("promoted:", result["promoted"], "superseded:", result["superseded"],
              "contract_version:", result["contract_version"])
        return 0
    if args.cmd == "gate":
        status = binding_gate_status(args.feature, args.behavior)
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
