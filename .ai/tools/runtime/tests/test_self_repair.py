#!/usr/bin/env python3
"""Self-Repair 回归测试（Test 5 及安全边界）。

覆盖：
    Test 5  单次自修：Runtime FAIL -> Diagnosis -> Repair -> Validator -> Runtime PASS
    附加    多轮自修（attempt 2 才 PASS）+ max-attempts 上限
    附加    回滚（修复引入新错误时恢复原文件）
    附加    不可自动修复的错误（script_error / scene_load_error）不修改项目
    附加    dry-run 只出计划不修改
    附加    修复历史字段完整性与文件编号递增
    附加    修复安全边界（禁止路径 / 禁止修改 / 计划 schema 校验）

用法:
    python .ai/tools/runtime/tests/test_self_repair.py
全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。
每个用例都在临时项目副本上运行，不修改仓库中的 fixture 与真实项目。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import yaml
except ImportError:
    print("FAIL: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    raise SystemExit(2)

TEST_DIR = Path(__file__).resolve().parent                 # .ai/tools/runtime/tests
RUNTIME_DIR = TEST_DIR.parent                              # .ai/tools/runtime
DOTAI_DIR = RUNTIME_DIR.parent.parent                      # .ai
PROJECT_ROOT = DOTAI_DIR.parent                            # 项目根
FIXTURES_DIR = TEST_DIR / "fixtures"
SELF_REPAIR = RUNTIME_DIR / "self_repair.py"

if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

from diagnose_runtime import diagnose                                      # noqa: E402
from repair_plan import build_plan, validate_plan, safety_violation        # noqa: E402
from self_repair import self_repair, FAIL, PASS                            # noqa: E402
from repair_engine import apply_change, read_text_preserve, revert_change  # noqa: E402
from runtime_result import load_contract, load_repair_safety               # noqa: E402

_failures: list[str] = []
_temp_dirs: list[Path] = []

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))
        print("FAIL: " + name + (" | " + detail if detail else ""))


def materialize(fixture: str) -> Path:
    target = Path(tempfile.mkdtemp(prefix="selfrepair-"))
    _temp_dirs.append(target)
    source = FIXTURES_DIR / fixture
    for item in source.iterdir():
        if item.name == ".godot":
            continue
        if item.is_dir():
            shutil.copytree(item, target / item.name)
        else:
            shutil.copy2(item, target / item.name)
    return target


def history_dir_for(project: Path) -> Path:
    path = project / "repair-history"
    return path


def cleanup() -> None:
    for directory in _temp_dirs:
        shutil.rmtree(directory, ignore_errors=True)


def test5_cli_single_attempt() -> None:
    print("=== Test 5: 单次自修（CLI，与验收命令一致）===")
    project = materialize("broken_node_path")
    history = history_dir_for(project)
    script = project / "Scenes" / "broken_node_path.gd"
    before = read_text_preserve(script)

    proc = subprocess.run(
        [sys.executable, str(SELF_REPAIR), "--project", str(project),
         "--scene", "res://Scenes/BrokenNodePath.tscn",
         "--max-attempts", "3", "--history-dir", str(history)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        stdin=subprocess.DEVNULL, cwd=str(PROJECT_ROOT),
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    ok("test5: CLI exit code 0", proc.returncode == 0, "exit=%s\n%s" % (proc.returncode, out[-500:]))
    ok("test5: attempt 1 runtime FAIL printed", "Attempt 1" in out and "Runtime      FAIL" in out,
       out[-400:])
    ok("test5: diagnosis PASS printed", "Diagnosis    PASS" in out, out[-400:])
    ok("test5: repair PASS printed", "Repair       PASS" in out, out[-400:])
    ok("test5: validator PASS printed", "Validator    PASS" in out, out[-400:])
    ok("test5: repaired runtime PASS printed", "Runtime      PASS" in out, out[-400:])
    ok("test5: result PASS printed", "Result: PASS" in out, out[-200:])

    after = read_text_preserve(script)
    # 只断言代码中的节点路径被修复（注释里保留的原始拼写说明不算问题）
    ok("test5: hardcoded path repaired",
       'get_node("Health")' in after and 'get_node("Helth")' not in after, after)
    ok("test5: change is minimal (one line)",
       len(before.splitlines()) == len(after.splitlines()), "%d -> %d" % (len(before.splitlines()), len(after.splitlines())))

    entries = sorted(history.glob("repair-*.yaml"))
    ok("test5: one repair history entry", len(entries) == 1, str([p.name for p in entries]))
    if entries:
        entry = yaml.safe_load(entries[0].read_text(encoding="utf-8"))
        for field in ("attempt", "timestamp", "error", "diagnosis", "changed_files",
                      "validation_result", "runtime_result", "status", "reverted"):
            ok("test5: history has %s" % field, field in entry, str(sorted(entry)))
        ok("test5: history attempt == 1", entry.get("attempt") == 1, str(entry.get("attempt")))
        ok("test5: history error classification node_not_found",
           (entry.get("error") or {}).get("classification") == "node_not_found",
           str(entry.get("error")))
        ok("test5: history changed_files recorded",
           entry.get("changed_files") == ["Scenes/broken_node_path.gd"], str(entry.get("changed_files")))
        ok("test5: history validation ok", (entry.get("validation_result") or {}).get("ok") is True,
           str(entry.get("validation_result")))
        ok("test5: history runtime after PASS",
           ((entry.get("runtime_result") or {}).get("after") or {}).get("status") == PASS,
           str(entry.get("runtime_result")))
        ok("test5: history status repaired", entry.get("status") == "repaired", str(entry.get("status")))
        ok("test5: history not reverted", entry.get("reverted") is False)

    pristine = FIXTURES_DIR / "broken_node_path" / "Scenes" / "broken_node_path.gd"
    ok("test5: repository fixture untouched", "Helth" in read_text_preserve(pristine),
       read_text_preserve(pristine))


def test_multi_attempt() -> None:
    print()
    print("=== 多轮自修 ===")
    project = materialize("multiple_node_paths")
    history = history_dir_for(project)
    report = self_repair(
        project=project, scene="res://Scenes/MultipleNodePaths.tscn",
        max_attempts=3, history_dir=history, verbose=False,
    )
    block = report["self_repair"]
    ok("multi: overall PASS", block["status"] == PASS, str(block))
    ok("multi: attempts_used == 2", block["attempts_used"] == 2, str(block["attempts_used"]))
    ok("multi: two history entries", len(sorted(history.glob("repair-*.yaml"))) == 2,
       str(sorted(p.name for p in history.glob("repair-*.yaml"))))
    text = read_text_preserve(project / "Scenes" / "multiple_node_paths.gd")
    ok("multi: both node paths fixed", 'get_node("Health")' in text and 'get_node("Mana")' in text, text)
    ok("multi: runtime after PASS", block["final_runtime_status"] == PASS, str(block["final_runtime_status"]))

    print()
    print("=== max-attempts 上限 ===")
    capped_project = materialize("multiple_node_paths")
    capped_history = history_dir_for(capped_project)
    capped = self_repair(
        project=capped_project, scene="res://Scenes/MultipleNodePaths.tscn",
        max_attempts=1, history_dir=capped_history, verbose=False,
    )
    capped_block = capped["self_repair"]
    ok("capped: status FAIL", capped_block["status"] == FAIL, str(capped_block["status"]))
    ok("capped: attempts_used == 1", capped_block["attempts_used"] == 1, str(capped_block["attempts_used"]))
    ok("capped: one history entry", len(sorted(capped_history.glob("repair-*.yaml"))) == 1)
    capped_text = read_text_preserve(capped_project / "Scenes" / "multiple_node_paths.gd")
    ok("capped: first repair kept (progress)", 'get_node("Health")' in capped_text and "Manah" in capped_text,
       capped_text)


def test_revert() -> None:
    print()
    print("=== 回滚（修复无效 / 引入新错误）===")
    project = materialize("revert_case")
    history = history_dir_for(project)
    script = project / "Scenes" / "revert_case.gd"
    before = read_text_preserve(script)

    report = self_repair(
        project=project, scene="res://Scenes/RevertCase.tscn",
        max_attempts=3, history_dir=history, verbose=False,
    )
    block = report["self_repair"]
    ok("revert: overall FAIL", block["status"] == FAIL, str(block["status"]))
    ok("revert: stopped after attempt 1", block["attempts_used"] == 1, str(block["attempts_used"]))
    ok("revert: file restored byte-identical", read_text_preserve(script) == before,
       read_text_preserve(script))
    ok("revert: changed_files empty", block["changed_files"] == [], str(block["changed_files"]))
    entries = sorted(history.glob("repair-*.yaml"))
    ok("revert: history written", len(entries) == 1, str([p.name for p in entries]))
    if entries:
        entry = yaml.safe_load(entries[0].read_text(encoding="utf-8"))
        ok("revert: history reverted flag", entry.get("reverted") is True, str(entry.get("reverted")))
        ok("revert: history status reverted", entry.get("status") == "reverted", str(entry.get("status")))
        ok("revert: history changed_files empty", entry.get("changed_files") == [], str(entry.get("changed_files")))
        ok("revert: history note explains", "revert" in str(entry.get("note") or ""), str(entry.get("note")))


def test_not_repairable() -> None:
    print()
    print("=== 不可自动修复（禁止编造原因 / 不修改项目）===")
    project = materialize("script_error")
    history = history_dir_for(project)
    script = project / "Scenes" / "script_error.gd"
    before = read_text_preserve(script)

    report = self_repair(
        project=project, scene="res://Scenes/ScriptError.tscn",
        max_attempts=3, history_dir=history, verbose=False,
    )
    block = report["self_repair"]
    ok("not-repairable: status FAIL", block["status"] == FAIL, str(block["status"]))
    ok("not-repairable: attempts_used == 1", block["attempts_used"] == 1, str(block["attempts_used"]))
    ok("not-repairable: project untouched", read_text_preserve(script) == before)
    ok("not-repairable: no changed files", block["changed_files"] == [], str(block["changed_files"]))
    ok("not-repairable: reason explains strategy limit",
       "no deterministic repair strategy" in str(block.get("note") or ""), str(block.get("note")))
    entries = sorted(history.glob("repair-*.yaml"))
    if entries:
        entry = yaml.safe_load(entries[0].read_text(encoding="utf-8"))
        ok("not-repairable: history status", entry.get("status") == "not_repairable", str(entry.get("status")))
        ok("not-repairable: history reason recorded", bool(entry.get("repair", {}).get("reason")),
           str(entry.get("repair")))

    cli = subprocess.run(
        [sys.executable, str(SELF_REPAIR), "--project", str(project),
         "--scene", "res://Scenes/ScriptError.tscn", "--history-dir", str(history)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        stdin=subprocess.DEVNULL, cwd=str(PROJECT_ROOT),
    )
    ok("not-repairable: CLI exit code 1", cli.returncode == 1, "exit=%s" % cli.returncode)

    print()
    print("=== Scene 不存在 ===")
    project_missing = materialize("hangs")
    report_missing = self_repair(
        project=project_missing, scene="res://Scenes/NoSuchScene.tscn",
        max_attempts=3, history_dir=history_dir_for(project_missing), verbose=False,
    )
    block_missing = report_missing["self_repair"]
    ok("missing scene: status FAIL", block_missing["status"] == FAIL, str(block_missing["status"]))
    ok("missing scene: no repair attempted",
       block_missing["attempts"][0]["diagnosis"] == "scene_load_error",
       str(block_missing["attempts"]))


def test_dry_run() -> None:
    print()
    print("=== Dry run ===")
    project = materialize("broken_node_path")
    script = project / "Scenes" / "broken_node_path.gd"
    before = read_text_preserve(script)
    report = self_repair(
        project=project, scene="res://Scenes/BrokenNodePath.tscn",
        dry_run=True, history_dir=history_dir_for(project), verbose=False,
    )
    block = report["self_repair"]
    ok("dry-run: status FAIL", block["status"] == FAIL, str(block["status"]))
    ok("dry-run: project untouched", read_text_preserve(script) == before)
    ok("dry-run: note records dry run", "dry run" in str(block.get("note") or "").lower(),
       str(block.get("note")))
    ok("dry-run: no history written",
       not sorted(history_dir_for(project).glob("repair-*.yaml")))


def test_history_numbering() -> None:
    print()
    print("=== 修复历史编号递增 ===")
    project = materialize("broken_node_path")
    history = history_dir_for(project)
    history.mkdir(parents=True, exist_ok=True)
    (history / "repair-001.yaml").write_text("attempt: 1\n", encoding="utf-8")
    report = self_repair(
        project=project, scene="res://Scenes/BrokenNodePath.tscn",
        history_dir=history, verbose=False,
    )
    names = sorted(p.name for p in history.glob("repair-*.yaml"))
    ok("history: existing entry not overwritten", (history / "repair-001.yaml").read_text(encoding="utf-8") == "attempt: 1\n")
    ok("history: new entry numbered 002", "repair-002.yaml" in names, str(names))
    ok("history: report lists history paths", len(report["self_repair"]["history"]) == 1,
       str(report["self_repair"]["history"]))


def test_safety_and_plan_schema() -> None:
    print()
    print("=== 修复安全边界与计划 schema ===")
    safety = load_repair_safety()
    contract = load_contract()
    project = materialize("broken_node_path")

    error = {"classification": "node_not_found", "file": "res://Scenes/broken_node_path.gd",
             "line": 6, "related_feature": "", "confidence": "high"}
    ok("safety: forbids .ai/",
       bool(safety_violation(project, project / ".ai" / "config" / "agent.yaml", error,
                             "res://Scenes/BrokenNodePath.tscn", safety)))
    ok("safety: forbids project.godot",
       bool(safety_violation(project, project / "project.godot", error,
                             "res://Scenes/BrokenNodePath.tscn", safety)))
    ok("safety: forbids unrelated feature files",
       bool(safety_violation(project, project / "Features" / "other" / "other.gd", error,
                             "res://Scenes/BrokenNodePath.tscn", safety)))
    ok("safety: allows the error script",
       safety_violation(project, project / "Scenes" / "broken_node_path.gd", error,
                        "res://Scenes/BrokenNodePath.tscn", safety) == "")
    ok("safety: allows the playtest scene",
       safety_violation(project, project / "Scenes" / "BrokenNodePath.tscn", error,
                        "res://Scenes/BrokenNodePath.tscn", safety) == "")

    # plan schema：合法计划
    from run_scene import run_runtime
    result = run_runtime(project=project, scene="res://Scenes/BrokenNodePath.tscn",
                         timeout=20, write_logs=False)
    diagnosis = diagnose(result, project, "res://Scenes/BrokenNodePath.tscn")
    plan = build_plan(diagnosis, project, attempt=1, contract=contract, safety=safety)
    ok("plan: repairable node path error", plan["repair"]["repairable"] is True, str(plan["repair"]))
    ok("plan: schema valid", validate_plan(plan, safety) == [], str(validate_plan(plan, safety)))
    ok("plan: target scope is script", plan["repair"]["target"]["scope"] == "script",
       str(plan["repair"]["target"]))
    ok("plan: risk is low for high-confidence script fix", plan["repair"]["risk"] == "low",
       str(plan["repair"]["risk"]))

    tampered = {**plan, "_edit": {**(plan.get("_edit") or {}), "change_kind": "rewrite_file"}}
    ok("plan: disallowed change kind rejected", validate_plan(tampered, safety) != [],
       str(validate_plan(tampered, safety)))

    not_repairable = {
        "repair": {
            "attempt": 1,
            "error": {"classification": "parser_error", "message": "x", "file": "", "line": 0,
                      "scene": "", "confidence": "low"},
            "target": {"file": "", "scope": "", "feature": ""},
            "reason": "",
            "changes": [],
            "validation": [],
            "risk": "unknown",
            "repairable": False,
        }
    }
    ok("plan: non-repairable plan requires reason", validate_plan(not_repairable, safety) != [])

    # 回滚原语：字节级往返一致（含 CRLF）
    crlf = Path(tempfile.mkdtemp(prefix="crlf-")) / "sample.gd"
    _temp_dirs.append(crlf.parent)
    original = 'extends Node2D\r\n\r\nfunc _ready() -> void:\r\n\tget_node("Helth")\r\n'
    crlf.write_text(original, encoding="utf-8", newline="")
    applied = apply_change(crlf, '"Helth"', '"Health"')
    ok("revert primitive: apply ok", applied.get("ok") is True, str(applied))
    ok("revert primitive: crlf preserved after apply",
       read_text_preserve(crlf) == original.replace('"Helth"', '"Health"'),
       repr(read_text_preserve(crlf)))
    revert_change(applied["backup"])
    ok("revert primitive: byte-identical restore", read_text_preserve(crlf) == original,
       repr(read_text_preserve(crlf)))

    # 歧义字面量必须拒绝修改
    ambiguous = Path(tempfile.mkdtemp(prefix="ambiguous-")) / "sample.gd"
    _temp_dirs.append(ambiguous.parent)
    ambiguous.write_text('get_node("X")\nget_node("X")\n', encoding="utf-8")
    refused = apply_change(ambiguous, '"X"', '"Y"')
    ok("revert primitive: ambiguous literal refused", refused.get("ok") is False, str(refused))


def run() -> int:
    test5_cli_single_attempt()
    test_multi_attempt()
    test_revert()
    test_not_repairable()
    test_dry_run()
    test_history_numbering()
    test_safety_and_plan_schema()
    print()
    if _failures:
        print("FAIL: %d failing check(s)" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: all self-repair checks passed")
    return 0


def main() -> int:
    try:
        return run()
    finally:
        cleanup()


if __name__ == "__main__":
    sys.exit(main())
