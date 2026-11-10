#!/usr/bin/env python3
"""Mutation Harness 真实端到端测试（Phase 1.59）

用**真实 Godot**（headless 采集器 + Validator + Evaluation）跑两条 catalog mutation，
覆盖两种不同类型的 Feature：

    M03 collect_pickup —— 收集后不释放拾取物（状态/生命周期）
    M05 openable_door —— 开门状态变了但信号被吞（状态 + 信号）

对每条 mutation 断言：

    1. Negative Control（副本未改）真实执行且 VERIFIED_PASS
    2. Positive Control（注入缺陷）真实执行且被 Evaluation/Validator 拒绝 → MUTANT_KILLED
    3. Effectiveness 由运行时观测证明（control 与 mutant 观测不同）
    4. Recovery（逐字节恢复）重新 VERIFIED_PASS
    5. 仓库 `Features/**` 全程未变（哈希快照）

用法：
    python .ai/tools/evaluation/mutation/tests/test_mutation_integration.py
"""

from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_MUTATION = os.path.dirname(_HERE)
_EVALUATION = os.path.dirname(_MUTATION)
_TOOLS = os.path.dirname(_EVALUATION)
PROJECT_ROOT = os.path.dirname(os.path.dirname(_TOOLS))

for _path in (_MUTATION, _EVALUATION):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import catalog                                                     # noqa: E402
import harness                                                     # noqa: E402
import workspace                                                   # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

TARGETS = ("M03", "M05")
RUNS_ROOT = os.path.join(PROJECT_ROOT, ".ai", "tmp", "p159", "integration")
REPORTS = os.path.join(PROJECT_ROOT, ".ai", "tmp", "p159", "reports")

_failures: list = []
_checks = 0


def ok(name: str, condition: bool, detail: str = "") -> None:
    global _checks
    _checks += 1
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))
        print("FAIL: " + name + (" | " + detail if detail else ""))


def entry_of(prefix: str) -> dict:
    for entry in catalog.load():
        if str(entry["mutation_id"]).startswith(prefix):
            return entry
    raise SystemExit("no catalog entry for %s" % prefix)


def observation(report: dict, phase: str) -> dict:
    return (report["effectiveness"].get("%s_observation" % phase) or {})


def main() -> int:
    print("Project root: %s" % PROJECT_ROOT)
    repo_before = workspace.snapshot(workspace.FEATURES_DIR)
    reports = []

    for prefix in TARGETS:
        entry = entry_of(prefix)
        mutation_id = entry["mutation_id"]
        print("\n--- %s (%s/%s) ---" % (mutation_id, entry["feature_id"], entry["behavior_id"]))
        report = harness.run_mutation(entry, {"runs_root": RUNS_ROOT, "timeout": 240,
                                              "replay": 2})
        reports.append(report)
        os.makedirs(REPORTS, exist_ok=True)
        with open(os.path.join(REPORTS, "it-%s.json" % mutation_id), "w",
                  encoding="utf-8", newline="\n") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write("\n")

        print("    verdict=%s  (%s)" % (report["verdict"], report["verdict_reason"]))
        control = report["controls"]["control"]
        mutant = report["controls"]["mutant"]
        recovery = report.get("recovery") or {}
        print("    control=%s  mutant=%s/%s  recovery=%s" % (
            control["evaluation"].get("evaluation_status"),
            mutant["evaluation"].get("evaluation_status"),
            mutant["evaluation"].get("validator_status"),
            recovery.get("evaluation", {}).get("evaluation_status")))

        ok("%s: negative control passes on the untouched copy" % prefix,
           control["verified"] is True, str(control["evaluation"].get("reason")))
        ok("%s: the mutant is killed by the existing evaluation chain" % prefix,
           report["verdict"] == harness.MUTANT_KILLED
           and mutant["evaluation"].get("evaluation_status") in harness.NON_PASS_EVALUATION
           and mutant["evaluation"].get("validator_status") == "FAIL",
           "%s / %s" % (report["verdict"], mutant["evaluation"].get("evaluation_status")))
        ok("%s: effectiveness is proven by runtime observations, not by config" % prefix,
           report["effectiveness"].get("effective") is True
           and observation(report, "control").get("observed")
           != observation(report, "mutant").get("observed"),
           "%s vs %s" % (observation(report, "control").get("observed"),
                         observation(report, "mutant").get("observed")))
        run_root = report["isolation"].get("run_root", "")
        mutant_copy = os.path.join(run_root, "Features",
                                   *entry["target_file"].split("/")[1:])
        repo_file = os.path.join(PROJECT_ROOT, *entry["target_file"].split("/"))
        # 注意：run_mutation 返回时副本已被恢复，所以这里不能拿副本哈希和仓库比；
        # 能证明的是：副本在 run 目录内、它曾经被写成 mutant（source_sha256 已记录）、
        # 现在逐字节回到了原值，而仓库文件从头到尾没动过（上面单独断言）。
        ok("%s: the mutation was applied inside an isolated copy, and only there" % prefix,
           report["isolation"].get("repository_features") == "Features"
           and os.path.isfile(mutant_copy)
           and os.path.abspath(mutant_copy).startswith(os.path.abspath(RUNS_ROOT) + os.sep)
           and workspace.sha256_file(mutant_copy) == report["static"]["source_sha256"]
           == workspace.sha256_file(repo_file),
           "%s vs %s" % (mutant_copy, repo_file))
        ok("%s: recovery restores the original bytes and passes again" % prefix,
           recovery.get("verified") is True
           and recovery.get("restored_byte_for_byte") is True,
           str(recovery.get("restored_byte_for_byte")))
        ok("%s: the repository tree is unchanged" % prefix,
           report["repo_guard"].get("changed") is False,
           str(report["repo_guard"].get("changes"))[:200])

    ok("I1: two different feature types were exercised",
       len({report["catalog"]["feature_id"] for report in reports}) == 2,
       str([report["catalog"]["feature_id"] for report in reports]))
    ok("I2: every recorded report keeps evaluation and validator status apart",
       all(report["controls"]["mutant"]["evaluation"].get("validator_status") == "FAIL"
           and report["controls"]["mutant"]["evaluation"].get("evaluation_status")
           == "INVALID_EVIDENCE" for report in reports))
    ok("I3: the whole batch left Features/** byte-identical",
       workspace.diff_snapshots(repo_before, workspace.snapshot(workspace.FEATURES_DIR)) == [],
       str(workspace.diff_snapshots(repo_before,
                                    workspace.snapshot(workspace.FEATURES_DIR)))[:300])

    for report in reports:
        root = report["isolation"].get("run_root") or ""
        if root:
            workspace.remove_run_dir(root, report["run_id"], RUNS_ROOT)

    print("\n%d check(s), %d failure(s)" % (_checks, len(_failures)))
    if _failures:
        for item in _failures:
            print(" - " + item)
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
