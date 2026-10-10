#!/usr/bin/env python3
"""Gameplay Planner 回归测试。

覆盖：
    1. 需求解析：survival 需求 -> player+enemy 实体、spawn/reward 系统、循环三段
    2. Blueprint 生成：实体 Feature 组合（enemy 含 health/contact_damage/chase_movement；
       player 含 health/player_movement）、entity_graph 边（Enemy -[attack]-> Player）
    3. Validator：合法蓝图 PASS；缺实体场景 / 能力缺口 / System 引用缺失 /
       loop 不闭合 的报告

用法:
    python .ai/tools/gameplay_planner/tests/test_gameplay_planner.py
全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。
"""

import io
import json
import os
import shutil
import sys
import tempfile

TOOL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))            # .ai/tools/gameplay_planner
TOOLS_DOTAI = os.path.dirname(TOOL_DIR)                                           # .ai/tools
DOTAI = os.path.dirname(TOOLS_DOTAI)                                              # .ai
PROJECT_ROOT = os.path.dirname(DOTAI)
VALIDATOR_DIR = os.path.join(DOTAI, "tools", "validator")
FEATURE_REG_DIR = os.path.join(TOOLS_DOTAI, "feature_registry")

for path in (TOOL_DIR, VALIDATOR_DIR, FEATURE_REG_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

import yaml

import compose_features as composer
from requirement_parser import parse_requirement
from blueprint_generator import build_entity_graph, generate_blueprint
import check_gameplay

_failures = []


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))
        print("FAIL: " + name + (" | " + detail if detail else ""))


def run() -> int:
    index = composer.load_index()

    print("=== 1. Requirement parsing ===")
    intent = parse_requirement("create enemy survival game")
    ok("parse: game id", intent["game_id"] == "survival_game", str(intent["game_id"]))
    ok("parse: player + enemy entities",
       set(intent["entities"]) >= {"player", "enemy"}, str(sorted(intent["entities"])))
    ok("parse: enemy seeds movement/damage/health",
       set(intent["entities"]["enemy"]) >= {"character_movement", "damage_source", "health_state"},
       str(intent["entities"]["enemy"]))
    ok("parse: systems enemy_spawn + reward",
       set(intent["systems"]) >= {"enemy_spawn", "reward"}, str(intent["systems"]))
    ok("parse: loop has start/cycle/end",
       all(intent["loop"].get(k) for k in ("start", "cycle", "end")), str(intent["loop"]))

    print("=== 2. Blueprint generation ===")
    bp = generate_blueprint("create enemy survival game", index)
    ok("bp: gameplay id", bp["gameplay"]["id"] == "survival_game")
    enemy = bp["entities"].get("enemy") or {}
    player = bp["entities"].get("player") or {}
    ok("bp: enemy has health/contact_damage/chase_movement",
       {"health", "contact_damage", "chase_movement"} <= set(enemy.get("features", [])),
       str(enemy.get("features")))
    ok("bp: player has health/player_movement",
       {"health", "player_movement"} <= set(player.get("features", [])),
       str(player.get("features")))
    ok("bp: player reuses Player.tscn",
       player.get("scene") == "res://Features/player_movement/Player.tscn", str(player.get("scene")))
    ok("bp: loop end settlement",
       "defeat" in bp["loop"]["end"].lower() or "reward" in bp["loop"]["end"].lower())
    ok("bp: required_features include damage_source",
       "damage_source" in bp["validation"]["required_features"], str(bp["validation"]["required_features"]))

    graph = build_entity_graph(bp, index)
    ok("graph: Player + Enemy nodes", set(graph["nodes"]) == {"Player", "Enemy"}, str(graph["nodes"]))
    ok("graph: Enemy -[attack]-> Player edge",
       any(e["from"] == "Enemy" and e["to"] == "Player" and e["relation"] == "attack" for e in graph["edges"]),
       str(graph["edges"]))

    print("=== 3. Validator ===")
    # 3a. 合法蓝图：player 复用 Player.tscn（存在），enemy 需生成场景 —— 用临时项目隔离
    tmp = tempfile.mkdtemp(prefix="gameplay_test_")
    try:
        # 临时项目：Scenes/EnemyBasic.tscn 预置（空文件即可，路径存在性检查）+
        # .ai/context/feature_index.json + Systems/
        os.makedirs(os.path.join(tmp, "Scenes"))
        os.makedirs(os.path.join(tmp, ".ai", "context"))
        for system_id in bp["systems"]:
            os.makedirs(os.path.join(tmp, "Systems", system_id))
            io.open(os.path.join(tmp, "Systems", system_id, "system.yaml"), "w", encoding="utf-8").write("id: %s\n" % system_id)
        shutil.copy(os.path.join(PROJECT_ROOT, ".ai", "context", "feature_index.json"),
                    os.path.join(tmp, ".ai", "context", "feature_index.json"))
        # 预置 enemy 生成场景（实体 id enemy -> Scenes/Enemy.tscn 约定名）
        io.open(os.path.join(tmp, "Scenes", "Enemy.tscn"), "w", encoding="utf-8").write("[gd_scene format=3]\n")
        # 预置 player 复用场景（res://Features/player_movement/Player.tscn）
        os.makedirs(os.path.join(tmp, "Features", "player_movement"))
        shutil.copy(os.path.join(PROJECT_ROOT, "Features", "player_movement", "Player.tscn"),
                    os.path.join(tmp, "Features", "player_movement", "Player.tscn"))

        result = check_gameplay.check_gameplay(bp, tmp)
        ok("validator: valid blueprint PASS", result["failures"] == [], str(result["failures"]))
        ok("validator: checked 2 entities", result["checked"] == 2, str(result["checked"]))

        # 3b. 缺实体场景
        os.remove(os.path.join(tmp, "Scenes", "Enemy.tscn"))
        result = check_gameplay.check_gameplay(bp, tmp)
        ok("validator: Missing Entity Scene: Enemy",
           any("Missing Entity Scene: Enemy" in f for f in result["failures"]), str(result["failures"]))
        io.open(os.path.join(tmp, "Scenes", "Enemy.tscn"), "w", encoding="utf-8").write("[gd_scene format=3]\n")

        # 3c. 能力缺口：required_features 加 stun
        bp_gap = json.loads(json.dumps(bp))
        bp_gap["validation"]["required_features"].append("stun")
        result = check_gameplay.check_gameplay(bp_gap, tmp)
        ok("validator: Gameplay incomplete for stun",
           any("Gameplay incomplete" in f and "stun_state" in f for f in result["failures"]), str(result["failures"]))

        # 3d. System 引用缺失
        bp_bad_sys = json.loads(json.dumps(bp))
        bp_bad_sys["systems"].append("nonexistent_system")
        result = check_gameplay.check_gameplay(bp_bad_sys, tmp)
        ok("validator: Unknown System reported",
           any("Unknown System: nonexistent_system" in f for f in result["failures"]), str(result["failures"]))

        # 3e. loop 不闭合（end 无结算语义 -> warning）
        bp_bad_loop = json.loads(json.dumps(bp))
        bp_bad_loop["loop"]["end"] = "and then it goes on forever"
        result = check_gameplay.check_gameplay(bp_bad_loop, tmp)
        ok("validator: loop incomplete warning",
           any("Gameplay loop incomplete" in w for w in result["warnings"]), str(result["warnings"]))
        ok("validator: loop incomplete is warning not failure",
           result["failures"] == [], str(result["failures"]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if _failures:
        print("FAIL: %d failing check(s)" % len(_failures))
        for f in _failures:
            print("  - " + f)
        return 1
    print("PASS: all gameplay planner checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
