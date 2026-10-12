#!/usr/bin/env python3
"""Runtime Playtest 回归测试（Test 1 - Test 4 + 契约与解析器事实检查）。

覆盖：
    Test 1  正常 Scene（真实项目 Scenes/EnemyBasic.tscn）-> PASS / exit_code 0
    Test 2  故意制造 Node Path 错误        -> FAIL / node_not_found
    Test 3  故意制造 Script Error          -> FAIL / script_error
    Test 4  Timeout（不会结束的场景）      -> TIMEOUT
    附加     Scene 不存在 / 资源缺失 / Parser Error 的分类
    附加     输出解析事实（raw 保留 / 模式 / 位置 / repeat）
    附加     runtime_result schema 自洽性 + Validator 第 5 阶段 check_runtime

用法:
    python .ai/tools/runtime/tests/test_runtime_playtest.py
全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent                 # .ai/tools/runtime/tests
RUNTIME_DIR = TEST_DIR.parent                              # .ai/tools/runtime
DOTAI_DIR = RUNTIME_DIR.parent.parent                      # .ai
PROJECT_ROOT = DOTAI_DIR.parent                            # 项目根
VALIDATOR_DIR = DOTAI_DIR / "tools" / "validator"
FIXTURES_DIR = TEST_DIR / "fixtures"

for path in (RUNTIME_DIR, VALIDATOR_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from capture_output import parse_output                                    # noqa: E402
from check_runtime import check_runtime                                    # noqa: E402
from diagnose_runtime import diagnose                                      # noqa: E402
from run_scene import run_runtime                                          # noqa: E402
from runtime_result import (                                               # noqa: E402
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_TIMEOUT,
    load_contract,
    load_repair_safety,
    save_logs,
    validate_result,
)

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
    """把 fixture 复制到临时目录（保证测试不污染仓库，也不复用 .godot 缓存）。"""
    target = Path(tempfile.mkdtemp(prefix="runtime-fixture-"))
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


def cleanup() -> None:
    for directory in _temp_dirs:
        shutil.rmtree(directory, ignore_errors=True)


def primary_classification(result: dict, project: Path, scene: str) -> str:
    diagnosis = diagnose(result, project, scene)
    block = diagnosis["diagnosis"]
    errors = block.get("errors") or []
    return str(errors[0]["type"]) if errors else ""


def run() -> int:
    contract = load_contract()
    print("=== Contract ===")
    ok("contract: timeout is set", isinstance(contract.get("timeout"), (int, float)), str(contract.get("timeout")))
    ok("contract: max_repair_attempts is set", int(contract.get("max_repair_attempts") or 0) >= 1,
       str(contract.get("max_repair_attempts")))
    ok("contract: fail_on_error enabled", contract.get("fail_on_error") is True)
    ok("contract: fail_on_warning disabled", contract.get("fail_on_warning") is False)
    safety = load_repair_safety()
    ok("contract: repair safety forbids .ai/", ".ai/" in (safety.get("forbidden_path_prefixes") or []))

    print()
    print("=== Test 1: 正常 Scene（真实项目）===")
    scene1 = "res://Scenes/EnemyBasic.tscn"
    result1 = run_runtime(project=PROJECT_ROOT, scene=scene1, timeout=30, write_logs=False)
    ok("test1: schema valid", validate_result(result1) == [], str(validate_result(result1)))
    ok("test1: status PASS", result1["status"] == STATUS_PASS, str(result1["status"]))
    ok("test1: exit_code == 0", result1["exit_code"] == 0, str(result1["exit_code"]))
    ok("test1: no parsed errors", result1["errors"] == [], str(result1["errors"]))
    ok("test1: scene recorded", result1["scene"] == scene1, result1["scene"])
    ok("test1: raw output preserved", "Godot Engine" in result1["stdout"], result1["stdout"][:60])
    ok("test1: runtime validation PASS", check_runtime(result1, str(PROJECT_ROOT))["failures"] == [])

    print()
    print("=== Test 2: Node Path 错误 ===")
    fixture2 = materialize("broken_node_path")
    scene2 = "res://Scenes/BrokenNodePath.tscn"
    result2 = run_runtime(project=fixture2, scene=scene2, timeout=20, write_logs=False)
    ok("test2: schema valid", validate_result(result2) == [], str(validate_result(result2)))
    ok("test2: status FAIL", result2["status"] == STATUS_FAIL, str(result2["status"]))
    ok("test2: exit_code == 0 (错误不改退出码)", result2["exit_code"] == 0, str(result2["exit_code"]))
    ok("test2: raw stderr preserved", "Node not found" in result2["stderr"], result2["stderr"][:80])
    ok("test2: node_not_found parsed",
       any("node_not_found" in entry["patterns"] for entry in result2["errors"]),
       str([entry["patterns"] for entry in result2["errors"]]))
    entry2 = next((e for e in result2["errors"] if "node_not_found" in e["patterns"]), {})
    ok("test2: script located", entry2.get("script") == "res://Scenes/broken_node_path.gd", str(entry2.get("script")))
    ok("test2: line located", entry2.get("line") == 6, str(entry2.get("line")))
    ok("test2: diagnosis node_not_found",
       primary_classification(result2, fixture2, scene2) == "node_not_found",
       primary_classification(result2, fixture2, scene2))
    ok("test2: runtime validation FAIL", check_runtime(result2, str(fixture2))["failures"] != [])

    print()
    print("=== Test 3: Script Error ===")
    fixture3 = materialize("script_error")
    scene3 = "res://Scenes/ScriptError.tscn"
    result3 = run_runtime(project=fixture3, scene=scene3, timeout=20, write_logs=False)
    ok("test3: status FAIL", result3["status"] == STATUS_FAIL, str(result3["status"]))
    ok("test3: script_error parsed",
       any(entry["type"] == "script_error" for entry in result3["errors"]),
       str([entry["type"] for entry in result3["errors"]]))
    ok("test3: diagnosis script_error",
       primary_classification(result3, fixture3, scene3) == "script_error",
       primary_classification(result3, fixture3, scene3))

    print()
    print("=== Test 4: Timeout ===")
    fixture4 = materialize("hangs")
    scene4 = "res://Scenes/Hang.tscn"
    result4 = run_runtime(project=fixture4, scene=scene4, timeout=5, write_logs=False)
    ok("test4: status TIMEOUT", result4["status"] == STATUS_TIMEOUT, str(result4["status"]))
    ok("test4: timeout flag", result4["timeout"] is True)
    ok("test4: crash flag false", result4["crash"] is False)
    ok("test4: duration >= timeout", float(result4["duration"]) >= 4.5, str(result4["duration"]))
    ok("test4: diagnosis timeout",
       primary_classification(result4, fixture4, scene4) == "timeout",
       primary_classification(result4, fixture4, scene4))
    ok("test4: runtime validation FAIL", check_runtime(result4, str(fixture4))["failures"] != [])

    print()
    print("=== 附加分类：Scene 不存在 / 资源缺失 / Parser Error ===")
    fixture5 = materialize("hangs")
    result5 = run_runtime(project=fixture5, scene="res://Scenes/NoSuchScene.tscn", timeout=5, write_logs=False)
    ok("missing scene: status FAIL", result5["status"] == STATUS_FAIL, str(result5["status"]))
    ok("missing scene: exit_code is null (未启动 Godot)", result5["exit_code"] is None, str(result5["exit_code"]))
    ok("missing scene: not timed out", result5["timeout"] is False)
    ok("missing scene: diagnosis scene_load_error",
       primary_classification(result5, fixture5, "res://Scenes/NoSuchScene.tscn") == "scene_load_error",
       primary_classification(result5, fixture5, "res://Scenes/NoSuchScene.tscn"))

    fixture6 = materialize("missing_resource")
    scene6 = "res://Scenes/MissingResource.tscn"
    result6 = run_runtime(project=fixture6, scene=scene6, timeout=20, write_logs=False)
    ok("missing resource: status FAIL", result6["status"] == STATUS_FAIL, str(result6["status"]))
    ok("missing resource: diagnosis resource_missing",
       primary_classification(result6, fixture6, scene6) == "resource_missing",
       primary_classification(result6, fixture6, scene6))
    ok("missing resource: warnings separated",
       len(result6["warnings"]) >= 1, str(len(result6["warnings"])))

    fixture7 = materialize("parser_error")
    scene7 = "res://Scenes/ParserError.tscn"
    result7 = run_runtime(project=fixture7, scene=scene7, timeout=20, write_logs=False)
    ok("parser error: status FAIL", result7["status"] == STATUS_FAIL, str(result7["status"]))
    ok("parser error: diagnosis parser_error",
       primary_classification(result7, fixture7, scene7) == "parser_error",
       primary_classification(result7, fixture7, scene7))

    print()
    print("=== 输出解析事实 ===")
    parsed = parse_output("", "ERROR: Node not found: \"X\".\n   at: get_node (scene/main/node.cpp:1)\n"
                              "   GDScript backtrace (most recent call first):\n"
                              "       [0] _ready (res://a.gd:12)\n")
    ok("parser: raw_output retained", "Node not found" in parsed["raw_output"])
    ok("parser: one error parsed", parsed["counts"]["errors"] == 1, str(parsed["counts"]))
    ok("parser: script from backtrace", parsed["parsed_errors"][0]["script"] == "res://a.gd",
       parsed["parsed_errors"][0]["script"])
    ok("parser: line from backtrace", parsed["parsed_errors"][0]["line"] == 12,
       str(parsed["parsed_errors"][0]["line"]))

    repeated = parse_output("", "ERROR: Same thing.\nERROR: Same thing.\n")
    ok("parser: duplicate errors merged with repeat",
       repeated["counts"]["errors"] == 1 and repeated["parsed_errors"][0]["repeat"] == 2,
       str(repeated["parsed_errors"]))

    scene_ref = parse_output("", "ERROR: res://Scenes/A.tscn:7 - Parse Error: [ext_resource] referenced "
                                 "non-existent resource at: res://Scenes/Missing.tscn.\n")
    entry_ref = scene_ref["parsed_errors"][0]
    ok("parser: non-script location goes to resource", entry_ref["resource"] == "res://Scenes/A.tscn"
       and entry_ref["script"] == "", str(entry_ref))

    print()
    print("=== Runtime Validation（Validator 第 5 阶段）===")
    outcome6 = check_runtime(result6, str(fixture6))
    ok("check_runtime: FAIL result reported",
       any("error(s)" in failure for failure in outcome6["failures"]), str(outcome6["failures"]))
    ok("check_runtime: checked count matches errors", outcome6["checked"] == len(result6["errors"]),
       "%s vs %s" % (outcome6["checked"], len(result6["errors"])))
    broken = dict(result2)
    broken["status"] = STATUS_PASS
    ok("check_runtime: inconsistent status detected",
       check_runtime(broken, str(fixture2))["failures"] != [], "PASS with parsed errors must fail")

    print()
    print("=== 日志保存 ===")
    log_dir = Path(tempfile.mkdtemp(prefix="runtime-logs-"))
    _temp_dirs.append(log_dir)
    paths = save_logs(result2, tag="unittest", log_dir=log_dir)
    ok("logs: stdout/stderr/result written",
       all(Path(path).is_file() for path in paths.values()), str(paths))
    ok("logs: stderr content preserved",
       "Node not found" in Path(paths["stderr"]).read_text(encoding="utf-8"))

    print()
    if _failures:
        print("FAIL: %d failing check(s)" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: all runtime playtest checks passed")
    return 0


def main() -> int:
    try:
        return run()
    finally:
        cleanup()


if __name__ == "__main__":
    sys.exit(main())
