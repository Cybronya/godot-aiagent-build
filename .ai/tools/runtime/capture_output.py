#!/usr/bin/env python3
"""Godot Output Parser —— 把 Godot 的原始输出拆成结构化 runtime 事件。

职责：只做「事实抽取」，不做「原因判断」。

    - 识别 ERROR / SCRIPT ERROR / WARNING 块，并保留 raw_output
    - 从消息、内联位置（<file>:<line>）、`at:` 行、GDScript backtrace 中
      抽取 script / line / function
    - 标记命中的已知错误模式（patterns），供 diagnose_runtime.py 分类使用
    - 重复出现的同一条错误合并为一个条目并记录 repeat

已知模式（对应任务要求的 Runtime Error 识别清单，模式名 -> 事实来源）：
    node_not_found      Node not found
    null_instance       null instance / is null
    invalid_get_index   Invalid get index
    invalid_set_index   Invalid set index
    invalid_assignment  Invalid assignment
    invalid_access      Invalid access
    invalid_call        Invalid call
    unknown_function    Function/function ... not found / not found in base
    parser_error        Parse Error / Parser Error / Compile Error
    resource_missing    Cannot load resource / Cannot open file /
                        Failed loading resource / Failed to load / No loader found /
                        referenced non-existent resource
    signal_error        signal / Signal
    crash               Program crashed / Fatal / Segmentation / abort /
                        handle_crash

本模块只输出事实；把事实映射为错误分类（classification）是 diagnose_runtime.py
的职责，禁止在这里编造原因。

用法:
    python .ai/tools/runtime/capture_output.py <log-file> [--json]

作为模块导入:
    from capture_output import parse_output
    parsed = parse_output(stdout_text, stderr_text)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any

# ---------- 结构 ----------

ERROR_PREFIX_RE = re.compile(
    r"^(SCRIPT ERROR|USER SCRIPT ERROR|ERROR|USER ERROR|WARNING|USER WARNING|FATAL):\s?(.*)$"
)
# Godot 的定位行： "   at: get_node (scene/main/node.cpp:1975)"
AT_RE = re.compile(r"^\s+at:\s*(?P<context>.*?)\s*\((?P<file>[^()]+?)(?::(?P<line>\d+))?\)\s*$")
# GDScript backtrace： "       [0] _ready (res://Scenes/x.gd:6)"
BACKTRACE_RE = re.compile(
    r"^\s+\[(?P<index>\d+)\]\s+(?P<func>.*?)\s*\((?P<file>[^()]+?)(?::(?P<line>\d+))?\)\s*$"
)
# 内联位置（.tscn 解析错误）： "res://Scenes/X.tscn:7 - Parse Error: ..."
INLINE_LOCATION_RE = re.compile(r"^(?P<file>res://[^\s:]+):(?P<line>\d+)\s*-\s*(?P<rest>.*)$")

# ---------- 已知模式 ----------

PATTERNS: dict[str, str] = {
    "node_not_found": r"Node not found",
    "null_instance": r"null instance|\bis null\b",
    "invalid_get_index": r"Invalid get index",
    "invalid_set_index": r"Invalid set index",
    "invalid_assignment": r"Invalid assignment",
    "invalid_access": r"Invalid access",
    "invalid_call": r"Invalid call",
    "unknown_function": r"[Ff]unction .* not found|[Nn]ot found in base",
    "parser_error": r"Parse [Ee]rror|Parser Error|Compile [Ee]rror",
    "resource_missing": (
        r"Cannot load resource|Cannot open file|Failed loading resource|Failed to load"
        r"|No loader found|referenced non-existent resource"
    ),
    "signal_error": r"\bsignal\b|\bSignal\b",
    "crash": r"Program crashed|Fatal|Segmentation|handle_crash|\babort\b",
}
PATTERN_RES = {name: re.compile(rx) for name, rx in PATTERNS.items()}

_SEVERITY_BY_PREFIX = {
    "ERROR": "error",
    "USER ERROR": "error",
    "SCRIPT ERROR": "error",
    "USER SCRIPT ERROR": "error",
    "FATAL": "error",
    "WARNING": "warning",
    "USER WARNING": "warning",
}
_TYPE_BY_PREFIX = {
    "ERROR": "runtime_error",
    "USER ERROR": "runtime_error",
    "SCRIPT ERROR": "script_error",
    "USER SCRIPT ERROR": "script_error",
    "FATAL": "runtime_error",
    "WARNING": "warning",
    "USER WARNING": "warning",
}
_USER_PREFIXES = {"USER ERROR", "USER WARNING", "USER SCRIPT ERROR"}


SCRIPT_SUFFIXES = (".gd", ".cs", ".gdshader", ".gdshaderinc")


def _is_godot_source(path: str) -> bool:
    return path.startswith("res://") or path.startswith("user://")


def _is_script(path: str) -> bool:
    return path.lower().endswith(SCRIPT_SUFFIXES)


def _strip_inline_location(message: str) -> tuple[str, str, int]:
    """拆出消息中内联的 <res://file>:<line> 位置。"""
    match = INLINE_LOCATION_RE.match(message.strip())
    if not match:
        return message, "", 0
    return match.group("rest").strip(), match.group("file"), int(match.group("line"))


def _match_patterns(text: str) -> list[str]:
    return sorted(name for name, rx in PATTERN_RES.items() if rx.search(text))


def _blocks(text: str) -> list[tuple[str, list[str]]]:
    """按行切分输出：以 ERROR/WARNING 前缀行开始，遇空行或下一条目结束。"""
    blocks: list[tuple[str, list[str]]] = []
    current_type = ""
    current: list[str] = []
    for raw_line in (text or "").splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            if current:
                blocks.append((current_type, current))
                current, current_type = [], ""
            continue
        match = ERROR_PREFIX_RE.match(line.strip())
        if match:
            if current:
                blocks.append((current_type, current))
            current_type = match.group(1)
            current = [line.strip()]
            continue
        if current:
            current.append(line)
    if current:
        blocks.append((current_type, current))
    return blocks


def _first_location(lines: list[str]) -> tuple[str, int, str]:
    """从块内取第一个 res:// 位置（at: 行优先，其次 backtrace）。"""
    for line in lines[1:]:
        match = AT_RE.match(line)
        if match and _is_godot_source(match.group("file").strip()):
            return (match.group("file").strip(),
                    int(match.group("line") or 0),
                    match.group("context").strip())
    for line in lines[1:]:
        match = BACKTRACE_RE.match(line)
        if match and _is_godot_source(match.group("file").strip()):
            return (match.group("file").strip(),
                    int(match.group("line") or 0),
                    match.group("func").strip())
    return "", 0, ""


def _entry(block_type: str, lines: list[str], source: str) -> dict[str, Any]:
    prefix_match = ERROR_PREFIX_RE.match(lines[0])
    prefix = prefix_match.group(1) if prefix_match else block_type
    message = (prefix_match.group(2) if prefix_match else lines[0]).strip()
    message, inline_file, inline_line = _strip_inline_location(message)

    detail_lines = [ln.strip() for ln in lines[1:]
                    if not AT_RE.match(ln) and not BACKTRACE_RE.match(ln) and not ln.strip().startswith("GDScript backtrace")]
    script, line, function = _first_location(lines)
    if not script and inline_file:
        script, line, function = inline_file, inline_line, ""
    # 位置可能指向脚本，也可能指向资源（如 .tscn 解析错误）：分别记录事实
    resource = ""
    if script and not _is_script(script):
        resource, script = script, ""

    # 事实文本：消息 + 定位行，用于模式识别
    text = "\n".join([lines[0]] + lines[1:])
    severity = _SEVERITY_BY_PREFIX.get(prefix, "error" if block_type.endswith("ERROR") else "warning")
    entry = {
        "type": _TYPE_BY_PREFIX.get(prefix, block_type.lower()),
        "severity": severity,
        "message": message,
        "detail": " ".join(detail_lines).strip(),
        "script": script,
        "resource": resource,
        "line": line,
        "function": function,
        "source": source,
        "patterns": _match_patterns(text),
        "repeat": 1,
    }
    return entry


def _signature(entry: dict[str, Any]) -> tuple:
    return (entry["type"], entry["message"], entry["script"], entry["line"])


def parse_text(text: str, source: str = "stderr") -> list[dict[str, Any]]:
    """解析单份 Godot 输出文本，去重并合并重复条目。"""
    entries: list[dict[str, Any]] = []
    index: dict[tuple, dict[str, Any]] = {}
    for block_type, lines in _blocks(text):
        entry = _entry(block_type, lines, source)
        key = _signature(entry)
        if key in index:
            index[key]["repeat"] += 1
            continue
        index[key] = entry
        entries.append(entry)
    return entries


def parse_output(stdout: str = "", stderr: str = "") -> dict[str, Any]:
    """解析完整运行输出。

    返回:
        {
          "raw_output": <stdout+stderr 原文>,
          "parsed_errors": [...],     # severity == error
          "parsed_warnings": [...],   # severity == warning（含 Godot 泄漏等噪音）
          "counts": {"errors": int, "warnings": int},
        }
    """
    stdout = stdout or ""
    stderr = stderr or ""
    entries = parse_text(stderr, "stderr") + parse_text(stdout, "stdout")
    # 去重：同一条错误 stdout/stderr 都出现时只保留一次
    seen: set[tuple] = set()
    unique: list[dict[str, Any]] = []
    for entry in entries:
        key = _signature(entry)
        if key in seen:
            continue
        seen.add(key)
        unique.append(entry)
    errors = [e for e in unique if e["severity"] == "error"]
    warnings = [e for e in unique if e["severity"] == "warning"]
    return {
        "raw_output": stdout + stderr,
        "parsed_errors": errors,
        "parsed_warnings": warnings,
        "counts": {"errors": len(errors), "warnings": len(warnings)},
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Parse Godot runtime output into structured events.")
    parser.add_argument("log", help="Log file containing Godot stdout/stderr")
    parser.add_argument("--json", action="store_true", help="Print the parsed structure as JSON")
    args = parser.parse_args(argv)

    try:
        text = open(args.log, encoding="utf-8", errors="replace").read()
    except OSError as exc:
        print("FAIL: cannot read log: %s (%s)" % (args.log, exc))
        return 2

    parsed = parse_output("", text)
    if args.json:
        print(json.dumps(parsed, indent=2, ensure_ascii=False))
        return 0

    print("Godot Output Parser")
    print("Log: %s" % args.log)
    print("Parsed errors: %d, warnings: %d" % (parsed["counts"]["errors"], parsed["counts"]["warnings"]))
    for entry in parsed["parsed_errors"] + parsed["parsed_warnings"]:
        location = entry["script"] or "<engine>"
        if entry["line"]:
            location += ":%d" % entry["line"]
        print("  - [%s] %s (%s) patterns=%s repeat=%d"
              % (entry["severity"], entry["message"][:120], location, entry["patterns"], entry["repeat"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
