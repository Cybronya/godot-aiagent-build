#!/usr/bin/env python3
"""Feature Composition Planner (v1)

把需求文本转成 Entity Blueprint：多个 Feature 如何组合成一个 Gameplay Entity。

用法:
    python compose_features.py "enemy follows player and deals damage"
    python compose_features.py "enemy follows player and deals damage" --id boss_guard

流程（无 LLM）:
    需求文本 -> 关键词提取 -> Discovery（能力匹配）
            -> Feature relation lookup（faith 工具：读索引 v2 的 relations）
            -> Build graph -> Rank combination -> Entity Blueprint

评分:
    score = provides_match * 5 + relation_match * 3 + entity_role_match * 2

架构约束:
    - Entity 不拥有 Gameplay State；Feature 各自管理状态，Scene 只负责组合。
    - 本工具只生成 Blueprint（组合计划），不生成代码、不创建场景。

数据来源:
    .ai/context/feature_index.json（v2，含 relations；由 build_feature_index.py
    从 Features/*/feature.yaml 生成，feature.yaml 是 Source of Truth）。
    角色与格式约定见 .ai/context/composition_schema.yaml。
"""

import argparse
import io
import json
import os
import re
import sys
from collections import Counter

# 目录定位：本文件位于 <root>/.ai/tools/feature_registry/ 下
_TOOL_DOTAI = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .ai
INDEX_PATH = os.path.join(_TOOL_DOTAI, "context", "feature_index.json")

# 与 discover_feature.py 保持一致的权重体系，另加关系项
W_PROVIDES = 5
W_RELATION = 3
W_ROLE = 2

# 复用 discover 的关键词提取与 Discovery 匹配
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import discover_feature as discovery  # noqa: E402

# 需求词 -> 实体角色（用于选择 plan 主角色；ROLES 取自 relations.entity_roles 实际值）
ROLE_KEYWORDS = {
    "enemy": "enemy",
    "boss": "enemy",
    "monster": "enemy",
    "player": "player",
    "avatar": "player",
    "character": "player",
    "destructible": "destructible",
    "crate": "destructible",
    "trap": "trap",
    "spikes": "trap",
    "platform": "level_geometry",
    "door": "level_geometry",
    "pickup": "world_item",
    "coin": "world_item",
    "key": "key_item",
}

# 需求词 -> 组合能力（除常规 Discovery 匹配外，针对「实体目标可以被 X」句式）
TARGET_VERB_MAP = {
    "stunned": ["stun_state"],
    "stunned/disabled": ["stun_state"],
    "healed": ["heal_receiver"],
    "collected": ["collect_event"],
}

# 角色所需的种子能力（保证最小可玩组合）；值 = provides 标签
ROLE_SEEDS = {
    "enemy": ["character_movement", "damage_source"],
    "player": ["input_driven_movement"],
    "destructible": ["health_state"],
    "trap": ["damage_source"],
    "world_item": ["consumable_pickup"],
    "key_item": ["collect_event"],
    "level_geometry": ["platform_transport"],
    "logic": [],
}


def load_index(path: str = INDEX_PATH) -> list:
    if not os.path.isfile(path):
        raise SystemExit(
            "FAIL: Feature index not found: %s\n"
            "Please run: python .ai/tools/feature_registry/build_feature_index.py" % path
        )
    with io.open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("features", [])


def role_score(feature: dict, role: str) -> tuple:
    """角色匹配分：命中 relations.entity_roles 得 W_ROLE。"""
    roles = (feature.get("relations") or {}).get("entity_roles", [])
    hits = W_ROLE if role in roles else 0
    return hits, (["role: " + role] if hits else [])


def capability_score(feature: dict, needed: set) -> tuple:
    """能力匹配分：feature provides 命中所需能力标签，每个 W_PROVIDES。"""
    hits = sorted(set(feature.get("provides", [])) & needed)
    if not hits:
        return 0, []
    return W_PROVIDES * len(hits), ["provides: " + p for p in hits]


def relation_score(feature: dict, chosen_ids: set) -> tuple:
    """关系匹配分：与已选 Feature 存在 works_with/commonly_used_with 关系，每个 W_RELATION。"""
    relations = feature.get("relations") or {}
    related = set(relations.get("works_with", [])) | set(relations.get("commonly_used_with", []))
    hits = sorted(related & chosen_ids)
    if not hits:
        return 0, []
    return W_RELATION * len(hits), ["relation: " + h for h in hits]


def requires_satisfied(feature: dict, chosen: list) -> tuple:
    """relations.requires（语义型）与顶层 requires（能力型）是否可由 chosen 满足。

    返回 (missing_capability_tags, unmet_descriptions)。
    """
    capability_pool = set()
    for entry in chosen:
        capability_pool |= set(entry.get("provides", []))
    missing, unmet = [], []
    for req in feature.get("requires", []):
        if req not in capability_pool:
            unmet.append("%s requires %s" % (feature["id"], req))
            missing.append(req)
    relations = feature.get("relations") or {}
    for req in relations.get("requires", []):
        if req not in capability_pool:
            unmet.append("%s (relations) requires %s" % (feature["id"], req))
            missing.append(req)
    return missing, unmet


def conflicts_present(feature: dict, chosen: list) -> list:
    """feature 的 relations.conflicts 若与已选成员（id 或能力标签）相冲，返回描述。"""
    conflicts = (feature.get("relations") or {}).get("conflicts", [])
    chosen_tags = {tag for entry in chosen for tag in entry.get("provides", [])}
    present = []
    for c in conflicts:
        if any(entry["id"] == c for entry in chosen) or c in chosen_tags:
            present.append("%s conflicts with %s" % (feature["id"], c))
    return present


def plan(requirement: str, index: list, entity_id: str = "") -> dict:
    """核心 planners：需求 → 角色 → 种子组合 → 迭代增强 → Blueprint。"""
    terms = discovery.extract_terms(requirement)
    # 「X can be stunned/healed/collected」类句式：目标能力标签直接并入需求 (terms)
    for token, tags in TARGET_VERB_MAP.items():
        if re.search(r"\b%s\b" % token.split("/")[0], requirement.lower()):
            terms.update(tags)
    # 角色选择：显式角色词 > 组合 Feature 的 entity_roles 多数票 > enemy 兜底
    role = None
    for word in ROLE_KEYWORDS:
        if re.search(r"\b%s\b" % word, requirement.lower()):
            role = ROLE_KEYWORDS[word]
            break
    if role is None:
        votes = Counter()
        for feature in index:
            for r in (feature.get("relations") or {}).get("entity_roles", []):
                if feature.get("provides") and (set(feature.get("provides", [])) & terms):
                    votes[r] += 1
        role = votes.most_common(1)[0][0] if votes else "enemy"
    # 反混淆：非玩家角色需求中，player/player_control 类标签不应触发玩家组件——
    # 但需求里明确出现 "player" 只说明「以玩家为目标」，不是「玩家组件入组合」。
    if role != "player":
        terms.discard("player_control")
        terms.discard("input_driven_movement")
        terms.discard("health_display")   # 敌方蓝图不因组契约加入展示层
    seed_tags = set(ROLE_SEEDS.get(role, []))
    # 第一轮：满足种子能力 / 与需求词直接命中的 Feature
    chosen: list = []
    chosen_ids: set = set()
    reasons: dict = {}

    def try_add(feature: dict, base_reasons: list) -> None:
        if feature["id"] in chosen_ids:
            return
        if conflicts_present(feature, chosen):
            return
        missing, unmet_after = requires_satisfied(feature, chosen)
        # 缺的是前置能力（damage_receiver 等）时仍允许加入，最终由组合轮补齐；
        # 其他在组合内无法满足的 requires 不阻断组建，由 Validator 层报告。
        chosen.append(feature)
        chosen_ids.add(feature["id"])
        reasons[feature["id"]] = base_reasons

    # 种子满足：优先 Discovery 高分 + 提供种子能力
    scored = []
    for feature in index:
        d_score, d_reasons = discovery.match_feature(feature, terms)
        r_score, r_reasons = role_score(feature, role) if role else (0, [])
        scored.append((feature, d_score + r_score, d_reasons + r_reasons))
    scored.sort(key=lambda t: (-t[1], t[0]["id"]))

    for feature, score, reasons_found in scored:
        if seed_tags and (set(feature.get("provides", [])) & seed_tags) and score > 0:
            try_add(feature, reasons_found)
    chosen_tags_present = {tag for f in chosen for tag in f.get("provides", [])}
    for tag in sorted(seed_tags - chosen_tags_present):
        for feature, score, reasons_found in scored:
            if tag in feature.get("provides", []):
                try_add(feature, reasons_found)
                break

    # 第二轮：按关系增强。为避免把纯展示/外围组件也拖进来（over-join），
    # 候选必须命中需求词的能力标签，或是某已选成员的「必要前置」提供者。
    relation_counter = Counter()
    for feature in chosen:
        relations = feature.get("relations") or {}
        for key in ("works_with", "commonly_used_with"):
            for other in relations.get(key, []):
                relation_counter[other] += 1
    for other, _ in relation_counter.most_common():
        candidate = next((f for f in index if f["id"] == other), None)
        if candidate is None:
            continue
        rs, r_matched = relation_score(candidate, chosen_ids)
        if rs <= 0:
            continue
        d_score, _ = discovery.match_feature(candidate, terms)
        term_hit = bool(set(candidate.get("provides", [])) & terms)
        needed_by = any(
            req not in {t for e in chosen for t in e.get("provides", [])}
            for other_f in chosen
            for req in [r for r in (other_f.get("relations") or {}).get("requires", [])]
        ) and bool(set(candidate.get("provides", [])) & (
            {req for f2 in chosen for req in (f2.get("relations") or {}).get("requires", [])}
        ))
        if term_hit or needed_by or d_score >= W_PROVIDES:
            try_add(candidate, r_matched)

    # 第三轮：补齐成员的关系型 requires（如 contact_damage 需 damage_receiver → health）
    for _ in range(2):   # 有限轮次收敛
        capability_pool = {tag for f in chosen for tag in f.get("provides", [])}
        for feature in chosen:
            _, unmet = requires_satisfied(feature, chosen)
            for line in unmet:
                req = line.split(" requires ")[-1]
                if req in capability_pool:
                    continue
                provider = next((f for f in index if req in f.get("provides", [])), None)
                if provider is not None:
                    try_add(provider, ["required by " + feature["id"] + " (" + req + ")"])
                    capability_pool |= set(provider.get("provides", []))

    # 冲突过滤：若最终组合含已选成员的 conflicts 对象，二选一（保留先加入者），
    # 冲突对象是能力标签时检查 provides。
    final: list = []
    for feature in chosen:
        if conflicts_present(feature, final):
            continue
        final.append(feature)

    final.sort(key=lambda f: f["id"])
    missing_caps = []
    for feature in final:
        missing, _ = requires_satisfied(feature, final)
        missing_caps.extend(missing)

    blueprint = {
        "entity": {
            "id": entity_id or suggest_entity_id(role),
            "role": role or infer_role(final, index),
        },
        "features": [f["id"] for f in final],
        "reason": {f["id"]: "; ".join(reasons.get(f["id"], [])) or "matched requirement terms" for f in final},
        "validation": {"required_tests": [f["id"] for f in final]},
    }
    return {"blueprint": blueprint, "missing_requirements": sorted(set(missing_caps))}


def infer_role(features: list, index: list) -> str:
    votes = Counter()
    for f in features:
        for r in (f.get("relations") or {}).get("entity_roles", []):
            votes[r] += 1
    if votes:
        return votes.most_common(1)[0][0]
    return "entity"


def suggest_entity_id(role: str) -> str:
    return {"enemy": "basic_enemy", "player": "player_avatar", "trap": "basic_trap",
            "world_item": "pickup_item", "key_item": "key_item", "level_geometry": "level_element",
            "destructible": "destructible_object", "logic": "logic_node", "entity": "basic_entity"}.get(role, "basic_entity")


def compose_from_index(requirement: str, index: list, entity_id: str = "") -> dict:
    idx_map = {f["id"]: f for f in index}
    result = plan(requirement, index, entity_id)
    blueprint = result["blueprint"]
    # 补充 Interfaces 展示（供用户直接参考）
    details = {}
    for fid in blueprint["features"]:
        f = idx_map.get(fid, {})
        signals = set(f.get("signals", []))
        details[fid] = [
            (i + " signal") if i in signals else (i + "()")
            for i in f.get("interfaces", [])
        ]
    blueprint["interfaces_by_feature"] = details
    blueprint["_missing_requirements"] = result["missing_requirements"]
    return blueprint


def print_blueprint(bp: dict) -> None:
    print("Feature Composition Result")
    print()
    print("Entity Blueprint")
    print()
    print("entity:")
    print("  id: %s" % bp["entity"]["id"])
    print("  role: %s" % bp["entity"]["role"])
    print()
    print("features:")
    for fid in bp["features"]:
        print("- %s" % fid)
    print()
    print("reason:")
    for fid in bp["features"]:
        print("%s: %s" % (fid, bp["reason"].get(fid, "")))
    print()
    if bp.get("interfaces_by_feature"):
        print("Interfaces:")
        for fid, lines in bp["interfaces_by_feature"].items():
            print("%s: %s" % (fid, ", ".join(lines)))
        print()
    print("validation:")
    print("  required_tests:")
    for fid in bp["validation"]["required_tests"]:
        print("  - %s" % fid)
    if bp.get("_missing_requirements"):
        print()
        print("Composition incomplete:")
        for item in bp["_missing_requirements"]:
            print("- missing capability: %s" % item)


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(description="Compose features into an Entity Blueprint.")
    parser.add_argument("requirement", nargs="+", help="Requirement text")
    parser.add_argument("--id", dest="entity_id", default="", help="Explicit entity id")
    args = parser.parse_args(argv)
    requirement = " ".join(args.requirement)
    index = load_index()
    bp = compose_from_index(requirement, index, args.entity_id)
    print_blueprint(bp)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
