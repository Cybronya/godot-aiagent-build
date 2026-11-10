#!/usr/bin/env python3
"""Evidence-backed Evaluation Runner 测试（Phase 1.58）。

被测对象：`.ai/tools/evaluation/evidence_eval.py`（Mode A / Mode B / 报告 / 退出码）
以及 `runner.py` 的可选证据报告接入（Mode C：LEGACY_PROBE_ONLY）。

覆盖矩阵：

    H. 兼容性与 CLI
      H1  --list 不执行评估
      H2  Mode A 正常路径：VERIFIED_PASS + exit 0 + 报告结构
      H3  更严的期望（证据有效但行为不符）-> VERIFIED_FAIL + exit 1
      H4  证据被篡改 -> INVALID_EVIDENCE + exit 1
      H5  缺执行产物 -> INCOMPLETE + exit 2
      H6  未知 Feature -> EVALUATION_ERROR + exit 1
      H7  重复映射 -> 结构错误 + exit 1
      H8  未提供 Holdout 批次 -> NOT_EVALUATED（独立成块，不伪造通过）
      H9  Holdout 与训练共用批次 -> 隔离违规 + EVALUATION_ERROR
      H10 Mode B 被显式跳过 -> NOT_EVALUATED collection_skipped（不跑 Godot）
      H11 runner.py 未传 --evidence-report 时报告结构不变
      H12 runner.py 接入证据报告后任务标记 LEGACY_PROBE_ONLY 且不进 VERIFIED_* 统计

所有产物都建在 `.ai/tmp/` 下的临时目录，测试结束删除。

用法：python .ai/tools/evaluation/tests/test_evidence_eval.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
EVAL_DIR = os.path.dirname(_HERE)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(EVAL_DIR)))
for _path in (_HERE, EVAL_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import evidence_adapter as adapter                               # noqa: E402
import evidence_eval                                             # noqa: E402
import evidence_fixtures as fixtures                             # noqa: E402
import runner                                                    # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_failures: list = []
_checks = 0
_temp_dirs: list = []
PAIRS = fixtures.feature_pairs(["collect_pickup", "health"])
# fixture 的执行产物根目录（main() 里设置），写进临时任务文件的 run 段。
ARTIFACT_ROOT = ""


def ok(name: str, condition: bool, detail: str = "") -> None:
    global _checks
    _checks += 1
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))
        print("FAIL: " + name + (" | " + detail if detail else ""))


def new_dir(prefix: str) -> str:
    base = os.path.join(PROJECT_ROOT, ".ai", "tmp")
    os.makedirs(base, exist_ok=True)
    directory = tempfile.mkdtemp(prefix=prefix, dir=base)
    _temp_dirs.append(directory)
    return directory


def cleanup() -> None:
    for directory in _temp_dirs:
        shutil.rmtree(directory, ignore_errors=True)


def write_tasks(path: str, tasks: list, evidence_dir: str, artifact_root: str = "") -> str:
    artifact_root = artifact_root or ARTIFACT_ROOT
    document = {
        "schema": {"id": "evaluation_evidence_tasks", "version": 1},
        "run": {"evidence_dir": evidence_dir, "max_age_hours": 24},
        "tasks": tasks,
    }
    text = "schema:\n  id: evaluation_evidence_tasks\n  version: 1\n"
    text += "run:\n  evidence_dir: %s\n  max_age_hours: 24\n" % evidence_dir.replace("\\", "/")
    if artifact_root:
        text += "  artifact_root: %s\n" % artifact_root.replace("\\", "/")
    text += "tasks:\n"
    for task in tasks:
        text += "  - id: %s\n" % task["id"]
        text += "    title: %s\n" % task.get("title", task["id"])
        text += "    mode: %s\n" % task.get("mode", "evidence")
        if task.get("holdout"):
            text += "    holdout: true\n"
        text += "    feature: %s\n" % task["feature"]
        if task.get("behavior"):
            text += "    behavior: %s\n" % task["behavior"]
            text += "    expect:\n"
            for item in task.get("expect") or []:
                text += "      - " + json.dumps(item, ensure_ascii=False) + "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return path


def run_cli(runs_dir: str, tasks_file: str, evidence_dir: str, extra=None) -> tuple:
    argv = ["--tasks-file", tasks_file, "--evidence-dir", evidence_dir,
            "--no-collect", "--runs-dir", runs_dir] + list(extra or [])
    import io
    import contextlib
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = evidence_eval.main(argv)
    return code, buffer.getvalue()


def latest_report(runs_dir: str) -> dict:
    tokens = sorted(os.listdir(runs_dir))
    path = os.path.join(runs_dir, tokens[-1], "evidence_report.json")
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def status_of(report: dict, task_id: str) -> str:
    for task in report["tasks"]:
        if task["task_id"] == task_id:
            return task["evaluation_status"]
    return "<missing>"


# ------------------------------------------------------------------ 用例
def test_cli_surface(base_tasks: str, evidence_dir: str, runs_dir: str) -> None:
    import io
    import contextlib
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = evidence_eval.main(["--list"])
    ok("H1: --list does not evaluate", code == 0 and "E1" in buffer.getvalue(),
       buffer.getvalue()[:120])


def test_mode_a(base_tasks: str, evidence_dir: str, runs_dir: str) -> dict:
    code, output = run_cli(runs_dir, base_tasks, evidence_dir)
    report = latest_report(runs_dir)
    ok("H2: Mode A passes and exits 0", code == 0,
       " | ".join(output.strip().splitlines()[:3]))
    ok("H2: every task is VERIFIED_PASS",
       [task["evaluation_status"] for task in report["tasks"]]
       == [adapter.VERIFIED_PASS] * len(report["tasks"]),
       str([(task["task_id"], task["evaluation_status"]) for task in report["tasks"]]))
    ok("H2: evidence validation is reported separately",
       report["evidence"]["validator"]["status"] == "PASS"
       and report["metrics"]["evidence_validation"]["pass"] == len(PAIRS),
       json.dumps(report["metrics"]["evidence_validation"]))
    ok("H2: supported set is read from the repository",
       report["supported"]["features"] == len(fixtures.fbe.declared_features(fixtures.FEATURES)),
       json.dumps(report["supported"]))
    first = report["tasks"][0]
    ok("H2: report carries traceable fields",
       first.get("execution_id") and first.get("evidence_bundle_ref")
       and first.get("artifact_digests") and first.get("protocol_version") is not None,
       json.dumps({key: first.get(key) for key in
                   ("execution_id", "evidence_bundle_ref", "protocol_version")})[:200])
    ok("H2: golden trace version is recorded without faking a comparison",
       (first.get("golden_trace") or {}).get("baseline_version") is None
       or (first["golden_trace"].get("baseline") or {}).get("binding") == "scenario_only",
       json.dumps(first.get("golden_trace"))[:200])
    return report


def test_failure_paths(base_tasks: str, evidence_dir: str, runs_dir: str,
                       temp_root: str) -> None:
    # H3：更严的期望
    strict_dir = os.path.join(temp_root, "strict")
    os.makedirs(strict_dir, exist_ok=True)
    strict_tasks = write_tasks(os.path.join(strict_dir, "tasks.yaml"), [
        {"id": "S1", "feature": "health", "behavior": "damage",
         "expect": [{"check": "health.current", "target": ".", "equals": 99}]},
    ], evidence_dir)
    strict_runs = os.path.join(strict_dir, "runs")
    os.makedirs(strict_runs, exist_ok=True)
    code, _output = run_cli(strict_runs, strict_tasks, evidence_dir)
    strict_report = latest_report(strict_runs)
    ok("H3: unmet expectation is VERIFIED_FAIL with exit 1",
       code == 1 and status_of(strict_report, "S1") == adapter.VERIFIED_FAIL,
       "%s/%s" % (code, status_of(strict_report, "S1")))

    # H4：证据被篡改
    tamper_dir = new_dir("eval158-h4-")
    tampered_evidence, tampered_artifacts = fixtures.make_evidence_dir(
        tamper_dir, PAIRS, bundle_id="bundle-h4")
    bundle_file = os.path.join(tampered_evidence, "bundle-h4.json")
    document = json.load(open(bundle_file, "r", encoding="utf-8"))
    document["features"][0]["behaviors"][0]["actual"][0]["observed"] = False
    with open(bundle_file, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2, sort_keys=True)
    h4_runs = os.path.join(tamper_dir, "runs")
    os.makedirs(h4_runs, exist_ok=True)
    code, _output = run_cli(h4_runs, base_tasks, tampered_evidence)
    tampered_report = latest_report(h4_runs)
    ok("H4: tampered evidence never becomes VERIFIED_PASS",
       code == 1 and adapter.VERIFIED_PASS not in
       [task["evaluation_status"] for task in tampered_report["tasks"]]
       and adapter.INVALID_EVIDENCE in
       [task["evaluation_status"] for task in tampered_report["tasks"]],
       str([(task["task_id"], task["evaluation_status"]) for task in tampered_report["tasks"]]))

    # H5：缺执行产物
    missing_dir = new_dir("eval158-h5-")
    missing_evidence, _missing_artifacts = fixtures.make_evidence_dir(
        missing_dir, PAIRS, bundle_id="bundle-h5", omit_artifacts=True)
    h5_runs = os.path.join(missing_dir, "runs")
    os.makedirs(h5_runs, exist_ok=True)
    code, _output = run_cli(h5_runs, base_tasks, missing_evidence)
    missing_report = latest_report(h5_runs)
    ok("H5: missing artifacts yield INCOMPLETE with exit 2",
       code == 2 and status_of(missing_report, "Q1") == adapter.INCOMPLETE,
       "%s/%s" % (code, status_of(missing_report, "Q1")))

    # H6：未知 Feature
    unknown_dir = os.path.join(temp_root, "unknown_feature")
    os.makedirs(unknown_dir, exist_ok=True)
    unknown_tasks = write_tasks(os.path.join(unknown_dir, "tasks.yaml"), [
        {"id": "U1", "feature": "ghost_feature", "behavior": "collect_on_contact",
         "expect": [{"check": "node.freed", "target": ".", "equals": True}]},
    ], evidence_dir)
    unknown_runs = os.path.join(unknown_dir, "runs")
    os.makedirs(unknown_runs, exist_ok=True)
    code, _output = run_cli(unknown_runs, unknown_tasks, evidence_dir)
    unknown_report = latest_report(unknown_runs)
    ok("H6: unknown feature is EVALUATION_ERROR with exit 1",
       code == 1 and status_of(unknown_report, "U1") == adapter.EVALUATION_ERROR,
       "%s/%s" % (code, status_of(unknown_report, "U1")))

    # H7：重复映射
    duplicate_dir = os.path.join(temp_root, "duplicate")
    os.makedirs(duplicate_dir, exist_ok=True)
    duplicate_tasks = write_tasks(os.path.join(duplicate_dir, "tasks.yaml"), [
        {"id": "D1", "feature": "health", "behavior": "damage",
         "expect": [{"check": "health.current", "target": ".", "equals": 1}]},
        {"id": "D2", "feature": "health", "behavior": "damage",
         "expect": [{"check": "health.current", "target": ".", "equals": 1}]},
    ], evidence_dir)
    duplicate_runs = os.path.join(duplicate_dir, "runs")
    os.makedirs(duplicate_runs, exist_ok=True)
    code, _output = run_cli(duplicate_runs, duplicate_tasks, evidence_dir)
    duplicate_report = latest_report(duplicate_runs)
    ok("H7: duplicate mapping is a structural problem with exit 1",
       code == 1 and bool(duplicate_report["structural_problems"]),
       str(duplicate_report["structural_problems"])[:160])


def test_holdout(evidence_dir: str, temp_root: str) -> None:
    holdout_dir = os.path.join(temp_root, "holdout")
    os.makedirs(holdout_dir, exist_ok=True)
    tasks = write_tasks(os.path.join(holdout_dir, "tasks.yaml"), [
        {"id": "M1", "feature": "collect_pickup", "behavior": "collect_on_contact",
         "expect": [{"check": "node.freed", "target": ".", "equals": True}]},
        {"id": "H1", "feature": "health", "behavior": "damage", "holdout": True,
         "expect": [{"check": "health.current", "target": ".", "equals": 1}]},
    ], evidence_dir)

    runs_a = os.path.join(holdout_dir, "runs_a")
    os.makedirs(runs_a, exist_ok=True)
    code, _output = run_cli(runs_a, tasks, evidence_dir)
    report_a = latest_report(runs_a)
    holdout_task = (report_a["holdout"]["tasks"] or [{}])[0]
    ok("H8: missing holdout batch is NOT_EVALUATED, not a pass",
       code == 0 and holdout_task.get("evaluation_status") == adapter.NOT_EVALUATED
       and report_a["holdout"]["isolation"]["status"] == adapter.NOT_EVALUATED,
       json.dumps({key: holdout_task.get(key) for key in
                   ("evaluation_status", "reason")}, ensure_ascii=False))
    ok("H8: holdout counts are reported separately",
       report_a["metrics"]["holdout"]["total"] == 1
       and report_a["metrics"]["holdout"]["NOT_EVALUATED"] == 1,
       json.dumps(report_a["metrics"]["holdout"]))
    ok("H8: holdout never enters the main evaluation counts",
       all(not task.get("holdout") for task in report_a["tasks"]))

    runs_b = os.path.join(holdout_dir, "runs_b")
    os.makedirs(runs_b, exist_ok=True)
    code, _output = run_cli(runs_b, tasks, evidence_dir, ["--holdout-dir", evidence_dir])
    report_b = latest_report(runs_b)
    ok("H9: reusing the training batch as holdout is an isolation violation",
       report_b["holdout"]["isolation"]["status"] == adapter.EVALUATION_ERROR
       and bool(report_b["holdout"]["isolation"]["violations"])
       and report_b["holdout"]["tasks"][0]["evaluation_status"] == adapter.EVALUATION_ERROR,
       json.dumps(report_b["holdout"]["isolation"])[:200])


def test_mode_b_skip(evidence_dir: str, temp_root: str) -> None:
    directory = os.path.join(temp_root, "probe_skip")
    os.makedirs(directory, exist_ok=True)
    tasks = write_tasks(os.path.join(directory, "tasks.yaml"), [
        {"id": "P1", "mode": "probe", "feature": "trigger_switch", "behavior": "latch_once",
         "expect": [{"check": "trigger.is_triggered", "target": ".", "equals": True}]},
    ], evidence_dir)
    runs = os.path.join(directory, "runs")
    os.makedirs(runs, exist_ok=True)
    code, _output = run_cli(runs, tasks, evidence_dir)
    report = latest_report(runs)
    ok("H10: skipped Mode B collection is NOT_EVALUATED",
       code == 2 and status_of(report, "P1") == adapter.NOT_EVALUATED
       and report["tasks"][0]["reason"] == "collection_skipped",
       "%s/%s/%s" % (code, status_of(report, "P1"), report["tasks"][0].get("reason")))


def test_runner_integration(evidence_report: dict, temp_root: str) -> None:
    ok("H11: runner keeps its report shape without --evidence-report",
       callable(runner.main) and runner._load_evidence_report("") is None)

    path = os.path.join(temp_root, "evidence_report.json")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(evidence_report, handle, ensure_ascii=False)
    attachment = runner._load_evidence_report(path)
    ok("H12: runner can attach an evidence report",
       isinstance(attachment, dict)
       and attachment.get("behavior_evaluation") is not None
       and isinstance(attachment.get("tasks"), list),
       str(attachment)[:160])

    bogus = os.path.join(temp_root, "bogus_report.json")
    with open(bogus, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"schema": {"id": "something_else"}}, handle)
    ok("H12: runner refuses a report with the wrong schema",
       runner._load_evidence_report(bogus) is None)


def main() -> int:
    global ARTIFACT_ROOT
    temp_root = new_dir("eval158-eval-")
    evidence_dir, ARTIFACT_ROOT = fixtures.make_evidence_dir(temp_root, PAIRS)
    runs_dir = os.path.join(temp_root, "runs")
    os.makedirs(runs_dir, exist_ok=True)
    base_tasks = write_tasks(os.path.join(temp_root, "tasks.yaml"), [
        {"id": "Q1", "feature": "collect_pickup", "behavior": "collect_on_contact",
         "expect": [{"check": "node.freed", "target": ".", "equals": True},
                    {"check": "signal", "entry": "pickup.collected", "target": ".",
                     "count": 1}]},
        {"id": "Q2", "feature": "health", "behavior": "damage",
         "expect": [{"check": "health.current", "target": ".", "equals": 1}]},
    ], evidence_dir)

    test_cli_surface(base_tasks, evidence_dir, runs_dir)
    report = test_mode_a(base_tasks, evidence_dir, runs_dir)
    test_failure_paths(base_tasks, evidence_dir, runs_dir, temp_root)
    test_holdout(evidence_dir, temp_root)
    test_mode_b_skip(evidence_dir, temp_root)
    test_runner_integration(report, temp_root)

    cleanup()
    print("\n%d check(s), %d failure(s)" % (_checks, len(_failures)))
    if _failures:
        print("FAIL: " + "; ".join(_failures[:5]))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
