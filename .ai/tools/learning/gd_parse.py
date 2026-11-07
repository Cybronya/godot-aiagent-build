"""GDScript 轻量静态解析（Phase 1.65）。

只做「够用于行为源码分析」的事情：声明、函数体、调用、信号、写入。**不做**类型推导，
也不假装理解动态调用——遇到无法静态确定的写法，调用方必须记 `UNKNOWN`。

设计原则：
- 纯文本、无第三方依赖、可重复（同输入同输出）。
- 每个结论都带行号，行号是来源可追溯性的最小单位。
- 解析失败不抛异常给调用方以外的地方：返回 `ParseError` 由上层转成 `SOURCE_NOT_FOUND`/`UNRESOLVED`。
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field

FUNC_RE = re.compile(r"^(?P<indent>\s*)(?:static\s+)?func\s+(?P<name>\w+)\s*"
                     r"\((?P<params>[^)]*)\)\s*(?:->\s*(?P<ret>[^:]+))?\s*:")
SIGNAL_RE = re.compile(r"^signal\s+(?P<name>\w+)\s*(?:\((?P<params>[^)]*)\))?")
CLASS_RE = re.compile(r"^class_name\s+(?P<name>\w+)")
EXTENDS_RE = re.compile(r"^extends\s+(?P<base>[\w\.\"]+)")
EXPORT_RE = re.compile(r"^@export\s+(?:var\s+)?(?P<name>\w+)\s*(?::\s*(?P<type>[\w\[\]]+))?"
                       r"\s*(?::=\s*(?P<value>.+))?$")
VAR_RE = re.compile(r"^(?:@onready\s+)?var\s+(?P<name>\w+)\s*(?::\s*(?P<type>[\w\[\]\.]+))?"
                    r"\s*(?::=\s*(?P<value>.+))?$")
CONST_RE = re.compile(r"^const\s+(?P<name>\w+)\s*(?::\s*(?P<type>[\w\[\]]+))?\s*:?=\s*(?P<value>.+)$")

EMIT_RE = re.compile(r"(?P<signal>\w+)\s*\.\s*emit\s*\(")
EMIT_SIGNAL_RE = re.compile(r"emit_signal\s*\(\s*[\"'](?P<signal>\w+)[\"']")
CALL_RE = re.compile(r"(?P<receiver>[A-Za-z_]\w*)\s*\.\s*(?P<method>[A-Za-z_]\w*)\s*\(")
CONNECT_RE = re.compile(r"(?P<emitter>[A-Za-z_]\w*(?:\.[A-Za-z_]\w+)?)\s*\.\s*(?P<signal>\w+)"
                        r"\s*\.\s*connect\s*\(\s*(?P<handler>[A-Za-z_]\w+)")
# 单标识信号写法：`body_entered.connect(_on_body_entered)`（emitter 就是自身节点）
CONNECT_SIMPLE_RE = re.compile(r"(?<![\w.])(?P<signal>[A-Za-z_]\w*)\s*\.\s*connect\s*\("
                               r"\s*(?P<handler>[A-Za-z_]\w+)")
ATTR_WRITE_RE = re.compile(r"(?P<receiver>self\.)?(?P<obj>[A-Za-z_]\w*)\.(?P<attr>[A-Za-z_]\w*)"
                           r"\s*(?:=|\.set_deferred\s*\()")
SET_DEFERRED_RE = re.compile(r"(?P<obj>[A-Za-z_]\w*)\.set_deferred\s*\(\s*[\"'](?P<attr>\w+)[\"']"
                             r"\s*,\s*(?P<value>[^)]*)\)")
FILE_ACCESS_RE = re.compile(r"FileAccess\.(?:open|open_encrypted)\s*\(\s*(?P<path>[^,)]+)"
                             r"(?:\s*,\s*(?P<mode>[A-Za-z_\.]+))?")
RESOURCE_RE = re.compile(r"(?:preload|load)\s*\(\s*[\"'](?P<path>[^\"']+)[\"']")
NODE_RE = re.compile(r"get_node(?:_or_null)?\s*\(\s*[\"'](?P<path>[^\"']+)[\"']")
GUARD_RE = re.compile(r"^\s*(?:if|elif|while|match)\b")
RETURN_RE = re.compile(r"^\s*return\b\s*(?P<value>.*)$")
DYNAMIC_RE = re.compile(r"\b(?:call|call_deferred|callv|Callable|funcref)\s*\(")


class ParseError(ValueError):
    """文件缺失或不是可解析的 GDScript。"""


@dataclass
class Function:
    name: str
    params: str
    returns: str
    start_line: int
    end_line: int
    body: list[tuple[int, str]] = field(default_factory=list)

    def text(self) -> str:
        return "\n".join(line for _, line in self.body)


@dataclass
class Script:
    path: str
    digest: str
    class_name: str = ""
    extends: str = ""
    signals: list[dict] = field(default_factory=list)
    exports: list[dict] = field(default_factory=list)
    variables: list[dict] = field(default_factory=list)
    constants: list[dict] = field(default_factory=list)
    functions: list[Function] = field(default_factory=list)

    def function(self, name: str) -> Function | None:
        for item in self.functions:
            if item.name == name:
                return item
        return None

    def all_lines(self) -> list[str]:
        return list(self._lines)

    def __post_init__(self) -> None:
        self._lines = []


def _strip_comment(line: str) -> str:
    out = []
    in_string = None
    for index, char in enumerate(line):
        if in_string:
            out.append(char)
            if char == in_string and line[index - 1] != "\\":
                in_string = None
            continue
        if char in "\"'":
            in_string = char
        if char == "#":
            break
        out.append(char)
    return "".join(out).rstrip()


def _indent_width(line: str) -> int:
    expanded = line.replace("\t", "    ")
    return len(expanded) - len(expanded.lstrip(" "))


def parse_text(path: str, text: str) -> Script:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    script = Script(path=path, digest=digest)
    raw_lines = text.splitlines()
    script._lines = raw_lines
    lines = [_strip_comment(item) for item in raw_lines]

    current: Function | None = None
    current_indent = 0
    for index, line in enumerate(lines, start=1):
        if not line.strip():
            if current is not None:
                current.body.append((index, ""))
                current.end_line = index
            continue
        width = _indent_width(line)
        if current is not None and width > current_indent:
            current.body.append((index, line))
            current.end_line = index
            continue
        current = None

        match = FUNC_RE.match(line)
        if match:
            current = Function(name=match.group("name"),
                               params=(match.group("params") or "").strip(),
                               returns=(match.group("ret") or "").strip(),
                               start_line=index, end_line=index)
            current_indent = width
            script.functions.append(current)
            continue

        stripped = line.strip()
        match = CLASS_RE.match(stripped)
        if match:
            script.class_name = match.group("name")
            continue
        match = EXTENDS_RE.match(stripped)
        if match:
            script.extends = match.group("base").strip()
            continue
        match = SIGNAL_RE.match(stripped)
        if match:
            script.signals.append({"name": match.group("name"),
                                   "params": (match.group("params") or "").strip(),
                                   "line": index})
            continue
        if width == 0:
            match = EXPORT_RE.match(stripped)
            if match:
                script.exports.append({"name": match.group("name"),
                                       "type": (match.group("type") or "").strip(),
                                       "value": (match.group("value") or "").strip(),
                                       "line": index})
                continue
            match = CONST_RE.match(stripped)
            if match:
                script.constants.append({"name": match.group("name"),
                                         "value": match.group("value").strip(),
                                         "line": index})
                continue
            match = VAR_RE.match(stripped)
            if match:
                script.variables.append({"name": match.group("name"),
                                         "type": (match.group("type") or "").strip(),
                                         "value": (match.group("value") or "").strip(),
                                         "line": index})
                continue
    return script


def parse_file(path: str) -> Script:
    if not os.path.isfile(path):
        raise ParseError("script not found: %s" % path)
    with open(path, encoding="utf-8", errors="replace") as handle:
        return parse_text(path, handle.read())


def emits(function: Function) -> list[dict]:
    found = []
    for number, line in function.body:
        for match in EMIT_RE.finditer(line):
            found.append({"signal": match.group("signal"), "line": number})
        for match in EMIT_SIGNAL_RE.finditer(line):
            found.append({"signal": match.group("signal"), "line": number})
    return found


def connects(function: Function) -> list[dict]:
    found = []
    seen = set()
    for number, line in function.body:
        for match in CONNECT_RE.finditer(line):
            key = (match.group("signal"), match.group("handler"))
            if key in seen:
                continue
            seen.add(key)
            found.append({"emitter": match.group("emitter"),
                          "signal": match.group("signal"),
                          "handler": match.group("handler"),
                          "line": number})
        for match in CONNECT_SIMPLE_RE.finditer(line):
            key = (match.group("signal"), match.group("handler"))
            if key in seen:
                continue
            seen.add(key)
            found.append({"emitter": "self",
                          "signal": match.group("signal"),
                          "handler": match.group("handler"),
                          "line": number})
    return found


def calls(function: Function) -> list[dict]:
    found = []
    for number, line in function.body:
        for match in CALL_RE.finditer(line):
            receiver = match.group("receiver")
            method = match.group("method")
            if receiver in ("self",) or method in ("emit", "connect", "call_deferred",
                                                   "set_deferred", "new"):
                continue
            found.append({"receiver": receiver, "method": method, "line": number})
    return found


def attribute_writes(function: Function) -> list[dict]:
    found = []
    for number, line in function.body:
        for match in ATTR_WRITE_RE.finditer(line):
            obj = match.group("obj")
            if obj in ("self", "_visual") or obj[0].isdigit():
                continue
            found.append({"object": obj, "attribute": match.group("attr"), "line": number})
    return found


def set_deferred(function: Function) -> list[dict]:
    return [{"object": match.group("obj"), "attribute": match.group("attr"),
             "value": match.group("value").strip(), "line": number}
            for number, line in function.body
            for match in SET_DEFERRED_RE.finditer(line)]


def file_access(function: Function) -> list[dict]:
    return [{"path": match.group("path").strip(),
            "mode": (match.group("mode") or "READ").split(".")[-1],
            "line": number}
            for number, line in function.body
            for match in FILE_ACCESS_RE.finditer(line)]


def resources(function: Function) -> list[dict]:
    return [{"path": match.group("path"), "line": number}
            for number, line in function.body
            for match in RESOURCE_RE.finditer(line)]


def nodes(function: Function) -> list[dict]:
    return [{"path": match.group("path"), "line": number}
            for number, line in function.body
            for match in NODE_RE.finditer(line)]


def guards(function: Function) -> list[dict]:
    found = []
    for number, line in function.body:
        if GUARD_RE.match(line):
            found.append({"condition": line.strip(), "line": number})
        match = RETURN_RE.match(line)
        if match and match.group("value").strip():
            found.append({"condition": "return %s" % match.group("value").strip(),
                          "line": number})
    return found


def dynamic_calls(function: Function) -> list[dict]:
    return [{"line": number, "text": line.strip()}
            for number, line in function.body if DYNAMIC_RE.search(line)]


def state_reads(function: Function, known: set[str]) -> list[dict]:
    """函数体里读到的 `_state` 变量（赋值左侧不算读）。"""
    found = []
    for number, line in function.body:
        for name in known:
            if re.search(r"(?<![\w.])%s(?!\w)" % re.escape(name), line):
                if re.match(r"^\s*%s\s*(?::=|=)" % re.escape(name), line):
                    continue
                found.append({"variable": name, "line": number})
    return found


def state_writes(function: Function, known: set[str]) -> list[dict]:
    found = []
    for number, line in function.body:
        for name in known:
            if re.match(r"^\s*%s\s*(?::=|\+=|-=|=)" % re.escape(name), line):
                found.append({"variable": name, "line": number})
    return found
