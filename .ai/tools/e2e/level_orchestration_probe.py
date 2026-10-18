#!/usr/bin/env python3
"""Generated Level Orchestration Probe（Phase 1.13）。

在**真实 Godot 运行时**验证「生成链路产出的关卡编排配置」是否真的驱动了关卡行为：

    被测配置 = `gameplay_planner/level_planner.py` 为某个 Gameplay Blueprint 生成的
              `Levels/<level_id>.json`（其中引用的实体场景是 Scene Composer 的生成物）；
    宿主场景 = 项目真实游戏场景 `res://Scenes/TimedCombatArena.tscn`（承载既有胜负逻辑）；
    观测对象 = 运行时状态：生成数量 / 波次推进 / 出口门 / 胜负状态 / 胜负事件次数。

断言（编号对应任务书）：

    L7  生成数量来自**配置**（Python 侧先从同一份配置解析期望数量，再交给探针断言运行时一致）
    L8  首波按配置生成：敌人都来自**配置声明的实体场景集合**，并注册进既有管理链路
        （`Health` + `target_path`）；聚焦生成物（--focus-scene）被实际生成的次数单独报告
    L9  首波未清除时第二波不生成
    L10 首波清除后第二波按配置生成（数量来自配置），且只推进一次
    L11 仍有必需敌人存活时出口保持关闭
    L12 全部必需波次清除后出口开启
    L13 玩家真实输入走进出口区 → Completed
    L14 胜负事件恰好一次
    Q   受控负向：无效配置（count=0）必须被运行时拒绝（探针失败 + 可定位诊断，零生成）

    python .ai/tools/e2e/level_orchestration_probe.py res://Levels/E2eProbeLevel.json \
        --focus-scene res://Scenes/E2eProbeEnemy.tscn
    python .ai/tools/e2e/level_orchestration_probe.py <无效配置> --expect invalid

机制与其它探针同构：渲染临时 GDScript（Tests/e2e_level_orchestration_probe.gd；**不带 test_
前缀**，即使清理失败也不会被 run_tests.py 当作长期套件）→ 项目真实 Godot `-s` 运行 →
解析 `LEVEL:` 机读行 → finally 删除脚本。

退出码: 0 = 断言通过；1 = 断言失败（含前置条件不成立）；2 = 输入 / 环境错误。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

_DOTAI = Path(__file__).resolve().parents[2]              # <project>/.ai
PROJECT_ROOT = _DOTAI.parent                              # <project>

DEFAULT_ARENA = "res://Scenes/TimedCombatArena.tscn"

PROBE_SCRIPT_REL = "Tests/e2e_level_orchestration_probe.gd"
PROBE_SCRIPT_NAME = "e2e_level_orchestration_probe.gd"

EXPECT_VALID = "valid"        # 正向：配置必须被接受并驱动完整关卡流程
EXPECT_INVALID = "invalid"    # 受控负向：配置必须被运行时拒绝（不生成任何敌人）

# 模拟参数（物理帧 60 Hz）
OTHER_DISTANCE = 600.0         # 攻击目标隔离距离：其余敌人移远，保证攻击命中首波首个敌人
ATTACK_BUDGET_PER_ENEMY = 12   # 单个敌人用真实攻击路径击杀的攻击预算
EXIT_BUDGET = 300              # 玩家走向出口区的物理帧上限
EXIT_START = (560.0, 0.0)      # 出口门前起跑点（与既有竞技场测试一致）

PROBE_SOURCE = '''extends SceneTree
## 由 .ai/tools/e2e/level_orchestration_probe.py 生成——关卡编排探针（Phase 1.13）。
## 不要手工编辑；重新生成请运行:
##   python .ai/tools/e2e/level_orchestration_probe.py {{LEVEL}}
##
## 用法：godot --headless --path . -s res://Tests/{{PROBE_NAME}}
## 断言的是运行时状态（生成数量 / 波次 / 出口门 / 胜负），不是「配置文件是否存在」。
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

const ARENA_SCENE := "{{ARENA}}"
const LEVEL_CONFIG := "{{LEVEL}}"
const ENTITY_SCENES := {{ENTITY_SCENES}}
const FOCUS_SCENE := "{{FOCUS_SCENE}}"
const EXPECT := "{{EXPECT}}"
const EXPECT_VALID := "{{EXPECT_VALID}}"
const WAVE_COUNTS := {{WAVE_COUNTS}}
const OTHER_DISTANCE := {{OTHER_DISTANCE}}
const ATTACK_BUDGET := {{ATTACK_BUDGET}}
const EXIT_BUDGET := {{EXIT_BUDGET}}
const EXIT_START := Vector2({{EXIT_X}}, {{EXIT_Y}})
const TRACE_PATH := "{{TRACE_PATH}}"
const ATTACK_ACTION := "p1_attack"
const MOVE_ACTION := "move_right"
const TRUE := 1
const FALSE := 0

var _failures: PackedStringArray = []
var _finish_events: Array = []
var _focus_seen: Dictionary = {}


func _initialize() -> void:
	var packed: PackedScene = load(ARENA_SCENE)
	if packed == null:
		_fail("Scene Load: 无法加载宿主场景 %s" % ARENA_SCENE)
		_report()
		return
	# 关卡配置必须在 _ready 之前设置：由配置（而不是场景内数据）决定生成与胜负规则
	var arena: Node2D = packed.instantiate()
	arena.level_config_path = LEVEL_CONFIG
	arena.arena_finished.connect(_on_finished)
	root.add_child(arena)
	await physics_frame

	var config_errors: int = arena.get_config_errors().size()
	var waves: int = arena.waves.size()
	var spawned_wave1: int = arena.alive_count

	if EXPECT != EXPECT_VALID:
		# ---- Q：受控负向 —— 无效配置必须被拒绝 ----
		if config_errors == 0:
			_fail("Q: 无效配置应被运行时拒绝，实际被接受（waves=%d）" % waves)
		elif not String(arena.get_config_errors()[0]).contains("count"):
			_fail("Q: 配置错误信息应可定位到字段，实际 %s" % arena.get_config_errors()[0])
		if arena.state != arena.State.Failed:
			_fail("Q: 配置无效时应拒绝开始（state=Failed），实际 %d" % int(arena.state))
		if spawned_wave1 != 0 or not _live_enemies(arena).is_empty():
			_fail("Q: 配置无效时不应生成任何敌人（alive_count=%d）" % spawned_wave1)
		if waves != 0:
			_fail("Q: 配置无效时不得静默回退到场景内数据（waves=%d）" % waves)
		print("LEVEL: config_errors=%d waves=%d spawned_wave1=%d state=%d"
			% [config_errors, waves, spawned_wave1, int(arena.state)])
		_report()
		return

	# ---- L7：生成数量来自配置（期望数量由 Python 侧从同一配置解析后传入）----
	if config_errors != 0:
		_fail("L7: 配置应被运行时接受，实际错误 %s" % arena.get_config_errors())
	if waves != WAVE_COUNTS.size():
		_fail("L7: 配置声明 %d 波，运行时读到 %d 波" % [WAVE_COUNTS.size(), waves])
	if spawned_wave1 != WAVE_COUNTS[0]:
		_fail("L7: 第一波应按配置生成 %d 个敌人，实际 %d" % [WAVE_COUNTS[0], spawned_wave1])

	# ---- L8：首波敌人来自配置声明的实体场景，并注册进既有管理链路 ----
	var scene_match := _check_spawned(arena)
	var wave1: Array[Node] = _live_enemies(arena)
	if wave1.size() != WAVE_COUNTS[0]:
		_fail("L8: 第一波应生成 %d 个敌人节点，实际 %d" % [WAVE_COUNTS[0], wave1.size()])

	# ---- L9：首波未清除时第二波不得生成 ----
	var player: CharacterBody2D = arena.get_node("Player")
	if waves > 1 and (arena.wave_index != 0 or _live_enemies(arena).size() != WAVE_COUNTS[0]):
		_fail("L9: 首波未清除时不应生成第二波（wave_index=%d 存活 %d）"
			% [arena.wave_index, _live_enemies(arena).size()])

	# ---- 清空首波：首个用真实攻击输入路径（先隔离其余敌人保证命中），其余用既有伤害接口 ----
	for i in range(1, wave1.size()):
		var other: Node = wave1[i]
		if is_instance_valid(other):
			other.global_position = player.global_position - Vector2(OTHER_DISTANCE + 100.0 * i, 0)
	await physics_frame
	var index_after_wave1 := -1
	var alive_after_wave1 := -1
	for i in wave1.size():
		var enemy: Node = wave1[i]
		if not is_instance_valid(enemy):
			continue
		if i == 0:
			await _kill_by_attack(enemy)
			if not _is_defeated(enemy):
				_fail("L10: 真实攻击路径应在 %d 次攻击内击败首波目标" % ATTACK_BUDGET)
		else:
			enemy.get_node("Health").take_damage(9999)
		await process_frame
		index_after_wave1 = arena.wave_index
		alive_after_wave1 = arena.alive_count
		if i < wave1.size() - 1 and arena.wave_index != 0:
			_fail("L9: 首波仍有敌人存活时不应推进波次，实际 index %d" % arena.wave_index)

	# ---- L10：首波清除 → 第二波按配置生成（只推进一次）----
	if waves > 1:
		if arena.wave_index != 1:
			_fail("L10: 首波清空后应进入第二波（index 1），实际 %d" % arena.wave_index)
		if arena.alive_count != WAVE_COUNTS[1]:
			_fail("L10: 第二波应按配置生成 %d 个敌人，实际 %d"
				% [WAVE_COUNTS[1], arena.alive_count])
		scene_match = scene_match and _check_spawned(arena)
		if _live_enemies(arena).size() != WAVE_COUNTS[1]:
			_fail("L10: 第二波应生成 %d 个敌人节点，实际 %d"
				% [WAVE_COUNTS[1], _live_enemies(arena).size()])

	# ---- L11：仍有必需敌人存活时出口保持关闭 ----
	var door: StaticBody2D = arena.get_node("Mechanism/ExitDoor")
	var door_open_with_survivor := FALSE
	if not _live_enemies(arena).is_empty() and door.is_open():
		door_open_with_survivor = TRUE
		_fail("L11: 仍有敌人存活时出口不应打开")

	# ---- L12：逐波清空全部必需波次（清完一波会生成下一波，直到无存活敌人）→ 出口开启 ----
	var clear_budget: int = WAVE_COUNTS.size() + 2
	while not _live_enemies(arena).is_empty() and clear_budget > 0:
		clear_budget -= 1
		for enemy in _live_enemies(arena).duplicate():
			if is_instance_valid(enemy):
				enemy.get_node("Health").take_damage(9999)
		await process_frame
		if not _live_enemies(arena).is_empty() and door.is_open():
			door_open_with_survivor = TRUE
			_fail("L12: 仍有敌人存活时出口不应打开")
	var door_open_after_all := TRUE if door.is_open() else FALSE
	if not door_open_after_all:
		_fail("L12: 全部必需波次清空后出口应开启（存活 %d，index %d）"
			% [arena.alive_count, arena.wave_index])
	if arena.state != arena.State.Playing:
		_fail("L12: 出口开启但玩家未进出口区时应仍为 Playing，实际 %d" % int(arena.state))

	# ---- L13/L14：玩家真实输入走进出口区 → Completed，胜负事件恰好一次 ----
	player.global_position = EXIT_START
	await physics_frame
	Input.action_press(MOVE_ACTION)
	for _i: int in EXIT_BUDGET:
		if arena.state == arena.State.Completed:
			break
		await physics_frame
	Input.action_release(MOVE_ACTION)
	if arena.state != arena.State.Completed:
		_fail("L13: 玩家走进出口区后应进入 Completed，实际 %d（x=%.1f）"
			% [int(arena.state), player.global_position.x])
	if _finish_events != [true]:
		_fail("L14: 胜负事件应恰好发出一次且 success=true，实际 %s" % str(_finish_events))

	# Phase 1.24：真实运行结束后导出编排诊断 trace（黄金基线比较的输入）。
	# 导出失败按断言失败处理，绝不静默。
	if not arena.export_trace_json(TRACE_PATH):
		_fail("L-trace: 导出编排诊断 trace 失败")

	print("LEVEL: config_errors=%d waves=%d wave1_count=%d wave2_count=%d spawned_wave1=%d "
		% [config_errors, waves, WAVE_COUNTS[0],
		   WAVE_COUNTS[1] if WAVE_COUNTS.size() > 1 else 0, spawned_wave1]
		+ "index_after_wave1=%d alive_after_wave1=%d door_open_with_survivor=%d "
		% [index_after_wave1, alive_after_wave1, door_open_with_survivor]
		+ "door_open_after_all=%d state_after_exit=%d finish_events=%d "
		% [door_open_after_all, int(arena.state), _finish_events.size()]
		+ "entity_scene_match=%d declared_scenes=%d focus_hits=%d"
		% [TRUE if scene_match else FALSE, ENTITY_SCENES.size(), _focus_seen.size()])
	_report()


## 校验当前存活敌人是否都来自配置声明的实体场景集合，并累计聚焦场景的实际生成次数
func _check_spawned(arena: Node) -> bool:
	var matches := true
	for enemy in _live_enemies(arena):
		var scene := String(enemy.scene_file_path)
		if not ENTITY_SCENES.has(scene):
			matches = false
			_fail("L8: 生成敌人来源场景 %s 不在配置声明的实体场景集合 %s 中"
				% [scene, str(ENTITY_SCENES)])
		if not FOCUS_SCENE.is_empty() and scene == FOCUS_SCENE:
			_focus_seen[enemy.get_instance_id()] = true
	return matches


func _live_enemies(arena: Node) -> Array[Node]:
	var result: Array[Node] = []
	var entities := arena.get_node_or_null("Entities")
	if entities == null:
		return result
	for child in entities.get_children():
		if child.is_in_group("enemies") and is_instance_valid(child) \
				and not child.is_queued_for_deletion():
			result.append(child)
	return result


## 注意：参数不能标 Node 类型 —— 死亡会驱动 queue_free，已释放实例传进类型化参数会报
## "previously freed is not a subclass of Node"（同理内部也不再触碰已释放节点）。
func _is_defeated(enemy) -> bool:
	if not is_instance_valid(enemy):
		return true
	var health := enemy.get_node_or_null("Health") as Health
	return health == null or health.is_dead()


func _kill_by_attack(enemy) -> void:
	for _i: int in ATTACK_BUDGET:
		Input.action_press(ATTACK_ACTION)
		await physics_frame
		await physics_frame
		Input.action_release(ATTACK_ACTION)
		await physics_frame
		if _is_defeated(enemy):
			return


func _on_finished(success: bool) -> void:
	_finish_events.append(success)


func _fail(message: String) -> void:
	_failures.append(message)


func _report() -> void:
	if _failures.is_empty():
		print("PASS: 关卡编排配置驱动验证通过 (%s)" % LEVEL_CONFIG)
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
'''


@dataclass
class LevelProbeResult:
    """一次关卡编排探针运行的结果（原始输出 + 解析出的度量值）。"""

    ok: bool
    exit_code: int
    level: str
    arena: str
    expect: str
    wave_counts: list = field(default_factory=list)
    declared_scenes: list = field(default_factory=list)
    focus_scene: str = ""
    output: str = ""
    metrics: dict = field(default_factory=dict)
    script_removed: bool = False
    trace_path: str = ""
    trace_document: dict = field(default_factory=dict)   # 真实导出的编排诊断 trace（读取后已清理）
    trace_removed: bool = False

    @property
    def failure_messages(self) -> list:
        return [line.strip() for line in self.output.splitlines()
                if line.strip().startswith("FAIL:")]


def find_godot(project_root: Path = PROJECT_ROOT):
    """与 .ai/tools/run_tests.py 一致的二进制查找（相邻目录 / PATH）。"""
    for candidate in (project_root.parent / "Godot_v4.7-stable_win64_console.exe",
                      project_root.parent / "Godot_v4.7-stable_win64.exe"):
        if candidate.is_file():
            return candidate
    for name in ("godot", "godot4"):
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


def read_level(path: Path) -> dict:
    """读取关卡配置（调用方负责处理读取失败）。"""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def wave_counts_of(level: dict) -> list:
    """从配置解析每波敌人数量（L7 的期望值来源：同一份配置，Python 侧独立解析）。"""
    return [sum(int(entry.get("count", 0)) for entry in (wave.get("entries") or []))
            for wave in (level.get("waves") or [])]


def declared_scenes_of(level: dict) -> list:
    """配置声明的全部实体场景（生成物来源校验用）。"""
    entities = level.get("entities") or {}
    scenes = []
    for entity_id in sorted(entities):
        scene = (entities[entity_id] or {}).get("scene")
        if scene and scene not in scenes:
            scenes.append(str(scene))
    return scenes


def render_probe_source(level_res: str, wave_counts: list, declared_scenes: list,
                        focus_scene: str = "", expect: str = EXPECT_VALID,
                        arena_res: str = DEFAULT_ARENA,
                        trace_res: str = "res://Tests/e2e_level_trace.json") -> str:
    """渲染探针 GDScript（{{TOKEN}} 字面替换，模板正文的 % 格式化原样保留）。"""
    if expect not in (EXPECT_VALID, EXPECT_INVALID):
        raise ValueError("expectation must be %r or %r, got %r"
                         % (EXPECT_VALID, EXPECT_INVALID, expect))
    counts_literal = "[%s]" % ", ".join(str(int(value)) for value in wave_counts)
    scenes_literal = "[%s]" % ", ".join('"%s"' % scene for scene in declared_scenes)
    replacements = {
        "{{ARENA}}": arena_res,
        "{{LEVEL}}": level_res,
        "{{ENTITY_SCENES}}": scenes_literal,
        "{{FOCUS_SCENE}}": focus_scene or "",
        "{{EXPECT_VALID}}": EXPECT_VALID,
        "{{TRACE_PATH}}": trace_res,
        "{{EXPECT}}": expect,
        "{{WAVE_COUNTS}}": counts_literal,
        "{{PROBE_NAME}}": PROBE_SCRIPT_NAME,
        "{{OTHER_DISTANCE}}": repr(float(OTHER_DISTANCE)),
        "{{ATTACK_BUDGET}}": str(ATTACK_BUDGET_PER_ENEMY),
        "{{EXIT_BUDGET}}": str(EXIT_BUDGET),
        "{{EXIT_X}}": repr(float(EXIT_START[0])),
        "{{EXIT_Y}}": repr(float(EXIT_START[1])),
    }
    source = PROBE_SOURCE
    # {{EXPECT}} 与 {{EXPECT_VALID}} 有前缀关系：先替换长占位符，避免互相吃掉。
    for token in sorted(replacements, key=len, reverse=True):
        source = source.replace(token, replacements[token])
    if "{{" in source or "}}" in source:                   # pragma: no cover - 防占位符拼写错误
        raise RuntimeError("unresolved probe placeholder remains in rendered script")
    return source


def parse_metrics(output: str) -> dict:
    """从 LEVEL: 行解析度量值（供调用方独立断言）。"""
    metrics: dict = {}
    for line in output.splitlines():
        if not line.startswith("LEVEL:"):
            continue
        for key, value in re.findall(r"(\w+)=([-\d.]+)", line):
            try:
                metrics[key] = float(value)
            except ValueError:                              # pragma: no cover - 防御
                continue
    return metrics


def run_level_probe(level_res: str, project_root: Path = PROJECT_ROOT, godot=None,
                    expect: str = EXPECT_VALID, focus_scene: str = "",
                    arena_res: str = DEFAULT_ARENA, timeout: int = 300) -> LevelProbeResult:
    """在真实 Godot 中运行关卡编排探针。输入/环境错误抛 RuntimeError（调用方转 exit 2）。"""
    project_root = Path(project_root)
    level_path = project_root / level_res.replace("res://", "")
    if not level_path.is_file():
        raise RuntimeError("level config not found in project: %s (%s)" % (level_res, level_path))
    arena_path = project_root / arena_res.replace("res://", "")
    if not arena_path.is_file():
        raise RuntimeError("arena game scene not found in project: %s" % arena_res)
    try:
        level = read_level(level_path)
    except (OSError, ValueError) as exc:
        raise RuntimeError("cannot read level config %s: %s" % (level_res, exc))
    wave_counts = wave_counts_of(level) if isinstance(level, dict) else []
    declared_scenes = declared_scenes_of(level) if isinstance(level, dict) else []
    if focus_scene and focus_scene not in declared_scenes:
        raise RuntimeError("focus scene %s is not declared by %s (declared: %s)"
                           % (focus_scene, level_res, declared_scenes))
    godot = Path(godot) if godot else find_godot(project_root)
    if godot is None or not Path(godot).is_file():
        raise RuntimeError("godot executable not found; set GODOT_BIN or add it to PATH")

    script_path = project_root / PROBE_SCRIPT_REL
    script_path.parent.mkdir(parents=True, exist_ok=True)
    trace_res = "res://Tests/e2e_level_trace.json"
    script_path.write_text(render_probe_source(level_res, wave_counts, declared_scenes,
                                               focus_scene, expect, arena_res,
                                               trace_res),
                           encoding="utf-8", newline="\n")
    try:
        proc = subprocess.run(
            [str(godot), "--headless", "--path", str(project_root),
             "-s", "res://" + PROBE_SCRIPT_REL.replace(os.sep, "/")],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(project_root), stdin=subprocess.DEVNULL, timeout=timeout)
        output = (proc.stdout or "") + (proc.stderr or "")
        exit_code = proc.returncode
    finally:
        removed = True
        try:
            script_path.unlink()
        except OSError:                                     # pragma: no cover - 清理失败要报告
            removed = False
    trace_document: dict = {}
    trace_removed = False
    trace_disk = project_root / "Tests" / "e2e_level_trace.json"
    if trace_disk.is_file():
        try:
            trace_document = json.loads(trace_disk.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:                # pragma: no cover - 防御
            trace_document = {"parse_error": str(exc)}
        try:                                                # 读取后即清理（工具自清理）
            trace_disk.unlink()
            Path(str(trace_disk) + ".uid").unlink(missing_ok=True)
            trace_removed = True
        except OSError:                                     # pragma: no cover
            trace_removed = False
    return LevelProbeResult(ok=(exit_code == 0 and "PASS:" in output),
                            exit_code=exit_code, level=level_res, arena=arena_res,
                            expect=expect, wave_counts=wave_counts,
                            declared_scenes=declared_scenes, focus_scene=focus_scene,
                            output=output, metrics=parse_metrics(output), script_removed=removed,
                            trace_path=str(trace_disk),
                            trace_document=trace_document, trace_removed=trace_removed)


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Run a real-Godot level orchestration probe against a generated level config.")
    parser.add_argument("level", help="res:// path of the level config (e.g. res://Levels/<id>.json)")
    parser.add_argument("--arena", default=DEFAULT_ARENA,
                        help="res:// path of the host arena scene (default: %s)" % DEFAULT_ARENA)
    parser.add_argument("--focus-scene", default="",
                        help="res:// entity scene whose spawns are counted separately"
                             " (must be declared by the level config)")
    parser.add_argument("--expect", default=EXPECT_VALID, choices=(EXPECT_VALID, EXPECT_INVALID),
                        help="valid (default) or invalid for a controlled negative")
    parser.add_argument("--project", default=str(PROJECT_ROOT))
    parser.add_argument("--show-output", action="store_true", help="print raw Godot output")
    args = parser.parse_args(argv)

    try:
        result = run_level_probe(args.level, project_root=Path(args.project).resolve(),
                                 expect=args.expect, focus_scene=args.focus_scene,
                                 arena_res=args.arena)
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        print("FAIL: %s" % exc, file=sys.stderr)
        return 2

    print("Level Orchestration Probe")
    print("Level: %s" % result.level)
    print("Arena: %s" % result.arena)
    print("Expect: %s (waves=%s, scenes=%s, focus=%s)"
          % (result.expect, result.wave_counts, result.declared_scenes,
             result.focus_scene or "<none>"))
    if args.show_output:
        print(result.output)
    print("Result: status=%s exit_code=%d %s"
          % ("PASS" if result.ok else "FAIL", result.exit_code,
             " ".join("%s=%s" % (key, value) for key, value in sorted(result.metrics.items()))))
    for failure in result.failure_messages:
        print("  " + failure, file=sys.stderr)
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
