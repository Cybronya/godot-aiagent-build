#!/usr/bin/env python3
"""Evaluation Runner 自测（Phase 1.36）。

覆盖「评估器自己会不会骗人」的部分：
    L1 清理只删账本内且内容标记匹配的文件
    L2 标记不匹配 ⇒ 拒绝删除并保留文件（fail-closed）
    L3 stage 目标已存在 ⇒ 拒绝接管（不删除、不覆盖）
    L4 共享目录内的目录 ⇒ 拒绝递归删除
    R1 合成任务跑通：报告结构、指标分母、退出语义
    R2 JSON 断言 / 变异体 / 文件断言的判定
所有测试产物都在临时目录内创建，测试结束自行删除，不碰仓库既有文件。

用法：python .ai/tools/evaluation/tests/test_evaluation_runner.py
全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
EVAL_DIR = TEST_DIR.parent
TOOLS_DIR = EVAL_DIR.parent
PROJECT_ROOT = TOOLS_DIR.parent.parent
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

import runner  # noqa: E402
import scoring  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_failures: list[str] = []
_checks = 0
_temp_dirs: list[Path] = []


def ok(name: str, condition: bool, detail: str = "") -> None:
    global _checks
    _checks += 1
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))
        print("FAIL: " + name + (" | " + detail if detail else ""))


def new_run_dir(prefix: str) -> Path:
    base = PROJECT_ROOT / ".ai" / "tmp"
    base.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix=prefix, dir=str(base)))
    _temp_dirs.append(directory)
    return directory


def make_eval(run_dir: Path) -> runner.EvaluationRun:
    return runner.EvaluationRun(run_dir, {"run": {"artifact_marker": "EVAL136"}})


def cleanup() -> None:
    for directory in _temp_dirs:
        runner._rmtree(directory)


# ------------------------------------------------------------------ 清理语义

def test_cleanup_marker() -> None:
    run_dir = new_run_dir("eval136-clean-")
    evaluation = make_eval(run_dir)

    owned = PROJECT_ROOT / ".ai" / "tmp" / ("eval136_owned_%s.gd" % run_dir.name)
    foreign = PROJECT_ROOT / ".ai" / "tmp" / ("eval136_foreign_%s.gd" % run_dir.name)
    owned.write_text("# EVAL136 synthetic artifact\n", encoding="utf-8")
    foreign.write_text("# no marker here\n", encoding="utf-8")
    evaluation.ledger.append({"path": runner._relative(owned), "marker": "EVAL136"})
    evaluation.ledger.append({"path": runner._relative(foreign), "marker": "EVAL136"})

    result = evaluation.cleanup()
    ok("L1: marker-matching file removed", not owned.exists(), str(result["removed"]))
    ok("L2: marker-missing file kept", foreign.exists(), str(result["refused"]))
    ok("L2: refusal recorded", any("foreign" in item for item in result["refused"]),
       str(result["refused"]))
    foreign.unlink(missing_ok=True)


def test_cleanup_directory() -> None:
    run_dir = new_run_dir("eval136-dir-")
    evaluation = make_eval(run_dir)
    staged = run_dir / "staged_dir"
    staged.mkdir()
    (staged / "a.txt").write_text("x", encoding="utf-8")
    evaluation.ledger.append({"path": runner._relative(staged), "marker": ""})
    result = evaluation.cleanup()
    ok("L1: staged dir inside run dir removed", not staged.exists(), str(result["removed"]))

    outside = PROJECT_ROOT / ".ai" / "tmp" / ("eval136_outside_%s" % run_dir.name)
    outside.mkdir()
    evaluation2 = make_eval(new_run_dir("eval136-dir2-"))
    evaluation2.ledger.append({"path": runner._relative(outside), "marker": ""})
    result2 = evaluation2.cleanup()
    ok("L4: directory outside run dir refused", outside.exists(), str(result2["refused"]))
    ok("L4: refusal recorded", bool(result2["refused"]), str(result2["refused"]))
    shutil.rmtree(outside, ignore_errors=True)


def test_stage_refuses_existing() -> None:
    run_dir = new_run_dir("eval136-stage-")
    evaluation = make_eval(run_dir)
    target = PROJECT_ROOT / ".ai" / "tmp" / ("eval136_existing_%s.yaml" % run_dir.name)
    target.write_text("keep me\n", encoding="utf-8")
    result = evaluation.steps.run({
        "id": "stage1",
        "kind": "stage",
        "fixture": "t1_entity_blueprint.yaml",
        "dest": runner._relative(target),
    })
    ok("L3: existing destination → FAIL", result["status"] == "FAIL", str(result))
    ok("L3: existing file untouched", target.read_text(encoding="utf-8") == "keep me\n")
    target.unlink(missing_ok=True)


# ------------------------------------------------------------------ 断言语义

def test_assertions() -> None:
    run_dir = new_run_dir("eval136-assert-")
    evaluation = make_eval(run_dir)
    document = run_dir / "level.json"
    document.write_text(json.dumps({"level": {"id": "x"}, "waves": [{"count": 2}]}),
                        encoding="utf-8")

    good = evaluation.steps.run({
        "id": "a1", "kind": "assert_json", "path": runner._relative(document),
        "checks": [{"path": "waves.length", "equals": 1},
                   {"path": "waves[0].count", "equals": 2}],
    })
    ok("R2: json path assertions pass", good["status"] == "PASS", str(good))

    bad = evaluation.steps.run({
        "id": "a2", "kind": "assert_json", "path": runner._relative(document),
        "checks": [{"path": "waves.length", "equals": 2}],
    })
    ok("R2: wrong expectation → FAIL", bad["status"] == "FAIL", str(bad))

    unresolvable = evaluation.steps.run({
        "id": "a3", "kind": "assert_json", "path": runner._relative(document),
        "checks": [{"path": "nope.deep", "equals": 1}],
    })
    ok("R2: unresolved path → FAIL (not silent None)",
       unresolvable["status"] == "FAIL", str(unresolvable))

    mutant = run_dir / "mutant.json"
    mutated = evaluation.steps.run({
        "id": "a4", "kind": "mutate_json", "source": runner._relative(document),
        "dest": runner._relative(mutant), "set": {"waves[0].count": 9},
    })
    ok("R2: mutate_json writes document", mutated["status"] == "PASS"
       and json.loads(mutant.read_text(encoding="utf-8"))["waves"][0]["count"] == 9,
       str(mutated))

    text_file = run_dir / "probe.gd"
    text_file.write_text("extends SceneTree  # EVAL136\n", encoding="utf-8")
    ok_assert = evaluation.steps.run({
        "id": "a5", "kind": "assert_file",
        "contains_in": {runner._relative(text_file): "EVAL136"},
        "not_contains_in": {runner._relative(text_file): "FAIL"},
        "exists": [runner._relative(text_file)],
    })
    ok("R2: file assertions pass", ok_assert["status"] == "PASS", str(ok_assert))


# ------------------------------------------------------------------ 端到端合成任务

def test_synthetic_task() -> None:
    run_dir = new_run_dir("eval136-e2e-")
    evaluation = make_eval(run_dir)
    script = run_dir / "synthetic_step.py"
    script.write_text(
        "import pathlib, sys\n"
        "pathlib.Path(sys.argv[1]).write_text('EVAL136 synthetic\\n', encoding='utf-8')\n"
        "print('synthetic ok')\n",
        encoding="utf-8",
    )
    artifact = run_dir / "generated.txt"
    tasks = [{
        "id": "TX",
        "title": "synthetic",
        "requirement": "synthetic",
        "required_phases": ["plan"],
        "attempts": [{
            "name": "only",
            "kind": "initial",
            "steps": [{
                "id": "s1", "phase": "plan", "kind": "tool",
                "argv": [str(script), str(artifact)],
                "contains": ["synthetic ok"],
                "generated": [str(artifact)],
                "marker": "EVAL136",
            }],
        }],
        "verify": [],
    }]
    report = evaluation.run(tasks)
    task = report["tasks"][0]
    ok("R1: synthetic task PASS", task["verdict"] == "PASS", str(task.get("blocking")))
    ok("R1: report has metrics", "first_pass_rate" in report["metrics"]
       and report["metrics"]["tasks_total"] == 1)
    ok("R1: report keeps baselines before/after",
       "before" in report["baselines"] and "after" in report["baselines"])
    ok("R1: cleanup removed generated artifact", not artifact.exists(),
       str(report["cleanup"]["removed"]))
    ok("R1: no cleanup refusals", report["cleanup"]["refused"] == [],
       str(report["cleanup"]["refused"]))
    ok("R1: human_interventions default 0",
       report["metrics"]["human_interventions"] == 0)


def test_expect_failure_attempt() -> None:
    """A1：标记为 expect_failure 的尝试即使逐步骤符合预期，也不能结束任务尝试链。"""
    run_dir = new_run_dir("eval136-expect-")
    evaluation = make_eval(run_dir)
    script = run_dir / "expect_step.py"
    script.write_text(
        "import sys\n"
        "sys.exit(1 if sys.argv[1] == 'fail' else 0)\n",
        encoding="utf-8",
    )
    tasks = [{
        "id": "TY",
        "title": "expect_failure",
        "required_phases": ["plan"],
        "attempts": [
            {
                "name": "falsify",
                "kind": "initial",
                "expect_failure": True,
                "steps": [{
                    "id": "f1", "phase": "plan", "kind": "tool",
                    "argv": [str(script), "fail"], "expect_exit": 1,
                }],
            },
            {
                "name": "deliver",
                "kind": "plan_revision",
                "steps": [{
                    "id": "f2", "phase": "plan", "kind": "tool",
                    "argv": [str(script), "ok"],
                }],
            },
        ],
        "verify": [],
    }]
    report = evaluation.run(tasks)
    task = report["tasks"][0]
    ok("A1: expected-failure attempt does not end the chain",
       len(task["attempts"]) == 2, str(task["attempts"]))
    ok("A1: expected-failure attempt marked not passed",
       task["attempts"][0]["passed"] is False and task["attempts"][0]["steps_as_expected"],
       str(task["attempts"][0]))
    ok("A1: task still PASS via revision", task["verdict"] == "PASS", str(task.get("blocking")))
    ok("A1: first_pass stays False", task.get("first_pass") is False)
    ok("A1: plan revision credited",
       report["metrics"]["plan_revision_success_rate"]["numerator"] == 1,
       str(report["metrics"]["plan_revision_success_rate"]))


def main() -> int:
    try:
        test_cleanup_marker()
        test_cleanup_directory()
        test_stage_refuses_existing()
        test_assertions()
        test_synthetic_task()
        test_expect_failure_attempt()
    finally:
        cleanup()
    if _failures:
        print("FAIL: %d evaluation runner check(s) failed" % len(_failures))
        return 1
    print("PASS: evaluation runner (%d checks)" % _checks)
    return 0


if __name__ == "__main__":
    sys.exit(main())
