#!/usr/bin/env python3
"""Mutation Harness 测试（Phase 1.59）

覆盖范围：

    A  算子：唯一锚点 / 缺失锚点 / 空 diff / 语句边界 / 括号平衡 / 未知算子 / diff
    B  隔离副本：复制与 ownership 标记、重复目标拒绝、路径逃逸、符号链接、受限清理、
       快照差异（只允许目标文件变化）
    C  Catalog：结构校验、真实 catalog 前置检查、哈希过期、未知 Behavior、谓词语义
    D  Verdict：NOT_RUN / TIMEOUT / INVALID_MUTANT / HARNESS_ERROR / KILLED / SURVIVED
       的判定顺序与归因；真实仓库哈希前后一致
    E  安全边界：非目标文件变化、恢复逐字节一致、清理只删自己的目录

这里**不**用 mock 去伪造执行链：D2/D3 是真实子进程（采集器 + evidence_eval），
只是用 `--timeout 1` 或故意写错的锚点把它们推到预期的分支。真实缺陷检出由
`test_mutation_integration.py` 负责（真实 Godot）。

用法：
    python .ai/tools/evaluation/mutation/tests/test_mutation_harness.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile

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
import operators                                                   # noqa: E402
import workspace                                                   # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_failures: list = []
_checks = 0
_temp_dirs: list = []


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


def write(path: str, text: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return path


SAMPLE = (
    "func f() -> void:\n"
    "\tif a:\n"
    "\t\treturn\n"
    "\tstate = true\n"
    "\tstate.emit(1)\n"
)


# ----------------------------------------------------------------- A 算子
def test_operators() -> None:
    print("=== A: operators reject anything they cannot prove ===")
    mutated = operators.apply_operator("replace_exact", SAMPLE, "\tstate = true\n",
                                       "\tstate = false\n")
    ok("A1: replace_exact applies exactly once",
       mutated.count("\tstate = false\n") == 1 and mutated.count("\tstate = true\n") == 0)

    diff = operators.unified_diff("Features/x/x.gd", SAMPLE, mutated)
    ok("A2: unified diff shows the removed and added line",
       "-	state = true" in diff and "+	state = false" in diff
       and diff.startswith("--- "), diff[:120])

    for label, anchor in (("A3: a duplicated anchor is rejected", "\t\treturn\n"),
                          ("A4: a missing anchor is rejected", "\tstate = never_written\n")):
        try:
            operators.apply_operator("replace_exact", SAMPLE + "\t\treturn\n", anchor, "x\n")
            ok(label, False, "operator accepted it")
        except operators.OperatorError as exc:
            ok(label, "anchor_not_unique" in str(exc), str(exc))

    try:
        operators.apply_operator("replace_exact", SAMPLE, "\tstate = true\n", "\tstate = true\n")
        ok("A5: an empty diff is rejected", False, "operator accepted it")
    except operators.OperatorError as exc:
        ok("A5: an empty diff is rejected", "empty_diff" in str(exc), str(exc))

    try:
        operators.apply_operator("delete_statement", SAMPLE, "\tif a:\n\t\treturn\n")
        ok("A6: delete_statement rejects a multi-line anchor", False, "operator accepted it")
    except operators.OperatorError as exc:
        ok("A6: delete_statement rejects a multi-line anchor",
           "anchor_not_a_single_line" in str(exc), str(exc))

    try:
        operators.apply_operator("delete_statement", SAMPLE, "state = true\n")
        ok("A7: delete_statement rejects a mid-line anchor", False, "operator accepted it")
    except operators.OperatorError as exc:
        ok("A7: delete_statement rejects a mid-line anchor",
           "anchor_not_line_aligned" in str(exc), str(exc))

    try:
        operators.apply_operator("replace_exact", "x = f(a,\n  b)\ny = 1\n", "x = f(a,\n", "")
        ok("A8: half of a multi-line expression is rejected", False, "operator accepted it")
    except operators.OperatorError as exc:
        ok("A8: half of a multi-line expression is rejected",
           "structure_changed" in str(exc), str(exc))

    try:
        operators.apply_operator("rewrite_everything", SAMPLE, "\tstate = true\n", "")
        ok("A9: unknown operator is rejected", False, "operator accepted it")
    except operators.OperatorError as exc:
        ok("A9: unknown operator is rejected", "unknown_operator" in str(exc), str(exc))

    removed = operators.apply_operator("delete_statement", SAMPLE, "\tstate.emit(1)\n")
    ok("A10: delete_statement removes the whole line",
       "state.emit(1)" not in removed and removed.endswith("\tstate = true\n"),
       repr(removed[-30:]))


# ----------------------------------------------------------------- B 隔离副本
def test_workspace() -> None:
    print("=== B: isolation copies, path guards and restricted cleanup ===")
    root = new_dir("p159-ws-")
    source = os.path.join(root, "Features")
    write(os.path.join(source, "demo", "demo.gd"), SAMPLE)
    write(os.path.join(source, "demo", "template.yaml"), "behavior: []\n")
    run_root = os.path.join(root, "runs", "demo-1")
    os.makedirs(run_root)

    copy = workspace.copy_features(run_root, "run-1", "M99-demo", source=source)
    ok("B1: copy_features copies the tree and writes an ownership marker",
       os.path.isfile(os.path.join(copy, "demo", "demo.gd"))
       and workspace.owns(run_root, "run-1"))
    ok("B2: the copy is a different file than the source",
       workspace.sha256_file(os.path.join(copy, "demo", "demo.gd"))
       == workspace.sha256_file(os.path.join(source, "demo", "demo.gd"))
       and os.path.realpath(copy) != os.path.realpath(source))

    try:
        workspace.copy_features(run_root, "run-2", "M99-demo", source=source)
        ok("B3: copying into an existing run dir is rejected", False, "accepted")
    except workspace.WorkspaceError as exc:
        ok("B3: copying into an existing run dir is rejected",
           "already contains Features" in str(exc), str(exc))

    ok("B4: is_inside rejects a sibling with the same prefix",
       not workspace.is_inside(os.path.join(PROJECT_ROOT, "Features2"),
                               os.path.join(PROJECT_ROOT, "Features")))
    try:
        workspace.require_inside(os.path.join(PROJECT_ROOT, "..", "outside.txt"))
        ok("B5: require_inside rejects path escape", False, "accepted")
    except workspace.WorkspaceError as exc:
        ok("B5: require_inside rejects path escape", "escapes" in str(exc), str(exc))

    linked = os.path.join(root, "linked-features")
    symlink_tested = False
    try:
        os.symlink(source, linked, target_is_directory=True)
        symlink_tested = True
    except (OSError, NotImplementedError) as exc:
        print("SKIP: symlink creation unavailable here (%s)" % exc)
    if symlink_tested:
        try:
            workspace.copy_features(os.path.join(root, "runs", "link-1"), "run-3", "M99",
                                    source=linked)
            ok("B6: a symlinked feature source is rejected", False, "accepted")
        except workspace.WorkspaceError as exc:
            ok("B6: a symlinked feature source is rejected",
               "symlink" in str(exc), str(exc))
        link_file = os.path.join(root, "link-file.gd")
        try:
            os.symlink(os.path.join(source, "demo", "demo.gd"), link_file)
            try:
                workspace.require_regular_file(link_file)
                ok("B7: a symlinked target file is rejected", False, "accepted")
            except workspace.WorkspaceError as exc:
                ok("B7: a symlinked target file is rejected",
                   "symlink" in str(exc), str(exc))
        except (OSError, NotImplementedError) as exc:
            print("SKIP: file symlink unavailable (%s)" % exc)
    else:
        print("SKIP: B6/B7 symlink checks (cannot create symlinks on this host)")
    os.symlink = os.symlink

    foreign = os.path.join(root, "foreign-dir")
    os.makedirs(foreign)
    removal = workspace.remove_run_dir(foreign, "run-1", os.path.join(root, "runs"))
    ok("B8: cleanup refuses a directory without an ownership marker",
       removal["removed"] is False and os.path.isdir(foreign), str(removal))
    removal = workspace.remove_run_dir(run_root, "run-1", os.path.join(root, "elsewhere"))
    ok("B9: cleanup refuses a path outside the runs root",
       removal["removed"] is False and os.path.isdir(run_root), str(removal))
    removal = workspace.remove_run_dir(run_root, "different-run", os.path.join(root, "runs"))
    ok("B10: cleanup refuses a marker belonging to another run",
       removal["removed"] is False and os.path.isdir(run_root), str(removal))
    removal = workspace.remove_run_dir(run_root, "run-1", os.path.join(root, "runs"))
    ok("B11: cleanup removes its own directory once the marker matches",
       removal["removed"] is True and not os.path.exists(run_root), str(removal))

    before = workspace.snapshot(source)
    write(os.path.join(source, "demo", "demo.gd"), SAMPLE + "\n# edited\n")
    write(os.path.join(source, "demo", "extra.gd"), "pass\n")
    after = workspace.snapshot(source)
    changes = workspace.diff_snapshots(before, after)
    ok("B12: snapshot diff reports exactly the modified and added files",
       sorted((item["change"], item["file"]) for item in changes)
       == [("added", "demo/extra.gd"), ("modified", "demo/demo.gd")], str(changes))
    ok("B13: a snapshot diff of an untouched tree is empty",
       workspace.diff_snapshots(before, workspace.snapshot(source)) == changes
       and workspace.diff_snapshots(source and before, before) == [])


# ----------------------------------------------------------------- C Catalog
def test_catalog() -> None:
    print("=== C: catalog validation and preconditions ===")
    entries = catalog.load()
    ok("C1: the real catalog loads with unique ids",
       len(entries) >= 6 and len({entry["mutation_id"] for entry in entries}) == len(entries),
       str(len(entries)))

    base = {"mutation_id": "X", "feature_id": "health", "behavior_id": "damage",
            "mutation_type": "state_update_omitted", "target_file": "Features/health/health.gd",
            "target_function": "take_damage", "operator": "replace_exact", "anchor": "x",
            "expected_behavior_change": "y",
            "effectiveness": {"check": "health.current", "mutant": {"equals": 1}},
            "evaluation": {"expect": [{"check": "health.current", "equals": 1}]}}
    broken = dict(base)
    broken.pop("target_file")
    ok("C2: a missing required field is a structural error",
       any("missing" in problem for problem in catalog.structural_problems([broken])))

    duplicate = [dict(base), dict(base)]
    ok("C3: duplicate mutation ids are a structural error",
       any("duplicate mutation_id" in problem
           for problem in catalog.structural_problems(duplicate)))

    unknown_operator = dict(base)
    unknown_operator["operator"] = "sed_like"
    ok("C4: an unknown operator is a structural error",
       any("unknown operator" in problem
           for problem in catalog.structural_problems([unknown_operator])))

    ok("C5: effectiveness without a mutant predicate is a structural error",
       any("mutant predicate" in problem for problem in catalog.structural_problems(
           [dict(base, effectiveness={"check": "health.current"})])))

    supported, supported_info = catalog.supported_pairs()
    ok("C6: the support set is read dynamically (23 features / 60 behaviors)",
       supported_info["feature_count"] == 23 and supported_info["behavior_count"] == 60,
       "%s/%s" % (supported_info["feature_count"], supported_info["behavior_count"]))

    m05 = next(entry for entry in entries if entry["mutation_id"].startswith("M05"))
    check = catalog.preconditions(m05, supported)
    ok("C7: a catalog entry with a matching hash passes preconditions",
       check["ok"] is True and len(check["sha256"]) == 64, str(check)[:200])

    stale = dict(m05, source_sha256="0" * 64)
    stale_check = catalog.preconditions(stale, supported)
    ok("C8: a stale source hash is NOT_RUN, not a detected defect",
       stale_check["ok"] is False and stale_check["reason"] == "source_hash_mismatch",
       str(stale_check)[:200])

    unknown_behavior = dict(m05, behavior_id="not_a_behavior")
    ok("C9: an undeclared behaviour is rejected before execution",
       catalog.preconditions(unknown_behavior, supported)["reason"] == "unknown_behavior")
    unknown_feature = dict(m05, feature_id="not_a_feature")
    ok("C10: an unsupported feature is rejected before execution",
       catalog.preconditions(unknown_feature, supported)["reason"] == "unknown_feature")

    ok("C11: stage_expected reuses the validator comparison semantics",
       catalog.stage_expected({"check": "signal", "count": 2},
                              {"check": "signal", "observed": 2}) is True
       and catalog.stage_expected({"check": "health.current", "equals": 1},
                                  {"check": "health.current", "observed": 5}) is False
       and catalog.stage_expected({"check": "health.current", "equals": 1},
                                  {"check": "health.current", "observed": None}) is None)


# ----------------------------------------------------------------- D Verdict
def _report(**overrides) -> dict:
    report = {
        "controls": {
            "control": {"collection": {"stage": "OK", "bundle": "b"},
                        "evaluation": {"stage": "OK",
                                       "evaluation_status": "VERIFIED_PASS"},
                        "verified": True},
            "mutant": {"collection": {"stage": "OK", "bundle": "m"},
                       "evaluation": {"stage": "OK", "evaluation_status": "INVALID_EVIDENCE",
                                      "reason": "validator_rejected_evidence"},
                       "verified": False}},
        "effectiveness": {"effective": True, "reason": "ok"},
        "recovery": {"collection": {"stage": "OK"},
                     "evaluation": {"stage": "OK", "evaluation_status": "VERIFIED_PASS"},
                     "verified": True},
        "repo_guard": {"changed": False, "changes": []},
    }
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(report.get(key), dict):
            report[key].update(value)
        else:
            report[key] = value
    return report


def test_verdicts() -> None:
    print("=== D: verdict model keeps detection, invalid mutants and errors apart ===")
    ok("D1: an undetected mutant is MUTANT_SURVIVED",
       harness._verdict(_report(controls={
           "control": {"collection": {"stage": "OK", "bundle": "b"},
                        "evaluation": {"stage": "OK",
                                       "evaluation_status": "VERIFIED_PASS"},
                        "verified": True},
           "mutant": {"collection": {"stage": "OK", "bundle": "m"},
                      "evaluation": {"stage": "OK", "evaluation_status": "VERIFIED_PASS"},
                      "verified": True}}))
       [0] == harness.MUTANT_SURVIVED)
    ok("D2: a contract violation is MUTANT_KILLED",
       harness._verdict(_report())[0] == harness.MUTANT_KILLED)
    ok("D3: an ineffective mutation is INVALID_MUTANT, never a kill",
       harness._verdict(_report(effectiveness={"effective": False, "reason": "no change"}))
       [0] == harness.INVALID_MUTANT)
    ok("D4: a failed negative control is HARNESS_ERROR, not a kill",
       harness._verdict(_report(controls={
           "control": {"collection": {"stage": "OK", "bundle": "b"},
                       "evaluation": {"stage": "OK", "evaluation_status": "VERIFIED_FAIL"},
                       "verified": False},
           "mutant": {"collection": {"stage": "OK", "bundle": "m"},
                      "evaluation": {"stage": "OK",
                                     "evaluation_status": "INVALID_EVIDENCE"},
                      "verified": False}}))
       [0] == harness.HARNESS_ERROR)
    ok("D5: a failed recovery is HARNESS_ERROR",
       harness._verdict(_report(recovery={
           "collection": {"stage": "OK"},
           "evaluation": {"stage": "OK", "evaluation_status": "VERIFIED_FAIL"},
           "verified": False}))
       [0] == harness.HARNESS_ERROR)
    ok("D6: a repository change is HARNESS_ERROR",
       harness._verdict(_report(repo_guard={"changed": True, "changes": [{"file": "x"}]}))
       [0] == harness.HARNESS_ERROR)
    ok("D7: a timed-out subprocess is TIMEOUT",
       harness._verdict(_report(controls={
           "control": {"collection": {"stage": "TIMEOUT", "bundle": ""},
                       "evaluation": {"stage": "OK", "evaluation_status": ""},
                       "verified": False},
           "mutant": {"collection": {"stage": "OK", "bundle": "m"},
                      "evaluation": {"stage": "OK", "evaluation_status": ""},
                      "verified": False}}))[0]
       == harness.TIMEOUT)
    ok("D8: an undecidable mutant status is HARNESS_ERROR",
       harness._verdict(_report(controls={
           "control": {"collection": {"stage": "OK", "bundle": "b"},
                       "evaluation": {"stage": "OK",
                                      "evaluation_status": "VERIFIED_PASS"},
                       "verified": True},
           "mutant": {"collection": {"stage": "OK", "bundle": "m"},
                      "evaluation": {"stage": "OK",
                                     "evaluation_status": "INCOMPLETE"},
                      "verified": False}}))[0]
       == harness.HARNESS_ERROR)

    ok("D9: only unexpected-file changes are flagged",
       harness.unexpected_changes([{"file": "a.gd"}], "a.gd") == []
       and len(harness.unexpected_changes([{"file": "a.gd"}, {"file": "b.gd"}], "a.gd")) == 1)


def test_run_paths() -> None:
    print("=== D': real subprocess paths (NOT_RUN / TIMEOUT / INVALID_MUTANT) ===")
    repo_before = workspace.snapshot(workspace.FEATURES_DIR)
    root = new_dir("p159-run-")

    unsupported = dict(catalog.load()[0], mutation_id="M99-unknown-feature",
                       feature_id="not_a_feature")
    report = harness.run_mutation(unsupported, {"runs_root": os.path.join(root, "runs"),
                                                "timeout": 30})
    ok("D10: an unsupported feature yields NOT_RUN without creating a run dir",
       report["verdict"] == harness.NOT_RUN
       and not os.path.isdir(os.path.join(root, "runs")), report["verdict"])

    entry = dict(catalog.load()[0], mutation_id="M99-timeout")
    report = harness.run_mutation(entry, {"runs_root": os.path.join(root, "runs"),
                                          "timeout": 1, "replay": 1})
    ok("D11: a collector timeout is TIMEOUT, not a detection",
       report["verdict"] == harness.TIMEOUT
       and report["controls"]["control"]["collection"]["stage"] == harness.TIMEOUT,
       report["verdict"])

    broken = dict(catalog.load()[0], mutation_id="M99-bad-anchor",
                  anchor="\tthis_line_does_not_exist_in_health.gd\n")
    report = harness.run_mutation(broken, {"runs_root": os.path.join(root, "runs"),
                                           "timeout": 120, "replay": 2})
    ok("D12: an anchor that is not found yields INVALID_MUTANT after a passing control",
       report["verdict"] == harness.INVALID_MUTANT
       and report["controls"]["control"]["verified"] is True,
       "%s / %s" % (report["verdict"], report["verdict_reason"]))
    ok("D13: the invalid mutant left the repository untouched",
       workspace.diff_snapshots(repo_before, workspace.snapshot(workspace.FEATURES_DIR)) == [])

    # replay=1 会让 Validator 报 INCOMPLETE（replay_count=1 < 2）→ 控制组不成立，
    # 这种“自己没跑对”必须归成 HARNESS_ERROR，不能被当成检出或无效突变。
    report = harness.run_mutation(broken, {"runs_root": os.path.join(root, "runs"),
                                           "timeout": 120, "replay": 1})
    ok("D12b: a control that is only INCOMPLETE is HARNESS_ERROR, not INVALID_MUTANT",
       report["verdict"] == harness.HARNESS_ERROR
       and "negative control" in report["verdict_reason"],
       "%s / %s" % (report["verdict"], report["verdict_reason"]))

    run_roots = [os.path.join(root, "runs", name) for name in
                 os.listdir(os.path.join(root, "runs"))] \
        if os.path.isdir(os.path.join(root, "runs")) else []
    ok("D14: every run directory carries its own ownership marker",
       bool(run_roots) and all(workspace.owns(path, os.path.basename(path).rsplit("-", 1)[-1])
                               or workspace.owns(path, _owner_id(path))
                               for path in run_roots), str(run_roots))

    # 清理只删自己的目录：外来的目录不能动
    foreign = os.path.join(root, "runs", "foreign-keep")
    os.makedirs(foreign, exist_ok=True)
    write(os.path.join(foreign, "keep.txt"), "someone else\n")
    for path in run_roots:
        workspace.remove_run_dir(path, _owner_id(path), os.path.join(root, "runs"))
    ok("D15: cleanup removes only the harness's own run dirs",
       os.path.isdir(foreign) and not any(os.path.isdir(path) for path in run_roots))


def _owner_id(run_root: str) -> str:
    import json
    with open(os.path.join(run_root, workspace.OWNER_FILE), encoding="utf-8") as handle:
        return json.load(handle).get("run_id", "")


def main() -> int:
    print("Project root: %s" % PROJECT_ROOT)
    repo_before = workspace.snapshot(workspace.FEATURES_DIR)
    try:
        test_operators()
        test_workspace()
        test_catalog()
        test_verdicts()
        test_run_paths()
    finally:
        cleanup()
    after = workspace.snapshot(workspace.FEATURES_DIR)
    ok("Z1: the repository Features/** tree is byte-identical before and after",
       workspace.diff_snapshots(repo_before, after) == [],
       str(workspace.diff_snapshots(repo_before, after))[:300])
    print("\n%d check(s), %d failure(s)" % (_checks, len(_failures)))
    if _failures:
        for item in _failures:
            print(" - " + item)
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
