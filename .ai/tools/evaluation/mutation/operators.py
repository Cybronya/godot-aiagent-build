#!/usr/bin/env python3
"""Mutation Operators —— 精确、可拒绝的受控代码修改（Phase 1.59）。

设计要点（为什么不是简单的字符串替换）：

1. **锚点必须唯一**：出现 0 次或多次都拒绝，不做"尽力而为"的替换。
2. **语句边界**：`delete_statement` 的锚点必须是一条完整源码行（含行尾换行），
   且对齐到行首，避免削掉半行代码。
3. **空 diff 拒绝**：替换后内容不变 → 拒绝（否则会得到一个"看起来跑了"的假 mutant）。
4. **结构守恒**：修改前后的括号**平衡度**必须一致（删除一整句合法语句时总数会变，
   但不允许把半个表达式删掉导致块结构失衡）。
5. 所有拒绝都以 `OperatorError` 抛出，调用方必须把它记为 **INVALID_MUTANT**，
   不能当成"检测成功"，也不能当成"漏检"。

本模块只处理文本，不读写文件、不执行任何东西。
"""

from __future__ import annotations

import difflib

OPERATOR_IDS = ("replace_exact", "delete_statement")

_OPEN_CLOSE = (("(", ")"), ("[", "]"), ("{", "}"))


class OperatorError(Exception):
    """锚点/前置条件不满足：必须拒绝应用。"""


def delimiter_balance(text: str) -> dict:
    """每种括号的 (开 - 闭) 平衡度：用于证明修改没有破坏块结构（不是语法解析器）。

    删除一条完整语句时开/闭总数会同时减少，平衡度不变；而删掉半个多行表达式
    会让平衡度改变——这正是需要拒绝的情况。
    """
    return {"%s%s" % pair: text.count(pair[0]) - text.count(pair[1])
            for pair in _OPEN_CLOSE}


def _occurrences(text: str, anchor: str) -> int:
    if not anchor:
        raise OperatorError("anchor is empty")
    return text.count(anchor)


def _reject(reason: str, detail: str = "") -> None:
    raise OperatorError(reason + (": " + detail if detail else ""))


def replace_exact(text: str, anchor: str, replacement: str = "") -> str:
    """整段精确替换（锚点唯一）。"""
    count = _occurrences(text, anchor)
    if count != 1:
        _reject("anchor_not_unique", "found %d occurrence(s), expected exactly 1" % count)
    mutated = text.replace(anchor, replacement, 1)
    if mutated == text:
        _reject("empty_diff", "replacement produced identical content")
    return mutated


def delete_statement(text: str, anchor: str, replacement: str = "") -> str:
    """删除一条完整语句行（锚点含换行且对齐到行首）。"""
    if replacement:
        _reject("operator_mismatch", "delete_statement does not accept a replacement")
    if not anchor.endswith("\n") or anchor.count("\n") != 1:
        _reject("anchor_not_a_single_line",
                "anchor must contain exactly one trailing newline")
    count = _occurrences(text, anchor)
    if count != 1:
        _reject("anchor_not_unique", "found %d occurrence(s), expected exactly 1" % count)
    aligned = text.startswith(anchor) or ("\n" + anchor) in text
    if not aligned:
        _reject("anchor_not_line_aligned",
                "anchor does not start at the beginning of a source line")
    mutated = text.replace(anchor, "", 1)
    if mutated == text:
        _reject("empty_diff", "deleting the statement produced identical content")
    return mutated


_OPERATORS = {"replace_exact": replace_exact, "delete_statement": delete_statement}


def apply_operator(operator: str, text: str, anchor: str,
                   replacement: str = "") -> str:
    """按 operator id 修改文本，并验证块结构没有被破坏。"""
    handler = _OPERATORS.get(str(operator or ""))
    if handler is None:
        _reject("unknown_operator", "%r is not one of %s"
                % (operator, ", ".join(OPERATOR_IDS)))
    mutated = handler(text, anchor, replacement)
    before = delimiter_balance(text)
    after = delimiter_balance(mutated)
    if before != after:
        _reject("structure_changed",
                "delimiter balance changed: %s -> %s" % (before, after))
    return mutated


def unified_diff(path: str, before: str, after: str, context: int = 3) -> str:
    """可审计的修改前后 diff（写入 run 目录）。"""
    return "".join(difflib.unified_diff(
        before.splitlines(keepends=True), after.splitlines(keepends=True),
        fromfile="a/" + path, tofile="b/" + path, n=context))
