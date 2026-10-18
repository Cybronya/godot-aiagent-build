#!/usr/bin/env python3
"""Level Orchestration Validator（Phase 1.13）

校验关卡编排配置（`.ai/context/level_schema.yaml`）与其引用是否真实存在：

    1. schema / level.id —— 契约标识与关卡标识
    2. entities —— 实体 id 与实体场景（res:// 路径必须真实存在）
    3. waves / holdout / boss / stages —— 模式结构、实体引用、数量与阶段顺序
    4. exit.unlock_when / victory.condition —— 只接受契约列出的值（拼错即失败，不静默回退）
    5. 交叉规则 —— 出口永不开 + 胜利依赖出口 = 胜利不可达
    6. （--plan）LevelConfig ↔ composition_plan 身份交叉校验

校验逻辑由 `gameplay_planner/level_planner.validate_level` 提供（唯一实现，
producer CLI `level_planner.py --check` 与本 CLI 共用），本文件只做 CLI 包装，
与 `check_gameplay.py` / `check_scene_composition.py` 同为**独立**检查；
`validate.py --level [--level-plan]` 通过 `unified.py` 编排同一实现（见 CONTRACT_INDEX）。

用法:
    python .ai/tools/validator/check_level.py Levels/timed_combat_arena.json [--project-root .] [--json]
    python .ai/tools/validator/check_level.py Levels/<boss>.json --plan <composition_plan.yaml>

--plan 追加 LevelConfig ↔ composition_plan 交叉校验（Phase 1.21）：宿主根名、根级
instance 集合、boss.instance 与 stage 实体身份。省略时单独 LevelConfig 校验行为不变，
报告中 cross_check_skipped 如实标记缺少交叉校验输入（INCOMPLETE）。

作为模块导入:
    from check_level import check_level
    result = check_level(level_dict, project_root, plan=plan_dict)

退出码: 0 = PASS；1 = FAIL；2 = 输入错误。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parents[1]              # .ai/tools
if str(_TOOLS_DIR / "gameplay_planner") not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR / "gameplay_planner"))

from level_planner import validate_level                      # noqa: E402

PROJECT_ROOT = _TOOLS_DIR.parent.parent                       # <project>


def check_level(level, project_root=PROJECT_ROOT, plan=None) -> dict:
    """关卡编排配置校验（委托给唯一实现，本层不重复规则）。

    plan 给出时（Phase 1.21）追加 LevelConfig ↔ composition_plan 交叉校验；
    省略时保持单独 LevelConfig 校验的既有行为。
    """
    return validate_level(level, project_root, plan=plan)


def check_level_file(path, project_root=PROJECT_ROOT, plan_path=None) -> dict:
    """读取并校验关卡配置文件。读取失败抛 ValueError（调用方转 exit 2）。"""
    path = Path(path)
    if not path.is_file():
        raise ValueError("level config not found: %s" % path)
    try:
        level = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("cannot read level config %s: %s" % (path, exc))
    plan = None
    if plan_path:
        import yaml
        plan_file = Path(plan_path)
        if not plan_file.is_file():
            raise ValueError("composition plan not found: %s" % plan_file)
        try:
            plan = yaml.safe_load(plan_file.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise ValueError("cannot read composition plan %s: %s" % (plan_file, exc))
    report = check_level(level, project_root, plan=plan)
    report["path"] = str(path)
    if plan_path:
        report["plan_path"] = str(plan_path)
    return report


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Validate a level orchestration config.")
    parser.add_argument("level", help="path to the level config JSON (e.g. Levels/<id>.json)")
    parser.add_argument("--plan", help="composition_plan YAML for cross-contract identity checks "
                                     "(Phase 1.21; optional)")
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(argv)

    try:
        report = check_level_file(args.level, Path(args.project_root).resolve(), args.plan)
    except ValueError as exc:
        print("FAIL: %s" % exc, file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("Level Orchestration Validator")
        print("  Config: %s" % report["path"])
        print("  Checked items: %d" % report["checked"])
        if report.get("level_id"):
            print("  Level: %s" % report["level_id"])
        if report.get("cross_checked"):
            print("  Cross-contract: checked against %s" % report.get("plan_path", ""))
        elif report.get("cross_check_skipped"):
            print("  Cross-contract: INCOMPLETE (no --plan supplied)")
    if report["failures"]:
        for failure in report["failures"]:
            print("FAIL: %s" % failure, file=sys.stderr)
        return 1
    if not args.json:
        print("PASS: level orchestration valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
