"""Behavior Source Analysis（Phase 1.65）。

输入：正式契约（`Features/<f>/template.yaml#behavior`）+ 真实实现文件。
输出：入口、状态、条件、事件、副作用、失败路径，以及**无法确认的内容**。

硬约束：
- 只用真实磁盘文件；不按名字猜路径，不跨 Feature 借源码。
- 每条结论带 `file:line` 来源；静态结论一律 `SOURCE_OBSERVATION` 且 `static_only=true`。
- 入口找不到/多重歧义/动态调用无法确定时，写 `unresolved_questions`，状态降级，
  绝不把猜测当事实。

用法：
    python .ai/tools/learning/source_analysis.py --feature openable_door --behavior open
    python .ai/tools/learning/source_analysis.py --all
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time

import gd_parse
import paths

OUTPUT_DIR = os.path.join(paths.LEARNING_STATE, "source_analysis")
SCHEMA = "behavior_source_analysis"
SCHEMA_VERSION = 1

TRIGGER_KEYWORDS = ("_ready", "_process", "_physics_process", "_input", "_unhandled_input")

# 契约为真实执行准备的 harness 动词（不是被测组件的方法）。
# 只忽略这些前缀，不忽略任何真实组件方法。
HARNESS_PREFIXES = ("physics", "simulation", "input", "scene", "node", "time", "debug",
                    "wait", "assert")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _action_methods(behavior: dict) -> list[str]:
    """契约 action 里真正调用的方法名（`door.set_open` → `set_open`）。"""
    methods = []
    for action in behavior.get("actions") or []:
        kind = str(action.get("type") or "")
        if not kind or "." not in kind:
            continue
        prefix = kind.split(".")[0]
        method = kind.split(".")[-1]
        if prefix in HARNESS_PREFIXES or method.startswith("advance_"):
            continue
        if method not in methods:
            methods.append(method)
    return methods


def _check_symbols(behavior: dict) -> list[str]:
    """preconditions/expected 里被读取的符号（`door.is_open` → `is_open`）。"""
    symbols = []
    for section in ("preconditions", "expected"):
        for item in behavior.get(section) or []:
            check = str(item.get("check") or "")
            entry = str(item.get("entry") or "")
            for raw in (check, entry):
                if "." in raw:
                    symbol = raw.split(".")[-1]
                    if symbol and symbol not in symbols:
                        symbols.append(symbol)
    return symbols


def _expression_digest(script: gd_parse.Script) -> str:
    return script.digest


def _tokens(name: str) -> set[str]:
    return {part for part in re.split(r"_", name.lower()) if part}


def _resolve_function(name: str, mapping: dict) -> tuple[list, str]:
    """精确匹配优先；否则用 token 子集做**唯一**别名解析（契约别名，如 save_slot→save_to_slot）。

    只接受恰好一个候选；多个候选一律视为无法确定（不猜）。
    """
    exact = mapping.get(name) or []
    if exact:
        return exact, "exact"
    wanted = _tokens(name)
    if not wanted:
        return [], "none"
    candidates = [item for candidate_name, items in mapping.items()
                  if wanted <= _tokens(candidate_name) for item in items]
    if len(candidates) == 1:
        return candidates, "alias"
    return [], "none"


def _callee_map(scripts: list[gd_parse.Script]) -> dict[str, list[tuple[gd_parse.Script, gd_parse.Function]]]:
    mapping: dict[str, list] = {}
    for script in scripts:
        for function in script.functions:
            mapping.setdefault(function.name, []).append((script, function))
    return mapping


BARE_CALL_RE = re.compile(r"(?<![\w.\"])(?P<name>[a-z_]\w*)\s*\(")
NOT_CALLS = {"if", "for", "while", "match", "return", "func", "signal", "and", "or", "not",
             "in", "is", "print", "assert", "push_error", "push_warning", "emit_signal"}


def _internal_callees(function: gd_parse.Function, mapping: dict[str, list],
                      class_calls: dict[str, dict[str, tuple[gd_parse.Script, gd_parse.Function]]]
                      ) -> list[tuple[str, gd_parse.Script, gd_parse.Function]]:
    """本文件内的裸调用 + 同 Feature 内的静态类调用（`SaveData.read_from_file(`）。"""
    found = []
    seen = set()
    for _number, line in function.body:
        for match in BARE_CALL_RE.finditer(line):
            name = match.group("name")
            if name in NOT_CALLS or name == function.name or name in seen:
                continue
            targets = mapping.get(name) or []
            if len(targets) == 1:
                seen.add(name)
                found.append((name, targets[0][0], targets[0][1]))
        for match in gd_parse.CALL_RE.finditer(line):
            receiver, method = match.group("receiver"), match.group("method")
            if receiver not in class_calls:
                continue
            target = class_calls[receiver].get(method)
            key = "%s.%s" % (receiver, method)
            if target is None or key in seen:
                continue
            seen.add(key)
            found.append((method, target[0], target[1]))
    return found


def _collect(entries: list[tuple[gd_parse.Script, gd_parse.Function]],
             mapping: dict[str, list],
             class_calls: dict[str, dict[str, tuple[gd_parse.Script, gd_parse.Function]]],
             depth: int = 2) -> list[tuple[gd_parse.Script, gd_parse.Function]]:
    collected: list[tuple[gd_parse.Script, gd_parse.Function]] = []
    frontier = list(entries)
    seen = {(script.path, function.name) for script, function in entries}
    for _ in range(depth):
        next_frontier = []
        for script, function in frontier:
            for _name, callee_script, callee in _internal_callees(function, mapping, class_calls):
                key = (callee_script.path, callee.name)
                if key in seen:
                    continue
                seen.add(key)
                collected.append((callee_script, callee))
                next_frontier.append((callee_script, callee))
        frontier = next_frontier
    return collected


def analyze(feature_id: str, behavior_id: str, *, behavior: dict | None = None,
            contract_path: str = "", version: str = "") -> dict:
    behavior = behavior or next(
        (item["behavior"] for item in paths.supported_behaviors()
         if item["feature_id"] == feature_id and item["behavior_id"] == behavior_id), None)
    if behavior is None:
        raise KeyError("behavior %s/%s is not in the supported set" % (feature_id, behavior_id))
    contract_rel = contract_path or "Features/%s/template.yaml" % feature_id
    files = paths.implementation_files(feature_id)
    unresolved: list[str] = []
    record = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now(),
        "feature_id": feature_id,
        "behavior_id": behavior_id,
        "behavior_category": paths.category_of(feature_id, behavior_id),
        "contract_version": version or paths.contract_version(feature_id, behavior_id),
        "contract_reference": "%s#behavior=%s" % (contract_rel, behavior_id),
        "implementation_references": [paths.rel(path) for path in files],
        "scripts": [],
        "entry_points": [],
        "state_variables": [],
        "conditions": [],
        "events": [],
        "side_effects": [],
        "failure_paths": [],
        "static_only": True,
        "analysis_status": "COMPLETE",
        "unresolved_questions": unresolved,
    }
    if not files:
        record["analysis_status"] = "SOURCE_NOT_FOUND"
        unresolved.append("%s 没有可分析实现文件（Features/%s/*.gd 全部缺失）"
                          % (feature_id, feature_id))
        return record

    scripts = [gd_parse.parse_file(path) for path in files]
    for script in scripts:
        record["scripts"].append({"path": paths.rel(script.path), "digest": script.digest,
                                  "class_name": script.class_name, "digest_of": "file_bytes"})
    mapping = _callee_map(scripts)
    class_calls: dict[str, dict[str, tuple[gd_parse.Script, gd_parse.Function]]] = {}
    for script in scripts:
        if script.class_name:
            class_calls.setdefault(script.class_name, {}).update(
                {function.name: (script, function) for function in script.functions})

    entry_names = _action_methods(behavior)
    if not entry_names:
        unresolved.append("契约 action 里没有可识别的方法（只有 harness 动词），入口依赖信号连接或契约探测")

    entries: list[tuple[gd_parse.Script, gd_parse.Function]] = []
    missing_actions: list[str] = []
    for name in entry_names:
        targets, how = _resolve_function(name, mapping)
        if not targets:
            missing_actions.append(name)
            continue
        if how == "alias":
            unresolved.append("契约方法 %s 在源码中无同名函数，按 token 唯一匹配解析为 %s（契约/源码命名不一致，需评审）"
                              % (name, targets[0][1].name))
        if len({script.path for script, _ in targets}) > 1 or len(targets) > 1:
            record["analysis_status"] = "SOURCE_ENTRY_AMBIGUOUS"
            unresolved.append("方法 %s 在多个位置定义：%s" % (
                name, ", ".join("%s:%d" % (paths.rel(s.path), f.start_line) for s, f in targets)))
        for script, function in targets:
            entries.append((script, function))
            record["entry_points"].append({
                "name": function.name,
                "trigger": "contract_action",
                "file": paths.rel(script.path),
                "line": function.start_line,
                "params": function.params,
                "returns": function.returns,
                "source_reference": "%s:%d#func=%s" % (paths.rel(script.path),
                                                       function.start_line, function.name),
            })

    # 事件驱动入口：信号 connect 的处理函数（真实源码里的连接，不是猜的）
    for script in scripts:
        ready = script.function("_ready") or script.function("_enter_tree")
        if ready is None:
            continue
        for conn in gd_parse.connects(ready):
            handler = script.function(conn["handler"])
            if handler is None:
                unresolved.append("%s:%d 连接了 %s.%s 但找不到处理函数 %s"
                                  % (paths.rel(script.path), conn["line"], conn["emitter"],
                                     conn["signal"], conn["handler"]))
                continue
            reference = "%s:%d#func=%s" % (paths.rel(script.path), handler.start_line,
                                           handler.name)
            if any(item["source_reference"] == reference for item in record["entry_points"]):
                continue
            entries.append((script, handler))
            record["entry_points"].append({
                "name": handler.name,
                "trigger": "signal_handler",
                "signal": conn["signal"],
                "emitter": conn["emitter"],
                "file": paths.rel(script.path),
                "line": handler.start_line,
                "params": handler.params,
                "returns": handler.returns,
                "source_reference": reference,
            })

    # 回退：action 方法由 harness 间接驱动时，用契约 check 里被查询的方法作为入口
    # （`trigger.is_triggered` → 函数 is_triggered）；只接受源码里真实存在的函数。
    if not entries:
        for symbol in _check_symbols(behavior):
            targets, _how = _resolve_function(symbol, mapping)
            if len(targets) == 1:
                script, function = targets[0]
                entries.append((script, function))
                record["entry_points"].append({
                    "name": function.name, "trigger": "contract_probe",
                    "file": paths.rel(script.path), "line": function.start_line,
                    "params": function.params, "returns": function.returns,
                    "source_reference": "%s:%d#func=%s" % (paths.rel(script.path),
                                                           function.start_line, function.name)})
                unresolved.append("契约 action 没有对应函数（%s 由 harness 驱动），入口按契约探测方法 %s 认定"
                                  % (", ".join(missing_actions) or "无", symbol))

    # 回退 3：运动/接触类 Behavior 由帧推进驱动，入口就是帧回调（显式标注，不冒称契约入口）。
    if not entries:
        for frame_name in ("_physics_process", "_process"):
            targets, _how = _resolve_function(frame_name, mapping)
            if len(targets) == 1:
                script, function = targets[0]
                entries.append((script, function))
                record["entry_points"].append({
                    "name": function.name, "trigger": "frame_update",
                    "file": paths.rel(script.path), "line": function.start_line,
                    "params": function.params, "returns": function.returns,
                    "source_reference": "%s:%d#func=%s" % (paths.rel(script.path),
                                                           function.start_line, function.name)})
                unresolved.append("契约 action 均为 harness 驱动，入口按帧回调 %s 认定（未绑定具体方法）"
                                  % frame_name)
                break

    for name in missing_actions:
        if any(item["name"] == name for item in record["entry_points"]):
            continue
        unresolved.append("契约引用的方法 %s 不在实现文件，也不在信号处理入口（由 harness/组合层驱动）"
                          % name)

    if not entries:
        record["analysis_status"] = "SOURCE_ENTRY_AMBIGUOUS"
        unresolved.append("没有任何可确认入口：契约观测的是组合场景（触发源/门/位置等外部符号），"
                          "本 Feature 源码不含对应方法，需要跨 Feature 或场景级分析")
        return record

    callees = _collect(entries, mapping, class_calls)
    covered = entries + [(script, function) for script, function in callees]

    # ---- 状态变量 -------------------------------------------------------
    declared = {}
    for script in scripts:
        for item in script.variables + script.exports:
            declared.setdefault(item["name"], {"initial": item.get("value") or "",
                                               "declared_in": paths.rel(script.path),
                                               "declared_at_line": item["line"]})
    known = set(declared)
    state: dict[str, dict] = {}
    for script, function in covered:
        for read in gd_parse.state_reads(function, known):
            entry = state.setdefault(read["variable"], {
                "variable": read["variable"], "reads": [], "writes": [],
                "initial": declared[read["variable"]]["initial"],
                "declared_in": declared[read["variable"]]["declared_in"]})
            entry["reads"].append({"file": paths.rel(script.path), "line": read["line"],
                                   "function": function.name})
        for write in gd_parse.state_writes(function, known):
            entry = state.setdefault(write["variable"], {
                "variable": write["variable"], "reads": [], "writes": [],
                "initial": declared[write["variable"]]["initial"],
                "declared_in": declared[write["variable"]]["declared_in"]})
            entry["writes"].append({"file": paths.rel(script.path), "line": write["line"],
                                    "function": function.name})
    for item in state.values():
        item["read_count"] = len(item["reads"])
        item["write_count"] = len(item["writes"])
    record["state_variables"] = [state[key] for key in sorted(state)]

    # ---- 条件 / 事件 / 副作用 / 失败路径 --------------------------------
    for script, function in covered:
        for guard in gd_parse.guards(function):
            record["conditions"].append({"condition": guard["condition"],
                                         "file": paths.rel(script.path),
                                         "line": guard["line"], "function": function.name})
        for emit in gd_parse.emits(function):
            record["events"].append({"kind": "emit", "signal": emit["signal"],
                                     "file": paths.rel(script.path),
                                     "line": emit["line"], "function": function.name})
        for conn in gd_parse.connects(function):
            record["events"].append({"kind": "connect", "signal": conn["signal"],
                                     "emitter": conn["emitter"],
                                     "handler": conn["handler"],
                                     "file": paths.rel(script.path),
                                     "line": conn["line"], "function": function.name})
        for write in gd_parse.set_deferred(function):
            record["side_effects"].append({"kind": "deferred_property_write",
                                           "object": write["object"],
                                           "attribute": write["attribute"],
                                           "value": write["value"],
                                           "file": paths.rel(script.path),
                                           "line": write["line"]})
        for access in gd_parse.file_access(function):
            record["side_effects"].append({"kind": "file_access", "path": access["path"],
                                           "mode": access.get("mode", "READ"),
                                           "file": paths.rel(script.path),
                                           "line": access["line"]})
        for resource in gd_parse.resources(function):
            record["side_effects"].append({"kind": "resource_load", "path": resource["path"],
                                           "file": paths.rel(script.path),
                                           "line": resource["line"]})
        for node in gd_parse.nodes(function):
            record["side_effects"].append({"kind": "node_lookup", "path": node["path"],
                                           "file": paths.rel(script.path),
                                           "line": node["line"]})
        for dynamic in gd_parse.dynamic_calls(function):
            unresolved.append("%s:%d 含动态调用（%s），静态分析无法确定目标"
                              % (paths.rel(script.path), dynamic["line"], dynamic["text"]))

    for script, function in covered:
        for number, line in function.body:
            stripped = line.strip()
            if stripped in ("return", "return null"):
                record["failure_paths"].append({"kind": "guard_return", "value": "",
                                                "file": paths.rel(script.path),
                                                "line": number, "function": function.name})
            elif re.match(r"^return\s+(false|0|null|\[\]|\"\")", stripped):
                record["failure_paths"].append({"kind": "early_return",
                                                "value": stripped.split(None, 1)[1],
                                                "file": paths.rel(script.path),
                                                "line": number, "function": function.name})
            elif re.match(r"^if\s+.*(==\s*null|!=\s*null).*:$", stripped):
                record["failure_paths"].append({"kind": "null_guard",
                                                "condition": stripped,
                                                "file": paths.rel(script.path),
                                                "line": number, "function": function.name})

    # 契约里引用但源码观测不到的符号：显式记为未解决，不替契约圆场
    observed_names = {item["name"] for item in record["entry_points"]}
    declared_signals = {signal["name"] for script in scripts for signal in script.signals}
    for symbol in _check_symbols(behavior):
        if (symbol in mapping or symbol in declared or symbol in observed_names
                or symbol in declared_signals):
            continue
        unresolved.append("契约引用的符号 %s 在实现文件的函数/变量声明中未直接出现"
                          "（可能是引擎内建或实例属性）" % symbol)

    if record["analysis_status"] == "COMPLETE" and unresolved:
        record["analysis_status"] = "PARTIAL"
    for script in scripts:
        if not script.class_name:
            unresolved.append("%s 没有 class_name（跨类依赖无法静态归属）"
                              % paths.rel(script.path))
    return record


def output_path(feature_id: str, behavior_id: str, out_dir: str = "") -> str:
    base = out_dir or OUTPUT_DIR
    return os.path.join(base, feature_id, "%s.json" % behavior_id)


def write(record: dict, out_dir: str = "") -> str:
    path = output_path(record["feature_id"], record["behavior_id"], out_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Behavior source analysis")
    parser.add_argument("--feature")
    parser.add_argument("--behavior")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--out-dir", default="")
    args = parser.parse_args(argv)

    targets = []
    if args.all:
        targets = [(item["feature_id"], item["behavior_id"])
                   for item in paths.supported_behaviors()]
    elif args.feature and args.behavior:
        targets = [(args.feature, args.behavior)]
    else:
        parser.error("either --all or --feature/--behavior is required")

    stats: dict[str, int] = {}
    for feature_id, behavior_id in targets:
        record = analyze(feature_id, behavior_id)
        write(record, args.out_dir)
        stats[record["analysis_status"]] = stats.get(record["analysis_status"], 0) + 1
        print("%-58s %-26s entries=%d unresolved=%d"
              % ("%s/%s" % (feature_id, behavior_id), record["analysis_status"],
                 len(record["entry_points"]), len(record["unresolved_questions"])))
    print("analyzed=%d %s" % (len(targets), json.dumps(stats, ensure_ascii=False)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
