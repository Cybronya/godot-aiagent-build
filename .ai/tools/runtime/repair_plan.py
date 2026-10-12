#!/usr/bin/env python3
"""Repair Plan —— 把 Diagnosis 转成受安全策略约束的修复计划。

职责：
    - 决定「该不该改」：安全边界（第十一部分）在这里强制
    - 产出 repair_plan（契约见 .ai/context/repair_plan_schema.yaml）
    - 复核修复可行性（调用 repair_engine 的分析，但不修改项目）

安全边界（硬约束）：
    - 只允许修改：报错脚本 / 被验证场景 / 相关 Feature 内的文件
    - 每次尝试只允许一个文件，且只允许一种修改形式（单点字面量替换）
    - 禁止：删除 Feature / 删除 Scene / 修改 Project Settings / 修改 AI Framework /
      修改 Skill Registry / 修改 Validator / 修改无关 Feature / 修改 addons
    - 无法确定时：repairable: false + 明确 reason，禁止编造原因

不负责：应用修改（repair_engine.py）、流程编排（self_repair.py）。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    print("FAIL: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    raise SystemExit(2)

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from repair_engine import analyze_node_path_error                       # noqa: E402
from runtime_result import load_contract, load_repair_safety            # noqa: E402

REPAIR_KEYS = ("attempt", "error", "target", "reason", "changes", "validation", "risk", "repairable")

DEFAULT_VALIDATION_STEPS = (
    "run feature tests",
    "run scene validation",
    "run runtime playtest",
)


def _relative_ref(project_root: Path, path: Path) -> str:
    try:
        return "res://" + path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def safety_violation(project_root: Path, target: Path, error: dict, scene: str,
                     safety: dict | None = None) -> str:
    """返回违规原因；空串表示允许修改。"""
    safety = safety or load_repair_safety()
    root = project_root.resolve()
    resolved = target.resolve()
    try:
        rel = resolved.relative_to(root).as_posix()
    except ValueError:
        return "target is outside the project root: %s" % resolved

    for prefix in safety.get("forbidden_path_prefixes") or []:
        if rel.startswith(str(prefix)):
            return "target path is protected: %s (forbidden prefix %r)" % (rel, prefix)
    if rel in set(safety.get("forbidden_paths") or []):
        return "target path is protected: %s" % rel

    # 允许范围：报错脚本 / 被验证场景 / 相关 Feature 内文件
    allowed = False
    error_script = str(error.get("file") or "")
    if error_script.startswith("res://") and _relative_ref(root, resolved) == error_script:
        allowed = True
    if scene and _relative_ref(root, resolved) == scene:
        allowed = True
    feature = str(error.get("related_feature") or "")
    if feature and rel.startswith("Features/%s/" % feature):
        allowed = True
    if not allowed:
        return ("target is outside the allowed repair scope "
                "(error script / playtest scene / related feature): %s" % rel)
    return ""


def _plan_error_block(error: dict, scene: str) -> dict[str, Any]:
    return {
        "classification": str(error.get("classification") or error.get("type") or "unknown_runtime_error"),
        "message": str(error.get("message") or "").strip(),
        "file": str(error.get("file") or ""),
        "line": int(error.get("line") or 0),
        "scene": scene,
        "confidence": str(error.get("confidence") or "low"),
    }


def build_plan(diagnosis: dict, project_root: str | os.PathLike,
               attempt: int = 1, contract: dict | None = None,
               safety: dict | None = None,
               allow_medium: bool = False) -> dict[str, Any]:
    """根据 diagnosis 构建 repair_plan（只读分析，不修改项目）。"""
    contract = contract or load_contract()
    safety = safety or load_repair_safety()
    root = Path(project_root).resolve()
    block = diagnosis.get("diagnosis") or {}
    scene = str(block.get("scene") or "")
    candidates = [entry for entry in (block.get("errors") or []) if isinstance(entry, dict)]

    plan: dict[str, Any] = {
        "repair": {
            "attempt": int(attempt),
            "error": {},
            "target": {"file": "", "scope": "", "feature": ""},
            "reason": "",
            "changes": [],
            "validation": list(DEFAULT_VALIDATION_STEPS),
            "risk": "unknown",
            "repairable": False,
        },
        "_edit": None,
        "_scene": scene,
    }
    if not candidates:
        plan["repair"]["reason"] = "no error to repair (playtest status: %s)" % block.get("playtest_status")
        return plan

    strategy_owner = None
    analysis = None
    for entry in candidates:
        if entry.get("repair_strategy") != "node_path_literal":
            continue
        result = analyze_node_path_error(root, entry, scene)
        if result.get("ok"):
            confidence = str(result.get("confidence") or "low")
            if confidence == "high" or (confidence == "medium" and allow_medium):
                strategy_owner, analysis = entry, result
                break
            if analysis is None:
                strategy_owner, analysis = entry, result  # 记录但可能不采纳
        elif analysis is None:
            strategy_owner, analysis = entry, result

    primary = strategy_owner or candidates[0]
    plan["repair"]["error"] = _plan_error_block(primary, scene)

    if strategy_owner is None or analysis is None:
        classification = plan["repair"]["error"]["classification"]
        plan["repair"]["reason"] = (
            "no deterministic repair strategy for classification %r "
            "(automatic repair is limited to node_not_found with a unique node path literal)"
            % classification
        )
        return plan

    plan["repair"]["error"] = _plan_error_block(strategy_owner, scene)

    if not analysis.get("ok"):
        plan["repair"]["reason"] = "repair not applicable: %s" % (analysis.get("reason") or "unknown")
        return plan

    confidence = str(analysis.get("confidence"))
    if confidence == "medium" and not allow_medium:
        plan["repair"]["reason"] = (
            "candidate confidence is medium (%s -> %s, score %.2f); rerun with --allow-medium to accept"
            % (analysis.get("token"), analysis.get("candidate_path"), float(analysis.get("score") or 0.0))
        )
        plan["repair"]["target"] = {
            "file": analysis.get("target_rel") or "",
            "scope": "script" if str(analysis.get("target_rel", "")).endswith(".gd") else "scene",
            "feature": str(strategy_owner.get("related_feature") or ""),
        }
        return plan

    violation = safety_violation(root, Path(analysis["target_file"]), strategy_owner, scene, safety)
    if violation:
        plan["repair"]["reason"] = "blocked by repair safety policy: %s" % violation
        plan["repair"]["target"] = {"file": analysis.get("target_rel") or "", "scope": "", "feature": ""}
        return plan

    scope = "script" if str(analysis.get("target_rel", "")).endswith(".gd") else "scene"
    risk = "low" if (confidence == "high" and scope == "script") else "medium"
    plan["repair"].update({
        "target": {
            "file": analysis.get("target_rel") or "",
            "scope": scope,
            "feature": str(strategy_owner.get("related_feature") or ""),
        },
        "reason": (
            "hardcoded node path %r does not resolve; closest declared node in %s is %r "
            "(owner node path %r, score %.2f)"
            % (analysis.get("token"), scene or "<none>", analysis.get("candidate_path"),
               analysis.get("owner_path"), float(analysis.get("score") or 0.0))
        ),
        "changes": [
            "replace node path literal %s with %s in %s"
            % (analysis.get("old_literal"), analysis.get("new_literal"), analysis.get("target_rel"))
        ],
        "risk": risk,
        "repairable": True,
    })
    plan["_edit"] = {
        "target_file": str(analysis["target_file"]),
        "target_rel": analysis.get("target_rel") or "",
        "old_literal": analysis["old_literal"],
        "new_literal": analysis["new_literal"],
        "confidence": confidence,
        "score": analysis.get("score"),
        "candidate_path": analysis.get("candidate_path"),
        "owner_path": analysis.get("owner_path"),
        "strategy": "node_path_literal",
        "change_kind": "replace_single_literal",
    }
    return plan


def validate_plan(plan: dict, safety: dict | None = None) -> list[str]:
    """复核 plan 是否满足 repair_plan_schema 与安全策略。"""
    safety = safety or load_repair_safety()
    failures: list[str] = []
    repair = plan.get("repair") if isinstance(plan, dict) else None
    if not isinstance(repair, dict):
        return ["repair plan must contain a 'repair' mapping"]
    for key in REPAIR_KEYS:
        if key not in repair:
            failures.append("repair plan missing key: %s" % key)
    if failures:
        return failures

    if repair["repairable"]:
        if not repair["target"].get("file"):
            failures.append("repairable plan requires target.file")
        if not repair["changes"]:
            failures.append("repairable plan requires at least one change")
        edit = plan.get("_edit") or {}
        if edit.get("change_kind") not in set(safety.get("allowed_change_kinds") or []):
            failures.append("change kind %r is not allowed by repair safety"
                            % edit.get("change_kind"))
        if not edit.get("old_literal") or not edit.get("new_literal"):
            failures.append("repairable plan requires old_literal/new_literal")
        elif edit["old_literal"] == edit["new_literal"]:
            failures.append("repair would not change anything")
    else:
        if not repair["reason"]:
            failures.append("non-repairable plan requires a reason")
        if repair["changes"]:
            failures.append("non-repairable plan must not declare changes")
    return failures


def plan_to_yaml(plan: dict) -> str:
    """只序列化契约内的字段（下划线开头的是运行时内部字段）。"""
    public = {key: value for key, value in plan.items() if not str(key).startswith("_")}
    return yaml.safe_dump(public, sort_keys=False, allow_unicode=True, width=4096)


def print_plan(plan: dict) -> None:
    repair = plan["repair"]
    print("Repair Plan (attempt %d)" % repair["attempt"])
    print("  error:      %s" % repair["error"].get("classification"))
    print("  message:    %s" % repair["error"].get("message"))
    print("  target:     %s%s" % (repair["target"].get("file") or "<none>",
                                  " [%s]" % repair["target"]["scope"] if repair["target"].get("scope") else ""))
    print("  repairable: %s" % repair["repairable"])
    print("  reason:     %s" % repair["reason"])
    for change in repair["changes"]:
        print("  change:     %s" % change)
    print("  risk:       %s" % repair["risk"])


def main(argv=None) -> int:
    """独立入口：从 diagnosis YAML/JSON 生成 repair plan（dry run，不修改项目）。"""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Build a repair plan from a diagnosis (dry run).")
    parser.add_argument("diagnosis", help="diagnosis file (YAML or JSON)")
    parser.add_argument("--project", default=".", help="Project root")
    parser.add_argument("--attempt", type=int, default=1)
    parser.add_argument("--allow-medium", action="store_true", help="Accept medium-confidence candidates")
    parser.add_argument("--out", default="", help="Write repair plan YAML to this path")
    args = parser.parse_args(argv)

    path = Path(args.diagnosis)
    if not path.is_file():
        print("FAIL: diagnosis not found: %s" % args.diagnosis)
        return 2
    text = path.read_text(encoding="utf-8")
    data = json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)

    plan = build_plan(data, args.project, attempt=args.attempt, allow_medium=args.allow_medium)
    failures = validate_plan(plan)
    print_plan(plan)
    if args.out:
        Path(args.out).write_text(plan_to_yaml(plan), encoding="utf-8")
        print("repair plan written: %s" % args.out)
    for failure in failures:
        print("PLAN ERROR: %s" % failure)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
