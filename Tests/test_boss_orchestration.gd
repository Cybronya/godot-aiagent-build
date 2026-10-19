extends SceneTree
## Phase 1.20 Boss 编排验证（真实 Godot 运行时）。
##
## 覆盖：
##   B1 已存在 Boss 实例（boss.spawn=existing）：Boss 存活时不胜利（门已开也拒绝）、
##      受伤但不死亡不推进、死亡后按配置开出口、重复 died 通知不重复结算、
##      进入出口后 Completed 且 finished 恰好一次。
##   B2 on_start：编排器从 entities[boss.entity].scene 生成且只生成一个 Boss；
##      Boss 不计入 alive_count；死亡即胜利，重复通知不重复完成。
##   B3 非法引用：未知 Boss 实体 / 绑定错实例 / 无法解析实例 / 缺 Health 场景
##      一律拒绝开始（Failed + 可定位字段 + 零生成）。
##   B4 玩家死亡：Failed 且 finished 只发一次；不会产生胜利。
##   B5 BossChallenge 接入：场景真实使用 LevelOrchestrator（boss 模式），
##      Boss 实例来自配置路径；Boss 存活时不因门开而完成。
##   B6 多阶段 Boss（Phase 1.21）：清理普通敌人 → 激活 Boss → 击败 Boss → 完成；
##      清理未完成不激活 Boss、Boss 存活不胜利、提前击杀不跳阶段、阶段/死亡/完成
##      均幂等、complete_level 终结、非法阶段配置被拒绝。
##
## 用法：godot --headless --path . -s res://Tests/test_boss_orchestration.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

const PLAYER_SCENE := "res://Features/player_movement/Player.tscn"
const BOSS_SCENE := "res://Scenes/Boss.tscn"
const DOOR_SCENE := "res://Features/openable_door/OpenableDoor.tscn"
const BOSS_CHALLENGE_SCENE := "res://Scenes/BossChallenge.tscn"
const LEVEL_HOST_SCRIPT := preload("res://Orchestration/level_host.gd")
const BOSS_ENTITY := "boss"
const BOSS_INSTANCE := "Boss"
const ENEMY_SCENE := "res://Scenes/Enemy.tscn"

## Phase 1.33（F4-B）：本运行专属目录。临时关卡配置不再写入共享的 `res://Levels`，
## 而是落在 `.ai/tmp/runs/<pid>-<16 位十六进制随机后缀，与 Python run_workspace 同一契约>/`；只有「本运行写入且内容未变」的资源才允许删除。
var _run_dir := _make_run_dir()
var TEMP_CONFIG := _run_dir + "/E2eBossLifecycleTest.json"
var _owned: Dictionary = {}

var _failures: PackedStringArray = []
var _finish_events: Array = []


func _make_run_dir() -> String:
	var base := "res://.ai/tmp/runs"
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(base))
	for attempt in 16:
		var id := "%d-%08x%08x" % [OS.get_process_id(), randi(), randi()]
		var candidate := base + "/" + id
		if DirAccess.dir_exists_absolute(ProjectSettings.globalize_path(candidate)):
			continue                       # 标识冲突：拒绝接管，重试下一个候选
		if DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(candidate)) == OK:
			return candidate
	return ""


func _store_config(document: Dictionary) -> void:
	if _run_dir.is_empty() or DirAccess.open(_run_dir) == null:
		if _run_dir.is_empty() \
				or DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(_run_dir)) != OK:
			_fail("config: 无法创建运行目录 %s" % _run_dir)
			return
	var text := JSON.stringify(document, "  ") + "\n"
	var file := FileAccess.open(TEMP_CONFIG, FileAccess.WRITE)
	if file == null:
		_fail("config: 无法写入临时配置 %s" % TEMP_CONFIG)
		return
	file.store_string(text)
	file.close()
	_owned[TEMP_CONFIG] = text.sha256_text()


func _initialize() -> void:
	_remove_temp()
	await _case_b1_existing_boss()
	await _case_b2_on_start()
	await _case_b3_invalid_references()
	await _case_b4_player_death()
	await _case_b5_boss_challenge_integration()
	await _case_b6_multi_stage()
	_remove_temp()
	_report()


# ---------- B1：已存在 Boss 实例 ----------


func _case_b1_existing_boss() -> void:
	var host := _make_host()
	root.add_child(host["root"])
	await process_frame
	var orchestrator: LevelOrchestrator = host["orchestrator"]
	var boss: CharacterBody2D = host["boss"]
	var door: StaticBody2D = host["door"]
	var zone: Area2D = host["zone"]
	var player: CharacterBody2D = host["player"]
	var boss_health: Health = boss.get_node("Health")
	var player_health: Health = player.get_node("Health")
	boss.process_mode = Node.PROCESS_MODE_DISABLED

	var config := LevelConfig.from_file(_write_config("existing", BOSS_SCENE,
		{"entity": BOSS_ENTITY, "instance": BOSS_INSTANCE, "spawn": "existing"},
		{"unlock_when": "boss_defeated"}, {"condition": "exit_reached_after_unlock"}))
	if not config.is_valid():
		_fail("B1: valid existing-boss config was rejected: %s" % str(config.errors))
		host["root"].queue_free()
		return
	if not orchestrator.apply_config(config):
		_fail("B1: orchestrator rejected a valid existing-boss config: %s"
			% str(orchestrator.get_config_errors()))
		host["root"].queue_free()
		return
	if config.mode != LevelConfig.MODE_BOSS or config.boss_entity != BOSS_ENTITY:
		_fail("B1: config did not normalize the declared boss identity (mode=%s entity=%s)"
			% [config.mode, config.boss_entity])
	if not orchestrator.bind_boss(BOSS_ENTITY, boss):
		_fail("B1: binding the declared existing boss failed: %s"
			% str(orchestrator.get_config_errors()))
		host["root"].queue_free()
		return
	orchestrator.start()
	await process_frame
	if orchestrator.state != LevelOrchestrator.State.Playing:
		_fail("B1: a live boss must keep the level Playing (state=%d)" % int(orchestrator.state))
	if orchestrator.get_boss() != boss:
		_fail("B1: orchestrator did not bind the configured boss instance")
	if orchestrator.alive_count != 0:
		_fail("B1: the boss must not be counted as a wave enemy (alive_count=%d)"
			% orchestrator.alive_count)

	# Boss 存活 + 出口门已开 + 玩家在出口区 → 仍不得胜利
	door.set_open(true)
	# 数组按引用捕获（GDScript lambda 对局部标量是按值捕获）
	var zone_entries := [0]
	zone.body_entered.connect(func(_body: Node2D) -> void: zone_entries[0] += 1)
	player.global_position = zone.global_position
	for _i: int in 60:
		if zone_entries[0] > 0:
			break
		await physics_frame
	if zone_entries[0] == 0:
		_fail("B1: probe could not enter the exit zone (test precondition)")
	if orchestrator.state != LevelOrchestrator.State.Playing:
		_fail("B1: a live boss must block exit victory even with the door open (state=%d)"
			% int(orchestrator.state))
	# 受伤但不死亡 → 不胜利
	boss_health.take_damage(1)
	await process_frame
	if boss_health.is_dead() or orchestrator.state != LevelOrchestrator.State.Playing:
		_fail("B1: a damaged but living boss must not complete the level")

	# 先离开出口区，避免区域信号与死亡结算在同一帧交叠
	player.global_position = Vector2(-300, 0)
	await physics_frame
	# 死亡 → 出口打开，但胜利条件要求走进出口
	boss_health.take_damage(9999)
	await process_frame
	if not boss_health.is_dead():
		_fail("B1: boss should be dead after lethal damage")
	if orchestrator.get_boss_defeated_events() != 1:
		_fail("B1: boss death must be settled exactly once (events=%d)"
			% orchestrator.get_boss_defeated_events())
	if orchestrator.state != LevelOrchestrator.State.Playing:
		_fail("B1: victory=exit_reached must not complete on boss death alone (state=%d)"
			% int(orchestrator.state))
	if not door.is_open():
		_fail("B1: exit.unlock_when=boss_defeated must open the door on boss death")

	# 重复死亡事件：不重复结算 / 不重复完成
	boss_health.died.emit()
	boss_health.died.emit()
	await process_frame
	if orchestrator.get_boss_defeated_events() != 1 or _finish_events.size() != 0:
		_fail("B1: duplicate died notifications were settled twice (events=%d finish=%s)"
			% [orchestrator.get_boss_defeated_events(), str(_finish_events)])

	# 玩家真实进入出口区 → Completed，finished 恰好一次
	player.global_position = Vector2(-300, 0)
	await physics_frame
	player.global_position = zone.global_position
	for _i: int in 30:
		if orchestrator.state == LevelOrchestrator.State.Completed:
			break
		await physics_frame
	if orchestrator.state != LevelOrchestrator.State.Completed:
		_fail("B1: entering the exit after boss death must complete the level (state=%d)"
			% int(orchestrator.state))
	if _finish_events != [true]:
		_fail("B1: finished must be emitted exactly once with success=true, got %s"
			% str(_finish_events))
	# 终态重复结束无效
	orchestrator.finish(true)
	player_health.take_damage(9999)
	await process_frame
	if _finish_events != [true]:
		_fail("B1: a terminal level must ignore repeated finish/player-death events, got %s"
			% str(_finish_events))
	_finish_events.clear()
	host["root"].queue_free()
	await process_frame


# ---------- B2：on_start 生成 ----------


func _case_b2_on_start() -> void:
	var host := _make_host(false)
	root.add_child(host["root"])
	await process_frame
	var orchestrator: LevelOrchestrator = host["orchestrator"]
	var entities: Node2D = host["entities"]
	var boss_health: Health = host["boss"].get_node("Health")
	host["boss"].queue_free()
	await process_frame

	var config := LevelConfig.from_file(_write_config("on_start", BOSS_SCENE,
		{"entity": BOSS_ENTITY, "spawn": "on_start"},
		{"unlock_when": "never"}, {"condition": "boss_defeated"}))
	if not config.is_valid():
		_fail("B2: valid on_start config was rejected: %s" % str(config.errors))
		host["root"].queue_free()
		return
	if not orchestrator.apply_config(config):
		_fail("B2: orchestrator rejected a valid on_start config: %s"
			% str(orchestrator.get_config_errors()))
		host["root"].queue_free()
		return
	orchestrator.start()
	await process_frame
	var spawned := orchestrator.get_boss()
	if spawned == null or not is_instance_valid(spawned):
		_fail("B2: on_start must spawn the configured boss scene (errors=%s)"
			% str(orchestrator.get_config_errors()))
		host["root"].queue_free()
		return
	spawned.process_mode = Node.PROCESS_MODE_DISABLED
	var boss_children := 0
	for child in entities.get_children():
		if child.name == BOSS_INSTANCE or child.name.begins_with(BOSS_INSTANCE):
			boss_children += 1
	if boss_children != 1:
		_fail("B2: on_start must spawn exactly one boss (found %d)" % boss_children)
	if orchestrator.alive_count != 0:
		_fail("B2: spawned boss must not be counted as a wave enemy (alive_count=%d)"
			% orchestrator.alive_count)
	boss_health = spawned.get_node("Health")
	boss_health.take_damage(9999)
	await process_frame
	if orchestrator.state != LevelOrchestrator.State.Completed:
		_fail("B2: victory=boss_defeated must complete on boss death (state=%d)"
			% int(orchestrator.state))
	boss_health.died.emit()
	await process_frame
	if _finish_events != [true] or orchestrator.get_boss_defeated_events() != 1:
		_fail("B2: duplicate boss death must not complete twice (finish=%s events=%d)"
			% [str(_finish_events), orchestrator.get_boss_defeated_events()])
	_finish_events.clear()
	host["root"].queue_free()
	await process_frame


# ---------- B3：非法 Boss 引用 ----------


func _case_b3_invalid_references() -> void:
	# 1) 未知 Boss 实体（配置静态拒绝）
	var unknown := LevelConfig.from_file(_write_config("unknown_entity", BOSS_SCENE,
		{"entity": "ghost", "instance": BOSS_INSTANCE, "spawn": "existing"},
		{"unlock_when": "boss_defeated"}, {"condition": "exit_reached_after_unlock"}))
	if unknown.is_valid() or not _has_error_at(unknown.errors, "boss.entity"):
		_fail("B3: config with an unknown boss entity must fail at boss.entity, got %s"
			% str(unknown.errors))
	var host := _make_host()
	root.add_child(host["root"])
	await process_frame
	var orchestrator: LevelOrchestrator = host["orchestrator"]
	if orchestrator.apply_config(unknown):
		_fail("B3: orchestrator accepted a config with an unknown boss entity")
	if orchestrator.state != LevelOrchestrator.State.Failed:
		_fail("B3: rejected config must leave the orchestrator Failed")
	var spawned_before: int = host["entities"].get_child_count()
	orchestrator.start()
	await process_frame
	if host["entities"].get_child_count() != spawned_before:
		_fail("B3: a rejected config must not spawn anything")

	# 2) 绑定错误的实体 id（不按节点名猜测）—— 全新宿主，避免复用已 Failed 的编排器
	host["root"].queue_free()
	await process_frame
	host = _make_host()
	root.add_child(host["root"])
	await process_frame
	orchestrator = host["orchestrator"]
	var valid := LevelConfig.from_file(_write_config("valid_bind", BOSS_SCENE,
		{"entity": BOSS_ENTITY, "instance": BOSS_INSTANCE, "spawn": "existing"},
		{"unlock_when": "boss_defeated"}, {"condition": "exit_reached_after_unlock"}))
	if not orchestrator.apply_config(valid):
		_fail("B3: valid config was rejected before the binding check")
	if orchestrator.bind_boss("ghost", host["boss"]):
		_fail("B3: binding a node with the wrong entity id must be refused")
	if orchestrator.state != LevelOrchestrator.State.Failed:
		_fail("B3: failed binding must leave the orchestrator Failed")
	host["root"].queue_free()
	await process_frame

	# 3) 配置声明 existing 但实例无法解析（LevelHost 适配层）
	var adapter_host := _make_host()
	root.add_child(adapter_host["root"])
	await process_frame
	var adapter = LEVEL_HOST_SCRIPT.new()
	adapter.level_config_path = _write_config("missing_instance", BOSS_SCENE,
		{"entity": BOSS_ENTITY, "instance": "NoSuchBoss", "spawn": "existing"},
		{"unlock_when": "boss_defeated"}, {"condition": "exit_reached_after_unlock"})
	adapter_host["root"].add_child(adapter)
	await process_frame
	if adapter.is_setup_ok():
		_fail("B3: LevelHost must refuse an unresolvable boss.instance")
	if not _has_error_at(adapter.setup_errors, "boss.instance"):
		_fail("B3: LevelHost must report boss.instance for an unresolvable instance, got %s"
			% str(adapter.setup_errors))
	if adapter.orchestrator != null \
			and adapter.orchestrator.state != LevelOrchestrator.State.Failed:
		_fail("B3: LevelHost binding failure must leave the orchestrator Failed")
	adapter_host["root"].queue_free()
	await process_frame

	# 4) on_start 但实体场景没有 Health → 无法与死亡事件对应
	var no_health_host := _make_host(false)
	root.add_child(no_health_host["root"])
	await process_frame
	no_health_host["boss"].queue_free()
	var no_health_orchestrator: LevelOrchestrator = no_health_host["orchestrator"]
	var no_health := LevelConfig.from_file(_write_config("no_health",
		BOSS_CHALLENGE_SCENE, {"entity": BOSS_ENTITY, "spawn": "on_start"},
		{"unlock_when": "never"}, {"condition": "boss_defeated"}))
	if not no_health.is_valid():
		_fail("B3: on_start config with an existing scene should validate, got %s"
			% str(no_health.errors))
	elif no_health_orchestrator.apply_config(no_health):
		no_health_orchestrator.start()
		await process_frame
		if no_health_orchestrator.state != LevelOrchestrator.State.Failed:
			_fail("B3: spawning a boss scene without Health must fail the level")
		if not _has_error_at(no_health_orchestrator.get_config_errors(), "boss.entity"):
			_fail("B3: missing Health must be reported at boss.entity, got %s"
				% str(no_health_orchestrator.get_config_errors()))
		var leftover := 0
		for child in no_health_host["entities"].get_children():
			if child.name.begins_with("BossChallenge"):
				leftover += 1
		if leftover != 0:
			_fail("B3: a rejected boss scene must not be left in the scene tree")
	no_health_host["root"].queue_free()
	await process_frame


# ---------- B4：玩家死亡 ----------


func _case_b4_player_death() -> void:
	var host := _make_host()
	root.add_child(host["root"])
	await process_frame
	var orchestrator: LevelOrchestrator = host["orchestrator"]
	host["boss"].process_mode = Node.PROCESS_MODE_DISABLED
	var config := LevelConfig.from_file(_write_config("player_death", BOSS_SCENE,
		{"entity": BOSS_ENTITY, "instance": BOSS_INSTANCE, "spawn": "existing"},
		{"unlock_when": "boss_defeated"}, {"condition": "exit_reached_after_unlock"}))
	if not orchestrator.apply_config(config) \
			or not orchestrator.bind_boss(BOSS_ENTITY, host["boss"]):
		_fail("B4: setup failed before the player-death case: %s"
			% str(orchestrator.get_config_errors()))
		host["root"].queue_free()
		return
	orchestrator.start()
	await process_frame
	host["player"].get_node("Health").take_damage(9999)
	await process_frame
	if orchestrator.state != LevelOrchestrator.State.Failed:
		_fail("B4: player death must fail the boss level (state=%d)"
			% int(orchestrator.state))
	if _finish_events != [false]:
		_fail("B4: player death must emit finished(false) exactly once, got %s"
			% str(_finish_events))
	host["player"].get_node("Health").take_damage(9999)
	await process_frame
	if _finish_events != [false]:
		_fail("B4: repeated player death must not emit finished again, got %s"
			% str(_finish_events))
	_finish_events.clear()
	host["root"].queue_free()
	await process_frame


# ---------- B5：BossChallenge 接入同一编排器 ----------


func _case_b5_boss_challenge_integration() -> void:
	var challenge: Node2D = load(BOSS_CHALLENGE_SCENE).instantiate()
	root.add_child(challenge)
	current_scene = challenge
	await process_frame
	var orchestrator: LevelOrchestrator = challenge.get_orchestrator()
	if orchestrator == null:
		_fail("B5: BossChallenge must expose the shared LevelOrchestrator")
		challenge.queue_free()
		return
	if orchestrator.get_mode() != LevelConfig.MODE_BOSS:
		_fail("B5: BossChallenge must run in boss mode (mode=%s)" % orchestrator.get_mode())
	if orchestrator.get_boss() != challenge.get_node("Entities/Boss"):
		_fail("B5: BossChallenge boss instance must come from the declared config path")
	if orchestrator.get_config_errors().size() != 0:
		_fail("B5: BossChallenge config must be valid, got %s"
			% str(orchestrator.get_config_errors()))
	# Boss 存活 + 出口门人为打开 → 不得完成（boss guard）
	challenge.get_node("Mechanism/ExitDoor").set_open(true)
	var player: CharacterBody2D = challenge.get_node("Player")
	player.global_position = challenge.get_node("Mechanism/ExitZone").global_position
	for _i: int in 10:
		await physics_frame
	if challenge.state == challenge.State.Completed:
		_fail("B5: BossChallenge must not complete while the boss is alive")
	# Boss 死亡 → 出口解锁；重复 died 不重复结算
	var boss_health: Health = challenge.get_node("Entities/Boss/Health")
	boss_health.take_damage(9999)
	await process_frame
	boss_health.died.emit()
	await process_frame
	if orchestrator.get_boss_defeated_events() != 1:
		_fail("B5: BossChallenge boss death must be settled exactly once (events=%d)"
			% orchestrator.get_boss_defeated_events())
	if challenge.state != challenge.State.Playing:
		_fail("B5: BossChallenge victory=exit_reached must wait for the exit (state=%d)"
			% int(challenge.state))
	challenge.queue_free()
	await process_frame


# ---------- B6：多阶段 Boss（Phase 1.21） ----------


func _case_b6_multi_stage() -> void:
	# ---- B6a：清理阶段未完成 → Boss 阶段不激活；Boss 存活 → 不胜利 ----
	var host := _make_host()
	root.add_child(host["root"])
	await process_frame
	var orchestrator: LevelOrchestrator = host["orchestrator"]
	var boss: CharacterBody2D = host["boss"]
	boss.process_mode = Node.PROCESS_MODE_DISABLED
	var boss_health: Health = boss.get_node("Health")
	var config := LevelConfig.from_file(_write_stage_config("stages_clear_boss",
		_stage_clear("clear_1", 2), _stage_boss(),
		{"unlock_when": "never"}, {"condition": "boss_defeated"}))
	if not config.is_valid():
		_fail("B6: valid multi-stage config was rejected: %s" % str(config.errors))
		host["root"].queue_free()
		return
	if config.stages.size() != 2 or config.stages[0]["type"] != LevelConfig.STAGE_CLEAR_ENEMIES:
		_fail("B6: config did not normalize the declared stage order")
	if not orchestrator.apply_config(config):
		_fail("B6: orchestrator rejected a valid multi-stage config: %s"
			% str(orchestrator.get_config_errors()))
		host["root"].queue_free()
		return
	if not orchestrator.bind_boss(BOSS_ENTITY, boss):
		_fail("B6: binding the declared existing boss failed: %s"
			% str(orchestrator.get_config_errors()))
		host["root"].queue_free()
		return
	orchestrator.start()
	await process_frame
	if not orchestrator.has_stages() or not orchestrator.are_stages_done() == false:
		_fail("B6: stage chain did not start (has=%s done=%s)"
			% [str(orchestrator.has_stages()), str(orchestrator.are_stages_done())])
	if orchestrator.get_stage_index() != 0 \
			or orchestrator.get_stage_type() != LevelConfig.STAGE_CLEAR_ENEMIES:
		_fail("B6: first stage must be clear_enemies (index=%d type=%s)"
			% [orchestrator.get_stage_index(), orchestrator.get_stage_type()])
	if orchestrator.alive_count != 2:
		_fail("B6: clear stage must spawn its declared enemies (alive=%d)"
			% orchestrator.alive_count)
	if orchestrator.state != LevelOrchestrator.State.Playing or _finish_events.size() != 0:
		_fail("B6: a live boss during the clear stage must not finish the level")
	var clear_enemies := _stage_enemies(host["root"], orchestrator)
	if clear_enemies.size() != 2:
		_fail("B6: expected 2 spawned clear enemies, got %d" % clear_enemies.size())
		clear_enemies = []
	if clear_enemies.size() == 2:
		var first_health: Health = clear_enemies[0].get_node("Health")
		first_health.take_damage(9999)
		first_health.died.emit()
		await process_frame
		if orchestrator.get_stage_index() != 0:
			_fail("B6: clearing one of two enemies must not advance the stage (index=%d)"
				% orchestrator.get_stage_index())
		if orchestrator.state != LevelOrchestrator.State.Playing or _finish_events.size() != 0:
			_fail("B6: partial clear must not complete the level")
		clear_enemies[1].get_node("Health").take_damage(9999)
		await process_frame
	if orchestrator.get_stage_index() != 1 \
			or orchestrator.get_stage_type() != LevelConfig.STAGE_DEFEAT_BOSS:
		_fail("B6: clearing all enemies must activate the boss stage exactly once "
			+ "(index=%d type=%s)" % [orchestrator.get_stage_index(), orchestrator.get_stage_type()])
	if orchestrator.state != LevelOrchestrator.State.Playing or _finish_events.size() != 0:
		_fail("B6: a living boss must keep the level Playing")
	var events_after_activate: Dictionary = orchestrator.get_stage_event_counts()
	if events_after_activate.get("started", 0) != 2 \
			or events_after_activate.get("completed", 0) != 1:
		_fail("B6: stage activation/completion must be once each, got %s"
			% str(events_after_activate))
	# Boss 存活时即使门被强行打开也不得胜利
	var door: StaticBody2D = host["door"]
	door.set_open(true)
	var player: CharacterBody2D = host["player"]
	player.global_position = host["zone"].global_position
	for _i: int in 20:
		await physics_frame
	if orchestrator.state != LevelOrchestrator.State.Playing:
		_fail("B6: a live boss must block exit victory even with the door open")
	player.global_position = Vector2(-500, 0)
	await physics_frame

	# ---- B6b：Boss 死亡 → 完成一次；重复死亡不重复 ----
	boss_health.take_damage(9999)
	await process_frame
	if orchestrator.state != LevelOrchestrator.State.Completed \
			or _finish_events != [true]:
		_fail("B6: boss death in the final stage must complete once, got state=%d finish=%s"
			% [int(orchestrator.state), str(_finish_events)])
	if not orchestrator.are_stages_done():
		_fail("B6: all declared stages must be done after boss death")
	var completed_events: Dictionary = orchestrator.get_stage_event_counts()
	if completed_events.get("started", 0) != 2 \
			or completed_events.get("completed", 0) != 2:
		_fail("B6: final stage must complete exactly once, got %s" % str(completed_events))
	if orchestrator.get_stage_history() != ["clear_1", "boss"]:
		_fail("B6: stage history must follow the declared order, got %s"
			% str(orchestrator.get_stage_history()))
	boss_health.died.emit()
	boss_health.died.emit()
	await process_frame
	if orchestrator.get_boss_defeated_events() != 1 or _finish_events.size() != 1:
		_fail("B6: duplicate boss deaths must not re-settle (events=%d finish=%s)"
			% [orchestrator.get_boss_defeated_events(), str(_finish_events)])
	_finish_events.clear()
	host["root"].queue_free()
	await process_frame
	if _finish_events.size() != 0:
		_fail("B6: a freed multi-stage host must not leave a residual finish callback "
			+ "(finish=%s)" % str(_finish_events))

	# ---- B6c：清理阶段提前击杀 Boss → 不跳阶段；清理完成才结算一次 ----
	var early_host := _make_host()
	root.add_child(early_host["root"])
	await process_frame
	var early_orch: LevelOrchestrator = early_host["orchestrator"]
	var early_boss: CharacterBody2D = early_host["boss"]
	early_boss.process_mode = Node.PROCESS_MODE_DISABLED
	var early_boss_health: Health = early_boss.get_node("Health")
	var early_config := LevelConfig.from_file(_write_stage_config("stages_early_boss",
		_stage_clear("clear_1", 2), _stage_boss(),
		{"unlock_when": "never"}, {"condition": "boss_defeated"}))
	if not early_orch.apply_config(early_config) \
			or not early_orch.bind_boss(BOSS_ENTITY, early_boss):
		_fail("B6: early-death setup failed: %s" % str(early_orch.get_config_errors()))
		early_host["root"].queue_free()
		return
	early_orch.start()
	await process_frame
	early_boss_health.take_damage(9999)
	await process_frame
	if early_orch.get_boss_defeated_events() != 1:
		_fail("B6: early boss death must be recorded once (events=%d)"
			% early_orch.get_boss_defeated_events())
	if early_orch.get_stage_index() != 0 or early_orch.state != LevelOrchestrator.State.Playing:
		_fail("B6: early boss death must not skip the clear stage (index=%d state=%d)"
			% [early_orch.get_stage_index(), int(early_orch.state)])
	if _finish_events.size() != 0:
		_fail("B6: early boss death must not finish before the clear stage")
	for enemy in _stage_enemies(early_host["root"], early_orch):
		enemy.get_node("Health").take_damage(9999)
	await process_frame
	if early_orch.state != LevelOrchestrator.State.Completed \
			or _finish_events != [true]:
		_fail("B6: clearing after early boss death must complete once, got state=%d finish=%s"
			% [int(early_orch.state), str(_finish_events)])
	if early_orch.get_boss_defeated_events() != 1:
		_fail("B6: early boss death must not be re-settled on stage activation")
	_finish_events.clear()
	early_host["root"].queue_free()
	await process_frame

	# ---- B6d：complete_level 终结阶段 ----
	var complete_host := _make_host()
	root.add_child(complete_host["root"])
	await process_frame
	var complete_orch: LevelOrchestrator = complete_host["orchestrator"]
	var complete_boss: CharacterBody2D = complete_host["boss"]
	complete_boss.process_mode = Node.PROCESS_MODE_DISABLED
	var complete_config := LevelConfig.from_file(_write_stage_config("stages_complete",
		_stage_clear("clear_1", 1), _stage_boss(),
		{"unlock_when": "never"}, {"condition": "boss_defeated"}, _stage_complete()))
	if not complete_config.is_valid():
		_fail("B6: complete_level config was rejected: %s" % str(complete_config.errors))
	elif not complete_orch.apply_config(complete_config) \
			or not complete_orch.bind_boss(BOSS_ENTITY, complete_boss):
		_fail("B6: complete_level setup failed: %s" % str(complete_orch.get_config_errors()))
	else:
		complete_orch.start()
		await process_frame
		for enemy in _stage_enemies(complete_host["root"], complete_orch):
			enemy.get_node("Health").take_damage(9999)
		await process_frame
		complete_boss.get_node("Health").take_damage(9999)
		await process_frame
		if complete_orch.state != LevelOrchestrator.State.Completed \
				or _finish_events != [true]:
			_fail("B6: complete_level must finish once after boss death, got state=%d finish=%s"
				% [int(complete_orch.state), str(_finish_events)])
		if complete_orch.get_stage_history() != ["clear_1", "boss", "complete"]:
			_fail("B6: complete_level history mismatch: %s"
				% str(complete_orch.get_stage_history()))
	_finish_events.clear()
	complete_host["root"].queue_free()
	await process_frame

	# ---- B6e：非法阶段配置在加载期被拒绝（可定位字段，不产生假胜利） ----
	var invalid_cases := [
		["empty", []],
		["duplicate_ids", [_stage_clear("dup", 1), _stage_clear("dup", 1), _stage_boss()]],
		["unknown_type", [_stage_clear("clear_1", 1),
			{"id": "boss", "type": "teleport", "entity": BOSS_ENTITY}]],
		["missing_boss_entity", [_stage_clear("clear_1", 1),
			{"id": "boss", "type": "defeat_boss"}]],
		["empty_clear_entries", [{"id": "clear_1", "type": "clear_enemies", "entries": []},
			_stage_boss()]],
		["clear_boss_entity", [_stage_clear("clear_1", 1, BOSS_ENTITY), _stage_boss()]],
		["boss_not_last", [_stage_clear("clear_1", 1), _stage_boss(),
			_stage_clear("clear_2", 1)]],
		["complete_not_last", [_stage_complete(), _stage_clear("clear_1", 1), _stage_boss()]],
		["complete_with_exit", [_stage_clear("clear_1", 1), _stage_boss(), _stage_complete()],
			{"unlock_when": "boss_defeated"}, {"condition": "boss_defeated"}],
	]
	for item in invalid_cases:
		var label: String = item[0]
		var stages: Array = item[1]
		var exit_block: Dictionary = item[2] if item.size() > 2 else {"unlock_when": "never"}
		var victory_block: Dictionary = item[3] if item.size() > 3 \
			else {"condition": "boss_defeated"}
		var invalid := LevelConfig.from_file(_write_stage_config("stages_invalid_" + label,
			stages, [], exit_block, victory_block, [], true))
		var expected_field := "exit.unlock_when" if label == "complete_with_exit" else "stages"
		if invalid.is_valid():
			_fail("B6: invalid stage config %s was accepted" % label)
		elif not invalid.errors[0].contains(expected_field):
			_fail("B6: invalid stage config %s must report %s, got %s"
				% [label, expected_field, invalid.errors[0]])


func _stage_clear(stage_id: String, count: int, entity_id: String = "grunt") -> Dictionary:
	return {"id": stage_id, "type": "clear_enemies",
		"entries": [{"entity": entity_id, "count": count}]}


func _stage_boss() -> Dictionary:
	return {"id": "boss", "type": "defeat_boss", "entity": BOSS_ENTITY}


func _stage_complete() -> Dictionary:
	return {"id": "complete", "type": "complete_level"}


func _stage_enemies(host: Node, orchestrator: LevelOrchestrator) -> Array[Node]:
	var result: Array[Node] = []
	for child in orchestrator.entities.get_children():
		if child.is_in_group("enemies") and is_instance_valid(child) \
				and not child.is_queued_for_deletion():
			result.append(child)
	return result


func _write_stage_config(name: String, first_stage: Variant, second_stage,
		exit_block: Dictionary, victory_block: Dictionary,
		third_stage: Variant = null, only_entities: bool = false) -> String:
	var stages: Array = []
	if first_stage is Array:
		stages = first_stage
	else:
		stages.append(first_stage)
		if second_stage is Array:
			stages.append_array(second_stage)
		else:
			stages.append(second_stage)
		if third_stage != null:
			if third_stage is Array:
				stages.append_array(third_stage)
			else:
				stages.append(third_stage)
	var document := {
		"schema": {"id": "level_orchestration", "version": 2},
		"level": {"id": "e2e_stage_%s" % name,
			"arena_scene": "res://Scenes/BossChallenge.tscn"},
		"mode": "boss",
		"entities": {BOSS_ENTITY: {"scene": BOSS_SCENE},
			"grunt": {"scene": ENEMY_SCENE}},
		"boss": {"entity": BOSS_ENTITY, "instance": BOSS_INSTANCE, "spawn": "existing"},
		"stages": stages,
		"exit": exit_block,
		"victory": victory_block,
	}
	if only_entities:
		document["boss"] = {"entity": BOSS_ENTITY, "instance": BOSS_INSTANCE,
			"spawn": "existing"}
	_store_config(document)
	return TEMP_CONFIG


# ---------- 宿主构造 / 配置 / 断言辅助 ----------


func _make_host(with_boss: bool = true) -> Dictionary:
	var host := Node2D.new()
	host.name = "BossLifecycleHost"

	var player: CharacterBody2D = load(PLAYER_SCENE).instantiate()
	player.name = "Player"
	player.add_to_group("players")
	player.position = Vector2(-500, 0)

	var entities := Node2D.new()
	entities.name = "Entities"

	var boss: CharacterBody2D = load(BOSS_SCENE).instantiate()
	boss.name = BOSS_INSTANCE
	boss.position = Vector2(300, 0)
	if with_boss:
		entities.add_child(boss)

	var door: StaticBody2D = load(DOOR_SCENE).instantiate()
	door.name = "ExitDoor"
	door.position = Vector2(600, 0)

	var zone := Area2D.new()
	zone.name = "ExitZone"
	zone.position = Vector2(700, 0)
	var shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(120, 220)
	shape.shape = rect
	zone.add_child(shape)

	host.add_child(player)
	host.add_child(entities)
	host.add_child(door)
	host.add_child(zone)

	var orchestrator := LevelOrchestrator.new()
	host.add_child(orchestrator)
	orchestrator.player = player
	orchestrator.entities = entities
	orchestrator.exit_door = door
	orchestrator.exit_zone = zone
	orchestrator.spawn_offset = func() -> Vector2: return Vector2(300, 0)
	orchestrator.finished.connect(func(success: bool) -> void: _finish_events.append(success))

	return {"root": host, "player": player, "entities": entities, "boss": boss,
		"door": door, "zone": zone, "orchestrator": orchestrator}


func _write_config(name: String, scene: String, boss_block: Dictionary,
		exit_block: Dictionary, victory_block: Dictionary) -> String:
	var document := {
		"schema": {"id": "level_orchestration", "version": 2},
		"level": {"id": "e2e_boss_lifecycle",
			"arena_scene": "res://Scenes/BossChallenge.tscn"},
		"mode": "boss",
		"entities": {BOSS_ENTITY: {"scene": scene}},
		"boss": boss_block,
		"exit": exit_block,
		"victory": victory_block,
	}
	_store_config(document)
	return TEMP_CONFIG


func _has_error_at(errors: PackedStringArray, field: String) -> bool:
	for error in errors:
		var parts := String(error).split(": ")
		# 配置读取错误 = "<path>: <field>: <msg>"；运行期 bind 错误 = "<field>: <msg>"
		var error_field := parts[0].strip_edges() if parts.size() == 2 \
			else (parts[1].strip_edges() if parts.size() >= 3 else "")
		if error_field == field:
			return true
	return false


func _remove_temp() -> void:
	# 只删「本运行写入且内容未变」的资源；内容不符 = 所有权无法证明 ⇒拒绝并报告。
	for path: String in _owned.keys():
		if not FileAccess.file_exists(path):
			continue
		var current := FileAccess.get_file_as_string(path)
		if current.sha256_text() != _owned[path]:
			_fail("ownership: 内容与本运行写入不一致，拒绝删除 %s" % path)
			continue
		DirAccess.remove_absolute(ProjectSettings.globalize_path(path))
		if FileAccess.file_exists(path):
			_fail("cleanup: 无法删除 %s" % path)
	if not _run_dir.is_empty() and DirAccess.dir_exists_absolute(ProjectSettings.globalize_path(_run_dir)):
		if DirAccess.remove_absolute(ProjectSettings.globalize_path(_run_dir)) != OK:
			_fail("cleanup: 运行目录非空或无法删除 %s" % _run_dir)


func _fail(message: String) -> void:
	_failures.append(message)


## 只报告不删除：`res://Levels` 中前缀命中但**不属于本运行**的残留。
func _report_foreign_leftovers() -> void:
	var dir := DirAccess.open("res://Levels")
	if dir == null:
		return
	for file_name in dir.get_files():
		if not file_name.begins_with("E2e"):
			continue
		var path := "res://Levels/" + file_name
		if not _owned.has(path):
			print("LEFTOVER (not owned by this run, not removed): %s" % path)


func _report() -> void:
	if not _run_dir.is_empty() and DirAccess.dir_exists_absolute(ProjectSettings.globalize_path(_run_dir)):
		_failures.append("Z: 运行目录未清理 %s" % _run_dir)
	_report_foreign_leftovers()
	if _failures.is_empty():
		print("PASS: Boss 编排生命周期验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
