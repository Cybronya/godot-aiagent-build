#!/usr/bin/env python3
"""Mutation Harness —— 受控缺陷 → 真实执行 → 现有验证链路 → Verdict（Phase 1.59）。

一次 Mutation Run 的固定顺序（任何一步失败都**不会**被折算成 MUTANT_KILLED）：

    1. 静态前置检查（Feature/Behavior 在支持集内、目标文件非链接、哈希匹配）
    2. 生成本次独有的隔离副本 `Features/`（仓库只读）
    3. Negative Control：原始副本 → 采集器 → Validator → Evaluation，必须 VERIFIED_PASS
    4. 应用 Operator（唯一锚点、空 diff 拒绝、块结构守恒）→ 只允许目标文件变化
    5. Positive Control：mutant 副本 → 采集器 → Validator → Evaluation
    6. Effectiveness Check：control 与 mutant 的**同一条观测**必须按目录声明的方式不同
    7. Recovery：恢复副本原字节 → 再跑一次，必须 VERIFIED_PASS
    8. 仓库看守：`Features/**` 的 sha256 快照前后必须完全一致
    9. Verdict 汇总 + 报告（`reports/<mutation>-<run_id>.json`）

复用（不重写）：
    采集器  scene_composer/feature_behavior_evidence.py（CLI，`--features-dir` 指向副本）
    Validator/Evaluation  evaluation/evidence_eval.py（CLI，per-mutation 临时 tasks 文件）

状态语义（与 Evaluation 状态**不同层**，两者都保留在报告里）：
    MUTANT_KILLED      — mutation 生效且现有链路给出了非通过结论（这是**成功**的检测）
    MUTANT_SURVIVED    — mutation 生效但链路仍 VERIFIED_PASS（漏检）
    INVALID_MUTANT     — mutation 应用失败/无行为差异（分子分母都不算）
    HARNESS_ERROR      — 副本、控制组、恢复或仓库看守出问题（结论不可归因）
    TIMEOUT            — 采集器/评估子进程超时
    NOT_RUN            — 前置条件不满足（catalog 过期、Feature/Behavior 不在支持集等）
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
_EVALUATION = os.path.dirname(_HERE)
_TOOLS = os.path.dirname(_EVALUATION)
PROJECT_ROOT = os.path.dirname(os.path.dirname(_TOOLS))

for _path in (_HERE, _EVALUATION):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import catalog                                                     # noqa: E402
import operators                                                   # noqa: E402
import workspace                                                   # noqa: E402

try:
    import yaml
except ImportError:                                                # pragma: no cover
    print("FAIL: PyYAML is required.", file=sys.stderr)
    raise SystemExit(2)

COLLECTOR = os.path.join(_TOOLS, "scene_composer", "feature_behavior_evidence.py")
EVIDENCE_EVAL = os.path.join(_EVALUATION, "evidence_eval.py")
PROBE = os.path.join(_TOOLS, "scene_composer", "probes", "feature_behavior_probe.gd")

MUTANT_KILLED = "MUTANT_KILLED"
MUTANT_SURVIVED = "MUTANT_SURVIVED"
INVALID_MUTANT = "INVALID_MUTANT"
HARNESS_ERROR = "HARNESS_ERROR"
TIMEOUT = "TIMEOUT"
NOT_RUN = "NOT_RUN"
VERDICTS = (MUTANT_KILLED, MUTANT_SURVIVED, INVALID_MUTANT, HARNESS_ERROR, TIMEOUT, NOT_RUN)
NON_PASS_EVALUATION = ("VERIFIED_FAIL", "INVALID_EVIDENCE", "EVALUATION_ERROR")

SCHEMA = "evaluation_mutation_run"
SCHEMA_VERSION = 1


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _relative(path: str) -> str:
    try:
        return os.path.relpath(os.path.abspath(path), PROJECT_ROOT).replace("\\", "/")
    except (OSError, ValueError):
        return path


def _tail(text: str, limit: int = 1200) -> str:
    text = (text or "").strip()
    return text[-limit:]


def _run(argv, timeout: int, cwd: str = "") -> dict:
    """子进程执行：超时与启动失败都必须可区分（不能都变成"失败=检出"）。"""
    started = time.time()
    try:
        proc = subprocess.run(argv, cwd=cwd or PROJECT_ROOT, capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=timeout, stdin=subprocess.DEVNULL)
        return {"argv": [_relative(argv[0])] + argv[1:], "exit": proc.returncode,
                "stdout": proc.stdout or "", "stderr": proc.stderr or "",
                "duration_s": round(time.time() - started, 3),
                "timed_out": False, "start_error": ""}
    except subprocess.TimeoutExpired as exc:
        return {"argv": [_relative(argv[0])] + argv[1:], "exit": None,
                "stdout": (exc.stdout or "") if isinstance(exc.stdout, str) else "",
                "stderr": (exc.stderr or "") if isinstance(exc.stderr, str) else "",
                "duration_s": round(time.time() - started, 3),
                "timed_out": True, "start_error": ""}
    except OSError as exc:
        return {"argv": [_relative(argv[0])] + argv[1:], "exit": None, "stdout": "",
                "stderr": "", "duration_s": round(time.time() - started, 3),
                "timed_out": False, "start_error": repr(exc)}


def _stage(result: dict) -> str:
    if result.get("timed_out"):
        return TIMEOUT
    if result.get("start_error"):
        return HARNESS_ERROR
    return "OK"


def collect(feature: str, features_dir: str, out_dir: str, bundle_id: str,
            replay: int, timeout: int, godot: str = "") -> dict:
    """跑一次真实采集（现有采集器，只换 --features-dir / --evidence-out）。

    Phase 1.63（M06 根因修复）：每次 collect 用唯一 --user-dir-tag 获得**隔离的
    user:// 目录**——control / mutant / recovery 互不残留、不依赖仓库外历史数据
    （`user://saved_games/_last.txt` 跨 run 残留曾是 M06 判 INVALID 的根因）。
    采集结束即清理该隔离目录（只删自己创建的那一个）。
    """
    os.makedirs(out_dir, exist_ok=True)
    tag = "mutation-%s-%s" % (re.sub(r"[^A-Za-z0-9_-]", "-", bundle_id)[:60],
                              uuid.uuid4().hex[:8])
    argv = [sys.executable, COLLECTOR, "--feature", feature,
            "--features-dir", features_dir, "--evidence-out", out_dir,
            "--bundle-id", bundle_id, "--replay", str(int(replay)),
            "--user-dir-tag", tag]
    if godot:
        argv += ["--godot", godot]
    result = _run(argv, timeout)
    # 清理本次采集的隔离 user:// 目录（只删 basename == tag 的那一个）。
    user_dir_removed = False
    home = os.path.expanduser("~")
    for base in (os.environ.get("APPDATA", ""),
                 os.path.join(home, ".local", "share"),
                 os.path.join(home, "Library", "Application Support")):
        candidate = os.path.join(base, tag) if base else ""
        if candidate and os.path.isdir(candidate) and \
                os.path.basename(candidate) == tag:
            shutil.rmtree(candidate, ignore_errors=True)
            user_dir_removed = True
            break
    bundle = os.path.join(out_dir, "%s.json" % bundle_id)
    return {"stage": _stage(result), "exit": result.get("exit"),
            "duration_s": result.get("duration_s"), "timed_out": result.get("timed_out"),
            "exit_ok": result.get("exit") == 0,
            "bundle": bundle if os.path.isfile(bundle) else "",
            "user_dir_tag": tag, "user_dir_isolated": True,
            "user_dir_removed": user_dir_removed,
            "output_tail": _tail(result.get("stdout", "") + "\n" + result.get("stderr", "")),
            "command": result.get("argv")}


def evaluate(tasks_file: str, evidence_dir: str, runs_dir: str, timeout: int) -> dict:
    """走现有 Phase 1.58 入口：Validator + Adapter + Evaluation 都在里面。"""
    argv = [sys.executable, EVIDENCE_EVAL, "--tasks-file", tasks_file,
            "--evidence-dir", evidence_dir, "--no-collect",
            "--runs-dir", runs_dir, "--json"]
    result = _run(argv, timeout)
    report = None
    if result.get("exit") is not None and result.get("stdout"):
        text = result["stdout"].strip()
        start = text.find("{")
        if start >= 0:
            try:
                report = json.loads(text[start:])
            except ValueError:
                report = None
    record = {"stage": _stage(result), "exit": result.get("exit"),
              "duration_s": result.get("duration_s"), "timed_out": result.get("timed_out"),
              "output_tail": _tail(result.get("stderr", "")) if report is None else "",
              "command": result.get("argv"), "report": report}
    if report is None:
        record["evaluation_status"] = ""
        record["validator_status"] = ""
        record["reason"] = "report_unavailable"
        return record
    tasks = report.get("tasks") or []
    task = tasks[0] if tasks else {}
    record["evaluation_status"] = str(task.get("evaluation_status") or "")
    record["validator_status"] = str(task.get("validator_status") or "")
    record["reason"] = str(task.get("reason") or "")
    record["detail"] = str(task.get("detail") or "")
    record["evidence_summary"] = (report.get("metrics") or {}).get("evidence_validation") or {}
    record["behavior_evaluation"] = (report.get("metrics") or {}).get("behavior_evaluation") or {}
    record["bundle_rejections"] = (report.get("evidence") or {}).get("rejected_bundles") or []
    return record


def read_bundle(bundle_path: str) -> dict:
    try:
        with open(bundle_path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def behavior_record(bundle: dict, feature: str, behavior: str) -> dict:
    for group in bundle.get("features") or []:
        if group.get("feature") != feature:
            continue
        for record in group.get("behaviors") or []:
            if record.get("behavior") == behavior:
                return record
    return {}


def find_observation(record: dict, check: str, target: str = ".",
                     entry: str = "") -> dict:
    # 证据包里逐条观测叫 `actual`（`checks` 是更早的字段名，保留兼容）。
    for item in (record.get("actual") or record.get("checks") or []):
        if (str(item.get("check") or "") == check
                and str(item.get("target", ".")) == target
                and str(item.get("entry", "")) == entry):
            return item
    return {}


def observations_differ(control: dict, mutant: dict) -> bool:
    if not control or not mutant:
        return False
    return (control.get("observed") != mutant.get("observed")
            or control.get("observed_args") != mutant.get("observed_args"))


def make_tasks_file(run_root: str, entry: dict) -> str:
    """per-mutation 的临时 Evaluation 任务（不改 `evidence_tasks.yaml`）。"""
    task = {
        "id": str(entry["mutation_id"]),
        "title": "mutation %s on %s/%s" % (entry["mutation_id"], entry["feature_id"],
                                           entry["behavior_id"]),
        "requirement": str(entry.get("expected_behavior_change") or ""),
        "mode": "evidence",
        "feature": entry["feature_id"],
        "behavior": entry["behavior_id"],
        "expect": entry["evaluation"]["expect"],
    }
    document = {"schema": {"id": "evaluation_evidence_tasks", "version": 1},
                "run": {"artifact_root": ".ai/tmp/behavior"},
                "tasks": [task]}
    path = os.path.join(run_root, "tasks.yaml")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        yaml.safe_dump(document, handle, allow_unicode=True, sort_keys=False)
    return path


def _phase_report(name: str, collection: dict, evaluation: dict) -> dict:
    return {"name": name, "collection": collection,
            "evaluation": {key: value for key, value in evaluation.items()
                           if key != "report"}}


def _verdict(report: dict) -> tuple:
    """把上面各阶段的事实折算成 Verdict（顺序即优先级）。"""
    stages = [report["controls"]["control"]["collection"]["stage"],
              report["controls"]["mutant"]["collection"]["stage"],
              report["controls"]["control"]["evaluation"]["stage"],
              report["controls"]["mutant"]["evaluation"]["stage"]]
    if report.get("recovery"):
        stages.append(report["recovery"]["collection"]["stage"])
        stages.append(report["recovery"]["evaluation"]["stage"])
    if any(stage == TIMEOUT for stage in stages):
        return TIMEOUT, "a collector/evaluation subprocess timed out"
    if any(stage == HARNESS_ERROR for stage in stages):
        return HARNESS_ERROR, "a subprocess could not be started"
    if report["repo_guard"]["changed"]:
        return HARNESS_ERROR, "repository Features/** changed during the run"
    if not report["controls"]["control"]["verified"]:
        return HARNESS_ERROR, "negative control did not evaluate to VERIFIED_PASS"
    if not report["effectiveness"]["effective"]:
        return INVALID_MUTANT, report["effectiveness"]["reason"]
    if not report["recovery"]["verified"]:
        return HARNESS_ERROR, "recovered implementation did not evaluate to VERIFIED_PASS"
    mutated = report["controls"]["mutant"]["evaluation"]
    status = mutated.get("evaluation_status") or ""
    if status in NON_PASS_EVALUATION:
        return MUTANT_KILLED, "mutant evaluation is %s (%s)" % (status, mutated.get("reason") or "-")
    if status == "VERIFIED_PASS":
        return MUTANT_SURVIVED, "mutant evaluation is still VERIFIED_PASS"
    return HARNESS_ERROR, "mutant evaluation is not decidable: %r" % status


def run_mutation(entry: dict, options: dict) -> dict:
    """执行一条 mutation，返回完整报告（含 Verdict）。异常不外抛，记成 HARNESS_ERROR。"""
    started = time.time()
    mutation_id = str(entry["mutation_id"])
    run_id = str(options.get("run_id") or uuid.uuid4().hex[:8])
    runs_root = options.get("runs_root") or workspace.RUNS_ROOT
    replay = int(options.get("replay") or 2)
    timeout = int(options.get("timeout") or 240)
    godot = str(options.get("godot") or "")

    report = {
        "schema": SCHEMA, "schema_version": SCHEMA_VERSION,
        "mutation_id": mutation_id, "run_id": run_id, "started_at": now_iso(),
        "git": {"head": _git("rev-parse", "HEAD"), "branch": _git("rev-parse", "--abbrev-ref",
                                                                  "HEAD")},
        "catalog": {key: entry.get(key) for key in
                    ("mutation_id", "feature_id", "behavior_id", "mutation_type",
                     "target_file", "target_function", "operator", "precondition",
                     "expected_behavior_change", "risk_level", "status")},
        "tools": {"collector": _sha(COLLECTOR), "evaluation": _sha(EVIDENCE_EVAL),
                  "validator": _sha(os.path.join(_TOOLS, "validator",
                                                 "check_behavior_evidence.py")),
                  "adapter": _sha(os.path.join(_EVALUATION, "evidence_adapter.py")),
                  "probe": _sha(PROBE)},
        "isolation": {}, "static": {}, "controls": {}, "effectiveness": {},
        "recovery": {}, "repo_guard": {}, "verdict": "", "verdict_reason": "",
        "timings": {},
    }
    try:
        _execute(report, entry, options, run_id=run_id, runs_root=runs_root,
                 replay=replay, timeout=timeout, godot=godot)
    except Exception as exc:                                        # noqa: BLE001
        report["verdict"] = HARNESS_ERROR
        report["verdict_reason"] = "harness exception: %r" % (exc,)
    report["finished_at"] = now_iso()
    report["timings"]["total_s"] = round(time.time() - started, 2)

    if options.get("clean") and report["verdict"] in (MUTANT_KILLED, INVALID_MUTANT,
                                                      NOT_RUN, MUTANT_SURVIVED):
        root = report.get("isolation", {}).get("run_root") or ""
        if root:
            report["cleanup"] = workspace.remove_run_dir(root, run_id, runs_root)
    return report


def _execute(report, entry, options, run_id, runs_root, replay, timeout, godot) -> None:
    mutation_id = str(entry["mutation_id"])
    supported, supported_info = catalog.supported_pairs()
    static = catalog.preconditions(entry, supported)
    report["static"] = {"preconditions": static, "supported": {
        "features": supported_info["feature_count"],
        "behaviors": supported_info["behavior_count"]}}
    if not static.get("ok"):
        report["verdict"] = NOT_RUN
        report["verdict_reason"] = "%s: %s" % (static.get("reason"), static.get("detail", ""))
        return

    report["isolation"]["repository_features"] = _relative(workspace.FEATURES_DIR)
    repo_before = workspace.snapshot(workspace.FEATURES_DIR)
    run_root = workspace.create_run_dir(runs_root, mutation_id, run_id)
    report["isolation"]["run_root"] = run_root
    try:
        features_copy = workspace.copy_features(run_root, run_id, mutation_id)
        target_rel = str(entry["target_file"]).replace("\\", "/")
        target = os.path.join(run_root, *target_rel.split("/"))
        workspace.require_inside(target, run_root, "mutant target")
        original = workspace.read_text(target)
        report["static"]["source_sha256"] = workspace.sha256_bytes(original.encode("utf-8"))
        report["static"]["anchor_count"] = original.count(str(entry["anchor"]))

        tasks_file = make_tasks_file(run_root, entry)
        control_dir = os.path.join(run_root, "evidence", "control")
        mutant_dir = os.path.join(run_root, "evidence", "mutant")
        recovery_dir = os.path.join(run_root, "evidence", "recovery")

        # ---- 3. Negative Control（原始副本）
        control_collection = collect(entry["feature_id"], features_copy, control_dir,
                                     "%s-control" % run_id, replay, timeout, godot)
        control_evaluation = evaluate(tasks_file, control_dir,
                                      os.path.join(run_root, "eval", "control"), timeout)
        report["controls"]["control"] = {
            "collection": control_collection, "evaluation": control_evaluation,
            "verified": control_evaluation.get("evaluation_status") == "VERIFIED_PASS"}
        if control_collection["stage"] in (TIMEOUT, HARNESS_ERROR) or not control_collection["bundle"]:
            report["verdict"] = control_collection["stage"] if control_collection["stage"] in (
                TIMEOUT, HARNESS_ERROR) else HARNESS_ERROR
            report["verdict_reason"] = "negative control produced no evidence bundle"
            report["repo_guard"] = _repo_guard(repo_before)
            return
        # 控制组必须自己先 PASS，否则后面看到的"差异"无从归因（例如 replay<2 让
        # Validator 报 INCOMPLETE）。这种情况是 harness 设置错误，不是检出。
        if not report["controls"]["control"]["verified"]:
            report["verdict"] = HARNESS_ERROR
            report["verdict_reason"] = ("negative control did not evaluate to VERIFIED_PASS (%s: %s)"
                                        % (control_evaluation.get("evaluation_status"),
                                           control_evaluation.get("reason")))
            report["repo_guard"] = _repo_guard(repo_before)
            return

        # ---- 4. 应用 Operator（只允许目标文件变化）
        copy_before = workspace.snapshot(features_copy)
        try:
            mutated = operators.apply_operator(str(entry.get("operator") or ""), original,
                                               str(entry["anchor"]),
                                               str(entry.get("replacement") or ""))
        except operators.OperatorError as exc:
            report["verdict"] = INVALID_MUTANT
            report["verdict_reason"] = "operator rejected the mutation: %s" % exc
            report["repo_guard"] = _repo_guard(repo_before)
            return
        workspace.write_text(target, mutated)
        copy_after = workspace.snapshot(features_copy)
        changes = workspace.diff_snapshots(copy_before, copy_after)
        report["mutation"] = {
            "target_file": target_rel,
            "source_sha256": workspace.sha256_bytes(original.encode("utf-8")),
            "mutated_sha256": workspace.sha256_bytes(mutated.encode("utf-8")),
            "changed_files": changes,
            "diff": operators.unified_diff(target_rel, original, mutated),
            "diff_applied": 1 if changes else 0,
        }
        workspace.write_text(os.path.join(run_root, "mutation.diff"),
                             report["mutation"]["diff"])
        target_in_copy = os.path.relpath(target, features_copy).replace("\\", "/")
        unexpected = unexpected_changes(changes, target_in_copy)
        if unexpected or not changes:
            report["verdict"] = INVALID_MUTANT
            report["verdict_reason"] = ("mutation changed unexpected files: %s" % unexpected
                                        if unexpected else "mutation changed nothing")
            report["repo_guard"] = _repo_guard(repo_before)
            return

        # ---- 5. Positive Control（mutant 副本）
        mutant_collection = collect(entry["feature_id"], features_copy, mutant_dir,
                                    "%s-mutant" % run_id, replay, timeout, godot)
        mutant_evaluation = evaluate(tasks_file, mutant_dir,
                                     os.path.join(run_root, "eval", "mutant"), timeout)
        report["controls"]["mutant"] = {
            "collection": mutant_collection, "evaluation": mutant_evaluation,
            "verified": mutant_evaluation.get("evaluation_status") == "VERIFIED_PASS"}

        # ---- 6. Effectiveness Check（同一条观测的真实差异）
        effectiveness = _effectiveness(entry, control_collection, mutant_collection)
        report["effectiveness"] = effectiveness

        # ---- 7. Recovery（副本原字节 + 再跑一次）
        workspace.write_text(target, original)
        restored = workspace.sha256_file(target) == report["static"]["source_sha256"]
        restored &= workspace.snapshot(features_copy) == copy_before
        recovery_collection = collect(entry["feature_id"], features_copy, recovery_dir,
                                      "%s-recovery" % run_id, replay, timeout, godot)
        recovery_evaluation = evaluate(tasks_file, recovery_dir,
                                       os.path.join(run_root, "eval", "recovery"), timeout)
        report["recovery"] = {
            "restored_byte_for_byte": restored,
            "collection": recovery_collection, "evaluation": recovery_evaluation,
            "verified": restored and recovery_evaluation.get("evaluation_status") == "VERIFIED_PASS"}

        # ---- 8. 仓库看守
        report["repo_guard"] = _repo_guard(repo_before)

        # ---- 9. Verdict
        verdict, reason = _verdict(report)
        report["verdict"] = verdict
        report["verdict_reason"] = reason
    finally:
        # 即使中途 return/异常，也要留下仓库看守结论（这是安全边界，不是可选步骤）。
        if not report.get("repo_guard"):
            report["repo_guard"] = _repo_guard(repo_before)


def _effectiveness(entry: dict, control_collection: dict,
                   mutant_collection: dict) -> dict:
    effect = entry.get("effectiveness") or {}
    check = str(effect.get("check") or "")
    target = str(effect.get("target", "."))
    item_key = str(effect.get("entry", ""))
    result = {"check": check, "target": target, "entry": item_key, "effective": False,
              "reason": "", "baseline_predicate": effect.get("baseline"),
              "mutant_predicate": effect.get("mutant")}
    if not control_collection.get("bundle") or not mutant_collection.get("bundle"):
        result["reason"] = "missing evidence bundle for effectiveness comparison"
        return result
    control_record = behavior_record(read_bundle(control_collection["bundle"]),
                                     entry["feature_id"], entry["behavior_id"])
    mutant_record = behavior_record(read_bundle(mutant_collection["bundle"]),
                                    entry["feature_id"], entry["behavior_id"])
    control_obs = find_observation(control_record, check, target, item_key)
    mutant_obs = find_observation(mutant_record, check, target, item_key)
    result["control_observation"] = control_obs
    result["mutant_observation"] = mutant_obs
    # 采集侧自报状态只用于诊断："跑不起来"（INSUFFICIENT / action_unavailable）
    # 既不是行为差异，也不能当成检出。
    result["control_record"] = {"status": control_record.get("status"),
                                "reason": control_record.get("reason")}
    result["mutant_record"] = {"status": mutant_record.get("status"),
                               "reason": mutant_record.get("reason")}
    if not control_obs or not mutant_obs:
        result["reason"] = ("the targeted check was not observed in both runs "
                            "(control=%s/%s, mutant=%s/%s)"
                            % (control_record.get("status"), control_record.get("reason"),
                               mutant_record.get("status"), mutant_record.get("reason")))
        return result
    # 谓词只写断言部分（equals/count/...），check 来自 effectiveness.check；
    # Validator 的比较语义需要 check 才能选对分支。
    baseline_predicate = dict(effect.get("baseline") or {})
    baseline_predicate.setdefault("check", check)
    mutant_predicate = dict(effect.get("mutant") or {})
    mutant_predicate.setdefault("check", check)
    baseline_ok = catalog.stage_expected(baseline_predicate, control_obs)
    mutant_ok = catalog.stage_expected(mutant_predicate, mutant_obs)
    result["baseline_holds"] = baseline_ok
    result["mutant_holds"] = mutant_ok
    if baseline_ok is not True:
        result["reason"] = ("unmutated control does not satisfy the declared baseline "
                            "observation (probe or catalog is stale)")
        return result
    if not observations_differ(control_obs, mutant_obs):
        result["reason"] = "mutation produced no observable behavior change"
        return result
    if mutant_ok is not True:
        result["reason"] = "mutant observation does not match the declared defect"
        return result
    result["effective"] = True
    result["reason"] = "control and mutant observations differ as declared"
    return result


def unexpected_changes(changes, target_in_copy: str) -> list:
    """副本快照差异里不属于目标文件的那些（只允许改目标文件的硬校验）。"""
    return [change for change in changes or []
            if str(change.get("file")) != str(target_in_copy)]


def _repo_guard(before: dict) -> dict:
    after = workspace.snapshot(workspace.FEATURES_DIR)
    changes = workspace.diff_snapshots(before, after)
    return {"checked_files": len(after), "changed": bool(changes), "changes": changes}


def _sha(path: str) -> str:
    return workspace.sha256_file(path)


def _git(*args) -> str:
    try:
        proc = subprocess.run(["git", *args], cwd=PROJECT_ROOT, capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=30, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return ""
    return (proc.stdout or "").strip() if proc.returncode == 0 else ""


def summarize(reports) -> dict:
    counts = {verdict: 0 for verdict in VERDICTS}
    for report in reports:
        counts[report.get("verdict") or HARNESS_ERROR] = \
            counts.get(report.get("verdict") or HARNESS_ERROR, 0) + 1
    effective = [report for report in reports
                 if (report.get("effectiveness") or {}).get("effective")]
    return {
        "total": len(reports), "verdicts": counts,
        "effective_mutations": len(effective),
        "killed": counts.get(MUTANT_KILLED, 0),
        "survived": counts.get(MUTANT_SURVIVED, 0),
        "invalid": counts.get(INVALID_MUTANT, 0),
        "harness_error": counts.get(HARNESS_ERROR, 0),
        "timeout": counts.get(TIMEOUT, 0),
        "not_run": counts.get(NOT_RUN, 0),
        "features": sorted({str(report.get("catalog", {}).get("feature_id"))
                            for report in reports}),
        "behaviors": ["%s/%s" % (report.get("catalog", {}).get("feature_id"),
                                 report.get("catalog", {}).get("behavior_id"))
                      for report in reports],
    }
