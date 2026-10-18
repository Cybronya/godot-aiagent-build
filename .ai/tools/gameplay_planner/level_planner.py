#!/usr/bin/env python3
"""Level Orchestration Planner（Phase 1.13；Phase 1.20 增加 boss 模式）

把 Gameplay Blueprint 展开成**可运行的关卡编排配置**（`Levels/<level_id>.json`），
并提供该配置的校验实现（producer CLI 与 `validator/check_level.py` 共用同一函数）。

职责边界（见 `.ai/context/level_schema.yaml`）：

    - 只产出**声明式数据**：生成什么（实体 / 数量 / 波次或生成调度）、出口何时开、胜利条件。
      不生成场景、不实例化敌人、不启动 Godot、不建第二套运行时。
    - 运行时状态（已生成 / 剩余 / 当前波次 / 门状态）与运行时行为归场景组合层：
      `Orchestration/level_orchestrator.gd`（LevelOrchestrator，Phase 1.14 通用编排）；
      场景适配层 `Scenes/timed_combat_arena.gd`（waves）与 `Scenes/survival_arena.gd`
      （holdout）只做节点引用与表现。

    Gameplay Blueprint（gameplay_schema.yaml）
      -> Level Orchestration（level_schema.yaml，本模块产出）
        -> Levels/<level_id>.json（Generated Data）
          -> Orchestration/level_orchestrator.gd（运行时消费；waves / holdout / boss / 多阶段 boss）

版本兼容：version 1 = Phase 1.13 遗留 waves 配置（无 mode / holdout / boss 字段，仍然有效）；
version 2 = 增加 mode: waves | holdout | boss（本模块生成 version 2 的 waves / boss /
多阶段 boss 配置；holdout 配置暂为手工编写，生成器不产出 —— 不把尚未支持的能力
伪装成已支持）。

boss 模式（Phase 1.20）：

    python level_planner.py <gameplay.yaml> --mode boss --boss <entity> \\
        --plan <composition_plan.yaml> [--arena-scene res://Scenes/<Host>.tscn] --out Levels/<id>.json

    实体 -> 场景映射与实例名全部来自真实 composition_plan（host.name 派生默认 arena_scene），
    Boss 身份由 --boss 显式点名；不扫描目录、不按 role 猜 Boss。

多阶段 Boss（Phase 1.21）：在同一命令追加 `--stage`（按出现顺序，不重排）：

    --stage clear:<entity>:<count>[,<entity>:<count>]   # clear_enemies
    --stage boss                                        # defeat_boss（必须最后/或紧跟 complete）
    --stage complete                                    # complete_level（可选终结）

    validate_level(level, plan=...) 追加 LevelConfig ↔ composition_plan 交叉校验；
    plan=None 时保持单独 LevelConfig 校验行为，并报告 cross_check_skipped。

用法:

    python .ai/tools/gameplay_planner/level_planner.py <gameplay.yaml> --out Levels/<id>.json
        [--level-id X] [--arena-scene res://Scenes/TimedCombatArena.tscn]
        [--waves N] [--wave-size N] [--wave "entity:count[,entity:count]"...]
    python .ai/tools/gameplay_planner/level_planner.py --check Levels/<id>.json [--json]

退出码: 0 = 成功（含 --check 通过）；1 = 规划 / 校验失败；2 = 输入或环境错误。
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
from pathlib import Path

try:
    import yaml
except ImportError:                                          # pragma: no cover - 环境错误
    print("FAIL: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    raise SystemExit(2)

_DOTAI = Path(__file__).resolve().parents[2]                  # <project>/.ai
PROJECT_ROOT = _DOTAI.parent                                  # <project>

LEVEL_SCHEMA_ID = "level_orchestration"
LEVEL_SCHEMA_VERSION = 2
# 兼容接受 version 1（Phase 1.13 遗留 waves 配置：无 mode/holdout 字段）
SUPPORTED_LEVEL_VERSIONS = (1, 2)

# 编排模式（version 2 引入）
MODE_WAVES = "waves"
MODE_HOLDOUT = "holdout"
MODE_BOSS = "boss"
SUPPORTED_MODES = (MODE_WAVES, MODE_HOLDOUT, MODE_BOSS)

# 出口解锁规则（唯一合法值集合；拼错即失败，绝不静默回退）
EXIT_ALL_WAVES_CLEARED = "all_waves_cleared"
EXIT_NEVER = "never"
EXIT_BOSS_DEFEATED = "boss_defeated"
SUPPORTED_EXIT_UNLOCK = (EXIT_ALL_WAVES_CLEARED, EXIT_NEVER)
SUPPORTED_EXIT_UNLOCK_BOSS = (EXIT_BOSS_DEFEATED, EXIT_NEVER)

# 胜利条件（唯一合法值集合）
VICTORY_EXIT_REACHED = "exit_reached_after_unlock"
VICTORY_ALL_WAVES_CLEARED = "all_waves_cleared"
VICTORY_SURVIVE_DURATION = "survive_duration"
VICTORY_BOSS_DEFEATED = "boss_defeated"
SUPPORTED_VICTORY = (VICTORY_EXIT_REACHED, VICTORY_ALL_WAVES_CLEARED)
SUPPORTED_VICTORY_HOLDOUT = (VICTORY_SURVIVE_DURATION,)
SUPPORTED_VICTORY_BOSS = (VICTORY_BOSS_DEFEATED, VICTORY_EXIT_REACHED)

# Boss 实例来源（显式声明，绝不按 role / 名称推断）
BOSS_SPAWN_EXISTING = "existing"
BOSS_SPAWN_ON_START = "on_start"
SUPPORTED_BOSS_SPAWN = (BOSS_SPAWN_EXISTING, BOSS_SPAWN_ON_START)

# 多阶段 Boss（Phase 1.21）：阶段类型；顺序由 stages 数组显式声明。
STAGE_CLEAR_ENEMIES = "clear_enemies"
STAGE_DEFEAT_BOSS = "defeat_boss"
STAGE_COMPLETE_LEVEL = "complete_level"
SUPPORTED_STAGE_TYPES = (STAGE_CLEAR_ENEMIES, STAGE_DEFEAT_BOSS, STAGE_COMPLETE_LEVEL)

DEFAULT_WAVE_DURATION = 30.0
DEFAULT_WAVE_COUNT = 2        # 生成器默认波数（真实可玩的最小顺序波次）
DEFAULT_WAVE_SIZE = 2         # 生成器默认首波敌人数量（第 i 波 = wave_size + i）
DEFAULT_ARENA_SCENE = "res://Scenes/TimedCombatArena.tscn"
DEFAULT_HOLDOUT_ARENA_SCENE = "res://Scenes/SurvivalArena.tscn"
DEFAULT_HOLDOUT_SURVIVAL_DURATION = 3.0   # holdout 生成器默认存活时长（探针可等待的真实秒数）
DEFAULT_HOLDOUT_SPAWN_INTERVAL = 0.4      # holdout 生成器默认生成间隔
DEFAULT_HOLDOUT_SPAWN_DELAY = 0.0
DEFAULT_HOLDOUT_MAX_ALIVE = 4
SPAWNABLE_ROLE = "enemy"      # 竞技场只生成 enemy 角色的实体（角色词见 gameplay_schema.yaml）


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_positive_number(value) -> bool:
    return _is_number(value) and float(value) > 0.0


def _is_non_negative_number(value) -> bool:
    return _is_number(value) and float(value) >= 0.0


def _is_positive_integer(value) -> bool:
    return _is_number(value) and float(value) >= 1.0 and float(value) == int(value)


def _pascal(name: str) -> str:
    return "".join(part[:1].upper() + part[1:]
                   for part in str(name).replace("-", "_").split("_") if part)


def resolve_entity_scene(entity_id: str, entry: dict, project_root: Path):
    """实体 -> 实体场景 res:// 路径（复用声明优先，其次 `Scenes/<Pascal>.tscn` 生成约定）。

    只做「存在性解析」，不选资源、不推断路径、不编造：解析不到返回 None（由调用方报缺口）。
    """
    declared = str((entry or {}).get("scene") or "").strip()
    if declared:
        if declared.startswith("res://"):
            return declared if (project_root / declared[len("res://"):]).is_file() else None
        relative = declared.replace("\\", "/").lstrip("/")
        return ("res://" + relative) if (project_root / relative).is_file() else None
    generated = "Scenes/%s.tscn" % _pascal(entity_id)
    return ("res://" + generated) if (project_root / generated).is_file() else None


def validate_level(level, project_root=None, plan=None) -> dict:
    """校验关卡编排配置。返回 {failures, warnings, checked, level_id}；只判不修。

    每条 failure 以 JSON 路径开头（如 `waves[1].entries[0].count`），便于按错误定位修正。
    plan 给出时（Phase 1.21）追加 LevelConfig ↔ composition_plan 交叉校验；
    plan=None 保持单独 LevelConfig 校验的既有行为，并从 `cross_check_skipped`
    如实报告多阶段配置缺少交叉校验输入（INCOMPLETE 语义，不伪装通过）。
    """
    failures: list = []
    warnings: list = []
    checked = 0
    if not isinstance(level, dict):
        return {"failures": ["root: expected a JSON object, got %s" % type(level).__name__],
                "warnings": warnings, "checked": 0, "level_id": None,
                "cross_checked": False, "cross_check_skipped": False}

    schema = level.get("schema")
    version = None
    if not isinstance(schema, dict):
        failures.append("schema: missing required object 'schema'")
    else:
        if schema.get("id") != LEVEL_SCHEMA_ID:
            failures.append("schema.id: expected %r, got %r" % (LEVEL_SCHEMA_ID, schema.get("id")))
        version = schema.get("version")
        if version not in SUPPORTED_LEVEL_VERSIONS:
            failures.append("schema.version: expected one of %s, got %r"
                            % (", ".join(str(item) for item in SUPPORTED_LEVEL_VERSIONS), version))
        else:
            checked += 1

    level_block = level.get("level")
    level_id = None
    if not isinstance(level_block, dict):
        failures.append("level: missing required object 'level'")
    else:
        level_id = level_block.get("id")
        if not isinstance(level_id, str) or not level_id.strip():
            failures.append("level.id: required non-empty string")
            level_id = None
        else:
            checked += 1
        arena = level_block.get("arena_scene")
        if arena is not None and (not isinstance(arena, str) or not arena.startswith("res://")):
            failures.append("level.arena_scene: must be a res:// path string, got %r" % (arena,))

    entities = level.get("entities")
    entity_ids = set()
    if not isinstance(entities, dict) or not entities:
        failures.append("entities: required non-empty object")
    else:
        for entity_id in sorted(entities, key=str):
            node = entities[entity_id]
            if not isinstance(entity_id, str) or not entity_id.strip():
                failures.append("entities: entity id must be a non-empty string")
                continue
            if not isinstance(node, dict):
                failures.append("entities.%s: expected an object with 'scene'" % entity_id)
                continue
            scene = node.get("scene")
            if not isinstance(scene, str) or not scene.startswith("res://"):
                failures.append("entities.%s.scene: required res:// path string, got %r"
                                % (entity_id, scene))
                continue
            entity_ids.add(entity_id)
            checked += 1
            if project_root is not None and not (Path(project_root) / scene[len("res://"):]).is_file():
                failures.append("entities.%s.scene: scene not found in project: %s"
                                % (entity_id, scene))

    mode = level.get("mode")
    mode_value = MODE_WAVES
    if mode is not None:
        if not isinstance(mode, str) or mode not in SUPPORTED_MODES:
            failures.append("mode: unsupported value %r (supported: %s)"
                            % (mode, ", ".join(SUPPORTED_MODES)))
        else:
            mode_value = mode
            checked += 1
    if version == 1 and (mode_value == MODE_HOLDOUT or level.get("holdout") is not None):
        failures.append("mode: version 1 configs do not support holdout orchestration "
                        "(use version 2)")
    if version == 1 and (mode_value == MODE_BOSS or level.get("boss") is not None):
        failures.append("mode: version 1 configs do not support boss orchestration "
                        "(use version 2)")

    if mode_value == MODE_HOLDOUT:
        holdout_failures, holdout_checked = _validate_holdout(level, entity_ids)
        failures.extend(holdout_failures)
        checked += holdout_checked
        failures.extend(_validate_victory_holdout(level))
    elif mode_value == MODE_BOSS:
        boss_failures, boss_checked = _validate_boss(level, entity_ids)
        failures.extend(boss_failures)
        checked += boss_checked
    else:
        wave_failures, wave_checked = _validate_waves(level, entity_ids)
        failures.extend(wave_failures)
        checked += wave_checked
        if level.get("stages") is not None:
            failures.append("stages: only mode 'boss' supports multi-stage boss orchestration")

    cross_checked = plan is not None
    boss_block = level.get("boss") if isinstance(level.get("boss"), dict) else {}
    references_host_instance = (isinstance(level.get("stages"), list)
                                or str(boss_block.get("spawn") or "") == BOSS_SPAWN_EXISTING
                                or (not boss_block.get("spawn") and bool(boss_block.get("instance"))))
    cross_check_skipped = (plan is None and mode_value == MODE_BOSS
                           and references_host_instance)
    if plan is not None:
        if mode_value != MODE_BOSS:
            failures.append("plan: cross-contract validation only applies to mode 'boss'")
        else:
            cross_failures, cross_checked_items = _validate_plan_cross_contract(
                level, plan, project_root, entity_ids)
            failures.extend(cross_failures)
            checked += cross_checked_items

    return {"failures": failures, "warnings": warnings, "checked": checked,
            "level_id": level_id, "cross_checked": cross_checked,
            "cross_check_skipped": cross_check_skipped}


def _validate_waves(level, entity_ids):
    """waves 模式：waves / exit / victory 规则（Phase 1.13 语义，版本兼容保留）。

    返回 (failures, checked)。
    """
    failures: list = []
    checked = 0
    waves = level.get("waves")
    if not isinstance(waves, list) or not waves:
        failures.append("waves: required non-empty array")
    else:
        seen_wave_ids = set()
        for index, wave in enumerate(waves):
            where = "waves[%d]" % index
            if not isinstance(wave, dict):
                failures.append("%s: expected an object" % where)
                continue
            wave_id = wave.get("id")
            if not isinstance(wave_id, str) or not wave_id.strip():
                failures.append("%s.id: required non-empty string" % where)
            elif wave_id in seen_wave_ids:
                failures.append("%s.id: duplicate wave id %r" % (where, wave_id))
            else:
                seen_wave_ids.add(wave_id)
                checked += 1
            if "duration" in wave:
                duration = wave.get("duration")
                if isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration <= 0:
                    failures.append("%s.duration: must be a number > 0, got %r" % (where, duration))
                else:
                    checked += 1
            entries = wave.get("entries")
            if not isinstance(entries, list) or not entries:
                failures.append("%s.entries: required non-empty array" % where)
                continue
            for entry_index, entry in enumerate(entries):
                entry_where = "%s.entries[%d]" % (where, entry_index)
                if not isinstance(entry, dict):
                    failures.append("%s: expected an object" % entry_where)
                    continue
                entity_id = entry.get("entity")
                if not isinstance(entity_id, str) or not entity_id.strip():
                    failures.append("%s.entity: required non-empty string" % entry_where)
                elif entity_ids and entity_id not in entity_ids:
                    failures.append("%s.entity: unknown entity %r (not declared in entities)"
                                    % (entry_where, entity_id))
                count = entry.get("count")
                if isinstance(count, bool) or not isinstance(count, int) or count < 1:
                    failures.append("%s.count: must be an integer >= 1, got %r"
                                    % (entry_where, count))
                else:
                    checked += 1

    if level.get("boss") is not None:
        failures.append("boss: only valid when mode is 'boss' "
                        "(waves mode orchestrates entities through waves entries)")

    exit_block = level.get("exit")
    if exit_block is None:
        exit_block = {}
    elif not isinstance(exit_block, dict):
        failures.append("exit: expected an object")
        exit_block = {}
    unlock_when = exit_block.get("unlock_when", EXIT_ALL_WAVES_CLEARED)
    if unlock_when not in SUPPORTED_EXIT_UNLOCK:
        failures.append("exit.unlock_when: unsupported value %r (supported: %s)"
                        % (unlock_when, ", ".join(SUPPORTED_EXIT_UNLOCK)))
    else:
        checked += 1

    victory_block = level.get("victory")
    if victory_block is None:
        victory_block = {}
    elif not isinstance(victory_block, dict):
        failures.append("victory: expected an object")
        victory_block = {}
    condition = victory_block.get("condition", VICTORY_EXIT_REACHED)
    if condition not in SUPPORTED_VICTORY:
        failures.append("victory.condition: unsupported value %r (supported: %s)"
                        % (condition, ", ".join(SUPPORTED_VICTORY)))
    else:
        checked += 1

    # 交叉规则：出口永不开 + 胜利依赖出口 = 胜利不可达
    if unlock_when == EXIT_NEVER and condition == VICTORY_EXIT_REACHED:
        failures.append("victory.condition: unreachable — exit.unlock_when is 'never', "
                        "so the player can never reach the exit and win")
    return failures, checked


def _validate_holdout(level, entity_ids):
    """holdout 模式：waves / exit 不得出现；holdout 块（时长 / 总上限 / 生成调度）必填合法。

    返回 (failures, checked)。
    """
    failures: list = []
    checked = 0
    if level.get("waves") is not None:
        failures.append("waves: holdout mode does not support sequential waves "
                        "(use holdout.spawns for continuous spawning)")
    if level.get("exit") is not None:
        failures.append("exit: holdout mode has no exit (survival levels end by duration)")
    if level.get("boss") is not None:
        failures.append("boss: holdout mode has no boss phase (use mode: boss)")
    if level.get("stages") is not None:
        failures.append("stages: holdout mode does not support multi-stage boss orchestration")
    holdout = level.get("holdout")
    if not isinstance(holdout, dict):
        failures.append("holdout: required object (holdout mode)")
        return failures, checked
    duration = holdout.get("survival_duration")
    if not _is_positive_number(duration):
        failures.append("holdout.survival_duration: must be a number > 0, got %r" % (duration,))
    else:
        checked += 1
    if "max_alive" in holdout:
        max_alive = holdout.get("max_alive")
        if not _is_positive_integer(max_alive):
            failures.append("holdout.max_alive: must be an integer >= 1, got %r" % (max_alive,))
        else:
            checked += 1
    spawns = holdout.get("spawns")
    if not isinstance(spawns, list) or not spawns:
        failures.append("holdout.spawns: required non-empty array")
        return failures, checked
    for index, spawn in enumerate(spawns):
        where = "holdout.spawns[%d]" % index
        if not isinstance(spawn, dict):
            failures.append("%s: expected an object" % where)
            continue
        entity_id = spawn.get("entity")
        if not isinstance(entity_id, str) or not entity_id.strip():
            failures.append("%s.entity: required non-empty string" % where)
        elif entity_ids and entity_id not in entity_ids:
            failures.append("%s.entity: unknown entity %r (not declared in entities)"
                            % (where, entity_id))
        else:
            checked += 1
        if "count" in spawn:
            failures.append("%s.count: holdout mode uses max_alive instead of count "
                            "(count is only valid for waves entries)" % where)
        interval = spawn.get("interval")
        if not _is_positive_number(interval):
            failures.append("%s.interval: must be a number > 0, got %r" % (where, interval))
        else:
            checked += 1
        if "delay" in spawn:
            delay = spawn.get("delay")
            if not _is_non_negative_number(delay):
                failures.append("%s.delay: must be a number >= 0, got %r" % (where, delay))
            else:
                checked += 1
        if "max_alive" in spawn:
            spawn_max_alive = spawn.get("max_alive")
            if not _is_positive_integer(spawn_max_alive):
                failures.append("%s.max_alive: must be an integer >= 1, got %r"
                                % (where, spawn_max_alive))
            else:
                checked += 1
    return failures, checked


def _is_relative_node_path(value) -> bool:
    """相对节点路径：非空、不以 / 开头、不含 .. 段（不越出宿主场景根）。"""
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text or text.startswith("/"):
        return False
    return all(segment != ".." for segment in text.split("/"))


def _validate_boss(level, entity_ids):
    """boss 模式：waves / holdout 不得出现；Boss 身份与实例来源必须显式且可解析。

    返回 (failures, checked)。
    """
    failures: list = []
    checked = 0
    if level.get("waves") is not None:
        failures.append("waves: boss mode does not support sequential waves "
                        "(a boss level is completed by defeating the declared boss)")
    if level.get("holdout") is not None:
        failures.append("holdout: boss mode does not support holdout spawning")

    boss = level.get("boss")
    if not isinstance(boss, dict):
        failures.append("boss: required object (boss mode)")
        return failures, checked

    entity_id = boss.get("entity")
    instance = boss.get("instance")
    if not isinstance(entity_id, str) or not entity_id.strip():
        failures.append("boss.entity: required non-empty string")
    elif entity_ids and entity_id not in entity_ids:
        failures.append("boss.entity: unknown entity %r (not declared in entities)"
                        % (entity_id,))
    else:
        checked += 1

    if instance is not None:
        if not _is_relative_node_path(instance):
            failures.append("boss.instance: must be a relative node path string "
                            "(got %r)" % (instance,))
        else:
            checked += 1

    default_spawn = BOSS_SPAWN_EXISTING if instance is not None else BOSS_SPAWN_ON_START
    spawn = boss.get("spawn", default_spawn)
    if spawn not in SUPPORTED_BOSS_SPAWN:
        failures.append("boss.spawn: unsupported value %r (supported: %s)"
                        % (spawn, ", ".join(SUPPORTED_BOSS_SPAWN)))
    elif spawn == BOSS_SPAWN_EXISTING and not _is_relative_node_path(instance):
        failures.append("boss.instance: required when boss.spawn is 'existing' "
                        "(point at the existing boss instance explicitly)")
    else:
        checked += 1

    exit_block = level.get("exit")
    unlock_when = EXIT_BOSS_DEFEATED
    if exit_block is None:
        exit_block = {}
    elif not isinstance(exit_block, dict):
        failures.append("exit: expected an object")
        exit_block = {}
    else:
        unlock_when = exit_block.get("unlock_when", EXIT_BOSS_DEFEATED)
    if unlock_when not in SUPPORTED_EXIT_UNLOCK_BOSS:
        failures.append("exit.unlock_when: unsupported value %r (supported in boss mode: %s)"
                        % (unlock_when, ", ".join(SUPPORTED_EXIT_UNLOCK_BOSS)))
    else:
        checked += 1

    victory_block = level.get("victory")
    condition = VICTORY_BOSS_DEFEATED
    if victory_block is None:
        victory_block = {}
    elif not isinstance(victory_block, dict):
        failures.append("victory: expected an object")
        victory_block = {}
    else:
        condition = victory_block.get("condition", VICTORY_BOSS_DEFEATED)
    if condition not in SUPPORTED_VICTORY_BOSS:
        failures.append("victory.condition: unsupported value %r "
                        "(supported in boss mode: %s)"
                        % (condition, ", ".join(SUPPORTED_VICTORY_BOSS)))
    else:
        checked += 1

    if unlock_when == EXIT_NEVER and condition == VICTORY_EXIT_REACHED:
        failures.append("victory.condition: unreachable — exit.unlock_when is 'never', "
                        "so the player can never reach the exit and win")

    if level.get("stages") is not None:
        stage_failures, stage_checked = _validate_stages(
            level, entity_ids, entity_id, unlock_when, condition)
        failures.extend(stage_failures)
        checked += stage_checked
    return failures, checked


def _validate_stages(level, entity_ids, boss_entity, unlock_when, condition):
    """多阶段 Boss 契约（Phase 1.21）。返回 (failures, checked)。

    阶段顺序只由 stages 数组决定；不依赖目录顺序、节点遍历顺序或模糊名称匹配。
    """
    failures: list = []
    checked = 0
    stages = level.get("stages")
    if not isinstance(stages, list) or not stages:
        failures.append("stages: required non-empty array (multi-stage boss)")
        return failures, checked
    if len(stages) < 2:
        failures.append("stages: at least 2 stages required "
                        "(clear_enemies -> defeat_boss[ -> complete_level])")
    checked += 1
    seen_ids: set = set()
    clear_count = 0
    defeat_count = 0
    complete_count = 0
    for index, stage in enumerate(stages):
        where = "stages[%d]" % index
        if not isinstance(stage, dict):
            failures.append("%s: expected an object" % where)
            continue
        stage_id = stage.get("id")
        if not isinstance(stage_id, str) or not stage_id.strip():
            failures.append("%s.id: required non-empty string" % where)
        elif stage_id in seen_ids:
            failures.append("%s.id: duplicate stage id %r" % (where, stage_id))
        else:
            seen_ids.add(stage_id)
            checked += 1
        stage_type = stage.get("type")
        if stage_type not in SUPPORTED_STAGE_TYPES:
            failures.append("%s.type: unsupported stage type %r (supported: %s)"
                            % (where, stage_type, ", ".join(SUPPORTED_STAGE_TYPES)))
            continue
        if stage_type == STAGE_CLEAR_ENEMIES:
            clear_count += 1
            entries = stage.get("entries")
            if not isinstance(entries, list) or not entries:
                failures.append("%s.entries: clear_enemies requires a non-empty array" % where)
                continue
            for entry_index, entry in enumerate(entries):
                entry_where = "%s.entries[%d]" % (where, entry_index)
                if not isinstance(entry, dict):
                    failures.append("%s: expected an object" % entry_where)
                    continue
                entity_id = entry.get("entity")
                if not isinstance(entity_id, str) or not entity_id.strip():
                    failures.append("%s.entity: required non-empty string" % entry_where)
                elif entity_ids and entity_id not in entity_ids:
                    failures.append("%s.entity: unknown entity %r (not declared in entities)"
                                    % (entry_where, entity_id))
                elif entity_id == boss_entity:
                    failures.append("%s.entity: clear_enemies must not reference the boss entity %r "
                                    "(the boss is settled only by defeat_boss)"
                                    % (entry_where, boss_entity))
                count = entry.get("count")
                if isinstance(count, bool) or not isinstance(count, int) or count < 1:
                    failures.append("%s.count: must be an integer >= 1, got %r"
                                    % (entry_where, count))
                else:
                    checked += 1
        elif stage_type == STAGE_DEFEAT_BOSS:
            defeat_count += 1
            stage_entity = stage.get("entity")
            if not isinstance(stage_entity, str) or not stage_entity.strip() \
                    or stage_entity != boss_entity:
                failures.append("%s.entity: defeat_boss must reference boss.entity (%r), got %r"
                                % (where, boss_entity, stage_entity))
            is_last = index == len(stages) - 1
            before_complete = (index == len(stages) - 2
                               and isinstance(stages[index + 1], dict)
                               and stages[index + 1].get("type") == STAGE_COMPLETE_LEVEL)
            if not is_last and not before_complete:
                failures.append("%s: defeat_boss must be the last stage "
                                "(or immediately before complete_level)" % where)
        elif stage_type == STAGE_COMPLETE_LEVEL:
            complete_count += 1
            if index != len(stages) - 1:
                failures.append("%s: complete_level must be the last stage" % where)
    if clear_count == 0:
        failures.append("stages: at least one clear_enemies stage is required "
                        "(the boss must not activate before enemies are cleared)")
    if defeat_count != 1:
        failures.append("stages: exactly one defeat_boss stage is required, got %d"
                        % defeat_count)
    if complete_count > 1:
        failures.append("stages: complete_level may appear at most once, got %d"
                        % complete_count)
    if complete_count == 1:
        if condition != VICTORY_BOSS_DEFEATED:
            failures.append("victory.condition: complete_level requires condition %r, got %r"
                            % (VICTORY_BOSS_DEFEATED, condition))
        if unlock_when != EXIT_NEVER:
            failures.append("exit.unlock_when: complete_level requires %r, got %r"
                            % (EXIT_NEVER, unlock_when))
    return failures, checked


def _read_scene_identity(path: Path) -> tuple:
    """读取 .tscn 的根节点名与根级 instance 节点名（仅用于交叉校验）。"""
    import re
    text = path.read_text(encoding="utf-8")
    root = re.search(r'^\[node name="([^"]+)"', text, re.MULTILINE)
    root_name = root.group(1) if root else ""
    instances = re.findall(
        r'^\[node name="([^"]+)" parent="\."[^\]]*instance=ExtResource\(', text,
        re.MULTILINE)
    return root_name, instances


def _validate_plan_cross_contract(level, plan, project_root, entity_ids):
    """LevelConfig ↔ composition_plan 身份交叉校验（Phase 1.21）。

    只使用两份真实产物：plan 的 host/instances 与 arena_scene 的实际根节点/
    根级 instance 节点。拒绝模糊名称匹配；缺少任一输入时由调用方标记 INCOMPLETE。
    """
    failures: list = []
    checked = 0
    project_root = Path(project_root) if project_root else PROJECT_ROOT
    if not isinstance(plan, dict):
        return (["plan: expected a composition plan object, got %s"
                 % type(plan).__name__], 0)
    if plan.get("document") != "composition_plan":
        failures.append("plan.document: expected 'composition_plan', got %r"
                        % (plan.get("document"),))
    if plan.get("schema_version") != 1:
        failures.append("plan.schema_version: expected 1, got %r"
                        % (plan.get("schema_version"),))
    host = plan.get("host")
    host_name = str((host or {}).get("name") or "").strip() if isinstance(host, dict) else ""
    if not host_name:
        failures.append("plan.host.name: required non-empty string")
    instances = plan.get("instances")
    if not isinstance(instances, list) or not instances:
        failures.append("plan.instances: required non-empty array")
        instances = []
    instance_entities: dict = {}
    instance_names: dict = {}
    for index, instance in enumerate(instances):
        where = "plan.instances[%d]" % index
        if not isinstance(instance, dict):
            failures.append("%s: expected an object" % where)
            continue
        entity_id = str(instance.get("entity") or "").strip()
        scene = str(instance.get("scene") or "").strip()
        instance_name = str(instance.get("instance_name") or "").strip()
        if not entity_id:
            failures.append("%s.entity: required non-empty string" % where)
            continue
        if entity_id in instance_entities:
            failures.append("%s.entity: duplicate entity %r in the composition plan"
                            % (where, entity_id))
            continue
        if not scene.startswith("res://"):
            failures.append("%s.scene: required res:// path, got %r" % (where, scene))
            continue
        if not (project_root / scene[len("res://"):]).is_file():
            failures.append("%s.scene: scene not found in project: %s" % (where, scene))
            continue
        if not instance_name:
            failures.append("%s.instance_name: required to bind the level to the host "
                            "instance" % where)
            continue
        if instance_name in instance_names:
            failures.append("%s.instance_name: duplicate host instance %r"
                            % (where, instance_name))
            continue
        instance_entities[entity_id] = instance_name
        instance_names[instance_name] = entity_id
        checked += 1

    arena = str((level.get("level") or {}).get("arena_scene") or "").strip()
    if not arena.startswith("res://"):
        failures.append("level.arena_scene: required to cross-check against the composition plan")
        return failures, checked
    arena_path = project_root / arena[len("res://"):]
    if not arena_path.is_file():
        failures.append("level.arena_scene: composed host scene not found: %s" % arena)
        return failures, checked
    root_name, host_instances = _read_scene_identity(arena_path)
    if host_name and root_name != host_name:
        failures.append("level.arena_scene: host root %r does not match composition plan host %r"
                        % (root_name, host_name))
    else:
        checked += 1
    duplicate_host = sorted({name for name in host_instances if host_instances.count(name) > 1})
    if duplicate_host:
        failures.append("level.arena_scene: duplicate instance names in host: %s"
                        % ", ".join(duplicate_host))
    missing = sorted(set(instance_names) - set(host_instances))
    if missing:
        failures.append("level.arena_scene: host is missing declared instance(s): %s"
                        % ", ".join(missing))
    unknown = sorted(set(host_instances) - set(instance_names))
    if unknown:
        failures.append("level.arena_scene: host contains instance(s) not declared by the "
                        "composition plan: %s" % ", ".join(unknown))
    checked += len(instance_names)

    boss = level.get("boss") if isinstance(level.get("boss"), dict) else {}
    boss_entity = boss.get("entity")
    boss_spawn = boss.get("spawn", BOSS_SPAWN_EXISTING if boss.get("instance") else
                          BOSS_SPAWN_ON_START)
    if boss_spawn == BOSS_SPAWN_EXISTING:
        if boss_entity not in instance_entities:
            failures.append("boss.entity: boss entity %r is not an instance of the composition "
                            "plan" % (boss_entity,))
        else:
            expected = instance_entities[boss_entity]
            declared = boss.get("instance")
            if declared != expected:
                failures.append("boss.instance: level declares %r but composition plan instance "
                                "is %r" % (declared, expected))
            else:
                checked += 1

    stages = level.get("stages")
    if isinstance(stages, list):
        for index, stage in enumerate(stages):
            if not isinstance(stage, dict):
                continue
            if stage.get("type") == STAGE_CLEAR_ENEMIES:
                for entry_index, entry in enumerate(stage.get("entries") or []):
                    if not isinstance(entry, dict):
                        continue
                    entity_id = entry.get("entity")
                    if entity_id not in instance_entities:
                        failures.append("stages[%d].entries[%d].entity: entity %r is not "
                                        "declared by the composition plan (instances: %s)"
                                        % (index, entry_index, entity_id,
                                           ", ".join(sorted(instance_entities)) or "<none>"))
                    else:
                        checked += 1
            elif stage.get("type") == STAGE_DEFEAT_BOSS:
                entity_id = stage.get("entity")
                if entity_id not in instance_entities:
                    failures.append("stages[%d].entity: boss entity %r is not an instance of "
                                    "the composition plan" % (index, entity_id))
                else:
                    checked += 1
    return failures, checked


def _validate_victory_holdout(level) -> list:
    """holdout 模式胜利条件：仅支持 survive_duration（缺省即该值）。"""
    failures: list = []
    victory_block = level.get("victory")
    if victory_block is None:
        return failures
    if not isinstance(victory_block, dict):
        failures.append("victory: expected an object")
        return failures
    condition = victory_block.get("condition", VICTORY_SURVIVE_DURATION)
    if condition not in SUPPORTED_VICTORY_HOLDOUT:
        failures.append("victory.condition: holdout mode only supports %r, got %r"
                        % (VICTORY_SURVIVE_DURATION, condition))
    return failures


def parse_stage_spec(text: str) -> tuple:
    """解析 `--stage`：`boss` / `complete` / `clear:<entity>:<count>[,<entity>:<count>]`。

    非法形态抛 ValueError（调用方转 exit 2）。阶段顺序 = 参数出现顺序，绝不重排。
    """
    text = str(text).strip()
    if text in ("boss", STAGE_DEFEAT_BOSS):
        return (STAGE_DEFEAT_BOSS,)
    if text in ("complete", STAGE_COMPLETE_LEVEL):
        return (STAGE_COMPLETE_LEVEL,)
    if not text.startswith("clear:"):
        raise ValueError("stage must be 'boss', 'complete' or 'clear:entity:count[,entity:count]', "
                         "got %r" % text)
    entries = []
    for chunk in text[len("clear:"):].split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = chunk.split(":")
        if len(parts) != 2 or not parts[0].strip():
            raise ValueError("clear stage entry must look like entity:count, got %r" % chunk)
        try:
            count = int(parts[1].strip())
        except ValueError:
            raise ValueError("clear stage count must be an integer: %r" % chunk)
        if count < 1:
            raise ValueError("clear stage count must be >= 1: %r" % chunk)
        entries.append((parts[0].strip(), count))
    if not entries:
        raise ValueError("clear stage needs at least one entity:count entry")
    return (STAGE_CLEAR_ENEMIES, entries)


def parse_wave_spec(text: str, project_root: Path = None) -> list:
    """解析 `--wave "entity:count[,entity:count]"`。非法形态抛 ValueError（调用方转 exit 2）。"""
    entries = []
    for chunk in str(text).split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" not in chunk:
            raise ValueError("wave entry must look like entity:count, got %r" % chunk)
        entity_id, _, raw_count = chunk.partition(":")
        entity_id = entity_id.strip()
        if not entity_id:
            raise ValueError("wave entry is missing an entity id: %r" % chunk)
        try:
            count = int(raw_count.strip())
        except ValueError:
            raise ValueError("wave entry count must be an integer: %r" % chunk)
        entries.append((entity_id, count))
    if not entries:
        raise ValueError("wave entry list is empty")
    return entries


def build_level(gameplay: dict, project_root=None, level_id: str = None,
                arena_scene: str = DEFAULT_ARENA_SCENE, wave_count: int = DEFAULT_WAVE_COUNT,
                wave_size: int = DEFAULT_WAVE_SIZE, wave_specs: list = None) -> dict:
    """Gameplay Blueprint -> 关卡编排配置（不写盘）。

    只使用蓝图里**已声明或已生成**的事实：
        - 可生成实体 = role == "enemy" 且场景可解析（scene: 复用声明或 Scenes/<Pascal>.tscn 生成物）；
        - 波次默认按「首波 wave_size 个，之后每波 +1」生成（`--wave` 可显式覆盖）；
        - 出口 / 胜利条件使用契约默认值（all_waves_cleared / exit_reached_after_unlock）。
    返回 {ok, level, failures, warnings}；ok=False 时 level=None（不产出半成品）。
    """
    project_root = Path(project_root) if project_root else PROJECT_ROOT
    failures: list = []
    entities_block = (gameplay or {}).get("entities") or {}
    if not isinstance(entities_block, dict) or not entities_block:
        failures.append("gameplay.entities: required non-empty object (Gameplay Blueprint)")

    entities: dict = {}
    spawnable: list = []
    for entity_id in sorted(entities_block, key=str):
        entry = entities_block[entity_id]
        if not isinstance(entry, dict):
            continue
        if str(entry.get("role") or "") != SPAWNABLE_ROLE:
            continue
        scene = resolve_entity_scene(entity_id, entry, project_root)
        if scene is None:
            failures.append(
                "entities.%s.scene: enemy entity %r has no resolvable scene "
                "(declare scene: in the gameplay blueprint or generate Scenes/%s.tscn first)"
                % (entity_id, entity_id, _pascal(entity_id)))
            continue
        entities[entity_id] = {"scene": scene}
        spawnable.append(entity_id)

    if not failures and not spawnable:
        failures.append("gameplay.entities: no entity with role %r and a resolvable scene; "
                        "a level needs at least one spawnable enemy" % SPAWNABLE_ROLE)

    resolved_level_id = level_id or str(((gameplay or {}).get("gameplay") or {}).get("id") or "").strip()
    if not resolved_level_id:
        failures.append("level.id: cannot resolve (gameplay.gameplay.id missing; pass --level-id)")

    waves: list = []
    if wave_specs:
        for index, spec in enumerate(wave_specs):
            entries = []
            for entity_id, count in spec:
                if entity_id not in entities:
                    failures.append("waves[%d].entries: entity %r is not a spawnable enemy entity "
                                    "of this blueprint (available: %s)"
                                    % (index, entity_id, ", ".join(spawnable) or "<none>"))
                    continue
                entries.append({"entity": entity_id, "count": count})
            if entries:
                waves.append({"id": "wave_%d" % (index + 1), "duration": DEFAULT_WAVE_DURATION,
                              "entries": entries})
    elif spawnable:
        for index in range(max(int(wave_count), 0)):
            waves.append({"id": "wave_%d" % (index + 1), "duration": DEFAULT_WAVE_DURATION,
                          "entries": [{"entity": spawnable[0],
                                       "count": int(wave_size) + index}]})

    level = {
        "schema": {"id": LEVEL_SCHEMA_ID, "version": LEVEL_SCHEMA_VERSION},
        "level": {"id": resolved_level_id, "arena_scene": arena_scene},
        "mode": MODE_WAVES,
        "entities": entities,
        "waves": waves,
        "exit": {"unlock_when": EXIT_ALL_WAVES_CLEARED},
        "victory": {"condition": VICTORY_EXIT_REACHED},
    }
    failures.extend(validate_level(level, project_root)["failures"])
    return {"ok": not failures, "level": level if not failures else None,
            "failures": failures, "warnings": []}


def build_holdout_level(gameplay: dict, project_root=None, level_id: str = None,
                        arena_scene: str = None, survival_duration: float = None,
                        spawn_interval: float = None, spawn_delay: float = None,
                        max_alive: int = None) -> dict:
    """Gameplay Blueprint -> holdout 模式关卡配置（不写盘；Phase 1.24）。

    与 build_level 同一实体解析事实（role == enemy 且场景可解析）；
    每个可生成实体得到一条 holdout.spawns 调度（interval 共享，delay 共享），
    胜利条件 = survive_duration。arena_scene 缺省为 SurvivalArena（holdout 的
    既有适配层宿主）。返回 {ok, level, failures, warnings}。
    """
    project_root = Path(project_root) if project_root else PROJECT_ROOT
    failures: list = []
    entities_block = (gameplay or {}).get("entities") or {}
    if not isinstance(entities_block, dict) or not entities_block:
        return {"ok": False, "level": None, "warnings": [],
                "failures": ["gameplay.entities: required non-empty object "
                             "(Gameplay Blueprint)"]}
    resolved_level_id = str(level_id or (gameplay.get("gameplay") or {}).get("id")
                            or "holdout_level")
    arena = arena_scene or DEFAULT_HOLDOUT_ARENA_SCENE
    duration = float(survival_duration if survival_duration is not None
                     else DEFAULT_HOLDOUT_SURVIVAL_DURATION)
    interval = float(spawn_interval if spawn_interval is not None
                     else DEFAULT_HOLDOUT_SPAWN_INTERVAL)
    delay = float(spawn_delay if spawn_delay is not None else DEFAULT_HOLDOUT_SPAWN_DELAY)
    cap = int(max_alive if max_alive is not None else DEFAULT_HOLDOUT_MAX_ALIVE)

    entities: dict = {}
    spawns: list = []
    for entity_id in sorted(entities_block, key=str):
        entry = entities_block[entity_id]
        if not isinstance(entry, dict) or str(entry.get("role") or "") != SPAWNABLE_ROLE:
            continue
        scene = resolve_entity_scene(entity_id, entry, project_root)
        if scene is None:
            failures.append(
                "entities.%s.scene: enemy entity %r has no resolvable scene "
                "(declare scene: in the gameplay blueprint or generate Scenes/%s.tscn first)"
                % (entity_id, entity_id, _pascal(entity_id)))
            continue
        entities[entity_id] = {"scene": scene}
        spawns.append({"entity": entity_id, "interval": interval, "delay": delay})
    if not entities:
        failures.append("holdout.spawns: no spawnable enemy entity with a resolvable "
                        "scene (holdout needs at least one)")
    if not failures:
        level = {
            "schema": {"id": LEVEL_SCHEMA_ID, "version": LEVEL_SCHEMA_VERSION},
            "level": {"id": resolved_level_id, "arena_scene": arena},
            "mode": MODE_HOLDOUT,
            "entities": entities,
            "holdout": {"survival_duration": duration, "max_alive": cap,
                        "spawns": spawns},
            "victory": {"condition": VICTORY_SURVIVE_DURATION},
        }
        failures.extend(validate_level(level, project_root)["failures"])
        return {"ok": not failures, "level": level if not failures else None,
                "failures": failures, "warnings": []}
    return {"ok": False, "level": None, "failures": failures, "warnings": []}


def build_boss_level(gameplay: dict, plan: dict, project_root=None, level_id: str = None,
                     boss_entity: str = None, arena_scene: str = None,
                     stage_specs: list = None) -> dict:
    """Gameplay Blueprint + composition_plan -> boss 模式关卡配置（不写盘）。

    输入只使用真实产物：
        - entities / 实例名来自 composition_plan（scene 必须是存在的 res:// 场景）；
        - arena_scene 缺省为 `res://Scenes/<host.name>.tscn`（组合器的落盘约定），必须存在；
        - Boss 身份来自显式 --boss <entity>，绝不按 role / 实例名猜测。
    返回 {ok, level, failures, warnings}；ok=False 时 level=None（不产出半成品）。
    """
    project_root = Path(project_root) if project_root else PROJECT_ROOT
    failures: list = []
    warnings: list = []
    if not isinstance(plan, dict):
        return {"ok": False, "level": None, "warnings": warnings,
                "failures": ["plan: expected a composition plan object, got %s"
                             % type(plan).__name__]}
    if plan.get("document") != "composition_plan":
        failures.append("plan.document: expected 'composition_plan', got %r"
                        % (plan.get("document"),))
    if plan.get("schema_version") != 1:
        failures.append("plan.schema_version: expected 1, got %r"
                        % (plan.get("schema_version"),))
    host_name = str((plan.get("host") or {}).get("name") or "")
    if not host_name:
        failures.append("plan.host.name: required non-empty string")
    instances_spec = plan.get("instances")
    if not isinstance(instances_spec, list) or not instances_spec:
        failures.append("plan.instances: required non-empty array")
        instances_spec = []

    entities: dict = {}
    instance_names: dict = {}
    for index, instance in enumerate(instances_spec):
        where = "plan.instances[%d]" % index
        if not isinstance(instance, dict):
            failures.append("%s: expected an object" % where)
            continue
        entity_id = str(instance.get("entity") or "").strip()
        scene = str(instance.get("scene") or "").strip()
        instance_name = str(instance.get("instance_name") or "").strip()
        if not entity_id:
            failures.append("%s.entity: required non-empty string" % where)
            continue
        if entity_id in entities:
            failures.append("%s.entity: duplicate entity %r in the composition plan"
                            % (where, entity_id))
            continue
        if not scene.startswith("res://"):
            failures.append("%s.scene: required res:// path, got %r" % (where, scene))
            continue
        if not (project_root / scene[len("res://"):]).is_file():
            failures.append("%s.scene: scene not found in project: %s" % (where, scene))
            continue
        if not instance_name:
            failures.append("%s.instance_name: required to bind the level to the host instance"
                            % where)
            continue
        entities[entity_id] = {"scene": scene}
        instance_names[entity_id] = instance_name

    boss_entity = str(boss_entity or "").strip()
    if not boss_entity:
        failures.append("boss.entity: --boss <entity> is required for boss mode")
    elif boss_entity not in entities:
        failures.append("boss.entity: entity %r is not an instance of the composition plan "
                        "(instances: %s)" % (boss_entity, ", ".join(sorted(entities)) or "<none>"))
    elif boss_entity not in ((gameplay or {}).get("entities") or {}):
        failures.append("boss.entity: entity %r is not declared by the gameplay blueprint"
                        % (boss_entity,))

    resolved_level_id = level_id or str(((gameplay or {}).get("gameplay") or {}).get("id") or "").strip()
    if not resolved_level_id:
        failures.append("level.id: cannot resolve (gameplay.gameplay.id missing; pass --level-id)")

    resolved_arena = arena_scene or ("res://Scenes/%s.tscn" % host_name if host_name else "")
    if not resolved_arena.startswith("res://"):
        failures.append("level.arena_scene: required res:// path, got %r" % (resolved_arena,))
    elif not (project_root / resolved_arena[len("res://"):]).is_file():
        failures.append("level.arena_scene: composed host scene not found: %s "
                        "(compose the plan first, or pass --arena-scene)" % resolved_arena)

    stages = []
    if stage_specs:
        clear_index = 0
        for spec in stage_specs:
            if not isinstance(spec, (tuple, list)) or not spec:
                failures.append("stages: invalid stage spec %r" % (spec,))
                continue
            kind = spec[0]
            if kind == STAGE_CLEAR_ENEMIES:
                clear_index += 1
                entries = []
                for entry_index, (entity_id, count) in enumerate(spec[1]):
                    where = "stages[%d].entries[%d]" % (len(stages), entry_index)
                    if entity_id not in entities:
                        failures.append("%s.entity: entity %r is not an instance "
                                        "of the composition plan" % (where, entity_id))
                        continue
                    if entity_id not in ((gameplay or {}).get("entities") or {}):
                        failures.append("%s.entity: entity %r is not declared "
                                        "by the gameplay blueprint" % (where, entity_id))
                        continue
                    if entity_id == boss_entity:
                        failures.append("%s.entity: clear_enemies must not "
                                        "reference the boss entity %r" % (where, boss_entity))
                        continue
                    entries.append({"entity": entity_id, "count": int(count)})
                stages.append({"id": "clear_%d" % clear_index,
                               "type": STAGE_CLEAR_ENEMIES, "entries": entries})
            elif kind == STAGE_DEFEAT_BOSS:
                stages.append({"id": "boss", "type": STAGE_DEFEAT_BOSS,
                               "entity": boss_entity})
            elif kind == STAGE_COMPLETE_LEVEL:
                stages.append({"id": "complete", "type": STAGE_COMPLETE_LEVEL})
            else:
                failures.append("stages: unsupported stage spec %r" % (spec,))

    if failures:
        return {"ok": False, "level": None, "warnings": warnings, "failures": failures}

    boss_block = {"entity": boss_entity,
                  "instance": instance_names[boss_entity],
                  "spawn": BOSS_SPAWN_EXISTING}
    exit_block = {"unlock_when": EXIT_NEVER}
    victory_block = {"condition": VICTORY_BOSS_DEFEATED}
    if stages:
        if stages[-1].get("type") != STAGE_COMPLETE_LEVEL:
            exit_block = {"unlock_when": EXIT_BOSS_DEFEATED}
    level = {
        "schema": {"id": LEVEL_SCHEMA_ID, "version": LEVEL_SCHEMA_VERSION},
        "level": {"id": resolved_level_id, "arena_scene": resolved_arena},
        "mode": MODE_BOSS,
        "entities": entities,
        "boss": boss_block,
        "exit": exit_block,
        "victory": victory_block,
    }
    if stages:
        level["stages"] = stages
    failures.extend(validate_level(level, project_root)["failures"])
    return {"ok": not failures, "level": level if not failures else None,
            "failures": failures, "warnings": warnings}


def write_level(level: dict, path) -> str:
    """写出关卡配置（JSON，UTF-8，LF，缩进 2，末尾换行）。校验失败时调用方不得调用本函数。"""
    path = Path(path)
    if path.parent and not path.parent.is_dir():
        path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(level, ensure_ascii=False, indent=2) + "\n"
    with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return str(path)


def level_summary(level: dict) -> str:
    if level.get("mode") == MODE_BOSS:
        boss = level.get("boss") or {}
        stages = level.get("stages") or []
        stage_text = ""
        if stages:
            stage_text = ", stages=[%s]" % ", ".join(
                "%s:%s" % (stage.get("id"), stage.get("type")) for stage in stages)
        return ("level %s: boss mode (entity=%s, instance=%s, spawn=%s), arena=%s, "
                "exit=%s, victory=%s%s"
                % (level.get("level", {}).get("id"), boss.get("entity"),
                   boss.get("instance"), boss.get("spawn"),
                   level.get("level", {}).get("arena_scene"),
                   (level.get("exit") or {}).get("unlock_when"),
                   (level.get("victory") or {}).get("condition"), stage_text))
    waves = level.get("waves") or []
    total = sum(int(entry.get("count", 0))
                for wave in waves for entry in (wave.get("entries") or []))
    return ("level %s: %d wave(s), %d enem%s, exit=%s, victory=%s"
            % (level.get("level", {}).get("id"), len(waves), total,
               "y" if total == 1 else "ies",
               (level.get("exit") or {}).get("unlock_when"),
               (level.get("victory") or {}).get("condition")))


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Build or validate a level orchestration config.")
    parser.add_argument("gameplay", nargs="?", help="Gameplay Blueprint YAML (build mode)")
    parser.add_argument("--out", help="output path for the level config, e.g. Levels/<id>.json")
    parser.add_argument("--check", help="validate an existing level config and exit")
    parser.add_argument("--level-id", help="override level.id (default: gameplay.gameplay.id)")
    parser.add_argument("--mode", default=MODE_WAVES, choices=SUPPORTED_MODES,
                        help="orchestration mode (default: %s)" % MODE_WAVES)
    parser.add_argument("--boss", metavar="ENTITY",
                        help="boss entity id (required for --mode boss; must be a plan instance)")
    parser.add_argument("--plan", help="composition_plan yaml (required for --mode boss)")
    parser.add_argument("--stage", action="append", default=[], metavar="SPEC",
                        help="multi-stage boss spec in order: 'clear:entity:count[,entity:count]', "
                             "'boss', 'complete' (repeatable; default = single-stage boss)")
    parser.add_argument("--arena-scene", default=None,
                        help="arena/host scene that consumes this config "
                             "(default waves: %s; default boss: res://Scenes/<host>.tscn)"
                             % DEFAULT_ARENA_SCENE)
    parser.add_argument("--waves", type=int, default=DEFAULT_WAVE_COUNT,
                        help="generated wave count (default: %d)" % DEFAULT_WAVE_COUNT)
    parser.add_argument("--wave-size", type=int, default=DEFAULT_WAVE_SIZE,
                        help="wave 1 enemy count; wave i = wave_size + i (default: %d)" % DEFAULT_WAVE_SIZE)
    parser.add_argument("--wave", action="append", default=[],
                        help='explicit wave: "entity:count[,entity:count]" (repeatable; replaces default waves)')
    parser.add_argument("--survival-duration", type=float, default=None,
                        help="holdout mode: survival seconds before victory (default: %s)"
                             % DEFAULT_HOLDOUT_SURVIVAL_DURATION)
    parser.add_argument("--spawn-interval", type=float, default=None,
                        help="holdout mode: spawn interval seconds (default: %s)"
                             % DEFAULT_HOLDOUT_SPAWN_INTERVAL)
    parser.add_argument("--spawn-delay", type=float, default=None,
                        help="holdout mode: spawn delay seconds (default: %s)"
                             % DEFAULT_HOLDOUT_SPAWN_DELAY)
    parser.add_argument("--max-alive", type=int, default=None,
                        help="holdout mode: max alive enemies (default: %d)"
                             % DEFAULT_HOLDOUT_MAX_ALIVE)
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(argv)

    project_root = Path(args.project_root).resolve()

    if args.check:
        path = Path(args.check)
        if not path.is_file():
            print("FAIL: level config not found: %s" % path, file=sys.stderr)
            return 2
        try:
            level = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print("FAIL: cannot read level config %s: %s" % (path, exc), file=sys.stderr)
            return 2
        plan = None
        if args.plan:
            plan_path = Path(args.plan)
            if not plan_path.is_file():
                print("FAIL: composition plan not found: %s" % args.plan, file=sys.stderr)
                return 2
            try:
                plan = yaml.safe_load(plan_path.read_text(encoding="utf-8")) or {}
            except (OSError, yaml.YAMLError) as exc:
                print("FAIL: cannot read composition plan %s: %s" % (args.plan, exc),
                      file=sys.stderr)
                return 2
        report = validate_level(level, project_root, plan=plan)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print("Level Orchestration Check")
            print("  Config: %s" % path)
            print("  Checked items: %d" % report["checked"])
            if report["level_id"]:
                print("  Level: %s" % report["level_id"])
        if report["failures"]:
            for failure in report["failures"]:
                print("FAIL: %s" % failure, file=sys.stderr)
            return 1
        if not args.json:
            print("PASS: level orchestration valid")
        return 0

    if not args.gameplay:
        print("FAIL: needs a Gameplay Blueprint path or --check", file=sys.stderr)
        return 2
    if args.stage and args.mode != MODE_BOSS:
        print("FAIL: --stage is only valid for --mode boss", file=sys.stderr)
        return 2
    blueprint_path = Path(args.gameplay)
    if not blueprint_path.is_file():
        print("FAIL: gameplay blueprint not found: %s" % blueprint_path, file=sys.stderr)
        return 2
    try:
        gameplay = yaml.safe_load(blueprint_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        print("FAIL: cannot read gameplay blueprint %s: %s" % (blueprint_path, exc), file=sys.stderr)
        return 2
    if not isinstance(gameplay, dict):
        print("FAIL: gameplay blueprint must be a YAML mapping: %s" % blueprint_path, file=sys.stderr)
        return 2

    if args.mode == MODE_BOSS:
        if not args.plan:
            print("FAIL: --mode boss requires --plan <composition_plan.yaml>", file=sys.stderr)
            return 2
        if args.wave:
            print("FAIL: --wave is not valid for --mode boss (a boss level has no waves)",
                  file=sys.stderr)
            return 2
        plan_path = Path(args.plan)
        if not plan_path.is_file():
            print("FAIL: composition plan not found: %s" % args.plan, file=sys.stderr)
            return 2
        try:
            plan = yaml.safe_load(plan_path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            print("FAIL: cannot read composition plan %s: %s" % (args.plan, exc),
                  file=sys.stderr)
            return 2
        try:
            stage_specs = [parse_stage_spec(text) for text in args.stage] or None
        except ValueError as exc:
            print("FAIL: %s" % exc, file=sys.stderr)
            return 2
        result = build_boss_level(gameplay, plan, project_root=project_root,
                                  level_id=args.level_id, boss_entity=args.boss,
                                  arena_scene=args.arena_scene, stage_specs=stage_specs)
    elif args.mode == MODE_HOLDOUT:
        if args.wave or args.waves != DEFAULT_WAVE_COUNT or args.wave_size != DEFAULT_WAVE_SIZE:
            print("FAIL: --wave/--waves/--wave-size are waves-mode only "
                  "(holdout uses --survival-duration/--spawn-interval/--max-alive)",
                  file=sys.stderr)
            return 2
        result = build_holdout_level(
            gameplay, project_root=project_root, level_id=args.level_id,
            arena_scene=args.arena_scene, survival_duration=args.survival_duration,
            spawn_interval=args.spawn_interval, spawn_delay=args.spawn_delay,
            max_alive=args.max_alive)
    else:
        try:
            wave_specs = [parse_wave_spec(text) for text in args.wave] or None
        except ValueError as exc:
            print("FAIL: %s" % exc, file=sys.stderr)
            return 2
        result = build_level(gameplay, project_root=project_root, level_id=args.level_id,
                             arena_scene=args.arena_scene or DEFAULT_ARENA_SCENE,
                             wave_count=args.waves, wave_size=args.wave_size,
                             wave_specs=wave_specs)
    if args.json:
        print(json.dumps({"ok": result["ok"], "failures": result["failures"],
                          "level": result["level"]}, ensure_ascii=False, indent=2))
    if not result["ok"]:
        for failure in result["failures"]:
            print("FAIL: %s" % failure, file=sys.stderr)
        return 1
    level = result["level"]
    if not args.out:
        print("Level Orchestration Plan (no --out: nothing written)")
        print("  " + level_summary(level))
        return 0
    written = write_level(level, args.out)
    print("Level Orchestration")
    print("  Gameplay Blueprint: %s" % blueprint_path)
    print("  " + level_summary(level))
    print("Generated: %s" % written)
    report = validate_level(level, project_root)
    print("Validation: %s" % ("PASS" if not report["failures"] else "FAIL"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
