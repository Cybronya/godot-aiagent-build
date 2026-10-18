#!/usr/bin/env python3
"""Generated Entity Death & Victory Probe（Phase 1.12）。

在**真实 Godot 运行时**验证「生成链路产出的实体场景」能否走完项目既有的
死亡与胜负闭环 —— 被测对象放在**项目真实游戏场景** `res://Scenes/TimedCombatArena.tscn`
里（该场景承载既有胜负逻辑：全部必需敌人死亡 → 打开出口门 → 玩家进出口区 → 完成），
伤害通过**真实玩家攻击输入路径**（空格攻击 → AttackTrigger → Health.take_damage）结算，
断言的是运行时状态变化（生命值 / 死亡事件次数 / 存活计数 / 出口门 / 胜负状态），
不是「节点、信号或脚本是否声明存在」。

    python .ai/tools/e2e/death_victory_probe.py res://Scenes/E2eProbeEnemy.tscn
    python .ai/tools/e2e/death_victory_probe.py res://Scenes/Enemy.tscn     # 手写实体等价性
    python .ai/tools/e2e/death_victory_probe.py <不死变异体> --expect survive

机制（与行为探针同构，不引入第二套验证体系）：
    1. 由本模块渲染一段临时 GDScript（Tests/e2e_death_victory_probe.gd；**不带 test_ 前缀**，
       因此即使清理失败也不会被 run_tests.py 当作长期套件执行）；
    2. 用项目真实 Godot 以 `-s res://...` 运行它；
    3. 断言四段行为：
       a. 死亡前置：未致死伤害不改变存活计数、不开门、不改变状态（N1）；
       b. 死亡主行为：攻击输入把敌人体力打到 0 → Health.died 恰好一次 → 存活计数恰好减一
          → 实体按既有规则退出战斗（现实删除），且重复攻击不重复处理（D1/D2/N2）；
       c. 胜利条件：仍有必需敌人存活时不开门、不提前胜利（V2）；最后一个必需敌人死亡后
          出口门由场景自身逻辑打开（V1），玩家真实输入走进出口区后状态变为 Completed、
          arena_finished 恰好发出一次；
       d. 环境接口：竞技场的 AttackTrigger 必须配置 target_group（真实攻击路径解析目标），
          被测实体根必须接收既有管理链路赋值的 target_path（Phase 1.11：实体根即 motion 组件）。
    4. 返回退出码、原始输出与从 `DEATH:` / `VICTORY:` 行解析出的度量值；
    5. 无论成败都在 finally 中删除临时脚本。

`--expect die`（默认）用于正向；`--expect survive` 用于**受控负向**：同一物理配置下
（同场景、同攻击预算），把敌人改为不可能在预算内被杀死的变异体后，探针必须观察到
「敌人仍存活、存活计数不变、出口门始终关闭、胜负状态始终 Playing、无 arena_finished 事件」，
而同一变异体在 `--expect die` 下必须失败 —— 证明胜利断言依赖真实死亡，而不是恒真。

退出码: 0 = 断言全部通过；1 = 断言失败（含前置条件不成立）；
        2 = 输入 / 环境错误（场景不存在、Godot 缺失）。
"""

from __future__ import annotations

import argparse
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
# 手写敌人实体（既有死亡语义的对照物：同一探针必须得到同样结论）
DEFAULT_REFERENCE_ENEMY = "res://Scenes/Enemy.tscn"

# 探针脚本位置（非 test_ 前缀：不会被统一运行器当作长期套件发现）
PROBE_SCRIPT_REL = "Tests/e2e_death_victory_probe.gd"
PROBE_SCRIPT_NAME = "e2e_death_victory_probe.gd"

# 期望：die = 攻击预算内必须死亡并走到胜利；survive = 受控负向（不死的变异体）
EXPECT_DIE = "die"
EXPECT_SURVIVE = "survive"

# 模拟参数（物理帧 60 Hz）
ARENA_ENEMY_COUNT = 2      # 单波 2 个必需敌人：保证「未清场不得提前胜利」可观测
ARENA_DURATION = 60.0      # 波次倒计时：远大于测试窗口，避免超时失败干扰断言
VICTIM_DISTANCE = 140.0    # 受击目标与玩家的间距（远大于接触重叠范围 → 攻击不加接触伤害）
OTHER_DISTANCE = 600.0     # 另一个必需敌人的间距（确保攻击始终命中受击目标）
ATTACK_BUDGET = 12         # 攻击预算（damage=1 / max_health=5 → 5 次即可击杀）
FREE_BUDGET = 240          # 等待死亡实体真正出树的物理帧上限
EXIT_BUDGET = 300          # 玩家走向出口区的物理帧上限
WALK_WINDOW = 150          # 未开门时仍尝试靠近出口的帧数（验证不会提前获胜）
EXIT_START = (560.0, 0.0)  # 出口门前起跑点（与既有竞技场测试一致）

# 模板占位符用 {{TOKEN}} 而非 %-format：模板正文里大量使用 GDScript 的 % 格式化。
PROBE_SOURCE = '''extends SceneTree
## 由 .ai/tools/e2e/death_victory_probe.py 生成——死亡与胜利闭环探针（Phase 1.12）。
## 不要手工编辑；重新生成请运行:
##   python .ai/tools/e2e/death_victory_probe.py {{ENEMY}}
##
## 用法：godot --headless --path . -s res://Tests/{{PROBE_NAME}}
## 被测对象 = 生成链路产出的实体场景；宿主 = 项目真实竞技场场景（既有胜负逻辑）。
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

const ARENA_SCENE := "{{ARENA}}"
const ENEMY_SCENE := "{{ENEMY}}"
const EXPECT := "{{EXPECT}}"
const EXPECT_DIE := "{{EXPECT_DIE}}"
const ENEMY_COUNT := {{ENEMY_COUNT}}
const DURATION := {{DURATION}}
const VICTIM_DISTANCE := {{VICTIM_DISTANCE}}
const OTHER_DISTANCE := {{OTHER_DISTANCE}}
const ATTACK_BUDGET := {{ATTACK_BUDGET}}
const FREE_BUDGET := {{FREE_BUDGET}}
const EXIT_BUDGET := {{EXIT_BUDGET}}
const WALK_WINDOW := {{WALK_WINDOW}}
const EXIT_START := Vector2({{EXIT_X}}, {{EXIT_Y}})
const MOVE_ACTION := "move_right"

var _failures: PackedStringArray = []
var _finish_events: Array = []
var _victim_died_events := 0
var _other_died_events := 0
# 生命值 / 死亡状态镜像：死亡会驱动 queue_free，实体随即出树（previously freed）。
# 这里只通过 Health 组件自身的信号镜像状态，之后不再触碰可能已被释放的节点。
var _victim_dead := false
var _other_dead := false
var _victim_hp := 0
var _other_hp := 0


func _initialize() -> void:
	var arena_packed: PackedScene = load(ARENA_SCENE)
	if arena_packed == null:
		_fail("Scene Load: 无法加载宿主场景 %s" % ARENA_SCENE)
		_report()
		return
	var enemy_packed: PackedScene = load(ENEMY_SCENE)
	if enemy_packed == null:
		_fail("Scene Load: 无法加载被测实体场景 %s" % ENEMY_SCENE)
		_report()
		return

	# 用真实竞技场场景承载胜负逻辑；只把「敌人生成配置」指向被测实体场景
	# —— 与关卡作者在 waves 里配置敌人场景是同一件事，战斗/计数/胜负逻辑一行都不重写。
	# 本探针走竞技场的**手写 waves 通道**（显式清空 level_config_path，否则场景默认的
	# 关卡配置文件会接管生成）；配置驱动路径由 level_orchestration_probe.py 覆盖。
	var arena: Node2D = arena_packed.instantiate()
	arena.level_config_path = ""
	var waves: Array[Dictionary] = [{
		"enemy_scene": enemy_packed,
		"enemy_count": ENEMY_COUNT,
		"duration": DURATION,
	}]
	arena.waves = waves
	arena.arena_finished.connect(_on_arena_finished)
	root.add_child(arena)
	await physics_frame

	# ---- 前置条件 1：真实竞技场把被测实体纳入既有敌人管理链路 ----
	if arena.state != arena.State.Playing:
		_fail("Precondition: 竞技场初始状态应为 Playing，实际 %d" % int(arena.state))
	var player: CharacterBody2D = arena.get_node_or_null("Player")
	var entities: Node2D = arena.get_node_or_null("Entities")
	var door: StaticBody2D = arena.get_node_or_null("Mechanism/ExitDoor")
	if player == null or entities == null or door == null:
		_fail("Precondition: 竞技场场景结构不完整（Player/Entities/ExitDoor 缺失）")
		_report()
		return
	var player_health: Health = player.get_node_or_null("Health") as Health
	if player_health == null:
		_fail("Precondition: 玩家缺少 Health 组件")
		_report()
		return

	var spawned: Array[Node] = []
	for child in entities.get_children():
		if child.is_in_group("enemies"):
			spawned.append(child)
	if spawned.size() != ENEMY_COUNT:
		_fail("Precondition: 竞技场应生成 %d 个被测实体，实际 %d（alive_count=%d）"
			% [ENEMY_COUNT, spawned.size(), arena.alive_count])
		_report()
		return
	if arena.alive_count != ENEMY_COUNT:
		_fail("Precondition: 存活计数应为 %d，实际 %d" % [ENEMY_COUNT, arena.alive_count])
	var victim: CharacterBody2D = spawned[0]
	var other: CharacterBody2D = spawned[1]

	# ---- 前置条件 2：被测实体满足既有敌人接口（Health + 管理链路赋值的 target_path）----
	var victim_health: Health = victim.get_node_or_null("Health") as Health
	if victim_health == null:
		_fail("Precondition: 被测实体缺少 Health 组件（死亡语义由 Health 拥有），无法验证死亡流程")
		_report()
		return
	var other_health: Health = other.get_node_or_null("Health") as Health
	if other_health == null:
		_fail("Precondition: 第二个被测实体缺少 Health 组件")
		_report()
		return
	if victim.get("target_path") == null:
		_fail("Precondition: 被测实体根未接收既有管理链路赋值的 target_path"
			+ "（竞技场敌人生成接口要求实体根承担 motion 职责）")
		_report()
		return

	# ---- 前置条件 3：真实攻击路径必须可用（AttackTrigger 解析得到目标）----
	var trigger: Node = player.get_node_or_null("AttackTrigger")
	if trigger == null:
		_fail("Precondition: 玩家缺少 AttackTrigger，无法驱动真实伤害路径")
		_report()
		return
	var target_group := str(trigger.get("target_group"))
	var attack_action := str(trigger.get("attack_action"))
	var attack_damage := int(trigger.get("damage"))
	if target_group == "":
		_fail("Precondition: AttackTrigger 未配置 target_group，空格攻击解析不到任何目标"
			+ "（无法驱动真实伤害路径）")
		_report()
		return
	if attack_damage <= 0:
		_fail("Precondition: AttackTrigger.damage 应为正数，实际 %d" % attack_damage)
		_report()
		return
	if attack_damage >= victim_health.max_health:
		_fail("Precondition: 攻击伤害 %d 不应一次打死 max_health=%d 的目标"
			% [attack_damage, victim_health.max_health] + "（否则「未致死伤害不触发死亡」断言无意义）")
		_report()
		return

	# ---- 布置：受击目标最近（攻击必命中它），另一个必需敌人远离 ----
	var victim_max_health: int = victim_health.max_health
	var other_max_health: int = other_health.max_health
	victim_health.died.connect(_on_victim_died)
	victim_health.health_changed.connect(_on_victim_health_changed)
	other_health.died.connect(_on_other_died)
	other_health.health_changed.connect(_on_other_health_changed)
	_victim_hp = victim_health.get_current_health()
	_other_hp = other_health.get_current_health()
	victim.global_position = player.global_position + Vector2(VICTIM_DISTANCE, 0)
	other.global_position = player.global_position - Vector2(OTHER_DISTANCE, 0)
	await physics_frame

	var hp_before: int = _victim_hp
	var alive_before: int = arena.alive_count

	# ---- N1: 未致死伤害不得触发死亡处理，也不得改变胜负 ----
	await _press_attack(attack_action)
	var hp_after_first: int = _victim_hp
	if hp_after_first >= hp_before:
		_fail("Damage: 一次真实攻击后目标生命值应下降（AttackTrigger -> Health.take_damage），"
			+ "实际 %d -> %d（伤害 %d，目标组 %s）"
			% [hp_before, hp_after_first, attack_damage, target_group])
	if hp_after_first > 0:
		if _victim_died_events != 0:
			_fail("N1: 未致死伤害不应触发死亡，实际 died %d 次" % _victim_died_events)
		if arena.alive_count != alive_before:
			_fail("N1: 未致死伤害不应改变存活计数，实际 %d -> %d"
				% [alive_before, arena.alive_count])
		if door.is_open():
			_fail("N1: 仍有敌人存活时出口门不应打开")
	if arena.state != arena.State.Playing:
		_fail("N1: 未满足胜利条件时状态不应变化，实际 %d" % int(arena.state))

	# ---- D1: 通过真实攻击路径把生命值打到 0 ----
	var attacks := 1
	while not _victim_dead and attacks < ATTACK_BUDGET:
		await _press_attack(attack_action)
		attacks += 1
	var victim_dead: bool = _victim_dead
	var hp_after_kill: int = _victim_hp
	if victim_dead and hp_after_kill != 0:
		_fail("Death: 死亡时生命值应为 0，实际 %d" % hp_after_kill)
	if EXPECT == EXPECT_DIE and not victim_dead:
		_fail("Death: %d 次真实攻击内应进入死亡流程，实际生命值 %d（max_health=%d，伤害 %d）"
			% [ATTACK_BUDGET, hp_after_kill, victim_max_health, attack_damage])
	if EXPECT != EXPECT_DIE and victim_dead:
		_fail("Controlled negative: 该变异体不应在 %d 次攻击内死亡" % ATTACK_BUDGET)

	# ---- D2 / N2: 死亡事件恰好一次、存活计数恰好减一、重复攻击不重复处理 ----
	var alive_after_first: int = arena.alive_count
	var alive_after_extra: int = arena.alive_count
	var removed := false
	var live_entities := 0
	if victim_dead:
		if _victim_died_events != 1:
			_fail("D2: 生命值归零应恰好发出一次 died，实际 %d 次" % _victim_died_events)
		if alive_after_first != alive_before - 1:
			_fail("D2: 一次有效死亡应使存活计数恰好减一，实际 %d -> %d"
				% [alive_before, alive_after_first])
		if not String(arena.get_node("HUD/AliveLabel").text).contains(str(alive_after_first)):
			_fail("D2: 存活计数标签未同步更新（实际 %s）"
				% arena.get_node("HUD/AliveLabel").text)
		# 重复通知 / 重复伤害：不得造成重复计数或重复奖励结算
		await _press_attack(attack_action)
		if is_instance_valid(victim) and is_instance_valid(victim_health):
			victim_health.take_damage(attack_damage)
		alive_after_extra = arena.alive_count
		if _victim_died_events != 1:
			_fail("N2: 死亡后重复通知造成了重复的 died，累计 %d 次" % _victim_died_events)
		if alive_after_extra != alive_after_first:
			_fail("N2: 死亡后重复攻击造成了重复计数，实际 %d -> %d"
				% [alive_after_first, alive_after_extra])
		# 既有清理语义：died 驱动 queue_free，实体按项目规则退出战斗
		for _i: int in FREE_BUDGET:
			if not is_instance_valid(victim) or victim.is_queued_for_deletion():
				removed = true
				break
			await physics_frame
		if not removed:
			_fail("Removal: 被击败的实体应按既有规则退出战斗（等待 %d 帧超时）" % FREE_BUDGET)
		for child in entities.get_children():
			if is_instance_valid(child) and not child.is_queued_for_deletion() \
					and child.is_in_group("enemies"):
				live_entities += 1
		if live_entities != alive_after_extra:
			_fail("Consistency: 存活计数应与实体状态一致，计数 %d / 实际存活 %d"
				% [alive_after_extra, live_entities])

	# ---- V2: 仍有必需敌人存活时不得提前胜利 ----
	var door_after_first: bool = door.is_open()
	if victim_dead:
		# 攻击解析「最近的存活敌人」：额外攻击可能落到另一个敌人身上，因此这里只要求它仍存活
		# （这正是 V2 的前提：仍有必需敌人存在）。
		if _other_dead:
			_fail("Precondition: 第一个敌人死亡时不应连带击败第二个必需敌人"
				+ "（另一个敌人生命值 %d/%d）" % [_other_hp, other_max_health])
		if door_after_first:
			_fail("V2: 仍有必需敌人存活时出口门不应打开（提前胜利）")
		if arena.state != arena.State.Playing:
			_fail("V2: 仍有必需敌人存活时状态应保持 Playing，实际 %d" % int(arena.state))

	# ---- V1: 击败最后一个必需敌人 -> 场景自身逻辑打开出口 ----
	var state_before_exit := int(arena.state)
	var door_open_after_last := false
	if EXPECT == EXPECT_DIE and victim_dead:
		var attacks_last := 0
		while not _other_dead and attacks_last < ATTACK_BUDGET:
			await _press_attack(attack_action)
			attacks_last += 1
		if not _other_dead:
			_fail("Victory: 最后一个必需敌人在 %d 次攻击内应被击败，实际生命值 %d"
				% [ATTACK_BUDGET, _other_hp])
		else:
			if _other_died_events != 1:
				_fail("D2: 第二个必需敌人的 died 应恰好发出一次，实际 %d 次" % _other_died_events)
			door_open_after_last = door.is_open()
			if not door_open_after_last:
				_fail("Victory: 全部必需敌人被击败后，场景自身逻辑（died 驱动波次推进）应打开出口门")
			if arena.state != arena.State.Playing:
				_fail("Victory: 出口门打开但玩家未进出口区时状态应仍为 Playing，实际 %d"
					% int(arena.state))

	# ---- 玩家真实输入走向出口：满足胜利条件才完成；否则不得提前获胜 ----
	var walk_frames := WALK_WINDOW
	if EXPECT == EXPECT_DIE and door_open_after_last:
		walk_frames = EXIT_BUDGET
	# 未开门场景（受控负向）先把敌人移远，避免接触伤害干扰「是否提前获胜」的判定
	if walk_frames == WALK_WINDOW:
		if is_instance_valid(victim):
			victim.global_position = player.global_position - Vector2(OTHER_DISTANCE, 0)
		if is_instance_valid(other):
			other.global_position = player.global_position - Vector2(OTHER_DISTANCE + 100.0, 0)
	player.global_position = EXIT_START
	await physics_frame
	Input.action_press(MOVE_ACTION)
	for _i: int in walk_frames:
		await physics_frame
	Input.action_release(MOVE_ACTION)
	var state_after_exit := int(arena.state)

	if EXPECT == EXPECT_DIE:
		if victim_dead and door_open_after_last:
			if arena.state != arena.State.Completed:
				_fail("Victory: 玩家走进出口区后应进入 Completed 状态，实际 %d（玩家位置 %s）"
					% [int(arena.state), player.global_position])
			if _finish_events != [true]:
				_fail("Victory: arena_finished 应以 success=true 恰好发出一次，实际 %s"
					% str(_finish_events))
			if not String(arena.get_node("HUD/StatusLabel").text).contains("挑战完成"):
				_fail("Victory: 完成后状态栏应提示挑战完成，实际 %s"
					% arena.get_node("HUD/StatusLabel").text)
	else:
		if not _victim_dead and arena.alive_count != ENEMY_COUNT:
			_fail("Controlled negative: 变异体仍应存活，实际存活计数 %d" % arena.alive_count)
		if door.is_open():
			_fail("Controlled negative: 未击败必需敌人时出口门不应打开")
		if state_after_exit != int(arena.State.Playing):
			_fail("Controlled negative: 未满足胜利条件时状态应保持 Playing，实际 %d"
				% state_after_exit)
		if not _finish_events.is_empty():
			_fail("Controlled negative: 未满足胜利条件时不应有结算事件，实际 %s"
				% str(_finish_events))

	var premature_victory := 0
	if door_after_first and not EXPECT_DIE:
		premature_victory = 1
	print("DEATH: scene=%s expect=%s attack_damage=%d max_health=%d hp_before=%d "
		% [ENEMY_SCENE, EXPECT, attack_damage, victim_max_health, hp_before]
		+ "hp_after_first=%d hp_after_kill=%d attacks=%d died_events=%d alive_before=%d "
		% [hp_after_first, hp_after_kill, attacks, _victim_died_events, alive_before]
		+ "alive_after_death=%d alive_after_extra=%d removed=%d live_entities=%d"
		% [alive_after_first, alive_after_extra, 1 if removed else 0, live_entities])
	print("VICTORY: scene=%s door_open_with_survivor=%d door_open_after_last=%d "
		% [ENEMY_SCENE, 1 if door_after_first else 0, 1 if door_open_after_last else 0]
		+ "state_before_exit=%d state_after_exit=%d finish_events=%d premature_victory=%d "
		% [state_before_exit, state_after_exit, _finish_events.size(), premature_victory]
		+ "player_hp=%d enemies_expected=%d"
		% [player_health.get_current_health(), ENEMY_COUNT])
	_report()


## 真实攻击输入路径：按下攻击动作 -> Trigger 在真实物理帧里解析目标并调用 Health.take_damage。
func _press_attack(action: String) -> void:
	Input.action_press(action)
	await physics_frame
	await physics_frame
	Input.action_release(action)
	await physics_frame


func _on_victim_died() -> void:
	_victim_died_events += 1
	_victim_dead = true


func _on_victim_health_changed(current: int, _amount: int) -> void:
	_victim_hp = current


func _on_other_died() -> void:
	_other_died_events += 1
	_other_dead = true


func _on_other_health_changed(current: int, _amount: int) -> void:
	_other_hp = current


func _on_arena_finished(success: bool) -> void:
	_finish_events.append(success)


func _fail(message: String) -> void:
	_failures.append(message)


func _report() -> void:
	if _failures.is_empty():
		print("PASS: 生成实体死亡与胜利闭环验证通过 (%s, expect=%s)" % [ENEMY_SCENE, EXPECT])
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
'''


@dataclass
class DeathVictoryProbeResult:
    """一次死亡/胜利探针运行的结果（原始输出 + 解析出的度量值）。"""

    ok: bool
    exit_code: int
    scene: str
    arena: str
    expect: str
    output: str
    metrics: dict = field(default_factory=dict)
    script_removed: bool = False

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


def render_probe_source(enemy_res: str, expect: str = EXPECT_DIE,
                        arena_res: str = DEFAULT_ARENA) -> str:
    """渲染探针 GDScript（{{TOKEN}} 字面替换，模板正文的 % 格式化原样保留）。"""
    if expect not in (EXPECT_DIE, EXPECT_SURVIVE):
        raise ValueError("expectation must be %r or %r, got %r"
                         % (EXPECT_DIE, EXPECT_SURVIVE, expect))
    replacements = {
        "{{ARENA}}": arena_res,
        "{{ENEMY}}": enemy_res,
        "{{EXPECT_DIE}}": EXPECT_DIE,
        "{{EXPECT}}": expect,
        "{{PROBE_NAME}}": PROBE_SCRIPT_NAME,
        "{{ENEMY_COUNT}}": str(ARENA_ENEMY_COUNT),
        "{{DURATION}}": repr(float(ARENA_DURATION)),
        "{{VICTIM_DISTANCE}}": repr(float(VICTIM_DISTANCE)),
        "{{OTHER_DISTANCE}}": repr(float(OTHER_DISTANCE)),
        "{{ATTACK_BUDGET}}": str(ATTACK_BUDGET),
        "{{FREE_BUDGET}}": str(FREE_BUDGET),
        "{{EXIT_BUDGET}}": str(EXIT_BUDGET),
        "{{WALK_WINDOW}}": str(WALK_WINDOW),
        "{{EXIT_X}}": repr(float(EXIT_START[0])),
        "{{EXIT_Y}}": repr(float(EXIT_START[1])),
    }
    source = PROBE_SOURCE
    # {{EXPECT}} 与 {{EXPECT_DIE}} 有前缀关系：先替换长占位符，避免互相吃掉。
    for token in sorted(replacements, key=len, reverse=True):
        source = source.replace(token, replacements[token])
    if "{{" in source or "}}" in source:                   # pragma: no cover - 防占位符拼写错误
        raise RuntimeError("unresolved probe placeholder remains in rendered script")
    return source


def parse_metrics(output: str) -> dict:
    """从 DEATH / VICTORY 行解析度量值（供调用方独立断言）。"""
    metrics: dict = {}
    for line in output.splitlines():
        if not (line.startswith("DEATH:") or line.startswith("VICTORY:")):
            continue
        for key, value in re.findall(r"(\w+)=([-\d.]+)", line):
            try:
                metrics[key] = float(value)
            except ValueError:                              # pragma: no cover - 防御
                continue
    return metrics


def run_death_victory_probe(enemy_res: str, project_root: Path = PROJECT_ROOT, godot=None,
                            expect: str = EXPECT_DIE, arena_res: str = DEFAULT_ARENA,
                            timeout: int = 300) -> DeathVictoryProbeResult:
    """在真实 Godot 中运行死亡/胜利探针。输入/环境错误抛 RuntimeError（调用方转 exit 2）。"""
    project_root = Path(project_root)
    enemy_path = project_root / enemy_res.replace("res://", "")
    if not enemy_path.is_file():
        raise RuntimeError("scene not found in project: %s (%s)" % (enemy_res, enemy_path))
    arena_path = project_root / arena_res.replace("res://", "")
    if not arena_path.is_file():
        raise RuntimeError("arena game scene not found in project: %s" % arena_res)
    godot = Path(godot) if godot else find_godot(project_root)
    if godot is None or not Path(godot).is_file():
        raise RuntimeError("godot executable not found; set GODOT_BIN or add it to PATH")

    script_path = project_root / PROBE_SCRIPT_REL
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(render_probe_source(enemy_res, expect, arena_res),
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
    return DeathVictoryProbeResult(ok=(exit_code == 0 and "PASS:" in output),
                                   exit_code=exit_code, scene=enemy_res, arena=arena_res,
                                   expect=expect, output=output, metrics=parse_metrics(output),
                                   script_removed=removed)


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Run a real-Godot death & victory probe against a generated entity scene.")
    parser.add_argument("scene", help="res:// path of the entity scene under test")
    parser.add_argument("--arena", default=DEFAULT_ARENA,
                        help="res:// path of the host game scene carrying the victory logic"
                             " (default: %s)" % DEFAULT_ARENA)
    parser.add_argument("--expect", default=EXPECT_DIE, choices=(EXPECT_DIE, EXPECT_SURVIVE),
                        help="die (default) or survive for a controlled negative")
    parser.add_argument("--project", default=str(PROJECT_ROOT))
    parser.add_argument("--show-output", action="store_true", help="Print raw Godot output")
    args = parser.parse_args(argv)

    try:
        result = run_death_victory_probe(args.scene, project_root=Path(args.project).resolve(),
                                         expect=args.expect, arena_res=args.arena)
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        print("FAIL: %s" % exc, file=sys.stderr)
        return 2

    print("Death & Victory Probe")
    print("Scene: %s" % result.scene)
    print("Arena: %s" % result.arena)
    print("Expect: %s" % result.expect)
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
