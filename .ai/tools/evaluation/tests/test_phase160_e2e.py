#!/usr/bin/env python3
"""Phase 1.60 真实端到端验证（任务书 §8.5）——真实 Godot 证据 + 完整链路。

执行前提：`.ai/tmp/p160_e2e/evidence` 已由 feature_behavior_evidence.py
（真实 Godot headless）采集 health / collect_pickup / save_game 三类行为。

链路：真实 Feature -> Behavior Probe -> Evidence Collector -> Validator ->
      Binding Validation -> Baseline Validation -> Evaluation

用例：
    E1 正常证据 + 正确绑定 -> VERIFIED_PASS（exit 0）
    E2 证据包篡改（改观测 + 不重签）-> INVALID_EVIDENCE（exit 1）
    E3 Binding 缺失（任务声明 expected_source）-> INCOMPLETE binding_missing
    E4 Baseline 篡改副本 -> 绑定门禁 NOT_EVALUATED baseline_digest_mismatch
    E5 Holdout 缺失 -> NOT_EVALUATED holdout_unavailable（不降级为 PASS）

用法：python .ai/tools/evaluation/tests/test_phase160_e2e.py --evidence-dir <dir>
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
EVAL_DIR = os.path.dirname(_HERE)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(EVAL_DIR)))
COLLECTOR = os.path.join(PROJECT_ROOT, ".ai", "tools", "scene_composer",
                         "feature_behavior_evidence.py")
for _path in (_HERE, EVAL_DIR, os.path.join(PROJECT_ROOT, ".ai", "tools", "validator")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import evidence_adapter as adapter                               # noqa: E402
import evidence_eval                                              # noqa: E402
import trace_bindings as tb                                       # noqa: E402
import baseline_lifecycle as bl                                   # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_checks = 0
_failures: list = []
_temp_dirs: list = []


def ok(name, condition, detail=""):
    global _checks
    _checks += 1
    print(("PASS: " if condition else "FAIL: ") + name + ("" if condition else " | " + str(detail)[:300]))
    if not condition:
        _failures.append(name)


def new_dir(prefix):
    directory = tempfile.mkdtemp(prefix=prefix, dir=os.path.join(PROJECT_ROOT, ".ai", "tmp"))
    _temp_dirs.append(directory)
    return directory


def run_eval(tasks, evidence_dir, bindings=None, tasks_file=None):
    argv = ["--task", *tasks, "--evidence-dir", evidence_dir]
    if bindings is not None:
        path = os.path.join(new_dir("p160-bind-"), "bindings.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(bindings, handle)
        argv += ["--bindings", path]
    if tasks_file:
        argv += ["--tasks-file", tasks_file]
    return evidence_eval.main(argv)


def fresh_evidence_dir() -> str:
    """无参数运行时在隔离目录内真实采集；不读写任何历史 Evidence 目录。"""
    target = new_dir("p160-evidence-")
    command = [sys.executable, COLLECTOR,
               "--feature", "health", "--feature", "collect_pickup",
               "--feature", "save_game", "--evidence-out", target]
    completed = subprocess.run(command, cwd=PROJECT_ROOT, text=True,
                               capture_output=True, encoding="utf-8",
                               stdin=subprocess.DEVNULL, timeout=240)
    if completed.returncode != 0:
        print("FAIL: isolated evidence collection failed (exit=%d)"
              % completed.returncode)
        print((completed.stdout or "")[-800:])
        print((completed.stderr or "")[-800:])
        return ""
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default="",
                        help="optional existing evidence dir; default collects into an "
                             "isolated .ai/tmp directory")
    args = parser.parse_args()
    eval_root = os.path.join(PROJECT_ROOT, ".ai", "tmp", "eval")
    eval_before = set(os.listdir(eval_root)) if os.path.isdir(eval_root) else set()
    evidence_dir = args.evidence_dir or fresh_evidence_dir()
    if not evidence_dir:
        return 1

    # ---- E1: 正常证据 + 默认绑定 -> exit 0
    exit_code = run_eval(["E1", "E2", "E3"], evidence_dir)
    ok("E2E-1: real evidence + valid bindings -> exit 0 (VERIFIED_PASS)",
       exit_code == 0, "exit=%s" % exit_code)

    # ---- E2: 证据篡改 -> INVALID_EVIDENCE exit 1
    tampered_dir = new_dir("p160-tamper-")
    shutil.copytree(evidence_dir, tampered_dir, dirs_exist_ok=True)
    name = next(n for n in sorted(os.listdir(tampered_dir)) if n.endswith("bundle.json"))
    path = os.path.join(tampered_dir, name)
    with open(path, "r", encoding="utf-8") as handle:
        bundle = json.load(handle)
    for block in bundle.get("features") or []:
        if block.get("feature") == "health":
            block["behaviors"][0]["actual"][0]["observed"] = 999
            break
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(bundle, handle)          # 不重签：payload_sha256 不再匹配
    exit_code = run_eval(["E2"], tampered_dir)
    ok("E2E-2: tampered evidence -> INVALID_EVIDENCE (exit 1)",
       exit_code == 1, "exit=%s" % exit_code)

    # ---- E3: 任务声明 expected_source 但绑定缺失 -> INCOMPLETE binding_missing
    tasks_doc = {
        "schema": {"id": "evaluation_evidence_tasks", "version": 1},
        "run": {"evidence_dir": evidence_dir, "max_age_hours": 24,
                "collector": "scene_composer/feature_behavior_evidence.py",
                "artifact_root": ".ai/tmp/behavior"},
        "tasks": [{"id": "X1", "title": "binding required", "mode": "evidence",
                   "feature": "health", "behavior": "damage",
                   "expected_source": "behavior_contract",
                   "expect": [{"check": "health.current", "target": ".", "equals": 1}]}],
    }
    tasks_path = os.path.join(new_dir("p160-tasks-"), "tasks.yaml")
    # YAML 复用 evidence_eval 的加载器；手写 JSON 也能被 PyYAML 解析
    with open(tasks_path, "w", encoding="utf-8") as handle:
        json.dump(tasks_doc, handle)
    exit_code = run_eval(["X1"], evidence_dir,
                         bindings={"schema": tb.SCHEMA, "schema_version": 1,
                                   "bindings": []},
                         tasks_file=tasks_path)
    ok("E2E-3: declared expected_source with no binding -> INCOMPLETE (exit 2)",
       exit_code == 2, "exit=%s" % exit_code)

    # ---- E4: 真实基线篡改副本 -> 绑定门禁拒绝
    verified = adapter.load_verified(evidence_dir=evidence_dir,
                                     features=["health"],
                                     artifact_roots=[".ai/tmp/behavior"])
    real_registry = bl.REGISTRY_PATH
    bl.REGISTRY_PATH = os.path.join(new_dir("p160-reg-"), "registry.json")
    waves_path = os.path.join(adapter.VALIDATOR_DIR, "baselines", "waves.json")
    with open(waves_path, "r", encoding="utf-8") as handle:
        document = json.load(handle)
    tampered = copy.deepcopy(document)
    tampered["events"][0]["data"]["mode"] = "boss"
    tampered_path = os.path.join(new_dir("p160-bl-"), "waves_tampered.json")
    with open(tampered_path, "w", encoding="utf-8") as handle:
        json.dump(tampered, handle)
    binding = real_binding = tb.get_binding(tb.load_bindings(), "health", "damage")
    binding = copy.deepcopy(binding)
    binding["baseline_id"] = "waves"
    binding["baseline_path"] = tampered_path
    task = {"id": "E4", "feature": "health", "behavior": "damage",
            "expected_source": "behavior_contract"}
    record = adapter.evaluate_task(task, verified, adapter.supported_set(),
                                   bindings={"bindings": [binding]})
    bl.REGISTRY_PATH = real_registry
    ok("E2E-4: tampered real baseline copy -> NOT_EVALUATED baseline_digest_mismatch",
       record["evaluation_status"] == adapter.NOT_EVALUATED
       and record["behaviors"][0]["reason"] == "baseline_digest_mismatch",
       json.dumps(record["behaviors"][0], ensure_ascii=False)[:250])

    # ---- E5: Holdout 缺失 -> NOT_EVALUATED holdout_unavailable（报告独立成块，
    #      不降级为 PASS；退出码语义按 Phase 1.58 契约只看主任务，不擅改）
    argv = ["--task", "E5", "--evidence-dir", evidence_dir, "--json"]
    import io
    from contextlib import redirect_stdout
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        evidence_eval.main(argv)
    report = json.loads(buffer.getvalue())
    holdout_tasks = report.get("holdout", {}).get("tasks") or []
    ok("E2E-5: holdout unavailable -> NOT_EVALUATED holdout_unavailable (separate block)",
       holdout_tasks and holdout_tasks[0]["evaluation_status"] == adapter.NOT_EVALUATED
       and holdout_tasks[0]["reason"] == "holdout_unavailable",
       json.dumps(holdout_tasks[:1], ensure_ascii=False)[:250])

    for directory in _temp_dirs:
        shutil.rmtree(directory, ignore_errors=True)
    # evidence_eval 的默认报告根是 .ai/tmp/eval；只清理本次测试新增的目录。
    if os.path.isdir(eval_root):
        for name in set(os.listdir(eval_root)) - eval_before:
            shutil.rmtree(os.path.join(eval_root, name), ignore_errors=True)
    print("\n%d check(s), %d failure(s)" % (_checks, len(_failures)))
    if _failures:
        print("FAIL: " + "; ".join(_failures[:5]))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
