#!/usr/bin/env python3
"""Asset Compatibility —— 判定 Feature / Entity 与 Asset 是否合理搭配。

    python check_compatibility.py --feature player_movement --asset player_run
    python check_compatibility.py --entity enemy --asset slime_idle
    python check_compatibility.py --feature health --asset enemy_death_sound --json

判定等级（确定性，无 LLM）：
    COMPATIBLE   主体角色一致 + 能力提示命中（或 Feature 明确兼容该资源）
    WARNING      能对上但存在需要人工确认的点（如主体不一致的通用音频/UI 资源、
                 资源角色未被该 Feature 的任何能力使用）
    INCOMPATIBLE 主体角色明确冲突（player 资源配 enemy 专属 Feature/Entity 等）
    UNKNOWN      信息不足（资产不在索引、Feature 无角色与能力语义）

定位：单对（Feature|Entity, Asset）判定。
不做：批量绑定（bind_assets.py）、Validator 检查（.ai/tools/validator/check_assets.py）。
低兼容性不是错误：本工具只给出等级与理由。

退出码: 0 = COMPATIBLE；1 = WARNING / INCOMPATIBLE；2 = UNKNOWN / 输入错误。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    print("FAIL: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    raise SystemExit(2)

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from asset_metadata import (          # noqa: E402
    DEFAULT_PROJECT_ROOT,
    ROLE_CAPABILITY_HINTS,
    find_asset,
    load_index,
    read_json,
)

COMPATIBLE = "COMPATIBLE"
WARNING = "WARNING"
INCOMPATIBLE = "INCOMPATIBLE"
UNKNOWN = "UNKNOWN"

# 所有等级（供绑定/校验统一引用，避免多处硬编码字符串）
LEVELS = (COMPATIBLE, WARNING, INCOMPATIBLE, UNKNOWN)

# 与主体无关的通用资源类别：主体不一致时降级为 WARNING 而不是 INCOMPATIBLE
GENERIC_CATEGORIES = {"audio", "ui", "effect", "background", "environment"}

EXIT_CODES = {COMPATIBLE: 0, WARNING: 1, INCOMPATIBLE: 1, UNKNOWN: 2}


def load_feature(project_root: Path, key: str) -> dict | None:
    """按 feature id / 目录 / feature.yaml 路径读取 Feature metadata。"""
    if not key:
        return None
    candidate = Path(key)
    if candidate.suffix in (".yaml", ".yml") and candidate.is_file():
        data = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else None
    feature_yaml = project_root / "Features" / key / "feature.yaml"
    if feature_yaml.is_file():
        data = yaml.safe_load(feature_yaml.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else None
    index = read_json(project_root / ".ai/context/feature_index.json", {})
    for entry in (index or {}).get("features", []) if isinstance(index, dict) else []:
        if entry.get("id") == key:
            return entry
    return None


def feature_entity_roles(feature: dict | None) -> list[str]:
    if not feature:
        return []
    relations = feature.get("relations") or {}
    return list(relations.get("entity_roles") or feature.get("entity_roles") or [])


def feature_capabilities(feature: dict | None) -> set:
    if not feature:
        return set()
    return set(feature.get("provides") or [])


def compatibility(index: dict, asset: dict | None, feature: dict | None = None,
                  entity_role: str = "", role_hint: str = "") -> dict:
    """判定兼容性，返回 {level, reasons, asset_id}。

    role_hint：绑定时关心的资源角色（如 move / hurt / hurt_sfx）。
    承载多个动画的 SpriteFrames 资源自身 role 为空，此时按 role_hint 取能力提示。
    """
    reasons: list[str] = []
    if asset is None:
        return {"level": UNKNOWN, "reasons": ["asset not found in index"], "asset_id": None}

    asset_id = asset.get("id")
    asset_categories = set(asset.get("compatible_entities") or [])
    category = str(asset.get("category") or "unknown")
    role = str(asset.get("role") or "")
    hint_role = str(role_hint or "")
    if hint_role.endswith("_sfx"):
        hint_role = hint_role[:-4]
    # 方向角色（idle_down / move_left / run_up_right...）与基础角色共享能力语义：
    # player run_left + player_movement 与 player run 一样 COMPATIBLE；
    # slime 的 attack_down 等主体保护依旧由主体判定部分处理，本处只去方向外壳。
    from bind_assets import split_direction_role as _split_direction
    hint_base, hint_direction = _split_direction(hint_role) if hint_role else ("", "")
    if hint_direction:
        hint_role = hint_base
    hints = ROLE_CAPABILITY_HINTS.get(hint_role or role, set())

    # 1. Entity 角色判定
    role_targets = list(asset_categories)
    if entity_role:
        role_targets = role_targets or []
        if role_targets and entity_role not in role_targets:
            level = WARNING if category in GENERIC_CATEGORIES else INCOMPATIBLE
            reasons.append("entity role %r not in asset target roles %s" % (entity_role, role_targets))
            return {"level": level, "reasons": reasons, "asset_id": asset_id}
        if not role_targets:
            reasons.append("asset has no entity role binding (category=%s)" % category)
        else:
            reasons.append("entity role %r matches asset target roles %s" % (entity_role, role_targets))

    # 2. Feature 判定
    if feature is not None:
        roles = feature_entity_roles(feature)
        capabilities = feature_capabilities(feature)
        feature_id = feature.get("id")
        if roles and role_targets:
            if not set(roles) & set(role_targets):
                level = WARNING if category in GENERIC_CATEGORIES else INCOMPATIBLE
                reasons.append("feature %s supports roles %s, asset targets %s"
                               % (feature_id, roles, role_targets))
                return {"level": level, "reasons": reasons, "asset_id": asset_id}
            reasons.append("feature role %s compatible with asset roles %s"
                           % (sorted(set(roles) & set(role_targets)), role_targets))
        if feature_id and feature_id in (asset.get("compatible_features") or []):
            reasons.append("asset lists %s as compatible feature" % feature_id)
            return {"level": COMPATIBLE, "reasons": reasons, "asset_id": asset_id}
        if hints:
            overlap = capabilities & hints
            if overlap:
                reasons.append("capability match: %s" % sorted(overlap))
                return {"level": COMPATIBLE, "reasons": reasons, "asset_id": asset_id}
            reasons.append("asset role %r needs capabilities %s, feature provides %s"
                           % (role, sorted(hints), sorted(capabilities)))
            return {"level": WARNING, "reasons": reasons, "asset_id": asset_id}
        if not roles and not capabilities:
            reasons.append("feature %s has no role/capability semantics to judge" % feature_id)
            return {"level": UNKNOWN, "reasons": reasons, "asset_id": asset_id}
        if not hints:
            # 资源不带能力语义（SpriteFrames 承载全部动画 / tileset / font 等）：
            # 若角色层面已对齐则视为可搭配，否则信息不足（不假报 COMPATIBLE）。
            if roles and role_targets and set(roles) & set(role_targets):
                reasons.append("entity role %s aligned; asset carries no per-role capability "
                               "semantics (type=%s)" % (sorted(set(roles) & set(role_targets)),
                                                        asset.get("type")))
                return {"level": COMPATIBLE, "reasons": reasons, "asset_id": asset_id}
            reasons.append("asset role %r (type=%s, category=%s) carries no capability semantics "
                           "to compare with feature %s capabilities %s"
                           % (role or "-", asset.get("type"), category, feature_id, sorted(capabilities)))
            return {"level": UNKNOWN, "reasons": reasons, "asset_id": asset_id}
        reasons.append("generic asset (%s) is not bound to feature capabilities" % category)
        return {"level": COMPATIBLE, "reasons": reasons, "asset_id": asset_id}

    # 3. 只给了 Asset：按自身语义给结论
    if role_targets or asset.get("compatible_features"):
        reasons.append("asset is classified and usable; no feature/entity given to compare")
        return {"level": COMPATIBLE, "reasons": reasons, "asset_id": asset_id}
    reasons.append("asset metadata is too thin to judge compatibility")
    return {"level": UNKNOWN, "reasons": reasons, "asset_id": asset_id}


def print_result(result: dict, asset: dict | None, feature_key: str, entity_role: str) -> None:
    print("Asset Compatibility")
    print("Asset:   %s%s" % (result.get("asset_id"),
                             " (%s)" % asset.get("category") if asset else ""))
    if feature_key:
        print("Feature: %s" % feature_key)
    if entity_role:
        print("Entity:  role=%s" % entity_role)
    print()
    print("Result:  %s" % result["level"])
    for reason in result["reasons"]:
        print("  - %s" % reason)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Check Feature/Entity <-> Asset compatibility.")
    parser.add_argument("--asset", required=True, help="Asset id or res:// path")
    parser.add_argument("--feature", default="", help="Feature id or feature.yaml path")
    parser.add_argument("--entity", default="", help="Entity role, e.g. enemy / player")
    parser.add_argument("--role", default="", help="Binding role of interest, e.g. move / hurt_sfx")
    parser.add_argument("--project", default=str(DEFAULT_PROJECT_ROOT))
    parser.add_argument("--index", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    project = Path(args.project).resolve()
    index = load_index(args.index or None, project_root=project)
    asset = find_asset(index, args.asset)
    if asset is None:
        result = {"level": UNKNOWN, "reasons": ["asset not found in index: %s" % args.asset],
                  "asset_id": args.asset}
    else:
        feature = load_feature(project, args.feature) if args.feature else None
        result = compatibility(index, asset, feature, args.entity, args.role)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif asset is None:
        print("Asset Compatibility")
        print("Result:  UNKNOWN")
        print("  - asset not found in index: %s" % args.asset)
        print("\nHint: run build_asset_index.py first (assets are indexed, not guessed).")
    else:
        print_result(result, asset, args.feature, args.entity)
    return EXIT_CODES.get(result["level"], 2)


if __name__ == "__main__":
    sys.exit(main())
