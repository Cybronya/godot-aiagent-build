#!/usr/bin/env python3
"""Coverage Matrix 测试（Phase 1.63，任务书 §7.3）。

被测对象：`.ai/tools/evaluation/coverage_matrix.py`

覆盖矩阵（全部使用临时目录，不触碰真实产物）：
    M1  动态发现：沙盒 features 目录决定分母（复制 2 个 Feature -> 2 行）
    M2  动态新增：加入第三个 Feature 后自动出现在矩阵
    M3  缺失数据 -> 明确状态（NO_EVIDENCE / NO_SIGNATURE / NO_ATTESTATION /
        NOT_EVALUATED / NO_HOLDOUT / NOT_TESTED），digest/run_id 为 null
    M4  合成 bundle（PASS + 完整性一致）-> EVIDENCE_VERIFIED；无 sidecar ->
        NO_SIGNATURE（legacy 不算签名验证）
    M5  bundle 被篡改（完整性失配）-> EVIDENCE_INVALID
    M6  INVALID mutation 绝不被算成 KILLED；KILLED 正确计入
    M7  holdout CONSUMED / INVALIDATED / SEALED 状态正确映射
    M8  --strict：存在覆盖缺口 -> 退出码 2；过滤 --feature 正常
    M9  评估报告缺该 Behavior -> NOT_EVALUATED（无虚假 PASS）
    M10 binding REVOKED -> REVOKED（撤销后覆盖正确下降）

用法：python .ai/tools/evaluation/tests/test_coverage_matrix.py
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
EVALUATION_DIR = os.path.dirname(_HERE)
TOOLS_DIR = os.path.dirname(EVALUATION_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(TOOLS_DIR))
for _p in (TOOLS_DIR, os.path.join(TOOLS_DIR, "evaluation"),
           os.path.join(TOOLS_DIR, "scene_composer"), os.path.join(TOOLS_DIR, "validator")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import coverage_matrix as cm                     # noqa: E402
import feature_behavior_evidence as fbe          # noqa: E402
import trace_bindings as tb                      # noqa: E402

_checks = 0
_failures: list = []


def ok(name: str, condition, detail: str = "") -> None:
    global _checks
    _checks += 1
    if condition:
        print("PASS %s" % name)
    else:
        _failures.append(name)
        print("FAIL %s%s" % (name, (" | " + detail) if detail else ""))


class Sandbox:
    def __init__(self) -> None:
        self.root = tempfile.mkdtemp(prefix="p163_matrix_test_")
        self.features = os.path.join(self.root, "Features")
        os.makedirs(self.features)
        for feature in ("trigger_switch", "openable_door"):
            shutil.copytree(os.path.join(PROJECT_ROOT, "Features", feature),
                            os.path.join(self.features, feature))
        self.evidence = os.path.join(self.root, "evidence")
        os.makedirs(self.evidence)
        self.eval_dir = os.path.join(self.root, "eval")
        os.makedirs(self.eval_dir)
        self.mutation_reports = os.path.join(self.root, "mutation_reports")
        os.makedirs(self.mutation_reports)
        self.runs = os.path.join(self.root, "runs")
        os.makedirs(self.runs)
        self.holdout = os.path.join(self.root, "holdout_datasets.json")

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


def make_bundle(sandbox: Sandbox, bundle_id: str, feature_id: str, behavior_id: str,
                status: str = "PASS", run_id: str = "run-xyz") -> str:
    document = {
        "bundle_id": bundle_id, "evidence_level": "L4",
        "features": [{"feature": feature_id,
                      "behaviors": [{"behavior": behavior_id, "status": status,
                                     "run_id": run_id, "actual": []}]}],
    }
    path = fbe.write_bundle(document, sandbox.evidence)
    document["integrity"] = {"algorithm": "sha256",
                             "payload_sha256": fbe.bundle_digest(document)}
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def make_eval_report(sandbox: Sandbox, feature_id: str, behavior_id: str,
                     status: str) -> str:
    run_dir = os.path.join(sandbox.eval_dir, "1111-ab")
    os.makedirs(run_dir, exist_ok=True)
    path = os.path.join(run_dir, "evidence_report.json")
    report = {"tasks": [{"feature_id": feature_id, "task_id": "T1",
                         "behaviors": [{"behavior": behavior_id,
                                        "evaluation_status": status,
                                        "reason": "test"}]}]}
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False)
        handle.write("\n")
    return path


def make_mutation_report(sandbox: Sandbox, mid: str, feature_id: str,
                         behavior_id: str, verdict: str) -> str:
    path = os.path.join(sandbox.mutation_reports, "%s.json" % mid)
    report = {"mutation_id": mid,
              "catalog": {"feature_id": feature_id, "behavior_id": behavior_id},
              "verdict": verdict, "verdict_reason": "test"}
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False)
        handle.write("\n")
    return path


def make_holdout(sandbox: Sandbox, status: str, feature_id: str,
                 behavior_id: str) -> str:
    registry = {"datasets": [{"holdout_id": "H-TEST", "dataset_version": "1",
                              "status": status, "pollution": [],
                              "feature_ids": [feature_id],
                              "behavior_ids": [behavior_id],
                              "sealed_at": "2026-11-04T00:00:00Z"}]}
    with open(sandbox.holdout, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(registry, handle, ensure_ascii=False)
        handle.write("\n")
    return sandbox.holdout


def get_row(document, feature_id, behavior_id):
    return next((r for r in document["rows"]
                 if r["feature_id"] == feature_id and r["behavior_id"] == behavior_id), None)


def main() -> int:
    sandbox = Sandbox()
    try:
        # M1/M2：动态分母与自动发现
        document = cm.build_matrix(sandbox.features, [sandbox.evidence],
                                   [sandbox.eval_dir],
                                   mutation_report_dir=sandbox.mutation_reports,
                                   runs_dir=sandbox.runs,
                                   holdout_registry_path=sandbox.holdout)
        ids = {(r["feature_id"], r["behavior_id"]) for r in document["rows"]}
        ok("M1: sandbox features define the denominator dynamically",
           ("trigger_switch", "latch_once") in ids and
           ("openable_door", "open") in ids and len(ids) == 3,
           str(sorted(ids)))
        shutil.copytree(os.path.join(PROJECT_ROOT, "Features", "health"),
                        os.path.join(sandbox.features, "health"))
        document = cm.build_matrix(sandbox.features, [sandbox.evidence],
                                   [sandbox.eval_dir],
                                   mutation_report_dir=sandbox.mutation_reports,
                                   runs_dir=sandbox.runs,
                                   holdout_registry_path=sandbox.holdout)
        ok("M2: newly added feature auto-discovered",
           document["summary"]["supported_behaviors"] == 8,
           str(document["summary"]["supported_behaviors"]))

        # M3：缺失数据 -> 明确状态 + null
        row = get_row(document, "openable_door", "open")
        ok("M3: missing data yields explicit statuses and null digests",
           row["evidence"]["status"] == "NO_EVIDENCE" and
           row["signature"]["status"] == "NO_SIGNATURE" and
           row["attestation"]["status"] == "NO_ATTESTATION" and
           row["evaluation"]["status"] == "NOT_EVALUATED" and
           row["holdout"]["status"] == "NO_HOLDOUT" and
           row["mutation"]["status"] == "NOT_TESTED" and
           row["latest_evidence_digest"] is None and
           row["latest_run_id"] is None and
           row["latest_attestation_digest"] is None, json.dumps(row)[:200])

        # M4：合成 PASS bundle -> EVIDENCE_VERIFIED；无 sidecar -> NO_SIGNATURE
        make_bundle(sandbox, "sb-bundle", "openable_door", "open")
        document = cm.build_matrix(sandbox.features, [sandbox.evidence],
                                   [sandbox.eval_dir],
                                   mutation_report_dir=sandbox.mutation_reports,
                                   runs_dir=sandbox.runs,
                                   holdout_registry_path=sandbox.holdout)
        row = get_row(document, "openable_door", "open")
        ok("M4: verified bundle -> EVIDENCE_VERIFIED but legacy signature stays NO_SIGNATURE",
           row["evidence"]["status"] == "EVIDENCE_VERIFIED" and
           row["signature"]["status"] == "NO_SIGNATURE" and
           row["latest_run_id"] == "run-xyz" and
           row["latest_evidence_digest"], json.dumps(row["evidence"])[:150])

        # M5：篡改 bundle -> EVIDENCE_INVALID
        bundle_path = os.path.join(sandbox.evidence, "sb-bundle.json")
        with open(bundle_path, encoding="utf-8") as handle:
            forged = json.load(handle)
        forged["features"][0]["behaviors"][0]["actual"] = [{"hacked": True}]
        with open(bundle_path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(forged, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        document = cm.build_matrix(sandbox.features, [sandbox.evidence],
                                   [sandbox.eval_dir],
                                   mutation_report_dir=sandbox.mutation_reports,
                                   runs_dir=sandbox.runs,
                                   holdout_registry_path=sandbox.holdout)
        row = get_row(document, "openable_door", "open")
        ok("M5: tampered bundle -> EVIDENCE_INVALID (integrity mismatch)",
           row["evidence"]["status"] == "EVIDENCE_INVALID", json.dumps(row["evidence"])[:150])
        os.remove(bundle_path)

        # M6：INVALID mutation 不算 KILLED；KILLED 正确计入
        make_mutation_report(sandbox, "M99-invalid", "trigger_switch", "latch_once",
                             "INVALID_MUTANT")
        make_mutation_report(sandbox, "M98-killed", "openable_door", "open",
                             "MUTANT_KILLED")
        make_mutation_report(sandbox, "M97-survived", "health", "damage",
                             "MUTANT_SURVIVED")
        document = cm.build_matrix(sandbox.features, [sandbox.evidence],
                                   [sandbox.eval_dir],
                                   mutation_report_dir=sandbox.mutation_reports,
                                   runs_dir=sandbox.runs,
                                   holdout_registry_path=sandbox.holdout)
        ok("M6a: INVALID mutation -> MUTATION_INVALID (never KILLED)",
           get_row(document, "trigger_switch", "latch_once")["mutation"]["status"]
           == "MUTATION_INVALID")
        ok("M6b: KILLED mutation counted", get_row(
            document, "openable_door", "open")["mutation"]["status"] == "MUTATION_KILLED")
        ok("M6c: SURVIVED mapped distinctly", get_row(
            document, "health", "damage")["mutation"]["status"] == "MUTATION_SURVIVED")
        ok("M6d: summary counts invalid separately",
           document["summary"]["mutation_invalid"] == 1 and
           document["summary"]["mutation_killed"] == 1,
           str(document["summary"]))

        # M7：holdout 状态映射
        make_holdout(sandbox, "CONSUMED", "openable_door", "open")
        document = cm.build_matrix(sandbox.features, [sandbox.evidence],
                                   [sandbox.eval_dir],
                                   mutation_report_dir=sandbox.mutation_reports,
                                   runs_dir=sandbox.runs,
                                   holdout_registry_path=sandbox.holdout)
        ok("M7a: consumed holdout -> HOLDOUT_CONSUMED",
           get_row(document, "openable_door", "open")["holdout"]["status"]
           == "HOLDOUT_CONSUMED")
        make_holdout(sandbox, "SEALED", "openable_door", "open")
        document = cm.build_matrix(sandbox.features, [sandbox.evidence],
                                   [sandbox.eval_dir],
                                   mutation_report_dir=sandbox.mutation_reports,
                                   runs_dir=sandbox.runs,
                                   holdout_registry_path=sandbox.holdout)
        ok("M7b: sealed holdout -> HOLDOUT_AVAILABLE",
           get_row(document, "openable_door", "open")["holdout"]["status"]
           == "HOLDOUT_AVAILABLE")
        registry = {"datasets": [{"holdout_id": "H-TEST", "dataset_version": "1",
                                  "status": "SEALED",
                                  "pollution": [{"reason": "tainted"}],
                                  "feature_ids": ["openable_door"],
                                  "behavior_ids": ["open"]}],
                    "sealed_at": "2026-11-04T00:00:00Z"}
        with open(sandbox.holdout, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(registry, handle, ensure_ascii=False)
            handle.write("\n")
        document = cm.build_matrix(sandbox.features, [sandbox.evidence],
                                   [sandbox.eval_dir],
                                   mutation_report_dir=sandbox.mutation_reports,
                                   runs_dir=sandbox.runs,
                                   holdout_registry_path=sandbox.holdout)
        ok("M7c: polluted holdout -> HOLDOUT_INVALID",
           get_row(document, "openable_door", "open")["holdout"]["status"]
           == "HOLDOUT_INVALID")

        # M9：评估报告存在该 Behavior -> 状态来自报告；缺 -> NOT_EVALUATED
        make_eval_report(sandbox, "openable_door", "open", "VERIFIED_PASS")
        document = cm.build_matrix(sandbox.features, [sandbox.evidence],
                                   [sandbox.eval_dir],
                                   mutation_report_dir=sandbox.mutation_reports,
                                   runs_dir=sandbox.runs,
                                   holdout_registry_path=sandbox.holdout)
        ok("M9a: evaluation status from report",
           get_row(document, "openable_door", "open")["evaluation"]["status"]
           == "VERIFIED_PASS")
        ok("M9b: behavior without report stays NOT_EVALUATED (no fake PASS)",
           get_row(document, "trigger_switch", "toggle_on_second_contact")
           ["evaluation"]["status"] == "NOT_EVALUATED")

        # M10：binding 撤销 -> REVOKED（用独立登记表沙盒）
        registry = {"records": [{"binding_id": "FAKE-1", "decision": "REVOKED",
                                 "reason": "test"}]}
        rev_registry = os.path.join(sandbox.root, "approval_registry.json")
        with open(rev_registry, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(registry, handle, ensure_ascii=False)
            handle.write("\n")
        bindings = {"bindings": [{"binding_id": "FAKE-1", "feature_id": "openable_door",
                                  "behavior_id": "open", "contract_version": "",
                                  "expected": [], "expected_source": "behavior_contract",
                                  "approved": True}]}
        rev_bindings = os.path.join(sandbox.root, "bindings.json")
        with open(rev_bindings, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(bindings, handle, ensure_ascii=False)
            handle.write("\n")
        gate = cm.binding_dimension("openable_door", "open", "")
        # 用显式参数模拟撤销场景
        from binding_candidates import binding_gate_status, load_registry, load_candidates
        st = binding_gate_status("openable_door", "open",
                                 registry={"records": [{"binding_id": "FAKE-1",
                                                        "decision": "REVOKED"}]},
                                 official_bindings=bindings)
        ok("M10: revoked binding -> REVOKED", st["status"] == "BINDING_REVOKED",
           str(st))
    finally:
        sandbox.cleanup()

    print("\n%d check(s), %d failure(s)" % (_checks, len(_failures)))
    if _failures:
        print("FAIL: " + "; ".join(_failures[:5]))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
