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

# Batch E (Phase 1.76): the declaration grammar also accepts the Godot 3 bare
# modifiers, so a declaration is never dropped just because it predates the `@`
# syntax (`onready var x`, `export var x`, `export(Type) var x`, `remote func f()`).
# Capturing a modifier is NOT the same as understanding it: every captured
# declaration whose semantics are only partly modelled is still reported as a
# partially interpreted construct.
VAR_MODIFIERS = ("onready", "export", "static")
FUNC_MODIFIERS = ("static", "remote", "master", "puppet", "remotesync",
                  "mastersync", "puppetsync", "sync", "slave")
_VAR_MOD_ALT = "|".join(VAR_MODIFIERS)
_FUNC_MOD_ALT = "|".join(FUNC_MODIFIERS)
_ANY_MOD_ALT = "|".join(VAR_MODIFIERS + FUNC_MODIFIERS)
VAR_MOD_PREFIX = r"(?P<mods>(?:(?:%s)\s+)*)" % _VAR_MOD_ALT
FUNC_MOD_PREFIX = r"(?P<mods>(?:(?:%s)\s+)*)" % _FUNC_MOD_ALT

FUNC_RE = re.compile(r"^" + FUNC_MOD_PREFIX +
                     r"func\s+(?P<name>\w+)\s*"
                     r"\((?P<params>[^)]*)\)\s*(?:->\s*(?P<ret>[^:]+))?\s*:")
SIGNAL_RE = re.compile(r"^signal\s+(?P<name>\w+)\s*(?:\((?P<params>[^)]*)\))?")
CLASS_RE = re.compile(r"^class_name\s+(?P<name>\w+)")
EXTENDS_RE = re.compile(r"^extends\s+(?P<base>[\w\.\"]+)")
# Godot 3 legacy export: `export var`, `export(Type) var`, `export(int, 0, 100) var`.
LEGACY_EXPORT_RE = re.compile(r"^export\s*(?P<hint>\([^()]*\))?\s*(?P<rest>var\b.*)$")

# Phase 1.75: one declaration grammar for `var` and `@export`/`@onready`/`@rpc`/
# `@tool`/`static var`, accepting BOTH `=` and `:=` initialisers, an optional
# type annotation and an optional trailing `:` that opens a property block.
# The trailing colon is stripped by the caller before matching.
ANNOTATION_RE = re.compile(r"^@(?P<name>[A-Za-z_]\w*)\s*(?:\((?P<args>[^)]*)\))?\s*$")
ANN_PREFIX = r"(?:@[A-Za-z_]\w*(?:\([^)]*\))?\s+)*"
DECL_RE = re.compile(r"^(?P<ann>" + ANN_PREFIX + r")?"
                     + VAR_MOD_PREFIX +
                     r"var\s+(?P<name>[A-Za-z_]\w*)"
                     r"(?:\s*:\s*(?P<type>[^=:]+?))?"
                     r"(?:\s*(?P<op>:=|=)\s*(?P<value>.*))?$")
CONST_RE = re.compile(r"^(?P<ann>" + ANN_PREFIX + r")?"
                      r"const\s+(?P<name>[A-Za-z_]\w*)"
                      r"(?:\s*:\s*(?P<type>[^=:]+?))?"
                      r"\s*(?P<op>:=|=)\s*(?P<value>.*)$")
ENUM_RE = re.compile(r"^enum\s+(?P<name>[A-Za-z_]\w*)")
INNER_CLASS_RE = re.compile(r"^class\s+(?P<name>[A-Za-z_]\w*)\s*:")
ACCESSOR_RE = re.compile(r"^(?P<kind>get|set)\s*(?:\((?P<param>[^)]*)\))?\s*:$")
DECL_SHAPED_RE = re.compile(r"^(?:" + ANN_PREFIX + r")?"
                            r"(?:(?:" + _ANY_MOD_ALT + r")\s*"
                            r"(?:\([^()]*\))?\s*)*"
                            r"(?:var|const|signal|func|class|enum)\b")
FUNC_START_RE = re.compile(r"^(?:(?:%s)\s+)*func\s" % _FUNC_MOD_ALT)
CLASS_START_RE = re.compile(r"^(?:(?:%s)\s+)*class\s" % _ANY_MOD_ALT)
ENUM_START_RE = re.compile(r"^(?:(?:%s)\s+)*enum\s" % _ANY_MOD_ALT)

# Batch E: the three coordinate spaces a line number can live in. The parser only
# ever knows the first one — the file it actually read.
LINE_SPACE_ANALYSIS = "ANALYZED_FILE"
EXTENT_NOT_INTERPRETED = "NOT_INTERPRETED"
EXTENT_PARTIALLY_INTERPRETED = "PARTIALLY_INTERPRETED"
SETGET_ARGS_RE = re.compile(r"^(?P<setter>[A-Za-z_]\w*)?\s*"
                            r"(?:,\s*(?P<getter>[A-Za-z_]\w*))?$")

# Batch E: a top-level line the grammar did not capture is still a declaration gap
# when it carries one of these keywords, even if the line does not start with it
# (`export(Type) var x` used to be dropped silently this way).
DECLARATION_KEYWORDS = ("var", "func", "const", "signal", "enum", "class",
                        "static", "onready", "export", "setget")
# Top-level statements that are not declarations and are handled elsewhere.
HARMLESS_TOP_LEVEL = ("tool", "extends", "class_name", "pass")

# Kept as aliases so any external importer keeps working; the semantics are now
# the unified declaration grammar above.
EXPORT_RE = DECL_RE
VAR_RE = DECL_RE

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
    properties: list[dict] = field(default_factory=list)
    declarations: list[dict] = field(default_factory=list)
    coverage: dict = field(default_factory=dict)

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


def _brackets_balanced(text: str) -> bool:
    depth = 0
    for char in text:
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
    return depth <= 0


def _join_declaration(lines: list[str], index: int, *, until_colon: bool,
                      limit: int = 20) -> tuple[str, int]:
    """Join a declaration that continues over several physical lines.

    The joined text is only used for matching; the recorded line numbers stay
    the real ones (first line of the declaration), so nothing is fabricated.
    """
    text = lines[index].rstrip()
    last = index
    if text.endswith("\\"):
        text = text[:-1].rstrip()
        while last + 1 < len(lines) and (last - index) < limit:
            last += 1
            piece = lines[last].strip()
            continues = piece.endswith("\\")
            if continues:
                piece = piece[:-1].rstrip()
            text = (text + " " + piece).strip()
            if not continues and _brackets_balanced(text):
                break
        return text, last
    if until_colon:
        while (not text.rstrip().endswith(":") and last + 1 < len(lines)
               and (last - index) < limit):
            last += 1
            text = text.rstrip() + " " + lines[last].strip()
        return text, last
    while (not _brackets_balanced(text) and last + 1 < len(lines)
           and (last - index) < limit):
        last += 1
        text = text.rstrip() + " " + lines[last].strip()
    return text, last


def _annotation_names(text: str) -> list[dict]:
    found = []
    for match in re.finditer(r"@([A-Za-z_]\w*)\s*(?:\(([^)]*)\))?", text):
        found.append({"name": match.group(1),
                      "args": (match.group(2) or "").strip(),
                      "interpreted": match.group(1) in KNOWN_ANNOTATIONS})
    return found


KNOWN_ANNOTATIONS = frozenset({
    "export", "export_range", "export_enum", "export_flags", "export_category",
    "export_group", "export_subgroup", "export_file", "export_dir",
    "export_global_file", "export_global_dir", "export_multiline",
    "export_placeholder", "export_exp_easing", "export_color_no_alpha",
    "export_node_path", "export_storage", "onready", "tool", "icon", "rpc",
    "static_unload", "warning_ignore", "abstract",
})

# Annotations that actually export a member. `@export_category` / `@export_group`
# / `@export_subgroup` only organise the inspector and never export the member
# they precede, so they must not turn a plain `var` into an export.
EXPORT_ANNOTATIONS = frozenset({
    "export", "export_range", "export_enum", "export_flags", "export_file",
    "export_dir", "export_global_file", "export_global_dir", "export_multiline",
    "export_placeholder", "export_exp_easing", "export_color_no_alpha",
    "export_node_path", "export_storage",
})


def _construct(code: str, line: int, *, name: str = "",
               detail: dict | None = None,
               extent: str = EXTENT_NOT_INTERPRETED, reason: str = "",
               predecessor: str = "", declaration_gap: bool = True) -> dict:
    """One unsupported / partly supported construct, with its coordinate space.

    `line` keeps its historical meaning (a line of the analysed file). The
    coordinate space is now stated explicitly instead of being implied, and
    `extent` separates "the declaration is missing from the symbol table" from
    "the declaration is captured but the construct is only partly modelled".
    """
    item = {"code": code,
            "line": line,
            "line_space": LINE_SPACE_ANALYSIS,
            "analysis_line": line,
            "extent": extent,
            "declaration_gap": declaration_gap,
            "reason": reason}
    if name:
        item["name"] = name
    if detail:
        item["detail"] = detail
    if predecessor:
        item["predecessor_code"] = predecessor
    return item


def _find_outside_strings(text: str, token: str) -> int:
    """Index of `token` as a whole word outside string literals, else -1."""
    in_string = None
    index = 0
    while index < len(text):
        char = text[index]
        if in_string:
            if char == "\\":
                index += 2
                continue
            if char == in_string:
                in_string = None
            index += 1
            continue
        if char in "\"'":
            in_string = char
        elif text.startswith(token, index):
            before = text[index - 1] if index else " "
            after_at = index + len(token)
            after = text[after_at] if after_at < len(text) else " "
            if not (before.isalnum() or before == "_") and not (
                    after.isalnum() or after == "_"):
                return index
        index += 1
    return -1


def _split_legacy_setget(body: str) -> tuple[str, dict | None]:
    """Split the Godot 3 `setget` suffix off a declaration body.

    Returns the declaration without the suffix and the accessor information, or
    `None` when the line has no `setget` token outside a string literal.
    """
    at = _find_outside_strings(body, "setget")
    if at < 0:
        return body, None
    head = body[:at].rstrip()
    args_text = body[at + len("setget"):].strip()
    match = SETGET_ARGS_RE.match(args_text)
    interpreted = bool(match and (match.group("setter") or match.group("getter")))
    return head, {"setter": (match.group("setter") if interpreted else None),
                  "getter": (match.group("getter") if interpreted else None),
                  "interpreted": interpreted,
                  "args_text": args_text}


def _multiline_string_lines(raw_lines: list[str]) -> set[int]:
    """Line numbers that belong to a triple-quoted string block.

    Batch E: text inside a multi-line string is not code. Without this, a C# or
    shell snippet embedded in a GDScript string looked like an unsupported
    declaration and was reported as a false positive.
    """
    inside: set[int] = set()
    token = ""
    for number, line in enumerate(raw_lines, start=1):
        if token:
            inside.add(number)
        cursor = 0
        while cursor < len(line):
            if not token:
                for candidate in ('"""', "'''"):
                    if line.startswith(candidate, cursor):
                        token = candidate
                        inside.add(number)
                        cursor += len(candidate)
                        break
                else:
                    cursor += 1
                continue
            if line.startswith(token, cursor):
                inside.add(number)
                cursor += len(token)
                token = ""
                continue
            cursor += 1
    return inside


def _modifier_names(text: str, allowed: tuple[str, ...]) -> list[str]:
    return re.findall(r"\b(?:%s)\b" % "|".join(allowed), text or "")


def _normalise_constructs(items: list[dict]) -> list[dict]:
    """Deterministic order and no duplicate (code, line, name) triples."""
    ordered = sorted(items, key=lambda item: (int(item.get("line") or 0),
                                              str(item.get("code") or ""),
                                              str(item.get("name") or "")))
    unique: list[dict] = []
    seen: set[tuple] = set()
    for item in ordered:
        key = (item.get("code"), item.get("line"), item.get("name") or "")
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def project_construct_lines(items: list[dict], *, source_offset: int | None = None,
                            record_offset: int | None = None) -> list[dict]:
    """Add explicit `source_line` / `record_line` without rewriting `line`.

    `analysis_line` (== `line`) is a line of the file the parser read. A caller
    that knows how the analysed copy relates to the pinned commit passes that
    offset here. Unknown mappings stay `None` instead of being guessed.
    """
    projected = []
    for item in items:
        entry = dict(item)
        analysis_line = int(entry.get("analysis_line") or entry.get("line") or 0)
        source_line = (analysis_line - source_offset
                       if source_offset is not None and analysis_line else None)
        entry["source_line"] = source_line
        entry["record_line"] = (source_line + record_offset
                                if source_line is not None
                                and record_offset is not None else None)
        projected.append(entry)
    return projected


def _declaration_entry(kind: str, name: str, line: int, *, end_line: int | None = None,
                       type_annotation: str = "", value: str = "",
                       annotations: list[dict] | None = None,
                       initializer_kind: str = "NONE", extra: dict | None = None) -> dict:
    entry = {
        "name": name,
        "line": line,
        "end_line": end_line or line,
        "declaration_kind": kind,
        "type": type_annotation or "",
        "value": value,
        "annotations": annotations or [],
        "has_initializer": value != "",
        "initializer_kind": initializer_kind,
    }
    if extra:
        entry.update(extra)
    return entry


def parse_text(path: str, text: str) -> Script:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    script = Script(path=path, digest=digest)
    raw_lines = text.splitlines()
    script._lines = raw_lines
    lines = [_strip_comment(item) for item in raw_lines]

    current: Function | None = None
    current_indent = 0
    recognized: dict[int, str] = {}
    pending: list[dict] = []
    unsupported: list[dict] = []
    setget_lines: set[int] = set()
    total = len(lines)
    index = 0
    while index < total:
        number = index + 1
        line = lines[index]
        stripped = line.strip()

        if not stripped:
            if current is not None:
                current.body.append((number, ""))
                current.end_line = number
            index += 1
            continue
        width = _indent_width(line)
        if current is not None and width > current_indent:
            current.body.append((number, line))
            current.end_line = number
            index += 1
            continue
        if current is not None:
            current = None

        # A standalone annotation line applies to the next declaration only.
        if width == 0 and stripped.startswith("@") and ANNOTATION_RE.match(stripped):
            match = ANNOTATION_RE.match(stripped)
            name = match.group("name")
            pending.append({"name": name,
                            "args": (match.group("args") or "").strip(),
                            "line": number,
                            "interpreted": name in KNOWN_ANNOTATIONS})
            recognized[number] = "ANNOTATION"
            index += 1
            continue

        if width != 0:
            index += 1
            continue

        opens_property = (stripped.endswith(":")
                          and DECL_SHAPED_RE.match(stripped)
                          and not FUNC_START_RE.match(stripped)
                          and not CLASS_START_RE.match(stripped)
                          and not ENUM_START_RE.match(stripped))

        if FUNC_START_RE.match(stripped):
            joined, last = _join_declaration(lines, index, until_colon=True)
            match = FUNC_RE.match(joined.strip())
            if match:
                current = Function(name=match.group("name"),
                                   params=(match.group("params") or "").strip(),
                                   returns=(match.group("ret") or "").strip(),
                                   start_line=number, end_line=last + 1)
                current_indent = width
                script.functions.append(current)
                script.declarations.append(_declaration_entry(
                    "FUNCTION", current.name, number, end_line=last + 1,
                    annotations=pending))
                unmodelled = [item for item
                              in _modifier_names(match.group("mods") or "",
                                                 FUNC_MODIFIERS) if item != "static"]
                if unmodelled:
                    unsupported.append(_construct(
                        "LEGACY_RPC_MODIFIER_NOT_INTERPRETED", number,
                        name=current.name, extent=EXTENT_PARTIALLY_INTERPRETED,
                        declaration_gap=False,
                        reason="the function is captured, but the Godot 3 RPC "
                               "modifier carries network-authority semantics this "
                               "parser does not model",
                        detail={"modifiers": unmodelled}))
                for offset in range(index, last + 1):
                    recognized[offset + 1] = "FUNCTION"
                pending = []
                index = last + 1
                continue
            index += 1
            continue

        legacy_export = LEGACY_EXPORT_RE.match(stripped)
        if legacy_export is not None:
            body = legacy_export.group("rest").strip()
            last = index
        elif opens_property:
            body = stripped[:-1].rstrip()
            last = index
        else:
            body, last = _join_declaration(lines, index, until_colon=False)

        match = SIGNAL_RE.match(body)
        if match:
            entry = {"name": match.group("name"),
                     "params": (match.group("params") or "").strip(),
                     "line": number,
                     "declaration_kind": "SIGNAL"}
            script.signals.append(entry)
            script.declarations.append(entry)
            recognized[number] = "SIGNAL"
            pending = []
            index = last + 1
            continue

        match = CLASS_RE.match(body)
        if match:
            script.class_name = match.group("name")
            recognized[number] = "CLASS_NAME"
            pending = []
            index = last + 1
            continue

        match = EXTENDS_RE.match(body)
        if match:
            script.extends = match.group("base").strip()
            recognized[number] = "EXTENDS"
            pending = []
            index = last + 1
            continue

        match = ENUM_RE.match(body)
        if match:
            unsupported.append(_construct(
                "ENUM_NOT_INTERPRETED", number, name=match.group("name"),
                reason="enum members are not interpreted, so no enum symbol or "
                       "member is available to the symbol table"))
            recognized[number] = "ENUM"
            pending = []
            index = last + 1
            continue

        match = INNER_CLASS_RE.match(body)
        if match:
            unsupported.append(_construct(
                "INNER_CLASS_NOT_INTERPRETED", number, name=match.group("name"),
                reason="the inner class body is not interpreted, so its members "
                       "are absent from the symbol table"))
            recognized[number] = "INNER_CLASS"
            pending = []
            index = last + 1
            continue

        decl_body, setget = (body, None) if opens_property else _split_legacy_setget(body)
        if setget is not None:
            setget_lines.add(number)
        match = DECL_RE.match(decl_body)
        if match:
            modifiers = _modifier_names(match.group("mods") or "", VAR_MODIFIERS)
            annotations = list(pending) + _annotation_names(decl_body)
            hint_text = (legacy_export.group("hint") or "") if legacy_export else ""
            export_hint = hint_text[1:-1].strip() if hint_text else ""
            export_like = bool(legacy_export is not None or "export" in modifiers
                               or any(item["name"] in EXPORT_ANNOTATIONS
                                      for item in annotations))
            type_annotation = (match.group("type") or "").strip()
            if not type_annotation and export_hint:
                primary = export_hint.split(",")[0].strip()
                if re.match(r"^[A-Za-z_]\w*$", primary):
                    type_annotation = primary
            value = (match.group("value") or "").strip()
            operator = match.group("op") or ""
            initializer_kind = ("NONE" if not value
                                else "INFERRED" if operator == ":=" else "EXPLICIT")
            entry = _declaration_entry(
                "PROPERTY" if opens_property else "VARIABLE",
                match.group("name"), number, end_line=last + 1,
                type_annotation=type_annotation,
                value=value, annotations=annotations,
                initializer_kind=initializer_kind,
                extra={"is_exported": export_like,
                       "is_static": "static" in modifiers,
                       "is_onready": ("onready" in modifiers
                                      or any(item["name"] == "onready"
                                             for item in annotations))})
            if legacy_export is not None:
                entry["export_syntax"] = ("LEGACY_PARENTHESISED"
                                          if legacy_export.group("hint") is not None
                                          else "LEGACY_BARE")
                if export_hint and "," in export_hint:
                    unsupported.append(_construct(
                        "LEGACY_EXPORT_HINT_ARGS_NOT_INTERPRETED", number,
                        name=match.group("name"),
                        extent=EXTENT_PARTIALLY_INTERPRETED,
                        declaration_gap=False,
                        reason="the declaration and its type are captured, but the "
                               "extra legacy `export(...)` hint arguments (range or "
                               "allowed values) are not modelled",
                        detail={"hint": export_hint}))
            if opens_property:
                entry.update({"has_getter": False, "has_setter": False,
                              "accessors": []})
                cursor = last + 1
                while cursor < total:
                    inner = lines[cursor]
                    if not inner.strip():
                        cursor += 1
                        continue
                    if _indent_width(inner) <= width:
                        break
                    accessor = ACCESSOR_RE.match(inner.strip())
                    if not accessor:
                        cursor += 1
                        continue
                    accessor_indent = _indent_width(inner)
                    stop = cursor + 1
                    while stop < total and (not lines[stop].strip()
                                            or _indent_width(lines[stop]) > accessor_indent):
                        stop += 1
                    kind = accessor.group("kind")
                    entry["accessors"].append({
                        "kind": kind, "line": cursor + 1, "end_line": stop,
                        "param": (accessor.group("param") or "").strip()})
                    entry["has_%s" % ("getter" if kind == "get" else "setter")] = True
                    for offset in range(cursor, stop):
                        recognized[offset + 1] = "ACCESSOR"
                    cursor = stop
                last = max(last, cursor - 1)
                script.properties.append(entry)
            elif export_like:
                script.exports.append(entry)
            else:
                script.variables.append(entry)
            if setget is not None:
                entry["legacy_setget"] = {"setter": setget["setter"],
                                          "getter": setget["getter"],
                                          "interpreted": setget["interpreted"],
                                          "args_text": setget["args_text"]}
                if setget["setter"]:
                    entry["has_setter"] = True
                if setget["getter"]:
                    entry["has_getter"] = True
                if setget["interpreted"]:
                    unsupported.append(_construct(
                        "LEGACY_SETGET_WIRING_NOT_MODELED", number,
                        name=match.group("name"),
                        extent=EXTENT_PARTIALLY_INTERPRETED,
                        declaration_gap=False,
                        reason="the declaration and its accessor names are captured, "
                               "but the Godot 3 implicit accessor call on assignment "
                               "is not modelled",
                        predecessor="LEGACY_SETGET_NOT_INTERPRETED",
                        detail={"setter": setget["setter"],
                                "getter": setget["getter"]}))
                else:
                    unsupported.append(_construct(
                        "LEGACY_SETGET_SYNTAX_UNRECOGNISED", number,
                        name=match.group("name"),
                        reason="`setget` is present but its accessor list could not "
                               "be parsed, so the accessor wiring is unknown",
                        detail={"args_text": setget["args_text"]}))
            script.declarations.append(entry)
            for offset in range(index, last + 1):
                recognized.setdefault(offset + 1,
                                      "PROPERTY" if opens_property else "VARIABLE")
            pending = []
            index = last + 1
            continue

        match = CONST_RE.match(body)
        if match:
            entry = _declaration_entry(
                "CONSTANT", match.group("name"), number, end_line=last + 1,
                type_annotation=(match.group("type") or "").strip(),
                value=(match.group("value") or "").strip(),
                annotations=list(pending) + _annotation_names(body),
                initializer_kind="EXPLICIT")
            script.constants.append(entry)
            script.declarations.append(entry)
            for offset in range(index, last + 1):
                recognized[offset + 1] = "CONSTANT"
            pending = []
            index = last + 1
            continue

        index = max(last, index) + 1

    inside_string = _multiline_string_lines(raw_lines)
    for number, line in enumerate(lines, start=1):
        if number in inside_string:
            continue
        stripped = line.strip()
        if "lambda" in stripped:
            unsupported.append(_construct(
                "LAMBDA_NOT_ANALYZED", number, declaration_gap=False,
                reason="the anonymous function body is not interpreted, so its "
                       "captures and effects are unknown"))
        if number not in setget_lines and _find_outside_strings(line, "setget") >= 0:
            unsupported.append(_construct(
                "LEGACY_SETGET_UNATTRIBUTED", number, declaration_gap=False,
                reason="`setget` appears on a line this parser did not capture as a "
                       "top-level property declaration, so its wiring is unknown"))

    unrecognized: list[dict] = []
    for number, line in enumerate(lines, start=1):
        if number in inside_string:
            continue
        stripped = line.strip()
        if not stripped or number in recognized:
            continue
        if _indent_width(line) != 0 or stripped.startswith(("#", "@")):
            continue
        if stripped.split()[0] in HARMLESS_TOP_LEVEL:
            continue
        keyword = next((word for word in DECLARATION_KEYWORDS
                        if _find_outside_strings(stripped, word) >= 0), "")
        if DECL_SHAPED_RE.match(stripped) or keyword:
            unrecognized.append({"line": number,
                                 "line_space": LINE_SPACE_ANALYSIS,
                                 "analysis_line": number,
                                 "kind_hint": keyword or stripped.split()[0],
                                 "declaration_keyword": keyword,
                                 "extent": EXTENT_NOT_INTERPRETED,
                                 "declaration_gap": True,
                                 "reason": "a declaration-shaped top-level line the "
                                           "grammar did not capture, so its symbols "
                                           "are absent from the symbol table",
                                 "text": stripped[:80]})

    unsupported = _normalise_constructs(unsupported)
    not_interpreted = [item for item in unsupported
                       if item["extent"] == EXTENT_NOT_INTERPRETED]
    partially = [item for item in unsupported
                 if item["extent"] == EXTENT_PARTIALLY_INTERPRETED]
    declaration_gaps = [item for item in unsupported if item["declaration_gap"]]
    coverage_status = "PARTIAL" if (unsupported or unrecognized) else "COMPLETE"
    script.coverage = {
        "parse_execution_status": "PARSED",
        "syntax_coverage_status": coverage_status,
        "analysis_completeness": ("DECLARATION_GAPS"
                                  if (unrecognized or declaration_gaps) else "FULL"),
        "unsupported_constructs": unsupported,
        "unrecognized_declarations": unrecognized,
        "source_coordinates": LINE_SPACE_ANALYSIS,
        "line_coordinates": {
            "line": LINE_SPACE_ANALYSIS,
            "analysis_line": LINE_SPACE_ANALYSIS,
            "source_line": "NOT_MAPPED_BY_PARSER",
            "record_line": "NOT_MAPPED_BY_PARSER",
            "note": "the parser only knows the file it read; a caller that knows "
                    "how that copy relates to the pinned commit must call "
                    "project_construct_lines() and never reuse `line` as a "
                    "source or record coordinate",
        },
        "coverage_derivation": {
            "authoritative_field": "syntax_coverage_status",
            "rule": "COMPLETE only when no unsupported construct and no "
                    "unrecognized declaration remains; analysis_completeness "
                    "never upgrades syntax coverage",
            "unsupported_total": len(unsupported),
            "unsupported_not_interpreted": len(not_interpreted),
            "unsupported_partially_interpreted": len(partially),
            "declaration_gaps": len(declaration_gaps),
            "unrecognized_declarations": len(unrecognized),
            "forcing_codes": sorted({item["code"] for item in unsupported}),
        },
        "declaration_count": len(script.declarations),
    }
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
