#!/usr/bin/env python3
"""Runtime Validation —— Validator 的第 5 阶段。

与其它 Validator 阶段的关系（静态正确性 vs 运行期正确性）：

    1. Project Validation   (validate.py)
    2. Feature Validation   (check_feature_metadata.py)
    3. Scene Validation     (check_scene_composition.py)
    4. Gameplay Validation  (check_gameplay.py)
    5. Runtime Validation   (本文件)

职责边界（架构约束）：
    - 本文件只负责「判定」：把 runtime_result 与 runtime_playtest 契约比对。
    - 运行 Scene 由 Runtime Runner（.ai/tools/runtime/run_scene.py）负责，
      本文件通过 --project/--scene 触发同一份 Runner，不实现第二套运行逻辑。
    - Self-Repair 逻辑不进入 Validator：修复由 .ai/tools/runtime/self_repair.py 负责。

检查项:
    1. Schema      —— runtime_result 字段与 status 语义（runtime_result_schema.yaml）
    2. 契约        —— fail_on_error / fail_on_warning
    3. 可分类性    —— 错误必须能被 Runtime Diagnosis 分类（unknown 记为 warning）
    4. 可定位性    —— 需要定位的错误缺少 file/line 时给 warning
    5. 运行期结论  —— PASS / FAIL / TIMEOUT / CRASH

用法:
    python check_runtime.py <runtime_result.json>
    python check_runtime.py --project . --scene res://Scenes/EnemyBasic.tscn

作为模块导入:
    from check_runtime import check_runtime
    result = check_runtime(runtime_result_dict, project_root)

退出码: 0 = PASS（允许 warning）；1 = FAIL；2 = 输入错误。
"""

from __future__ import annotations

import argparse
import os
import sys

_TOOL_DOTAI = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .ai
PROJECT_ROOT = os.path.dirname(_TOOL_DOTAI)
RUNTIME_DIR = os.path.join(_TOOL_DOTAI, "tools", "runtime")
if RUNTIME_DIR not in sys.path:
    sys.path.insert(0, RUNTIME_DIR)

from diagnose_runtime import CLASSIFICATIONS, diagnose, classify_entry      # noqa: E402
from run_scene import RuntimeInputError, run_runtime                        # noqa: E402
from runtime_result import (                                                # noqa: E402
    STATUS_CRASH,
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_TIMEOUT,
    load_contract,
    read_result,
    validate_result,
)

# 这些分类必须能定位到具体文件/行，否则修复无从下手
LOCATION_REQUIRED = {"node_not_found", "parser_error", "invalid_property", "invalid_method",
                     "signal_error", "script_error"}


def check_runtime(result: dict, project_root: str = PROJECT_ROOT,
                  contract: dict | None = None) -> dict:
    """Runtime Validation：返回 {failures, warnings, checked}。"""
    contract = contract or load_contract()
    failures, warnings = [], []
    if not isinstance(result, dict):
        return {"failures": ["runtime_result must be a mapping"], "warnings": [], "checked": 0}

    # 1. schema
    failures.extend(validate_result(result))
    if failures and any("missing field" in f for f in failures):
        return {"failures": failures, "warnings": warnings, "checked": 0}

    status = str(result.get("status") or "")
    errors = [e for e in (result.get("errors") or []) if isinstance(e, dict)]
    parsed_warnings = [e for e in (result.get("warnings") or []) if isinstance(e, dict)]
    scene = str(result.get("scene") or "")

    # 2. 契约
    if errors and contract.get("fail_on_error", True):
        failures.append("Runtime playtest produced %d error(s) in %s" % (len(errors), scene or "<main scene>"))
    if parsed_warnings and contract.get("fail_on_warning", False):
        failures.append("Runtime playtest produced %d warning(s) (fail_on_warning: true)" % len(parsed_warnings))

    # 5. 运行期结论
    if status == STATUS_TIMEOUT:
        failures.append("Runtime playtest TIMEOUT after %ss in %s" % (result.get("duration"), scene or "<main scene>"))
    elif status == STATUS_CRASH:
        failures.append("Runtime playtest CRASH: exit_code=%s (no parseable error)" % result.get("exit_code"))
    elif status == STATUS_FAIL and not failures:
        failures.append("Runtime playtest FAIL in %s" % (scene or "<main scene>"))
    elif status == STATUS_PASS and (errors or result.get("timeout") or result.get("crash")):
        failures.append("Runtime playtest status PASS contradicts its own observation")

    # 3 / 4. 可分类性与可定位性
    diagnosis = diagnose(result, project_root or None, scene)
    diagnosed = (diagnosis.get("diagnosis") or {}).get("errors") or []
    for entry in diagnosed:
        classification = str(entry.get("type") or "")
        if classification not in CLASSIFICATIONS:
            warnings.append("Unclassifiable runtime error: %s" % entry.get("message"))
        elif classification == "unknown_runtime_error":
            warnings.append("Runtime error could not be classified (unknown_runtime_error): %s"
                            % entry.get("message"))
        if classification in LOCATION_REQUIRED and not (entry.get("file") and entry.get("line")):
            warnings.append("Runtime error %s has no file/line location: %s"
                            % (classification, entry.get("message")))

    # 与原始事件的分类一致性（防止 diagnosis 与 result 脱节）
    for entry in errors:
        expected = classify_entry(entry, scene)
        if expected == "unknown_runtime_error":
            warnings.append("Unclassified raw runtime error: %s" % entry.get("message"))

    return {"failures": failures, "warnings": warnings, "checked": len(errors)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validate a runtime_result (Runtime Validation stage).")
    parser.add_argument("result", nargs="?", default="", help="runtime_result JSON path")
    parser.add_argument("--project", default=".", help="Godot project directory")
    parser.add_argument("--scene", default="", help="Run the playtest for this scene first")
    parser.add_argument("--out", default="", help="Write the runtime_result JSON to this path")
    args = parser.parse_args(argv)

    if not args.result and not args.scene:
        print("FAIL: provide either <runtime_result.json> or --scene")
        return 2

    result: dict
    if args.scene:
        try:
            result = run_runtime(project=args.project, scene=args.scene)
        except RuntimeInputError as exc:
            print("FAIL: %s" % exc)
            return 2
        if args.out:
            from runtime_result import write_result
            write_result(result, args.out)
    else:
        if not os.path.isfile(args.result):
            print("FAIL: runtime_result not found: %s" % args.result)
            return 2
        result = read_result(args.result)

    print("Runtime Validator")
    print("Scene:  %s" % (result.get("scene") or "<project main scene>"))
    print("Status: %s (exit_code=%s, duration=%ss)"
          % (result.get("status"), result.get("exit_code"), result.get("duration")))
    outcome = check_runtime(result, PROJECT_ROOT)
    print("Checked runtime errors: %d" % outcome["checked"])
    if outcome["failures"]:
        print("\nFAILURES")
        for failure in outcome["failures"]:
            print("  - " + failure)
    if outcome["warnings"]:
        print("\nWARNINGS")
        for warning in outcome["warnings"]:
            print("  - " + warning)
    if outcome["failures"]:
        print("\nFAIL")
        return 1
    if outcome["warnings"]:
        print("\nWARNING: 0 error(s), %d warning(s)" % len(outcome["warnings"]))
        return 0
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
