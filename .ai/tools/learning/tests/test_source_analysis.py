#!/usr/bin/env python3
"""Phase 1.65：Source Analysis 测试（含攻击：缺失源码、入口歧义、别名解析）。

只读真实源码；所有"失败"用例都用内存/临时文件构造，不修改 Features/**。
"""

from __future__ import annotations

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LEARNING = os.path.dirname(HERE)
sys.path[:0] = [LEARNING]

import gd_parse  # noqa: E402
import paths  # noqa: E402
import source_analysis  # noqa: E402

checks = 0
failures = 0
TMP: list[str] = []


def ok(name: str, condition: bool, detail: str = "") -> None:
    global checks, failures
    checks += 1
    if condition:
        print("PASS: %s" % name)
    else:
        failures += 1
        print("FAIL: %s %s" % (name, detail))


def temp_script(name: str, text: str) -> str:
    directory = tempfile.mkdtemp(prefix="p165_src_")
    TMP.append(directory)
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path


SAMPLE = """class_name Sample
extends Node

signal changed(value: bool)

var _state := false
var _guard := 0
var _other: Sample


func set_state(value: bool) -> bool:
\tif _state == value:
\t\treturn true
\t_state = value
\tchanged.emit(value)
\treturn true


func _ready() -> void:
\tbody_entered.connect(_on_body_entered)


func _on_body_entered(_body) -> void:
\tif _guard > 0:
\t\treturn
\t_guard = 1
"""


def main() -> int:
    # S1 真实 Behavior：入口、状态、条件、事件、副作用都有真实来源
    record = source_analysis.analyze("openable_door", "open")
    ok("S1: real behavior resolves a single contract entry",
       [entry["name"] for entry in record["entry_points"]] == ["set_open"],
       str([entry["name"] for entry in record["entry_points"]]))
    ok("S2: every entry carries file:line source reference",
       all(entry["source_reference"].startswith("Features/") and ":" in entry["source_reference"]
           for entry in record["entry_points"]))
    ok("S3: idempotent guard is captured as a condition",
       any("_is_open == value" in item["condition"] for item in record["conditions"]))
    ok("S4: guard-body bare return is captured",
       any(item["kind"] == "guard_return" for item in record["failure_paths"]))
    ok("S5: emitted signal is captured with line",
       any(item["kind"] == "emit" and item["signal"] == "state_changed"
           for item in record["events"]))
    ok("S6: deferred property write is captured as side effect",
       any(item["kind"] == "deferred_property_write" and item["attribute"] == "disabled"
           for item in record["side_effects"]))
    ok("S7: analysis is marked static_only (not runtime evidence)",
       record["static_only"] is True)
    ok("S8: state variables include the real guard variable",
       any(item["variable"] == "_is_open" for item in record["state_variables"]))
    ok("S9: contract version matches the binding/matrix rule",
       len(record["contract_version"]) == 12)

    # S10-S12 手工脚本：信号入口、拿不到 class_name 的未解决项
    script = gd_parse.parse_file(temp_script("sample.gd", SAMPLE))
    ok("S10: parser finds functions/signals/vars",
       [item.name for item in script.functions] == ["set_state", "_ready", "_on_body_entered"]
       and [item["name"] for item in script.signals] == ["changed"]
       and {"_state", "_guard", "_other"} <= {item["name"] for item in script.variables})
    ready = script.function("_ready")
    ok("S11: single-identifier signal connect is parsed",
       [item["handler"] for item in gd_parse.connects(ready)] == ["_on_body_entered"])

    # S13 别名解析（save_slot → save_to_slot），并且是唯一匹配
    mapping = {"save_to_slot": [("s", "f")], "save_slot_to_other": [("s", "g")]}
    resolved, how = source_analysis._resolve_function("save_slot", mapping)
    ok("S12: alias resolution only accepts a unique token match",
       resolved == [] and how == "none", str((resolved, how)))
    mapping = {"save_to_slot": [("s", "f")]}
    resolved, how = source_analysis._resolve_function("save_slot", mapping)
    ok("S13: alias resolution finds the unique candidate",
       resolved and how == "alias")

    # S14-S15 攻击：源码缺失 / 入口歧义
    original = paths.implementation_files
    paths.implementation_files = lambda feature_id: []
    try:
        missing = source_analysis.analyze("openable_door", "open")
    finally:
        paths.implementation_files = original
    ok("S14: missing implementation is SOURCE_NOT_FOUND (no guessing)",
       missing["analysis_status"] == "SOURCE_NOT_FOUND" and not missing["entry_points"])
    ok("S15: missing implementation records an unresolved question",
       any("缺失" in item or "missing" in item for item in missing["unresolved_questions"]))

    # S16 攻击：契约要求的方法在源码里不存在
    ok("S16: unresolved contract methods are reported, not invented",
       any("take_damage" in item for item in
           source_analysis.analyze("save_game", "save_slot_persists_world_state")
           ["unresolved_questions"]))

    # S17 静态事实边界：不得出现 runtime 字段
    ok("S17: source analysis never claims runtime observation",
       "runtime" not in record and all(item.get("static_only") is not False
                                       for item in [record["entry_points"][0]]))
    print("\n===== test_source_analysis: %d checks, %d failures =====" % (checks, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
