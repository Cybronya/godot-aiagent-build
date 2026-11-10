#!/usr/bin/env python3
"""Baseline 生命周期与内容完整性测试（Phase 1.60，任务书 §8.2）。

被测对象：`.ai/tools/validator/baseline_lifecycle.py`

覆盖矩阵：
    A. 内容摘要
      A1 摘要可计算且确定（同输入同输出）
      A2 字段顺序 / 无关空白不影响摘要
      A3 approval 块变化不影响摘要（合法的 coverage 修订先例）
      A4 事件内容变化必改摘要
    B. 状态机
      B1 DRAFT -> PENDING_REVIEW -> APPROVED 合法
      B2 DRAFT -> APPROVED 跳步被拒
      B3 REVOKED 是终态
      B4 非法状态值被拒
      B5 重复登记不带 previous_status 被拒（防静默覆盖）
    C. 使用时复核（use_baseline）
      C1 APPROVED_OK：已批准 + 已登记 + 摘要一致
      C2 内容被篡改 -> DIGEST_MISMATCH（旧审批失效）
      C3 Expected/事件被改 -> DIGEST_MISMATCH
      C4 无登记记录 -> MISSING_REGISTRATION（旧数据不自动升级）
      C5 登记为 REVOKED -> 拒绝
      C6 登记为 SUPERSEDED -> 拒绝
      C7 文件内 approval.status 伪造为 approved 但无登记 -> 不放行
      C8 登记表损坏 -> INVALID_BASELINE（fail-closed）
    D. 迁移（既有基线）
      D1 四条真实基线已登记且摘要一致（APPROVED_OK）
      D2 迁移后修改真实基线副本内容 -> DIGEST_MISMATCH（不写入真实文件）
    E. 显式迁移护栏
      E1 未批准的文档不能迁移
      E2 结构非法的文档不能迁移

用法：python .ai/tools/validator/tests/test_baseline_lifecycle.py
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
VALIDATOR_DIR = os.path.dirname(_HERE)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(VALIDATOR_DIR)))
for _path in (VALIDATOR_DIR,):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import baseline_lifecycle as bl                                 # noqa: E402
import trace_baselines                                          # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_checks = 0
_failures: list = []


def ok(label: str, condition: bool, detail: str = "") -> None:
    global _checks
    _checks += 1
    if condition:
        print("PASS: %s" % label)
    else:
        _failures.append(label)
        print("FAIL: %s  %s" % (label, detail[:300]))


def expect_error(label: str, fn, *args, **kwargs) -> None:
    try:
        fn(*args, **kwargs)
        ok(label, False, "expected LifecycleError, none raised")
    except bl.LifecycleError as exc:
        ok(label, True, str(exc))
    except Exception as exc:                                  # noqa: BLE001
        ok(label, False, "unexpected %s: %s" % (type(exc).__name__, exc))


_TMP_ROOT = None


def new_dir(prefix: str) -> str:
    global _TMP_ROOT
    if _TMP_ROOT is None:
        _TMP_ROOT = tempfile.mkdtemp(prefix="p160-baseline-")
    path = tempfile.mkdtemp(prefix=prefix, dir=_TMP_ROOT)
    return path


def sample_baseline() -> dict:
    return {
        "baseline_schema_version": 1,
        "baseline_version": 3,
        "scenario_id": "test_scenario",
        "trace_schema_version": 1,
        "approved_behavior_version": 7,
        "comparison_policy": {"strict_fields": ["type", "index"]},
        "events": [{"type": "orchestration_started", "index": 0,
                    "data": {"mode": "waves"}}],
        "expected_final_state": {"state": "completed"},
        "coverage": {"chain": "started -> victory"},
        "approval": {"status": "approved", "approver": "tester",
                     "approved_at": "2026-11-03T00:00:00Z",
                     "candidate_fingerprint": "0" * 16},
    }


def register_ok(document: dict, registry_path: str, **overrides) -> dict:
    digest = bl.content_digest(document)["digest"]
    params = dict(baseline_id=document["scenario_id"],
                  baseline_version=document["baseline_version"],
                  status=bl.APPROVED, digest=digest,
                  approver="tester", approved_at="2026-11-03T00:00:00Z",
                  basis="test registration", registry_path=registry_path)
    params.update(overrides)
    return bl.register(**params)


def test_digest() -> None:
    document = sample_baseline()
    first = bl.content_digest(document)
    second = bl.content_digest(document)
    ok("A1: digest is deterministic", first["digest"] == second["digest"]
       and len(first["digest"]) == 64)

    reordered = json.loads(json.dumps(document))
    reordered["events"], reordered["expected_final_state"] = \
        document["expected_final_state"], document["events"]
    reordered["events"] = list(reversed(reordered["events"])) if False else reordered["events"]
    # 字段顺序（dict 插入顺序）变化不影响摘要
    shuffled = {k: document[k] for k in reversed(list(document.keys()))}
    ok("A2: key order does not change digest",
       bl.content_digest(shuffled)["digest"] == first["digest"])

    approved_variant = copy.deepcopy(document)
    approved_variant["approval"]["coverage_revision_note"] = "text-only revision"
    approved_variant["scenario_description"] = "new prose"
    ok("A3: approval metadata / prose changes do not change digest",
       bl.content_digest(approved_variant)["digest"] == first["digest"])

    tampered = copy.deepcopy(document)
    tampered["events"][0]["data"]["mode"] = "holdout"
    ok("A4: content change changes digest",
       bl.content_digest(tampered)["digest"] != first["digest"])


def test_state_machine() -> None:
    registry = os.path.join(new_dir("sm-"), "registry.json")
    document = sample_baseline()
    digest = bl.content_digest(document)["digest"]

    bl.register("s", 3, bl.DRAFT, digest=digest, basis="draft", registry_path=registry)
    bl.register("s", 3, bl.PENDING_REVIEW, digest=digest, basis="review",
                previous_status=bl.DRAFT, registry_path=registry)
    record = bl.register("s", 3, bl.APPROVED, digest=digest, basis="approve",
                         approver="tester", previous_status=bl.PENDING_REVIEW,
                         registry_path=registry)
    ok("B1: DRAFT -> PENDING_REVIEW -> APPROVED", record["status"] == bl.APPROVED)

    # 全新登记直达 APPROVED 是显式迁移路径（migrate_existing_baseline），合法；
    # 但已存在的 DRAFT 记录跳步到 APPROVED 必须被拒。
    bl.register("s2", 1, bl.DRAFT, digest=digest, basis="draft", registry_path=registry)
    expect_error("B2: existing DRAFT record cannot jump to APPROVED",
                 bl.register, "s2", 1, bl.APPROVED, digest=digest, basis="skip",
                 previous_status=bl.DRAFT, registry_path=registry)

    bl.register("s", 3, bl.REVOKED, digest=digest, basis="revoke",
                previous_status=bl.APPROVED, registry_path=registry)
    registry_doc = bl._load_registry(registry)
    entry = bl._find(registry_doc, "s", 3)
    ok("B3: REVOKED is terminal", entry["status"] == bl.REVOKED)
    expect_error("B3b: REVOKED cannot transition",
                 bl.register, "s", 3, bl.APPROVED, digest=digest, basis="re-approve",
                 previous_status=bl.REVOKED, registry_path=registry)

    expect_error("B4: unknown status rejected",
                 bl.register, "s", 4, "MAYBE", digest=digest, basis="x",
                 registry_path=registry)

    expect_error("B5: duplicate registration without explicit transition rejected",
                 bl.register, "s", 3, bl.APPROVED, digest=digest, basis="again",
                 registry_path=registry)


def test_use_baseline() -> None:
    document = sample_baseline()
    registry = os.path.join(new_dir("use-"), "registry.json")
    register_ok(document, registry)

    result = bl.use_baseline(document, registry_path=registry)
    ok("C1: approved + registered + digest match -> APPROVED_OK",
       result["status"] == "APPROVED_OK", str(result))

    tampered = copy.deepcopy(document)
    tampered["events"][0]["data"]["mode"] = "boss"
    result = bl.use_baseline(tampered, registry_path=registry)
    ok("C2: tampered events -> DIGEST_MISMATCH",
       result["status"] == "DIGEST_MISMATCH", str(result["reason"]))

    tampered = copy.deepcopy(document)
    tampered["expected_final_state"] = {"state": "failed"}
    result = bl.use_baseline(tampered, registry_path=registry)
    ok("C3: tampered expected_final_state -> DIGEST_MISMATCH",
       result["status"] == "DIGEST_MISMATCH", str(result["reason"]))

    unregistered = sample_baseline()
    unregistered["scenario_id"] = "never_registered"
    result = bl.use_baseline(unregistered, registry_path=registry)
    ok("C4: unregistered baseline -> MISSING_REGISTRATION",
       result["status"] == "MISSING_REGISTRATION", str(result["reason"]))

    registry2 = os.path.join(new_dir("use2-"), "registry.json")
    register_ok(document, registry2)
    bl.register(document["scenario_id"], document["baseline_version"], bl.REVOKED,
                digest=bl.content_digest(document)["digest"], basis="revoked",
                previous_status=bl.APPROVED, registry_path=registry2)
    result = bl.use_baseline(document, registry_path=registry2)
    ok("C5: REVOKED registration -> rejected",
       result["status"] == bl.REVOKED, str(result["reason"]))

    registry3 = os.path.join(new_dir("use3-"), "registry.json")
    register_ok(document, registry3)
    bl.register(document["scenario_id"], document["baseline_version"], bl.SUPERSEDED,
                digest=bl.content_digest(document)["digest"], basis="superseded",
                previous_status=bl.APPROVED, registry_path=registry3)
    result = bl.use_baseline(document, registry_path=registry3)
    ok("C6: SUPERSEDED registration -> rejected",
       result["status"] == bl.SUPERSEDED, str(result["reason"]))

    forged = sample_baseline()
    forged["approval"] = {"status": "approved", "approver": "attacker",
                          "approved_at": "2026-11-03T00:00:00Z"}
    result = bl.use_baseline(forged, registry_path=registry)
    ok("C7: forged approval block cannot pass (approver mismatch)",
       result["status"] == "APPROVAL_MISMATCH", str(result["reason"]))

    forged_unregistered = sample_baseline()
    forged_unregistered["scenario_id"] = "never_registered"
    result = bl.use_baseline(forged_unregistered, registry_path=registry)
    ok("C7b: forged approval with no registration -> MISSING_REGISTRATION",
       result["status"] == "MISSING_REGISTRATION", str(result["reason"]))

    bad_registry = os.path.join(new_dir("use4-"), "registry.json")
    with open(bad_registry, "w", encoding="utf-8") as handle:
        handle.write("{not json")
    result = bl.use_baseline(document, registry_path=bad_registry)
    ok("C8: malformed registry -> fail-closed",
       result["status"] == "INVALID_BASELINE", str(result["reason"]))


def test_migrated_baselines() -> None:
    registry_path = bl.REGISTRY_PATH
    names = ["waves", "holdout", "single_stage_boss", "multi_stage_boss"]
    for name in names:
        path = os.path.join(bl.BASELINES_DIR, "%s.json" % name)
        with open(path, "r", encoding="utf-8") as handle:
            document = json.load(handle)
        result = bl.use_baseline(document, baseline_path=path)
        ok("D1: %s migrated and digest-verified -> APPROVED_OK" % name,
           result["status"] == "APPROVED_OK", str(result))

    # 在副本上验证篡改检测（绝不写真实基线文件）
    path = os.path.join(bl.BASELINES_DIR, "waves.json")
    with open(path, "r", encoding="utf-8") as handle:
        document = json.load(handle)
    document["events"][0]["data"] = dict(document["events"][0].get("data") or {})
    document["events"][0]["data"]["mode"] = "holdout"  # waves -> 其它模式：必变摘要
    result = bl.use_baseline(document, registry_path=registry_path)
    ok("D2: tampered waves copy -> DIGEST_MISMATCH",
       result["status"] == "DIGEST_MISMATCH", str(result["reason"]))


def test_migration_guards() -> None:
    tmp = new_dir("mig-")
    unapproved = sample_baseline()
    unapproved["approval"]["status"] = "pending"
    path = os.path.join(tmp, "unapproved.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(unapproved, handle)
    expect_error("E1: unapproved document cannot be migrated",
                 bl.migrate_existing_baseline, path, basis="test")

    broken = sample_baseline()
    broken["approval"]["status"] = "approved"
    broken["events"] = []            # 违反回放契约（无 started 事件）
    path = os.path.join(tmp, "broken.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(broken, handle)
    expect_error("E2: structurally invalid document cannot be migrated",
                 bl.migrate_existing_baseline, path, basis="test")


def cleanup() -> None:
    if _TMP_ROOT and os.path.isdir(_TMP_ROOT):
        shutil.rmtree(_TMP_ROOT, ignore_errors=True)


def main() -> int:
    test_digest()
    test_state_machine()
    test_use_baseline()
    test_migrated_baselines()
    test_migration_guards()
    cleanup()
    print("\n%d check(s), %d failure(s)" % (_checks, len(_failures)))
    if _failures:
        print("FAIL: " + "; ".join(_failures[:5]))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
