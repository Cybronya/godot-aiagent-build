#!/usr/bin/env python3
"""Level Orchestration Planner 回归测试（Phase 1.13；Phase 1.14 增加 holdout 模式）。

覆盖：
    L1  合法关卡配置通过（随仓库发布的 Levels/timed_combat_arena.json + 内存构造）
    L2  缺必需字段失败，并指出具体字段
    L3  引用不存在的实体 / 场景失败
    L4  非法数量与非法波次结构被拒绝
    L5  不支持的出口规则 / 胜利条件被拒绝（含交叉规则：胜利不可达）
    L6  错误信息可定位到具体字段（JSON 路径前缀）
    L7  holdout 模式（Phase 1.14）：合法生存配置通过 / 缺块与非法调度被拒 /
        waves 与 holdout 互斥 / version 1 不支持 holdout / 随仓库发布的
        Levels/survival_arena.json 通过
    L8  版本兼容：version 1 遗留配置仍被接受；version 2 显式 mode 合法
    L9  boss 模式（Phase 1.20）：合法 Boss 配置通过 / Boss 身份与实例来源必须显式 /
        waves 与 boss 互斥 / version 1 不支持 boss /
        从真实 composition_plan 生成 boss 关卡配置（不手写）
    L10 多阶段 Boss（Phase 1.21）：合法阶段链 / 空/重复/未知类型/缺 Boss 引用/顺序/
        终结规则冲突 / waves 与 holdout 拒绝 stages / 阶段配置生成
    L11 LevelConfig ↔ composition_plan 交叉校验：宿主根/实例集合/Boss instance/stage
        实体/缺失输入 INCOMPLETE/单独 LevelConfig 兼容/check_level --plan CLI
    生成器：Gameplay Blueprint -> 关卡配置（默认波次策略 / 显式 --wave 覆盖 /
        非 enemy 角色不纳入 / 场景缺失时报告缺口 / 结果确定）
    CLI：build 写盘 + 校验通过；--check 通过（0）与失败（1）；非法参数 = 2

用法:
    python .ai/tools/gameplay_planner/tests/test_level_planner.py
全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。
"""

import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

TOOL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))      # .ai/tools/gameplay_planner
TOOLS_DIR = os.path.dirname(TOOL_DIR)                                      # .ai/tools
DOTAI = os.path.dirname(TOOLS_DIR)                                         # .ai
PROJECT_ROOT = os.path.dirname(DOTAI)
VALIDATOR_DIR = os.path.join(TOOLS_DIR, "validator")
FEATURE_REG_DIR = os.path.join(TOOLS_DIR, "feature_registry")

for path in (TOOL_DIR, VALIDATOR_DIR, FEATURE_REG_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

import level_planner                                          # noqa: E402
import check_level                                            # noqa: E402
import compose_features as composer                            # noqa: E402
from blueprint_generator import generate_blueprint             # noqa: E402

SHIPPED_LEVEL = os.path.join(PROJECT_ROOT, "Levels", "timed_combat_arena.json")
SHIPPED_SURVIVAL_LEVEL = os.path.join(PROJECT_ROOT, "Levels", "survival_arena.json")
SHIPPED_BOSS_LEVEL = os.path.join(PROJECT_ROOT, "Levels", "boss_challenge.json")

_failures = []


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))
        print("FAIL: " + name + (" | " + detail if detail else ""))


def _valid_level(project_root: str = PROJECT_ROOT) -> dict:
    """内存构造的合法配置（引用真实存在的 Enemy.tscn）。"""
    return {
        "schema": {"id": "level_orchestration", "version": 1},
        "level": {"id": "unit_test_level", "arena_scene": "res://Scenes/TimedCombatArena.tscn"},
        "entities": {"enemy": {"scene": "res://Scenes/Enemy.tscn"}},
        "waves": [
            {"id": "wave_1", "duration": 30.0, "entries": [{"entity": "enemy", "count": 2}]},
            {"id": "wave_2", "duration": 20.0, "entries": [{"entity": "enemy", "count": 1}]},
        ],
        "exit": {"unlock_when": "all_waves_cleared"},
        "victory": {"condition": "exit_reached_after_unlock"},
    }


def _valid_holdout(level_id: str = "unit_test_holdout", version: int = 2) -> dict:
    """内存构造的合法 holdout（生存）配置（引用真实存在的敌人场景）。"""
    level = {
        "schema": {"id": "level_orchestration", "version": version},
        "level": {"id": level_id, "arena_scene": "res://Scenes/SurvivalArena.tscn"},
        "mode": "holdout",
        "entities": {
            "enemy": {"scene": "res://Scenes/Enemy.tscn"},
            "elite_enemy": {"scene": "res://Scenes/EliteEnemy.tscn"},
        },
        "holdout": {
            "survival_duration": 30.0,
            "max_alive": 12,
            "spawns": [
                {"entity": "enemy", "interval": 1.2},
                {"entity": "elite_enemy", "delay": 10.0, "interval": 8.0, "max_alive": 2},
            ],
        },
        "victory": {"condition": "survive_duration"},
    }
    if version == 1:
        level.pop("mode")
    return level


def _valid_boss(level_id: str = "unit_test_boss", version: int = 2) -> dict:
    """内存构造的合法 boss 配置（引用真实存在的 Boss.tscn；实例路径显式点名）。"""
    level = {
        "schema": {"id": "level_orchestration", "version": version},
        "level": {"id": level_id, "arena_scene": "res://Scenes/BossChallenge.tscn"},
        "mode": "boss",
        "entities": {"boss": {"scene": "res://Scenes/Boss.tscn"}},
        "boss": {"entity": "boss", "instance": "Entities/Boss", "spawn": "existing"},
        "exit": {"unlock_when": "boss_defeated"},
        "victory": {"condition": "exit_reached_after_unlock"},
    }
    if version == 1:
        level.pop("mode")
    return level


def _valid_plan(host: str = "UnitBossHost") -> dict:
    """composition_plan 形态的真实产物（实例名来自组合器约定 = Pascal(entity id)）。"""
    return {
        "document": "composition_plan",
        "schema_version": 1,
        "host": {"name": host},
        "instances": [
            {"entity": "player", "scene": "res://Features/player_movement/Player.tscn",
             "instance_name": "Player"},
            {"entity": "boss", "scene": "res://Scenes/Boss.tscn",
             "instance_name": "Boss"},
        ],
    }


def _valid_stage_level(level_id: str = "unit_stage_boss") -> dict:
    """合法多阶段 Boss：清理普通敌人 → 击败 Boss（Phase 1.21）。"""
    return {
        "schema": {"id": "level_orchestration", "version": 2},
        "level": {"id": level_id, "arena_scene": "res://Scenes/BossChallenge.tscn"},
        "mode": "boss",
        "entities": {"boss": {"scene": "res://Scenes/Boss.tscn"},
                     "grunt": {"scene": "res://Scenes/Enemy.tscn"}},
        "boss": {"entity": "boss", "instance": "Entities/Boss", "spawn": "existing"},
        "stages": [
            {"id": "clear_1", "type": "clear_enemies",
             "entries": [{"entity": "grunt", "count": 2}]},
            {"id": "boss", "type": "defeat_boss", "entity": "boss"},
        ],
        "exit": {"unlock_when": "never"},
        "victory": {"condition": "boss_defeated"},
    }


def _cross_plan(host: str = "CrossHost") -> dict:
    return {
        "document": "composition_plan",
        "schema_version": 1,
        "host": {"name": host},
        "instances": [
            {"entity": "player", "scene": "res://Scenes/Player.tscn",
             "instance_name": "Player"},
            {"entity": "boss", "scene": "res://Scenes/Boss.tscn",
             "instance_name": "Boss"},
            {"entity": "grunt", "scene": "res://Scenes/Enemy.tscn",
             "instance_name": "Grunt"},
        ],
    }


def _valid_cross_level() -> dict:
    level = _valid_stage_level("unit_cross_boss")
    level["level"]["arena_scene"] = "res://Scenes/CrossHost.tscn"
    level["boss"]["instance"] = "Boss"
    return level


def _write_host(root: str, name: str, instances: list) -> None:
    """写一个最小但真实的 .tscn：根节点 + 根级 instance 节点（交叉校验读取）。"""
    lines = ["[gd_scene format=3]", "",
             '[node name="%s" type="Node2D"]' % name, ""]
    for index, instance_name in enumerate(instances):
        lines.append('[node name="%s" parent="." instance=ExtResource("%d_x")]'
                     % (instance_name, index + 1))
        lines.append("")
    io.open(os.path.join(root, "Scenes", name + ".tscn"), "w", encoding="utf-8",
            newline="\n").write("\n".join(lines))


def _cross_project(root: str) -> str:
    os.makedirs(os.path.join(root, "Scenes"), exist_ok=True)
    for name in ("Boss", "Enemy", "Player"):
        io.open(os.path.join(root, "Scenes", name + ".tscn"), "w", encoding="utf-8").write(
            "[gd_scene format=3]\n")
    _write_host(root, "CrossHost", ["Player", "Boss", "Grunt"])
    return root


def _failures_of(level: dict, project_root: str = PROJECT_ROOT, plan=None) -> list:
    return level_planner.validate_level(level, project_root, plan=plan)["failures"]


def _clone(level: dict) -> dict:
    return json.loads(json.dumps(level))


def _tmp_project(root: str) -> str:
    """临时项目：预置敌人实体场景（生成约定名），用于生成器 / CLI 的路径解析。"""
    os.makedirs(os.path.join(root, "Scenes"))
    io.open(os.path.join(root, "Scenes", "Enemy.tscn"), "w", encoding="utf-8").write("[gd_scene format=3]\n")
    return root


def run() -> int:
    print("=== L1 合法配置 ===")
    shipped = json.loads(io.open(SHIPPED_LEVEL, encoding="utf-8").read())
    shipped_report = level_planner.validate_level(shipped, PROJECT_ROOT)
    ok("L1: shipped Levels/timed_combat_arena.json passes", shipped_report["failures"] == [],
       str(shipped_report["failures"]))
    ok("L1: shipped config reports its level id and checked items",
       shipped_report["level_id"] == "timed_combat_arena" and shipped_report["checked"] > 0,
       str((shipped_report["level_id"], shipped_report["checked"])))
    ok("L1: shipped config declares 3 waves through the runtime consumer scene",
       len(shipped["waves"]) == 3
       and shipped["level"]["arena_scene"] == "res://Scenes/TimedCombatArena.tscn",
       str(shipped["level"]))
    ok("L1: in-memory level passes", _failures_of(_valid_level()) == [],
       str(_failures_of(_valid_level())))

    print("=== L2 缺必需字段 ===")
    for label, mutate, expected_path in (
        ("level block", lambda level: level.pop("level"), "level"),
        ("level.id", lambda level: level["level"].pop("id"), "level.id"),
        ("waves", lambda level: level.pop("waves"), "waves"),
        ("entry count", lambda level: level["waves"][0]["entries"][0].pop("count"),
         "waves[0].entries[0].count"),
        ("entities", lambda level: level.pop("entities"), "entities"),
    ):
        level = _valid_level()
        mutate(level)
        failures = _failures_of(level)
        ok("L2: missing %s fails and points at %s" % (label, expected_path),
           any(failure.startswith(expected_path) for failure in failures), str(failures))

    print("=== L3 未知实体 / 缺失场景 ===")
    level = _valid_level()
    level["waves"][0]["entries"][0]["entity"] = "no_such_entity"
    failures = _failures_of(level)
    ok("L3: unknown entity reference fails",
       any(f.startswith("waves[0].entries[0].entity") and "unknown entity" in f for f in failures),
       str(failures))
    level = _valid_level()
    level["entities"]["enemy"]["scene"] = "res://Scenes/NoSuchEnemy.tscn"
    failures = _failures_of(level)
    ok("L3: missing entity scene fails (existence checked on disk)",
       any(f.startswith("entities.enemy.scene") and "not found" in f for f in failures),
       str(failures))

    print("=== L4 非法数量 / 非法波次结构 ===")
    for label, value in (("zero", 0), ("negative", -1), ("fraction", 1.5), ("string", "2")):
        level = _valid_level()
        level["waves"][0]["entries"][0]["count"] = value
        failures = _failures_of(level)
        ok("L4: count %s rejected" % label,
           any(f.startswith("waves[0].entries[0].count") for f in failures), str(failures))
    level = _valid_level()
    level["waves"] = []
    ok("L4: empty waves rejected",
       any(f.startswith("waves") for f in _failures_of(level)), str(_failures_of(level)))
    level = _valid_level()
    level["waves"][1]["entries"] = []
    ok("L4: empty wave entries rejected",
       any(f.startswith("waves[1].entries") for f in _failures_of(level)), str(_failures_of(level)))
    level = _valid_level()
    level["waves"][1]["id"] = "wave_1"
    ok("L4: duplicate wave id rejected",
       any(f.startswith("waves[1].id") and "duplicate" in f for f in _failures_of(level)),
       str(_failures_of(level)))
    level = _valid_level()
    level["waves"][0]["duration"] = 0
    ok("L4: non-positive duration rejected",
       any(f.startswith("waves[0].duration") for f in _failures_of(level)), str(_failures_of(level)))

    print("=== L5 不支持的出口 / 胜利规则 ===")
    level = _valid_level()
    level["exit"] = {"unlock_when": "whenever_i_feel_like_it"}
    ok("L5: unsupported exit.unlock_when rejected (no silent fallback)",
       any(f.startswith("exit.unlock_when") and "unsupported" in f for f in _failures_of(level)),
       str(_failures_of(level)))
    level = _valid_level()
    level["victory"] = {"condition": "win_the_game"}
    ok("L5: unsupported victory.condition rejected",
       any(f.startswith("victory.condition") and "unsupported" in f
           for f in _failures_of(level)), str(_failures_of(level)))
    level = _valid_level()
    level["exit"] = {"unlock_when": "never"}
    ok("L5: cross rule (exit never + victory needs exit) reported as unreachable",
       any(f.startswith("victory.condition") and "unreachable" in f for f in _failures_of(level)),
       str(_failures_of(level)))
    level = _valid_level()
    level["exit"] = {"unlock_when": "never"}
    level["victory"] = {"condition": "all_waves_cleared"}
    ok("L5: exit=never + victory=all_waves_cleared is legal",
       _failures_of(level) == [], str(_failures_of(level)))

    print("=== L6 错误可定位 ===")
    level = _valid_level()
    level["waves"][0]["entries"][0]["count"] = 0
    level["waves"][1]["entries"][0]["entity"] = "ghost"
    level["victory"] = {"condition": "nope"}
    failures = _failures_of(level)
    path_pattern = re.compile(r"^[a-z_]+(\[\d+\])?(\.[a-z_]+(\[\d+\])?)*:")
    ok("L6: every failure starts with a JSON path prefix",
       bool(failures) and all(path_pattern.match(f) for f in failures), str(failures))
    ok("L6: distinct failures point at distinct fields",
       len({f.split(":")[0] for f in failures}) == len(failures), str(failures))

    print("=== L7 holdout 模式（Phase 1.14） ===")
    ok("L7: shipped Levels/survival_arena.json passes",
       _failures_of(json.loads(io.open(SHIPPED_SURVIVAL_LEVEL, encoding="utf-8").read())) == [],
       str(_failures_of(json.loads(io.open(SHIPPED_SURVIVAL_LEVEL, encoding="utf-8").read()))))
    ok("L7: in-memory holdout passes", _failures_of(_valid_holdout()) == [],
       str(_failures_of(_valid_holdout())))
    for label, mutate, expected_path in (
        ("holdout block", lambda level: level.pop("holdout"), "holdout"),
        ("survival_duration", lambda level: level["holdout"].pop("survival_duration"),
         "holdout.survival_duration"),
        ("spawns", lambda level: level["holdout"].pop("spawns"), "holdout.spawns"),
        ("spawn entity", lambda level: level["holdout"]["spawns"][0].pop("entity"),
         "holdout.spawns[0].entity"),
        ("spawn interval", lambda level: level["holdout"]["spawns"][0].pop("interval"),
         "holdout.spawns[0].interval"),
        ("spawn max_alive", lambda level: level["holdout"]["spawns"][1].update({"max_alive": 0}),
         "holdout.spawns[1].max_alive"),
        ("spawn delay", lambda level: level["holdout"]["spawns"][1].update({"delay": -1.0}),
         "holdout.spawns[1].delay"),
    ):
        level = _valid_holdout()
        mutate(level)
        failures = _failures_of(level)
        ok("L7: holdout missing/invalid %s fails and points at %s" % (label, expected_path),
           any(failure.startswith(expected_path) for failure in failures), str(failures))
    level = _valid_holdout()
    level["holdout"]["survival_duration"] = 0
    ok("L7: non-positive survival_duration rejected",
       any(f.startswith("holdout.survival_duration") for f in _failures_of(level)),
       str(_failures_of(level)))
    level = _valid_holdout()
    level["holdout"]["spawns"][0]["count"] = 3
    ok("L7: holdout spawn rejects waves-only count (no silent reinterpretation)",
       any(f.startswith("holdout.spawns[0].count") for f in _failures_of(level)),
       str(_failures_of(level)))
    level = _valid_holdout()
    level["holdout"]["spawns"][0]["entity"] = "ghost"
    ok("L7: holdout spawn with unknown entity rejected",
       any(f.startswith("holdout.spawns[0].entity") and "unknown entity" in f
           for f in _failures_of(level)), str(_failures_of(level)))
    level = _valid_holdout()
    level["waves"] = [_valid_level()["waves"][0]]
    ok("L7: holdout mode rejects sequential waves",
       any(f.startswith("waves") for f in _failures_of(level)), str(_failures_of(level)))
    level = _valid_holdout()
    level["exit"] = {"unlock_when": "all_waves_cleared"}
    ok("L7: holdout mode rejects exit config",
       any(f.startswith("exit") for f in _failures_of(level)), str(_failures_of(level)))
    level = _valid_holdout()
    level["victory"] = {"condition": "exit_reached_after_unlock"}
    ok("L7: holdout victory only supports survive_duration",
       any(f.startswith("victory.condition") for f in _failures_of(level)),
       str(_failures_of(level)))
    level = _valid_holdout()
    level["schema"]["version"] = 1
    ok("L7: version 1 configs reject holdout orchestration",
       any(f.startswith("mode") and "version 1" in f for f in _failures_of(level)),
       str(_failures_of(level)))
    level = _valid_holdout()
    level["mode"] = "survival_party"
    ok("L7: unsupported mode rejected (no silent fallback)",
       any(f.startswith("mode") and "unsupported" in f for f in _failures_of(level)),
       str(_failures_of(level)))

    print("=== L8 版本兼容 ===")
    ok("L8: legacy version 1 waves config still passes",
       _failures_of(_valid_level()) == [], str(_failures_of(_valid_level())))
    version2_waves = _valid_level()
    version2_waves["schema"]["version"] = 2
    version2_waves["mode"] = "waves"
    ok("L8: version 2 waves config passes", _failures_of(version2_waves) == [],
       str(_failures_of(version2_waves)))
    bad_version = _valid_level()
    bad_version["schema"]["version"] = 99
    ok("L8: unknown schema version rejected",
       any(f.startswith("schema.version") for f in _failures_of(bad_version)),
       str(_failures_of(bad_version)))
    holdout_v1 = _valid_holdout(version=1)
    holdout_v1["mode"] = "holdout"
    ok("L8: version 1 + mode=holdout rejected",
       any(f.startswith("mode") and "version 1" in f for f in _failures_of(holdout_v1)),
       str(_failures_of(holdout_v1)))
    holdout_v1_block = _valid_holdout(version=1)
    ok("L8: version 1 + holdout block rejected",
       any(f.startswith("mode") and "version 1" in f for f in _failures_of(holdout_v1_block)),
       str(_failures_of(holdout_v1_block)))

    print("=== L9 boss 模式（Phase 1.20） ===")
    shipped_boss = json.loads(io.open(SHIPPED_BOSS_LEVEL, encoding="utf-8").read())
    ok("L9: shipped Levels/boss_challenge.json passes",
       _failures_of(shipped_boss) == []
       and shipped_boss["mode"] == "boss"
       and shipped_boss["boss"]["entity"] == "boss"
       and shipped_boss["boss"]["instance"] == "Entities/Boss",
       str(_failures_of(shipped_boss)))
    ok("L9: in-memory boss config passes", _failures_of(_valid_boss()) == [],
       str(_failures_of(_valid_boss())))
    on_start = _valid_boss()
    on_start["boss"] = {"entity": "boss", "spawn": "on_start"}
    ok("L9: boss.spawn=on_start does not require an instance path",
       _failures_of(on_start) == [], str(_failures_of(on_start)))
    level = _valid_boss()
    level.pop("boss")
    ok("L9: missing boss block rejected",
       any(f.startswith("boss") for f in _failures_of(level)), str(_failures_of(level)))
    level = _valid_boss()
    level["boss"]["entity"] = "ghost"
    ok("L9: unknown boss entity rejected (no role/name guessing)",
       any(f.startswith("boss.entity") and "unknown entity" in f
           for f in _failures_of(level)), str(_failures_of(level)))
    level = _valid_boss()
    level["boss"].pop("instance")
    ok("L9: spawn=existing without an instance path rejected",
       any(f.startswith("boss.instance") for f in _failures_of(level)),
       str(_failures_of(level)))
    for label, value in (("absolute", "/Boss"), ("escaping", "../Boss"), ("blank", "  ")):
        level = _valid_boss()
        level["boss"]["instance"] = value
        ok("L9: %s boss.instance path rejected" % label,
           any(f.startswith("boss.instance") for f in _failures_of(level)),
           str(_failures_of(level)))
    level = _valid_boss()
    level["boss"]["spawn"] = "whenever"
    ok("L9: unsupported boss.spawn rejected",
       any(f.startswith("boss.spawn") for f in _failures_of(level)), str(_failures_of(level)))
    level = _valid_boss()
    level["waves"] = [_valid_level()["waves"][0]]
    ok("L9: boss mode rejects sequential waves",
       any(f.startswith("waves") for f in _failures_of(level)), str(_failures_of(level)))
    level = _valid_boss()
    level["holdout"] = _valid_holdout()["holdout"]
    ok("L9: boss mode rejects holdout spawning",
       any(f.startswith("holdout") for f in _failures_of(level)), str(_failures_of(level)))
    level = _valid_boss()
    level["exit"] = {"unlock_when": "all_waves_cleared"}
    ok("L9: boss mode rejects waves-only exit rules",
       any(f.startswith("exit.unlock_when") for f in _failures_of(level)),
       str(_failures_of(level)))
    level = _valid_boss()
    level["victory"] = {"condition": "all_waves_cleared"}
    ok("L9: boss mode rejects waves-only victory conditions",
       any(f.startswith("victory.condition") for f in _failures_of(level)),
       str(_failures_of(level)))
    level = _valid_boss()
    level["exit"] = {"unlock_when": "never"}
    ok("L9: boss mode exit=never + exit victory is unreachable",
       any(f.startswith("victory.condition") and "unreachable" in f
           for f in _failures_of(level)), str(_failures_of(level)))
    level = _valid_boss()
    level["exit"] = {"unlock_when": "never"}
    level["victory"] = {"condition": "boss_defeated"}
    ok("L9: boss_defeated victory without an exit is legal",
       _failures_of(level) == [], str(_failures_of(level)))
    level = _valid_boss(version=1)
    ok("L9: version 1 + boss mode rejected",
       any(f.startswith("mode") and "version 1" in f for f in _failures_of(level)),
       str(_failures_of(level)))
    level = _valid_level()
    level["boss"] = _valid_boss()["boss"]
    ok("L9: waves mode rejects a boss block",
       any(f.startswith("boss") for f in _failures_of(level)), str(_failures_of(level)))
    level = _valid_holdout()
    level["boss"] = _valid_boss()["boss"]
    ok("L9: holdout mode rejects a boss block",
       any(f.startswith("boss") for f in _failures_of(level)), str(_failures_of(level)))

    plan = _valid_plan()
    built = level_planner.build_boss_level(
        {"gameplay": {"id": "unit_boss_game"},
         "entities": {"player": {"role": "player", "features": ["health"]},
                      "boss": {"role": "enemy", "features": ["health", "chase_movement"]}}},
        plan, boss_entity="boss", arena_scene="res://Scenes/BossChallenge.tscn")
    built_level = built["level"] or {}
    ok("L9: boss level is generated from a real composition plan",
       built["ok"] and built_level.get("mode") == "boss"
       and built_level.get("boss") == {"entity": "boss", "instance": "Boss",
                                       "spawn": "existing"}
       and set(built_level.get("entities", {})) == {"player", "boss"}
       and built_level["level"]["arena_scene"] == "res://Scenes/BossChallenge.tscn",
       str(built.get("failures") or built_level))
    ok("L9: generated boss level validates against the contract",
       level_planner.validate_level(built_level, PROJECT_ROOT)["failures"] == [],
       str(level_planner.validate_level(built_level, PROJECT_ROOT)["failures"]))
    missing_boss = level_planner.build_boss_level(
        {"gameplay": {"id": "unit_boss_game"}, "entities": {"boss": {"role": "enemy"}}},
        plan, boss_entity="ghost", arena_scene="res://Scenes/BossChallenge.tscn")
    ok("L9: boss entity outside the plan is reported (no guesses)",
       (not missing_boss["ok"])
       and any(f.startswith("boss.entity") and "ghost" in f for f in missing_boss["failures"])
       and missing_boss["level"] is None, str(missing_boss["failures"]))
    bad_plan = _valid_plan()
    bad_plan["instances"][1]["scene"] = "res://Scenes/NoSuchBoss.tscn"
    missing_scene = level_planner.build_boss_level(
        {"gameplay": {"id": "unit_boss_game"},
         "entities": {"boss": {"role": "enemy"}}},
        bad_plan, boss_entity="boss", arena_scene="res://Scenes/BossChallenge.tscn")
    ok("L9: plan instance with a missing scene is reported, no artifact",
       (not missing_scene["ok"])
       and any("NoSuchBoss" in f for f in missing_scene["failures"])
       and missing_scene["level"] is None, str(missing_scene["failures"]))
    missing_arena = level_planner.build_boss_level(
        {"gameplay": {"id": "unit_boss_game"},
         "entities": {"boss": {"role": "enemy"}}},
        plan, boss_entity="boss", arena_scene="res://Scenes/UnitBossHost.tscn")
    ok("L9: a non-composed host scene is reported instead of a fake arena",
       (not missing_arena["ok"])
       and any(f.startswith("level.arena_scene") for f in missing_arena["failures"]),
       str(missing_arena["failures"]))

    print("=== L10 多阶段 Boss 契约（Phase 1.21） ===")
    ok("L10: valid clear_enemies -> defeat_boss config passes",
       _failures_of(_valid_stage_level()) == [], str(_failures_of(_valid_stage_level())))
    complete_level = _valid_stage_level()
    complete_level["stages"].append({"id": "complete", "type": "complete_level"})
    ok("L10: terminal complete_level stage passes with exit=never/victory=boss_defeated",
       _failures_of(complete_level) == [], str(_failures_of(complete_level)))
    for label, mutate, expected in (
        ("empty stages", lambda level: level.update({"stages": []}), "stages"),
        ("single stage", lambda level: level.update({"stages": [level["stages"][0]]}),
         "stages"),
        ("duplicate id", lambda level: level["stages"][1].update({"id": "clear_1"}),
         "stages[1].id"),
        ("unknown type", lambda level: level["stages"][1].update({"type": "teleport"}),
         "stages[1].type"),
        ("missing boss entity", lambda level: level["stages"][1].pop("entity"),
         "stages[1].entity"),
        ("wrong boss entity", lambda level: level["stages"][1].update({"entity": "grunt"}),
         "stages[1].entity"),
        ("empty clear entries", lambda level: level["stages"][0].update({"entries": []}),
         "stages[0].entries"),
        ("clear references boss",
         lambda level: level["stages"][0]["entries"][0].update({"entity": "boss"}),
         "stages[0].entries[0].entity"),
        ("clear unknown entity",
         lambda level: level["stages"][0]["entries"][0].update({"entity": "ghost"}),
         "stages[0].entries[0].entity"),
        ("clear bad count",
         lambda level: level["stages"][0]["entries"][0].update({"count": 0}),
         "stages[0].entries[0].count"),
        ("boss not last", lambda level: level["stages"].append(
            {"id": "clear_2", "type": "clear_enemies",
             "entries": [{"entity": "grunt", "count": 1}]}), "stages[1]"),
        ("complete not last", lambda level: level["stages"].insert(
            0, {"id": "complete", "type": "complete_level"}), "stages[0]"),
        ("complete with exit", lambda level: (level["stages"].append(
            {"id": "complete", "type": "complete_level"}),
            level["exit"].update({"unlock_when": "boss_defeated"})), "exit.unlock_when"),
        ("complete with exit victory", lambda level: (level["stages"].append(
            {"id": "complete", "type": "complete_level"}),
            level["victory"].update({"condition": "exit_reached_after_unlock"})),
         "victory.condition"),
        ("no clear stage", lambda level: level.update({"stages": [
            {"id": "boss", "type": "defeat_boss", "entity": "boss"},
            {"id": "complete", "type": "complete_level"}]}), "stages"),
    ):
        level = _valid_stage_level()
        mutate(level)
        failures = _failures_of(level)
        ok("L10: %s is rejected at %s" % (label, expected),
           any(failure.startswith(expected) for failure in failures), str(failures))
    waves_with_stages = _valid_level()
    waves_with_stages["stages"] = _valid_stage_level()["stages"]
    ok("L10: waves mode rejects stages",
       any(f.startswith("stages") for f in _failures_of(waves_with_stages)),
       str(_failures_of(waves_with_stages)))
    holdout_with_stages = _valid_holdout()
    holdout_with_stages["stages"] = _valid_stage_level()["stages"]
    ok("L10: holdout mode rejects stages",
       any(f.startswith("stages") for f in _failures_of(holdout_with_stages)),
       str(_failures_of(holdout_with_stages)))
    skipped = level_planner.validate_level(_valid_stage_level(), PROJECT_ROOT)
    ok("L10: standalone multi-stage validation reports the missing cross-check input",
       skipped["failures"] == [] and not skipped["cross_checked"]
       and skipped["cross_check_skipped"], str(skipped))

    stage_plan = _valid_plan()
    stage_plan["instances"].append({"entity": "grunt", "scene": "res://Scenes/Enemy.tscn",
                                    "instance_name": "Grunt"})
    stage_gameplay = {
        "gameplay": {"id": "unit_stage_game"},
        "entities": {"player": {"role": "player", "features": ["health"]},
                     "boss": {"role": "enemy", "features": ["health"]},
                     "grunt": {"role": "enemy", "features": ["health"]}},
    }
    built_stage = level_planner.build_boss_level(
        stage_gameplay, stage_plan, boss_entity="boss",
        arena_scene="res://Scenes/BossChallenge.tscn",
        stage_specs=[("clear_enemies", [("grunt", 2)]), ("defeat_boss",)])
    built_stage_level = built_stage["level"] or {}
    ok("L10: stage specs build a clear_enemies -> defeat_boss config in declared order",
       built_stage["ok"]
       and [stage.get("type") for stage in built_stage_level.get("stages") or []
            ] == ["clear_enemies", "defeat_boss"]
       and built_stage_level["stages"][0]["entries"]
       == [{"entity": "grunt", "count": 2}]
       and (built_stage_level.get("exit") or {}).get("unlock_when") == "boss_defeated"
       and (built_stage_level.get("victory") or {}).get("condition") == "boss_defeated",
       str(built_stage.get("failures") or built_stage_level))
    built_complete = level_planner.build_boss_level(
        stage_gameplay, stage_plan, boss_entity="boss",
        arena_scene="res://Scenes/BossChallenge.tscn",
        stage_specs=[("clear_enemies", [("grunt", 1)]), ("defeat_boss",),
                     ("complete_level",)])
    ok("L10: complete_level stage forces exit=never / victory=boss_defeated",
       built_complete["ok"]
       and (built_complete["level"].get("exit") or {}).get("unlock_when") == "never"
       and (built_complete["level"].get("victory") or {}).get("condition")
       == "boss_defeated", str(built_complete.get("failures") or built_complete.get("level")))
    bad_stage = level_planner.build_boss_level(
        stage_gameplay, stage_plan, boss_entity="boss",
        arena_scene="res://Scenes/BossChallenge.tscn",
        stage_specs=[("clear_enemies", [("ghost", 1)]), ("defeat_boss",)])
    ok("L10: a clear stage outside the composition plan is refused with no artifact",
       not bad_stage["ok"] and bad_stage["level"] is None
       and any("ghost" in failure for failure in bad_stage["failures"]),
       str(bad_stage["failures"]))
    bad_stage_boss = level_planner.build_boss_level(
        stage_gameplay, stage_plan, boss_entity="boss",
        arena_scene="res://Scenes/BossChallenge.tscn",
        stage_specs=[("clear_enemies", [("boss", 1)]), ("defeat_boss",)])
    ok("L10: clear_enemies cannot spawn the boss entity",
       not bad_stage_boss["ok"] and bad_stage_boss["level"] is None,
       str(bad_stage_boss["failures"]))

    print("=== L11 LevelConfig vs composition_plan 交叉校验（Phase 1.21） ===")
    tmp = tempfile.mkdtemp(prefix="level_cross_")
    try:
        _cross_project(tmp)
        plan = _cross_plan()
        level = _valid_cross_level()
        report = level_planner.validate_level(level, tmp, plan=plan)
        ok("L11: matching host root / instance identities pass", report["failures"] == [],
           str(report["failures"]))
        ok("L11: cross-check reports it actually ran", report["cross_checked"]
           and not report["cross_check_skipped"], str(report))
        for label, mutate, expected in (
            ("unknown boss instance", lambda c: c["boss"].update({"instance": "Ghost"}),
             "boss.instance"),
            ("plan missing boss", lambda c: None, "boss.entity"),
            ("wrong host root", lambda c: c["level"].update(
                {"arena_scene": "res://Scenes/OtherHost.tscn"}), "level.arena_scene"),
            ("host missing instance", lambda c: None, "level.arena_scene"),
            ("host extra instance", lambda c: None, "level.arena_scene"),
            ("stage clear entity absent from plan",
             lambda c: c["stages"][0]["entries"][0].update({"entity": "ghost"}),
             "stages[0].entries[0].entity"),
            ("duplicate plan instance name", lambda c: None, "plan.instances[2].instance_name"),
        ):
            bad_plan = json.loads(json.dumps(plan))
            bad_level = json.loads(json.dumps(level))
            if label == "plan missing boss":
                bad_plan["instances"] = [item for item in bad_plan["instances"]
                                        if item["entity"] != "boss"]
            elif label == "host missing instance":
                _write_host(tmp, "CrossHost", ["Player", "Grunt"])
            elif label == "host extra instance":
                _write_host(tmp, "CrossHost", ["Player", "Boss", "Grunt", "Ghost"])
            elif label == "wrong host root":
                _write_host(tmp, "OtherHost", ["Player", "Boss", "Grunt"])
                mutate(bad_level)
            elif label == "duplicate plan instance name":
                bad_plan["instances"][2]["instance_name"] = "Boss"
            else:
                mutate(bad_level)
            failures = _failures_of(bad_level, tmp, plan=bad_plan)
            ok("L11: %s is rejected at %s" % (label, expected),
               any(failure.startswith(expected) for failure in failures), str(failures))
            if label in ("host missing instance", "host extra instance", "wrong host root"):
                _write_host(tmp, "CrossHost", ["Player", "Boss", "Grunt"])
        ok("L11: a plan with the wrong document id is rejected",
           any(f.startswith("plan.document") for f in _failures_of(
               level, tmp, plan={"document": "scene_plan", "schema_version": 1})),
           str(_failures_of(level, tmp, plan={"document": "scene_plan", "schema_version": 1})))
        ok("L11: standalone LevelConfig validation still passes without a plan",
           _failures_of(level, tmp) == [], str(_failures_of(level, tmp)))

        # CLI：--plan 在构建期阻止不匹配配置进入成功路径。
        level_path = os.path.join(tmp, "Levels", "cross.json")
        plan_path = os.path.join(tmp, "plan.yaml")
        os.makedirs(os.path.dirname(level_path), exist_ok=True)
        io.open(level_path, "w", encoding="utf-8", newline="\n").write(
            json.dumps(level, ensure_ascii=False, indent=2))
        io.open(plan_path, "w", encoding="utf-8", newline="\n").write(
            "document: composition_plan\n"
            "schema_version: 1\n"
            "host:\n  name: CrossHost\n"
            "instances:\n"
            "  - {entity: player, scene: res://Scenes/Player.tscn, instance_name: Player}\n"
            "  - {entity: boss, scene: res://Scenes/Boss.tscn, instance_name: Boss}\n"
            "  - {entity: grunt, scene: res://Scenes/Enemy.tscn, instance_name: Grunt}\n")
        proc = subprocess.run(
            [sys.executable, os.path.join(VALIDATOR_DIR, "check_level.py"), level_path,
             "--plan", plan_path, "--project-root", tmp],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=PROJECT_ROOT, stdin=subprocess.DEVNULL, timeout=120)
        ok("L11: check_level --plan passes a matching config/host",
           proc.returncode == 0 and "Cross-contract: checked" in (proc.stdout or ""),
           "exit=%s %s" % (proc.returncode, (proc.stdout or proc.stderr)[-300:]))
        bad_level = json.loads(json.dumps(level))
        bad_level["boss"]["instance"] = "Ghost"
        io.open(level_path, "w", encoding="utf-8", newline="\n").write(
            json.dumps(bad_level, ensure_ascii=False, indent=2))
        proc = subprocess.run(
            [sys.executable, os.path.join(VALIDATOR_DIR, "check_level.py"), level_path,
             "--plan", plan_path, "--project-root", tmp],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=PROJECT_ROOT, stdin=subprocess.DEVNULL, timeout=120)
        ok("L11: check_level --plan rejects an unknown boss.instance (exit 1)",
           proc.returncode == 1 and "boss.instance" in (proc.stderr or ""),
           "exit=%s %s" % (proc.returncode, (proc.stderr or "")[-300:]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("=== 生成器 ===")
    index = composer.load_index()
    blueprint = generate_blueprint("create enemy survival game", index)
    tmp = tempfile.mkdtemp(prefix="level_planner_test_")
    try:
        _tmp_project(tmp)
        result = level_planner.build_level(blueprint, project_root=tmp)
        ok("gen: blueprint -> level config succeeds", result["ok"], str(result["failures"]))
        level = result["level"] or {}
        ok("gen: only enemy-role entities are spawnable (player not included)",
           set(level.get("entities", {})) == {"enemy"}, str(level.get("entities")))
        ok("gen: default policy = 2 waves with escalating counts (2, 3)",
           [entry["count"] for wave in level.get("waves", [])
            for entry in wave["entries"]] == [2, 3], str(level.get("waves")))
        ok("gen: defaults mirror the schema (exit=all_waves_cleared, victory=exit_reached_after_unlock)",
           (level.get("exit") or {}).get("unlock_when") == "all_waves_cleared"
           and (level.get("victory") or {}).get("condition") == "exit_reached_after_unlock",
           str((level.get("exit"), level.get("victory"))))
        ok("gen: generated config is schema version 2 in waves mode",
           level["schema"]["version"] == 2 and level.get("mode") == "waves",
           str((level["schema"], level.get("mode"))))
        ok("gen: generated config validates against the contract",
           level_planner.validate_level(level, tmp)["failures"] == [],
           str(level_planner.validate_level(level, tmp)["failures"]))
        explicit = level_planner.build_level(
            blueprint, project_root=tmp, wave_specs=[[("enemy", 1)], [("enemy", 4)]])
        ok("gen: explicit --wave overrides the default waves",
           explicit["ok"] and [entry["count"] for wave in explicit["level"]["waves"]
                               for entry in wave["entries"]] == [1, 4],
           str(explicit.get("failures") or explicit["level"]["waves"]))
        bad = level_planner.build_level(blueprint, project_root=tmp,
                                        wave_specs=[[("ghost", 2)]])
        ok("gen: unknown entity in --wave is reported, not silently dropped",
           (not bad["ok"]) and any("ghost" in f for f in bad["failures"]), str(bad["failures"]))
        repeat = level_planner.build_level(blueprint, project_root=tmp)
        ok("gen: generation is deterministic", repeat["level"] == level)
        # 场景缺失：只有 player（非 enemy 角色）或 enemy 场景不存在时报告缺口
        shutil.rmtree(os.path.join(tmp, "Scenes"))
        os.makedirs(os.path.join(tmp, "Scenes"))
        missing = level_planner.build_level(blueprint, project_root=tmp)
        ok("gen: missing enemy scene is reported as a gap (no fabrication)",
           (not missing["ok"]) and any("no resolvable scene" in f for f in missing["failures"]),
           str(missing["failures"]))
        ok("gen: failed build produces no level document", missing["level"] is None)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("=== CLI ===")
    tmp = tempfile.mkdtemp(prefix="level_planner_cli_")
    try:
        _tmp_project(tmp)
        blueprint_path = os.path.join(tmp, "gameplay.yaml")
        io.open(blueprint_path, "w", encoding="utf-8", newline="\n").write(
            "gameplay:\n  id: cli_test_game\n"
            "entities:\n  enemy:\n    role: enemy\n    features: [health]\n"
            "systems: [enemy_spawn]\n"
            "loop:\n  start: player spawned\n  cycle: enemy spawn\n  end: enemy defeated\n")
        out_path = os.path.join(tmp, "Levels", "cli_test_game.json")
        proc = subprocess.run(
            [sys.executable, os.path.join(TOOL_DIR, "level_planner.py"), blueprint_path,
             "--out", out_path, "--project-root", tmp, "--wave", "enemy:1", "--wave", "enemy:2"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=PROJECT_ROOT, stdin=subprocess.DEVNULL, timeout=120)
        ok("cli: build mode exits 0 and writes the level config",
           proc.returncode == 0 and os.path.isfile(out_path),
           "exit=%s out=%s" % (proc.returncode, (proc.stdout or proc.stderr)[-200:]))
        written = json.loads(io.open(out_path, encoding="utf-8").read()) if os.path.isfile(out_path) else {}
        ok("cli: written config carries the explicit waves",
           [entry["count"] for wave in written.get("waves", [])
            for entry in wave["entries"]] == [1, 2], str(written.get("waves")))
        ok("cli: build mode reports Validation: PASS",
           "Validation: PASS" in (proc.stdout or ""), (proc.stdout or "")[-200:])

        proc = subprocess.run(
            [sys.executable, os.path.join(TOOL_DIR, "level_planner.py"), "--check", out_path,
             "--project-root", tmp],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=PROJECT_ROOT, stdin=subprocess.DEVNULL, timeout=120)
        ok("cli: --check on a valid config exits 0", proc.returncode == 0,
           "exit=%s %s" % (proc.returncode, (proc.stderr or "")[-200:]))

        broken_path = os.path.join(tmp, "broken.json")
        broken = _clone(written)
        broken["waves"][0]["entries"][0]["count"] = -3
        io.open(broken_path, "w", encoding="utf-8", newline="\n").write(json.dumps(broken, indent=2))
        proc = subprocess.run(
            [sys.executable, os.path.join(TOOL_DIR, "level_planner.py"), "--check", broken_path,
             "--project-root", tmp],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=PROJECT_ROOT, stdin=subprocess.DEVNULL, timeout=120)
        ok("cli: --check on an invalid config exits 1 with a locatable failure",
           proc.returncode == 1 and "waves[0].entries[0].count" in (proc.stderr or ""),
           "exit=%s %s" % (proc.returncode, (proc.stderr or "")[-200:]))

        proc = subprocess.run(
            [sys.executable, os.path.join(TOOL_DIR, "level_planner.py"), blueprint_path,
             "--out", os.path.join(tmp, "never.json"), "--wave", "enemy_not_a_number",
             "--project-root", tmp],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=PROJECT_ROOT, stdin=subprocess.DEVNULL, timeout=120)
        ok("cli: malformed --wave argument exits 2 (input error)",
           proc.returncode == 2 and not os.path.exists(os.path.join(tmp, "never.json")),
           "exit=%s %s" % (proc.returncode, (proc.stderr or "")[-200:]))

        # validator CLI 包装同一实现
        proc = subprocess.run(
            [sys.executable, os.path.join(VALIDATOR_DIR, "check_level.py"), out_path,
             "--project-root", tmp],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=PROJECT_ROOT, stdin=subprocess.DEVNULL, timeout=120)
        ok("cli: validator/check_level.py PASSes the same config (single implementation)",
           proc.returncode == 0 and "PASS" in (proc.stdout or ""),
           "exit=%s %s" % (proc.returncode, (proc.stdout or proc.stderr)[-200:]))
        ok("cli: check_level module入口与 CLI 结论一致",
           check_level.check_level(written, tmp)["failures"] == [])

        # ---- boss 模式 CLI：真实 plan -> boss 关卡配置 ----
        for name in ("Boss.tscn", "Player.tscn", "CliBossHost.tscn"):
            io.open(os.path.join(tmp, "Scenes", name), "w", encoding="utf-8").write(
                "[gd_scene format=3]\n")
        boss_blueprint_path = os.path.join(tmp, "boss_gameplay.yaml")
        io.open(boss_blueprint_path, "w", encoding="utf-8", newline="\n").write(
            "gameplay:\n  id: cli_boss_game\n"
            "entities:\n"
            "  player:\n    role: player\n    features: [health]\n"
            "  boss:\n    role: enemy\n    features: [health, chase_movement]\n"
            "systems: []\n"
            "loop:\n  start: player spawned\n  cycle: boss fights\n  end: boss defeated\n")
        plan_path = os.path.join(tmp, "boss_plan.yaml")
        plan = _valid_plan("CliBossHost")
        plan["instances"][0]["scene"] = "res://Scenes/Player.tscn"
        plan["instances"][1]["scene"] = "res://Scenes/Boss.tscn"
        io.open(plan_path, "w", encoding="utf-8", newline="\n").write(
            "document: composition_plan\n"
            "schema_version: 1\n"
            "host:\n  name: CliBossHost\n"
            "instances:\n"
            "  - entity: player\n    scene: res://Scenes/Player.tscn\n    instance_name: Player\n"
            "  - entity: boss\n    scene: res://Scenes/Boss.tscn\n    instance_name: Boss\n")
        boss_out = os.path.join(tmp, "Levels", "cli_boss_game.json")
        proc = subprocess.run(
            [sys.executable, os.path.join(TOOL_DIR, "level_planner.py"), boss_blueprint_path,
             "--mode", "boss", "--boss", "boss", "--plan", plan_path,
             "--out", boss_out, "--project-root", tmp],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=PROJECT_ROOT, stdin=subprocess.DEVNULL, timeout=120)
        boss_written = (json.loads(io.open(boss_out, encoding="utf-8").read())
                        if os.path.isfile(boss_out) else {})
        ok("cli: --mode boss builds from the real plan and writes the config",
           proc.returncode == 0 and boss_written.get("mode") == "boss"
           and boss_written.get("boss") == {"entity": "boss", "instance": "Boss",
                                           "spawn": "existing"}
           and boss_written.get("level", {}).get("arena_scene")
           == "res://Scenes/CliBossHost.tscn",
           "exit=%s %s" % (proc.returncode, (proc.stdout or proc.stderr)[-300:]))
        ok("cli: boss output validates through the independent validator",
           check_level.check_level(boss_written, tmp)["failures"] == [])
        proc = subprocess.run(
            [sys.executable, os.path.join(TOOL_DIR, "level_planner.py"), boss_blueprint_path,
             "--mode", "boss", "--boss", "boss", "--out",
             os.path.join(tmp, "never_boss.json"), "--project-root", tmp],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=PROJECT_ROOT, stdin=subprocess.DEVNULL, timeout=120)
        ok("cli: boss mode without --plan exits 2 (input error)",
           proc.returncode == 2 and not os.path.exists(os.path.join(tmp, "never_boss.json")),
           "exit=%s %s" % (proc.returncode, (proc.stderr or "")[-200:]))
        proc = subprocess.run(
            [sys.executable, os.path.join(TOOL_DIR, "level_planner.py"), boss_blueprint_path,
             "--mode", "boss", "--boss", "boss", "--plan", plan_path, "--wave", "boss:1",
             "--out", os.path.join(tmp, "never_boss_wave.json"), "--project-root", tmp],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=PROJECT_ROOT, stdin=subprocess.DEVNULL, timeout=120)
        ok("cli: boss mode rejects --wave (no silent mixing of modes)",
           proc.returncode == 2
           and not os.path.exists(os.path.join(tmp, "never_boss_wave.json")),
           "exit=%s %s" % (proc.returncode, (proc.stderr or "")[-200:]))

        # 受控负向：缺场景映射 / 未知 Boss → exit 1 且不留下关卡配置产物。
        bad_plan_path = os.path.join(tmp, "boss_plan_bad.yaml")
        io.open(bad_plan_path, "w", encoding="utf-8", newline="\n").write(
            "document: composition_plan\n"
            "schema_version: 1\n"
            "host:\n  name: CliBossHost\n"
            "instances:\n"
            "  - entity: player\n    scene: res://Scenes/Player.tscn\n    instance_name: Player\n"
            "  - entity: boss\n    scene: res://Scenes/NoSuchBoss.tscn\n    instance_name: Boss\n")
        bad_out = os.path.join(tmp, "Levels", "cli_boss_bad_scene.json")
        proc = subprocess.run(
            [sys.executable, os.path.join(TOOL_DIR, "level_planner.py"), boss_blueprint_path,
             "--mode", "boss", "--boss", "boss", "--plan", bad_plan_path,
             "--out", bad_out, "--project-root", tmp],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=PROJECT_ROOT, stdin=subprocess.DEVNULL, timeout=120)
        ok("cli: missing plan scene exits 1 and writes no boss config",
           proc.returncode == 1 and not os.path.exists(bad_out)
           and "NoSuchBoss" in (proc.stderr or ""),
           "exit=%s %s" % (proc.returncode, (proc.stderr or "")[-300:]))
        ghost_out = os.path.join(tmp, "Levels", "cli_boss_ghost.json")
        proc = subprocess.run(
            [sys.executable, os.path.join(TOOL_DIR, "level_planner.py"), boss_blueprint_path,
             "--mode", "boss", "--boss", "ghost", "--plan", plan_path,
             "--out", ghost_out, "--project-root", tmp],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=PROJECT_ROOT, stdin=subprocess.DEVNULL, timeout=120)
        ok("cli: unknown Boss entity exits 1 and writes no config (no guessing)",
           proc.returncode == 1 and not os.path.exists(ghost_out)
           and "ghost" in (proc.stderr or ""),
           "exit=%s %s" % (proc.returncode, (proc.stderr or "")[-300:]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if _failures:
        print("FAIL: %d failing check(s)" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: all level orchestration planner checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
