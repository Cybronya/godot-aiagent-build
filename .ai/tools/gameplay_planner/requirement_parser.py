#!/usr/bin/env python3
"""Gameplay Requirement Parser

把自然语言游戏需求解析为结构化意图（无 LLM，规则式）：
    - 游戏题材关键词 -> 游戏 id
    - 角色词（玩家/敌人/陷阱/拾取物/门/平台/开关） -> 需要的实体与种子能力
    - 跨实体流程词（生成/击败/奖励/开门/收集/生存） -> System 需求
    - 循环语义 -> loop.start/cycle/end 描述

输出:
    {
      "game_id": "survival_game",
      "entities": {"player": [...], "enemy": [...]},   # 种子能力标签
      "systems": ["enemy_spawn", "reward"],
      "loop": {"start": ..., "cycle": ..., "end": ...},
    }
"""

import re

# 角色/实体词 -> (entity_id, 种子能力标签)；能力标签与 feature.yaml provides 对齐
ENTITY_KEYWORDS = [
    (r"\bplayer\b|\bavatar\b|\bcharacter\b", "player",
     ["input_driven_movement", "health_state"]),
    (r"\benemy\b|\bmonster\b|\bboss\b", "enemy",
     ["character_movement", "damage_source", "health_state"]),
    (r"\btrap\b|\bspikes\b", "trap", ["damage_source"]),
    (r"\bcoin\b|\bgem\b|\bpickup\b|\bcollectible\b", "coin", ["collect_event"]),
    (r"\bhealth potion\b|\bheal(ing)? pickup\b|\bpotion\b", "health_pickup",
     ["heal_source"]),
    (r"\bdoor\b|\bgate\b", "door", ["passage_control"]),
    (r"\bswitch\b|\blever\b|\bbutton\b", "switch", ["trigger_event"]),
    (r"\bplatform\b", "platform", ["platform_transport"]),
]

# 实体需求词 -> 能力标签（追加到对应实体种子能力）
ENTITY_CAPABILITY_KEYWORDS = [
    (r"\bstun(ted)?\b|\bparalyz", "enemy", ["stun_state"]),
    (r"\battack(s|ing)?\b|\bshoot(s|ing)?\b", "player", []),
    (r"\bcan be damaged\b|\btake(s)? damage\b|\bdamageable\b", "player", ["damage_receiver"]),
]

# 游戏 id 关键词（首个命中的决定 game_id）
GAME_ID_KEYWORDS = [
    (r"\bsurvival\b", "survival_game"),
    (r"\bplatform(er)?\b", "platformer_game"),
    (r"\bpuzzle\b", "puzzle_game"),
    (r"\barena\b", "arena_game"),
    (r"\bmaze\b", "maze_game"),
    (r"\bshoot(er|ing)?\b", "shooter_game"),
]

# 跨实体流程词 -> system id（需 Systems/<id>/system.yaml 登记）
SYSTEM_KEYWORDS = [
    (r"\bspawn(s|ing)?\b|\bwaves?\b", "enemy_spawn"),
    (r"\breward\b|\bscore\b|\bpoints?\b", "reward"),
    (r"\bcollect(s|ion)?\b|\bgather\b", "reward"),
    (r"\bopen(s)? the door\b|\bdoor(s)? (open|unlock)\b", "door_control"),
    (r"\bplatform(s)? (move|transport)\b|\btransport\b", "platform_service"),
]

# 循环语义
LOOP_TEMPLATES = {
    "default": {
        "start": "player spawned",
        "cycle": "entity spawn; entity interaction",
        "end": "objective completed",
    },
    "survival": {
        "start": "player spawned",
        "cycle": "enemy spawn; enemy chase; damage player",
        "end": "enemy defeated; reward gained",
    },
}


def _has(pattern: str, text: str) -> bool:
    return re.search(pattern, text) is not None


def parse_requirement(text: str) -> dict:
    """需求文本 -> 结构化意图。"""
    lower = text.lower()

    # 游戏 id
    game_id = "custom_game"
    for pattern, gid in GAME_ID_KEYWORDS:
        if _has(pattern, lower):
            game_id = gid
            break

    # 实体与种子能力
    entities = {}
    for pattern, entity_id, seeds in ENTITY_KEYWORDS:
        if _has(pattern, lower):
            caps = list(entities.get(entity_id, []))
            for tag in seeds:
                if tag not in caps:
                    caps.append(tag)
            entities[entity_id] = caps

    # 敌对/生存玩法隐含玩家：有 enemy/敌对动词但未显式提及 player 时补入玩家实体
    # （循环语义需要对立面：enemy 的 damage_source/chase 需要作用对象）
    if "enemy" in entities and "player" not in entities and _has(
            r"\bgame\b|\bsurvival\b|\barana\b|\bdefeat\b|\bbeat\b|\bkill\b", lower):
        entities["player"] = list(ENTITY_KEYWORDS[0][2])
    for pattern, entity_id, extra in ENTITY_CAPABILITY_KEYWORDS:
        if _has(pattern, lower) and entity_id in entities:
            for tag in extra:
                if tag not in entities[entity_id]:
                    entities[entity_id].append(tag)

    # 跨实体系统
    systems = []
    for pattern, system_id in SYSTEM_KEYWORDS:
        if _has(pattern, lower) and system_id not in systems:
            systems.append(system_id)

    # 生存/竞技场玩法隐含生成与结算系统（loop.cycle/end 提及 spawn/reward 时成立）
    if _has(r"\bsurvival\b|\barana\b", lower):
        for system_id in ("enemy_spawn", "reward"):
            if system_id not in systems:
                systems.append(system_id)

    # 循环模板
    loop = dict(LOOP_TEMPLATES.get(game_id.replace("_game", ""), LOOP_TEMPLATES["default"]))
    if _has(r"\bbeat(s)? enemies\b|\bdefeat(s)? enemies\b|\bkill(s)? enemies\b|\benemies? (are )?defeated\b", lower):
        loop["end"] = "enemy defeated; reward gained"

    return {
        "game_id": game_id,
        "entities": entities,
        "systems": systems,
        "loop": loop,
    }
