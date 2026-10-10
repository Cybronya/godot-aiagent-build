#!/usr/bin/env python3
"""Gameplay Blueprint Generator

把解析后的需求意图与 Feature Discovery 结果合成 Gameplay Blueprint：

    意图（requirement_parser）
      + Feature Index（能力发现与成员遴选）
        -> gameplay.entities（每实体 Feature 组合，复用 compose_features 的遴选内核）
        -> gameplay.systems / loop
        -> entity_graph.json（跨实体关系，由 provides/requires 能力推导）

Blueprint 格式见 .ai/context/gameplay_schema.yaml。
"""

import io
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "feature_registry"))

import compose_features as composer          # noqa: E402
from requirement_parser import parse_requirement  # noqa: E402

_TOOL_DOTAI = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .ai
PROJECT_ROOT = os.path.dirname(_TOOL_DOTAI)
INDEX_PATH = os.path.join(_TOOL_DOTAI, "context", "feature_index.json")
ENTITY_GRAPH_PATH = os.path.join(_TOOL_DOTAI, "context", "entity_graph.json")

# 实体角色 -> compose_features 的角色词（用于种子遴选）
ROLE_HINT = {
    "player": "player",
    "enemy": "enemy",
    "trap": "trap",
    "coin": "world_item",
    "health_pickup": "world_item",
    "door": "level_geometry",
    "switch": "logic",
    "platform": "level_geometry",
}

# 实体名 -> 场景复用（项目内已验证的手工场景）；无匹配则由 Scene Composer 生成
SCENE_REUSE = {
    "player": "res://Features/player_movement/Player.tscn",
}

# 跨实体关系表：提供方能力 -> 消费方能力 -> relation 名
RELATION_RULES = [
    ("damage_source", "damage_receiver", "attack"),
    ("heal_source", "heal_receiver", "heal"),
    ("collect_event", "condition_input", "collect"),
    ("trigger_event", "boolean_target", "trigger"),
    ("platform_transport", "character_movement", "carry"),
]


def _provides_of(feature_id: str, index: list) -> set:
    for entry in index:
        if entry.get("id") == feature_id:
            return set(entry.get("provides") or [])
    return set()


def _pascal(name: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in str(name).replace("-", "_").split("_") if part)


def generate_blueprint(requirement: str, index: list = None) -> dict:
    """需求 -> Gameplay Blueprint（含 per-entity Entity Blueprint 推导）。"""
    if index is None:
        index = composer.load_index()
    intent = parse_requirement(requirement)

    entities = {}
    for entity_id, seed_caps in intent["entities"].items():
        # 用「角色 + 种子能力标签」构造组合需求：能力标签直接作为关键词命中 provides。
        # 种子能力先强制入组合（保证生存循环最小可玩：player 必有 health 等），
        # 其余由 Discovery 关键词命中补足。
        role = ROLE_HINT.get(entity_id, entity_id)
        keyword_req = " ".join([role] + [tag.replace("_", " ") for tag in seed_caps])
        bp = composer.compose_from_index(keyword_req, index, entity_id=entity_id)
        features = list(bp["features"])
        for tag in seed_caps:
            provider = next((f["id"] for f in index if tag in (f.get("provides") or [])), None)
            if provider and provider not in features:
                features.append(provider)
        features.sort()
        # 需求种子能力若未被组合覆盖，显式记录缺口（Validator 会跟进）
        missing = [tag for tag in seed_caps if not any(tag in _provides_of(fid, index) for fid in features)]
        entry = {
            "role": role if role in ("player", "enemy", "trap", "world_item", "level_geometry", "logic") else "entity",
            "features": features,
        }
        if missing:
            entry["_missing_seed_capabilities"] = missing
        if entity_id in SCENE_REUSE:
            entry["scene"] = SCENE_REUSE[entity_id]
        entities[entity_id] = entry

    blueprint = {
        "gameplay": {"id": intent["game_id"]},
        "entities": entities,
        "systems": list(intent["systems"]),
        "loop": dict(intent["loop"]),
        "validation": {
            "required_entities": list(entities),
            "required_features": _required_features(intent, index),
            "required_tests": sorted({fid for e in entities.values() for fid in e["features"]}),
        },
    }
    return blueprint


def _required_features(intent: dict, index: list) -> list:
    """跨实体能力需求 -> 组合必须覆盖的能力标签/Feature id。

    语义需求词（如 damage/death）映射为能力标签：
        damage -> damage_source；death -> death_event；heal -> heal_receiver
    """
    text = " ".join(intent["loop"].values()).lower() + " " + intent["game_id"]
    wanted = []
    mapping = [
        (r"\bdamage\b", "damage_source"),
        (r"\bdefeat\b|\bdeath\b|\bdie\b|\bkill", "death_event"),
        (r"\bheal\b", "heal_receiver"),
        (r"\bcollect\b", "collect_event"),
        (r"\bstun\b", "stun_state"),
    ]
    for pattern, cap in mapping:
        import re
        if re.search(pattern, text) and cap not in wanted:
            wanted.append(cap)
    return wanted


def build_entity_graph(blueprint: dict, index: list) -> dict:
    """Gameplay Blueprint -> entity_graph.json 结构。

    节点 = 实体 id 的 PascalCase；边 = 跨实体能力作用（提供方 -> 消费方）。
    """
    nodes = []
    entity_caps = {}
    for entity_id, entry in blueprint.get("entities", {}).items():
        node = _pascal(entity_id)
        nodes.append(node)
        caps = set()
        for fid in entry.get("features", []):
            caps |= _provides_of(fid, index)
        entity_caps[entity_id] = caps

    edges = []
    seen = set()
    for src_id, src_caps in entity_caps.items():
        for dst_id, dst_caps in entity_caps.items():
            if src_id == dst_id:
                continue
            for provide_cap, require_cap, relation in RELATION_RULES:
                if provide_cap in src_caps and require_cap in dst_caps:
                    key = (src_id, dst_id, relation)
                    if key not in seen:
                        seen.add(key)
                        edges.append({
                            "from": _pascal(src_id),
                            "to": _pascal(dst_id),
                            "relation": relation,
                        })
    return {"nodes": sorted(set(nodes)), "edges": edges}


def write_entity_graph(graph: dict, path: str = ENTITY_GRAPH_PATH) -> None:
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    with io.open(path, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)
        f.write("\n")


def blueprint_to_yaml_text(bp: dict) -> str:
    """把 Blueprint 转成可落盘的 YAML 文本（够用子集，不引入额外依赖时用 yaml.dump）。"""
    import yaml
    return yaml.safe_dump(bp, allow_unicode=True, sort_keys=False)
