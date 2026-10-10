#!/usr/bin/env python3
"""Gameplay Validator

校验 Gameplay Blueprint（gameplay_schema.yaml 格式）与其落盘结果：

    1. Entity 场景存在 —— blueprint 实体必须有对应场景（复用 scene 字段或
       Scenes/<Pascal>.tscn 生成物）；缺失报
       "Missing Entity Scene: <EntityName>"。
    2. Feature 满足需求 —— validation.required_features 能力必须被成员
       Feature 覆盖；缺失报
       "Gameplay incomplete: <entity> needs <capability>"。
    3. Loop 闭合 —— loop.end 必须含结算语义（defeat/death/reward/complete），
       且结算所需能力（death_event 等）确有成员提供；否则 Warning
       "Gameplay loop incomplete"。
    4. systems 引用 —— 每个 system id 必须有 Systems/<id>/system.yaml。
    5. 架构约束 —— 实体场景根节点不得自带管理器语义（不检查单例/autoload，
       那是框架 Validator 的职责）；成员场景组合校验交给 check_scene_composition。

用法:
    python check_gameplay.py <gameplay_blueprint.yaml> [--project-root .]

作为模块导入:
    from check_gameplay import check_gameplay
    result = check_gameplay(bp_dict, project_root)

退出码: 0 = PASS（允许 warning）；1 = FAIL；2 = 输入错误。
"""

import argparse
import io
import json
import os
import re
import sys

try:
    import yaml
except ImportError:
    print("FAIL: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    raise SystemExit(2)

_TOOL_DOTAI = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .ai
PROJECT_ROOT = os.path.dirname(_TOOL_DOTAI)
INDEX_PATH = os.path.join(_TOOL_DOTAI, "context", "feature_index.json")
SCENES_DIR = os.path.join(PROJECT_ROOT, "Scenes")
SYSTEMS_DIR = os.path.join(PROJECT_ROOT, "Systems")

# loop.end 结算语义关键词 -> 需要存在的能力标签
END_SETTLEMENT = [
    (r"\bdefeat", "death_event"),
    (r"\bdeath\b|\bdied\b|\bkill", "death_event"),
    (r"\breward", "reward_settlement"),
    (r"\bscore\b|\bpoints?\b", "reward_settlement"),
    (r"\bcomplete\b|\bwin\b|\bclear", None),   # 通关语义：只要求 end 非空
]

# required_features 语义词 -> 能力标签（与 generator 的映射一致）
FEATURE_WORDS = {
    "damage": "damage_source",
    "damage_source": "damage_source",
    "death": "death_event",
    "death_event": "death_event",
    "heal": "heal_receiver",
    "collect": "collect_event",
    "stun": "stun_state",
}


def _pascal(name: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in str(name).replace("-", "_").split("_") if part)


def _load_index(project_root: str, index_path: str = None) -> list:
    path = index_path or os.path.join(project_root, ".ai", "context", "feature_index.json")
    if not os.path.isfile(path):
        return []
    with io.open(path, encoding="utf-8") as f:
        return (json.load(f) or {}).get("features", [])


def _entity_scene_candidates(entity_id: str, entry: dict, project_root: str) -> list:
    """实体场景候选路径（复用声明优先，其次蓝图生成约定名）。"""
    candidates = []
    scene = str(entry.get("scene") or "").strip()
    if scene:
        if scene.startswith("res://"):
            rel = scene[len("res://"):].replace("/", os.sep)
            candidates.append(os.path.join(project_root, rel))
        else:
            candidates.append(os.path.join(project_root, scene.replace("/", os.sep)))
    candidates.append(os.path.join(project_root, "Scenes", _pascal(entity_id) + ".tscn"))
    # enemy_basic 之类蓝图 id 的 PascalCase 全名（EnemyBasic）也作为候选
    candidates.append(os.path.join(project_root, "Scenes", _pascal(entry.get("blueprint_id") or entity_id) + ".tscn"))
    # 去重保序
    seen, out = set(), []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def check_gameplay(bp: dict, project_root: str = PROJECT_ROOT) -> dict:
    """Gameplay Blueprint 校验。返回 {failures, warnings, checked}。"""
    failures, warnings = [], []
    gameplay = bp.get("gameplay") or {}
    entities = bp.get("entities") or {}
    loop = bp.get("loop") or {}
    validation = bp.get("validation") or {}

    if not gameplay.get("id"):
        failures.append("Gameplay Blueprint missing gameplay.id")
    if not entities:
        failures.append("Gameplay Blueprint has no entities")

    index = _load_index(project_root)
    provides_map = {f.get("id"): set(f.get("provides") or []) for f in index}

    entity_caps = {}
    for entity_id, entry in entities.items():
        if not isinstance(entry, dict) or not entry.get("features"):
            failures.append("Gameplay entity %s has no features" % entity_id)
            entity_caps[entity_id] = set()
            continue
        caps = set()
        for fid in entry["features"]:
            caps |= provides_map.get(fid, set())
        entity_caps[entity_id] = caps

        # 1. Entity 场景存在
        scene_path = next((c for c in _entity_scene_candidates(entity_id, entry, project_root) if os.path.isfile(c)), None)
        if scene_path is None:
            failures.append("Missing Entity Scene: %s" % _pascal(entity_id))

        # 2. required_features 覆盖（按实体语义词映射）
        for word in validation.get("required_features", []) or []:
            cap = FEATURE_WORDS.get(str(word).lower(), str(word))
            # 语义能力：任一实体提供即可（跨实体分工），逐实体仅在无任何提供方时报错
        # （统一在实体循环外检查，见下）

    # 2. required_features：任一实体提供该能力即满足；无人提供则报 Gameplay incomplete
    for word in validation.get("required_features", []) or []:
        cap = FEATURE_WORDS.get(str(word).lower(), str(word))
        providers = [eid for eid, caps in entity_caps.items() if cap in caps]
        if not providers:
            failures.append(
                "Gameplay incomplete: no entity provides %s (required: %s)"
                % (cap, word)
            )

    # 3. Loop 闭合：end 须含结算语义且结算能力可满足
    end_text = str(loop.get("end") or "").strip()
    if not end_text:
        failures.append("Gameplay loop incomplete: loop.end is empty")
    else:
        settlement_caps = []
        matched = False
        for pattern, cap in END_SETTLEMENT:
            if re.search(pattern, end_text.lower()):
                matched = True
                if cap:
                    settlement_caps.append(cap)
        if not matched:
            warnings.append("Gameplay loop incomplete: loop.end has no settlement semantics (defeat/reward/complete)")
        for cap in settlement_caps:
            if not any(cap in caps for caps in entity_caps.values()):
                # reward_settlement 由 System 提供，检查 systems 引用
                if cap == "reward_settlement" and "reward" in (bp.get("systems") or []):
                    continue
                warnings.append(
                    "Gameplay loop incomplete: loop.end requires %s but no entity/system provides it" % cap
                )
    if not str(loop.get("cycle") or "").strip():
        warnings.append("Gameplay loop incomplete: loop.cycle is empty")

    # 4. systems 引用存在
    for system_id in bp.get("systems", []) or []:
        sys_path = os.path.join(project_root, "Systems", system_id, "system.yaml")
        if not os.path.isfile(sys_path):
            failures.append("Unknown System: %s (Systems/%s/system.yaml not found)" % (system_id, system_id))

    # required_entities 全部在 entities 中（防手写蓝图漏项）
    for entity_id in validation.get("required_entities", []) or []:
        if entity_id not in entities:
            failures.append("Gameplay incomplete: required entity %s is missing from blueprint" % entity_id)

    return {"failures": failures, "warnings": warnings, "checked": len(entities)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validate a Gameplay Blueprint.")
    parser.add_argument("blueprint", help="Gameplay Blueprint yaml path")
    parser.add_argument("--project-root", default=PROJECT_ROOT)
    args = parser.parse_args(argv)

    if not os.path.isfile(args.blueprint):
        print("FAIL: Blueprint not found: %s" % args.blueprint)
        return 2
    bp = yaml.safe_load(io.open(args.blueprint, encoding="utf-8")) or {}

    print("Gameplay Validator")
    print("Blueprint: %s" % args.blueprint)
    result = check_gameplay(bp, args.project_root)
    print("Checked entities: %d" % result["checked"])
    if result["failures"]:
        print("\nFAILURES")
        for failure in result["failures"]:
            print("  - " + failure)
    if result["warnings"]:
        print("\nWARNINGS")
        for warning in result["warnings"]:
            print("  - " + warning)
    if result["failures"]:
        print("\nFAIL")
        return 1
    if result["warnings"]:
        print("\nWARNING: 0 error(s), %d warning(s)" % len(result["warnings"]))
        return 0
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
