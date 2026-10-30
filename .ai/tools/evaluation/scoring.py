#!/usr/bin/env python3
"""Evaluation Scoring —— 端到端能力评估的判定与指标（Phase 1.36）。

定位：**纯函数**模块。不执行命令、不读文件、不驱动 Godot，只把
「步骤结果」折叠为「阶段状态」与「任务判定」，再折叠为「指标」。

为什么单独一层：
    评估最容易失去客观性的地方是**判定口径**（什么算通过、分母是什么）。
    把口径写成可单测的纯函数，报告里的每个数字都能回溯到同一套规则，
    而不是由 runner 里散落的 if 分支临时决定。

状态词表（与任务书 §6 一致）：
    PASS         已执行并通过
    FAIL         已执行但失败
    SKIP         明确跳过（附原因）
    NOT_EXECUTED 未实际执行
    INCOMPLETE   执行中断或未完成（超时、互斥锁冲突等）
    UNAVAILABLE  环境不具备执行条件（如 Godot 缺失）

阶段（Phase）含义见 tasks.yaml；判定规则：
    阶段 PASS  ⇐ 该阶段全部步骤 PASS，且至少一个步骤
    阶段 FAIL  ⇐ 任一必检步骤 FAIL（FAIL 优先于其它状态）
    阶段 INCOMPLETE / UNAVAILABLE ⇐ 无 FAIL 时按最严重的非 PASS 状态
    阶段 SKIP  ⇐ 全部步骤 SKIP
    阶段 NOT_EXECUTED ⇐ 该阶段没有任何步骤证据
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_SKIP = "SKIP"
STATUS_NOT_EXECUTED = "NOT_EXECUTED"
STATUS_INCOMPLETE = "INCOMPLETE"
STATUS_UNAVAILABLE = "UNAVAILABLE"

STATUSES = (STATUS_PASS, STATUS_FAIL, STATUS_SKIP,
            STATUS_NOT_EXECUTED, STATUS_INCOMPLETE, STATUS_UNAVAILABLE)

# 严重度：FAIL 最强，其余按「越不可判定越靠前」
_SEVERITY = {
    STATUS_FAIL: 5,
    STATUS_INCOMPLETE: 4,
    STATUS_UNAVAILABLE: 3,
    STATUS_NOT_EXECUTED: 2,
    STATUS_SKIP: 1,
    STATUS_PASS: 0,
}

PHASES = ("plan", "artifacts", "loadable", "behavior", "negative", "regression")


def normalize_status(value: Any) -> str:
    """把任意输入收敛到状态词表；未知值一律视为 INCOMPLETE（不静默放行为 PASS）。"""
    text = str(value or "").strip().upper()
    return text if text in STATUSES else STATUS_INCOMPLETE


def step_status(step: Mapping[str, Any]) -> str:
    """单个步骤的状态：以显式 status 为准，缺省按 exit == expect 推 PASS/FAIL。"""
    if "status" in step and step["status"]:
        return normalize_status(step["status"])
    if "exit" not in step:
        return STATUS_NOT_EXECUTED
    expected = step.get("expect_exit", 0)
    return STATUS_PASS if int(step["exit"]) == int(expected) else STATUS_FAIL


def fold_statuses(statuses: Iterable[str]) -> str:
    """把一组状态折叠成一个：任一 FAIL → FAIL；否则取最严重者。"""
    cleaned = [normalize_status(s) for s in statuses]
    if not cleaned:
        return STATUS_NOT_EXECUTED
    return max(cleaned, key=lambda s: _SEVERITY[s])


def phase_status(steps: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """把一个阶段的步骤折叠为 {status, checks, detail}。"""
    items = list(steps)
    if not items:
        return {"status": STATUS_NOT_EXECUTED, "checks": 0, "detail": "no evidence"}
    statuses = [(str(step.get("id") or "?"), step_status(step)) for step in items]
    status = fold_statuses(status for _, status in statuses)
    failed = [name for name, s in statuses if s == STATUS_FAIL]
    detail = ""
    if failed:
        detail = "failed: " + ", ".join(failed)
    elif status != STATUS_PASS:
        detail = "status " + status
    return {"status": status, "checks": len(statuses), "detail": detail}


def summarize_phases(steps: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """按 phase 字段分组折叠；步骤缺 phase 时归入 "artifacts"。"""
    grouped: dict[str, list] = {phase: [] for phase in PHASES}
    for step in steps:
        phase = str(step.get("phase") or "artifacts")
        grouped.setdefault(phase, []).append(step)
    return {phase: phase_status(items) for phase, items in grouped.items()}


def task_verdict(phases: Mapping[str, Mapping[str, Any]],
                 required: Iterable[str] = PHASES) -> dict[str, Any]:
    """任务判定：必需阶段全部 PASS 才算 PASS。

    required 里的阶段若为 NOT_EXECUTED / SKIP / INCOMPLETE / UNAVAILABLE，
    任务不得判 PASS —— 未执行不等于通过（任务书 §6 的硬约束）。
    """
    required_list = [str(p) for p in required]
    missing = [p for p in required_list if p not in phases]
    blocking = []
    for phase in required_list:
        status = normalize_status((phases.get(phase) or {}).get("status"))
        if status != STATUS_PASS:
            blocking.append("%s=%s" % (phase, status))
    status = STATUS_PASS if not blocking else (
        STATUS_FAIL if any("=FAIL" in item for item in blocking) else STATUS_INCOMPLETE)
    return {
        "status": status,
        "required": required_list,
        "blocking": blocking + ["%s=NOT_EXECUTED" % p for p in missing],
    }


def attempt_passed(steps: Iterable[Mapping[str, Any]]) -> bool:
    """一次尝试是否通过：**只看它自己的步骤**（不能借用其它尝试的证据）。

    任务级通过与否由 `task_verdict(phases, required_phases)` 判定；
    尝试级只回答「这一步计划是否原地跑通」，用于区分首次通过 / 计划修订 / 框架修复。
    """
    items = list(steps)
    if not items:
        return False
    return fold_statuses(step_status(step) for step in items) == STATUS_PASS


def _ratio(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "value": (round(numerator / denominator, 4) if denominator else None),
        "numerator": numerator,
        "denominator": denominator,
        "undefined_reason": "" if denominator else "denominator=0",
    }


def compute_metrics(runs: Iterable[Mapping[str, Any]],
                    human_interventions: int = 0,
                    cost: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """把任务结果折叠为报告指标；每个比率都带分子/分母。

    分母约定（必须显式写进报告）：
        first_pass  —— 分母 = 已尝试任务数（不含 NOT_EXECUTED / UNAVAILABLE）
        final_pass  —— 分母 = 已尝试任务数
        auto_repair —— 分母 = 框架自动修复尝试次数（人工改计划不计入）
        regression  —— 分母 = 实际执行的回归检查数
    """
    items = list(runs)
    executed = [r for r in items
                if normalize_status(r.get("verdict")) not in
                (STATUS_NOT_EXECUTED, STATUS_UNAVAILABLE)]

    first_pass = 0
    final_pass = 0
    for run in executed:
        if run.get("first_pass"):
            first_pass += 1
        if normalize_status(run.get("verdict")) == STATUS_PASS:
            final_pass += 1

    auto_total = 0
    auto_ok = 0
    plan_total = 0
    plan_ok = 0
    for run in executed:
        for attempt in run.get("attempts") or []:
            kind = str(attempt.get("kind") or "initial")
            if kind == "framework":
                auto_total += 1
                auto_ok += 1 if attempt.get("passed") else 0
            elif kind in ("plan_revision", "manual"):
                plan_total += 1
                plan_ok += 1 if attempt.get("passed") else 0

    regression_checks = 0
    regression_failed = 0
    for run in executed:
        for phase, info in (run.get("phases") or {}).items():
            if phase != "regression":
                continue
            checks = int(info.get("checks") or 0)
            if str(info.get("status")) in (STATUS_NOT_EXECUTED, STATUS_SKIP):
                continue
            regression_checks += checks
            if str(info.get("status")) == STATUS_FAIL:
                regression_failed += 1

    durations = {str(r.get("task_id")): float(r.get("duration_s") or 0.0) for r in items}
    counts = {status: 0 for status in STATUSES}
    for run in items:
        counts[normalize_status(run.get("verdict"))] += 1

    return {
        "tasks_total": len(items),
        "tasks_attempted": len(executed),
        "tasks_by_verdict": counts,
        "first_pass_rate": _ratio(first_pass, len(executed)),
        "final_pass_rate": _ratio(final_pass, len(executed)),
        "auto_repair_success_rate": _ratio(auto_ok, auto_total),
        "plan_revision_success_rate": _ratio(plan_ok, plan_total),
        "regression_defects": {
            "value": regression_failed,
            "denominator": regression_checks,
            "note": "任务级回归阶段失败的次数 / 实际执行的回归检查数",
        },
        "human_interventions": human_interventions,
        "task_duration_s": durations,
        "total_duration_s": round(sum(durations.values()), 3),
        "cost": dict(cost or {"status": STATUS_UNAVAILABLE,
                              "reason": "仓库无模型/资源用量计量入口"}),
    }
