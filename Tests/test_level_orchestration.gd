extends SceneTree
## 关卡编排运行时验证（Phase 1.13）：配置驱动的生成 / 波次 / 出口 / 胜利。
##
## 覆盖（对应任务编号）：
##   A  真实场景 TimedCombatArena.tscn 消费 Levels/timed_combat_arena.json（配置驱动生效）
##   L7  运行时从**配置**读取敌人数（与场景内手写数量不同，证明不依赖场景数据）
##   L8  首波按配置生成，并注册进既有敌人管理链路（enemies 组 + 计数 + Health/target_path）
##   L9  首波未清除时第二波不生成
##   L10 首波清除后第二波按配置生成（数量来自配置）
##   L11 第二波清除前出口保持关闭
##   L12 全部必需波次清除后出口开启
##   L13 玩家进入出口区后状态进入 Completed
##   L14 胜利事件只触发一次
##   L15 重复死亡通知不重复计数、不提前推进波次
##   B  胜利条件由配置决定（victory = all_waves_cleared 时清场即胜、不需要走到出口）
##   C  无效配置拒绝开始（state=Failed + 可定位错误 + 零生成，不静默回退）
##   D  场景内手写 waves 兼容路径仍可用（旧场景数据不失效）
##
## 用法：godot --headless --path . -s res://Tests/test_level_orchestration.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

const ARENA_SCENE := "res://Scenes/TimedCombatArena.tscn"
const ENEMY_SCENE := "res://Scenes/Enemy.tscn"
const SHIPPED_LEVEL := "res://Levels/timed_combat_arena.json"
const ATTACK_ACTION := "p1_attack"
const MOVE_ACTION := "move_right"
const ATTACK_BUDGET := 10
const EXIT_BUDGET := 300
const EXIT_START := Vector2(560, 0)

## Phase 1.33（F4-B）：本运行专属目录。三个临时关卡配置不再写入共享的 `res://Levels`，
## 而是落在 `.ai/tmp/runs/<pid>-<16 位十六进制随机后缀，与 Python run_workspace 同一契约>/`；只有「本运行写入且内容未变」的资源才允许删除。
var _run_dir := _make_run_dir()
var TEMP_LEVEL := _run_dir + "/E2eLevelOrchestrationTest.json"
var TEMP_LEVEL_DIRECT_WIN := _run_dir + "/E2eLevelDirectWinTest.json"
var TEMP_LEVEL_INVALID := _run_dir + "/E2eLevelInvalidTest.json"
var _owned: Dictionary = {}

var _failures: PackedStringArray = []
var _finish_events: Array = []
var _temp_files: PackedStringArray = [TEMP_LEVEL, TEMP_LEVEL_DIRECT_WIN, TEMP_LEVEL_INVALID]


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


func _initialize() -> void:
	await _case_shipped_level_config()
	await _case_config_driven_waves()
	await _case_direct_victory_config()
	await _case_invalid_config_refused()
	await _case_legacy_scene_waves()
	_cleanup()
	_report()


## A：真实场景 + 随仓库发布的关卡配置（生成数量/波次/时长全部来自配置）
func _case_shipped_level_config() -> void:
	# 不覆盖 level_config_path：这里验证的是**随仓库发布的场景自身**已接线到配置
	var arena := await _load_arena()
	if arena == null:
		return
	if arena.level_config_path != SHIPPED_LEVEL:
		_fail("A: 发布场景 %s 应声明 level_config_path=%s，实际 %s"
			% [ARENA_SCENE, SHIPPED_LEVEL, arena.level_config_path])
	if not arena.get_config_errors().is_empty():
		_fail("A: 发布配置 %s 应被运行时接受，实际错误 %s"
			% [SHIPPED_LEVEL, arena.get_config_errors()])
	if arena.waves.size() != 3:
		_fail("A: 发布配置声明 3 波，运行时读到 %d 波" % arena.waves.size())
	if arena.alive_count != 3:
		_fail("A: 发布配置第一波 3 个敌人，运行时生成 %d 个" % arena.alive_count)
	if arena.get_exit_unlock_when() != "all_waves_cleared" \
			or arena.get_victory_condition() != "exit_reached_after_unlock":
		_fail("A: 出口/胜利规则应来自配置，实际 exit=%s victory=%s"
			% [arena.get_exit_unlock_when(), arena.get_victory_condition()])
	arena.queue_free()
	await process_frame


## L7–L15：临时配置（2 波：2 个 + 3 个）驱动生成、波次、出口与胜利
func _case_config_driven_waves() -> void:
	var config := _base_config("level_orchestration_test", [
		_wave("wave_1", 2), _wave("wave_2", 3),
	])
	if not _write_json(TEMP_LEVEL, config):
		_fail("L7: 无法写入临时配置 %s" % TEMP_LEVEL)
		return
	var arena := await _load_arena(TEMP_LEVEL)
	if arena == null:
		return
	var door: StaticBody2D = arena.get_node("Mechanism/ExitDoor")
	var player: CharacterBody2D = arena.get_node("Player")

	# ---- L7/L8: 数量来自配置（2，而不是场景内任何手写数据），并注册进既有管理链路 ----
	if arena.waves.size() != 2:
		_fail("L7: 配置声明 2 波，运行时读到 %d 波" % arena.waves.size())
	if arena.alive_count != 2:
		_fail("L7: 配置声明第一波 2 个敌人，运行时存活计数 %d" % arena.alive_count)
	if not arena.get_node("HUD/AliveLabel").text.contains("2"):
		_fail("L7: 存活标签应显示配置数量 2，实际 %s" % arena.get_node("HUD/AliveLabel").text)
	if abs(arena.current_duration() - 30.0) > 0.001:
		_fail("L7: 波次时长应来自配置（30.0），实际 %.2f" % arena.current_duration())
	var wave1 := _live_enemies(arena)
	if wave1.size() != 2:
		_fail("L8: 第一波应生成 2 个敌人节点，实际 %d" % wave1.size())
		arena.queue_free()
		await process_frame
		return
	for enemy in wave1:
		var health: Health = enemy.get_node_or_null("Health") as Health
		if health == null:
			_fail("L8: 生成敌人 %s 缺少 Health 组件" % enemy.name)
			continue
		if enemy.get("target_path") == null:
			_fail("L8: 生成敌人 %s 未注册进既有管理链路（target_path 未赋值）" % enemy.name)

	# ---- L9: 首波未清除时第二波不得生成 ----
	if arena.wave_index != 0 or _live_enemies(arena).size() != 2:
		_fail("L9: 首波未清除时不应生成第二波（wave_index=%d 存活 %d）"
			% [arena.wave_index, _live_enemies(arena).size()])
	# ---- L15（第一段）：真实攻击击杀一个敌人 → 计数恰好减一 ----
	var victim: CharacterBody2D = wave1[0]
	victim.global_position = player.global_position + Vector2(140, 0)
	wave1[1].global_position = player.global_position - Vector2(600, 0)
	await physics_frame
	var killed := await _kill_by_attack(victim)
	if not killed:
		_fail("L15: 真实攻击路径应在预算内击杀目标")
	if arena.alive_count != 1:
		_fail("L15: 一次有效死亡应使计数恰好减一，实际 %d" % arena.alive_count)
	if arena.wave_index != 0:
		_fail("L9: 首波仍有敌人存活时不应推进波次，实际 index %d" % arena.wave_index)

	# ---- L10 + L15（第二段）：清空首波 → 推进一次；重复 died 通知不得重复计数/推进 ----
	var last: CharacterBody2D = wave1[1]
	var last_health: Health = last.get_node("Health")
	last_health.take_damage(9999)          # 真实伤害接口 → died 一次 → 推进第二波
	var alive_after_advance: int = arena.alive_count
	var index_after_advance: int = arena.wave_index
	last_health.died.emit()                # 同一帧重复通知（受控负向输入）
	if arena.alive_count != alive_after_advance:
		_fail("L15: 重复 died 通知造成了重复计数（%d -> %d）"
			% [alive_after_advance, arena.alive_count])
	if arena.wave_index != index_after_advance:
		_fail("L15: 重复 died 通知造成了重复推进（index %d -> %d）"
			% [index_after_advance, arena.wave_index])
	if index_after_advance != 1:
		_fail("L10: 首波清空后应进入第二波（index 1），实际 %d" % index_after_advance)
	if alive_after_advance != 3:
		_fail("L10: 第二波应按配置生成 3 个敌人，实际存活计数 %d" % alive_after_advance)
	await process_frame
	var wave2 := _live_enemies(arena)
	if wave2.size() != 3:
		_fail("L10: 第二波应生成 3 个敌人节点，实际 %d" % wave2.size())

	# ---- L11: 第二波清除前出口保持关闭（逐个击杀并复查，避免只验终态） ----
	if door.is_open():
		_fail("L11: 第二波仍有敌人存活时出口不应打开")
	for index in wave2.size():
		var enemy: Node = wave2[index]
		if not is_instance_valid(enemy):
			continue
		enemy.get_node("Health").take_damage(9999)
		await process_frame
		var remaining := _live_enemies(arena).size()
		if remaining > 0 and door.is_open():
			_fail("L11: 仍有 %d 个敌人存活时出口不应打开" % remaining)
	if not door.is_open():
		_fail("L12: 全部必需波次清空后出口应开启（存活 %d，index %d）"
			% [arena.alive_count, arena.wave_index])
	if arena.state != arena.State.Playing:
		_fail("L12: 出口开启但玩家未进出口区时应仍为 Playing，实际 %d" % int(arena.state))

	# ---- L13/L14: 玩家真实输入走进出口区 → Completed，胜负事件恰好一次 ----
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
	arena.queue_free()
	await process_frame
	_finish_events.clear()


## B：胜利条件由配置决定（all_waves_cleared：清场即胜，不需要走到出口）
func _case_direct_victory_config() -> void:
	var config := _base_config("level_direct_win_test", [_wave("wave_1", 1)])
	config["victory"] = {"condition": "all_waves_cleared"}
	if not _write_json(TEMP_LEVEL_DIRECT_WIN, config):
		_fail("B: 无法写入临时配置 %s" % TEMP_LEVEL_DIRECT_WIN)
		return
	var arena := await _load_arena(TEMP_LEVEL_DIRECT_WIN)
	if arena == null:
		return
	if arena.get_victory_condition() != "all_waves_cleared":
		_fail("B: 胜利条件应来自配置（all_waves_cleared），实际 %s" % arena.get_victory_condition())
	var enemies := _live_enemies(arena)
	if enemies.size() != 1:
		_fail("B: 配置声明 1 个敌人，实际 %d" % enemies.size())
	if not enemies.is_empty():
		enemies[0].get_node("Health").take_damage(9999)
	await process_frame
	if arena.state != arena.State.Completed:
		_fail("B: victory=all_waves_cleared 时清场即应胜利（不需要走到出口），实际 %d"
			% int(arena.state))
	if _finish_events != [true]:
		_fail("B: 直接胜利路径的胜负事件应恰好一次，实际 %s" % str(_finish_events))
	if arena.get_node("Mechanism/ExitDoor").is_open():
		_fail("B: 直接胜利路径不应打开出口门")
	arena.queue_free()
	await process_frame
	_finish_events.clear()


## C：无效配置拒绝开始（可定位错误 + 零生成 + state=Failed）
func _case_invalid_config_refused() -> void:
	var config := _base_config("level_invalid_test", [_wave("wave_1", 2)])
	config["waves"][0]["entries"][0]["count"] = 0        # 非法数量
	if not _write_json(TEMP_LEVEL_INVALID, config):
		_fail("C: 无法写入临时配置 %s" % TEMP_LEVEL_INVALID)
		return
	var arena := await _load_arena(TEMP_LEVEL_INVALID)
	if arena == null:
		return
	if arena.get_config_errors().is_empty():
		_fail("C: 非法配置必须被运行时拒绝（count=0）")
	elif not arena.get_config_errors()[0].contains("count"):
		_fail("C: 配置错误信息应可定位到字段，实际 %s" % arena.get_config_errors()[0])
	if arena.state != arena.State.Failed:
		_fail("C: 配置无效时应拒绝开始（state=Failed），实际 %d" % int(arena.state))
	if _live_enemies(arena).size() != 0 or arena.alive_count != 0:
		_fail("C: 配置无效时不应生成任何敌人（存活 %d / 计数 %d）"
			% [_live_enemies(arena).size(), arena.alive_count])
	if arena.waves.size() != 0:
		_fail("C: 配置无效时不应静默回退到场景内数据（waves=%d）" % arena.waves.size())
	arena.queue_free()
	await process_frame


## D：场景内手写 waves 兼容路径（旧场景数据不失效）
func _case_legacy_scene_waves() -> void:
	var packed: PackedScene = load(ARENA_SCENE)
	if packed == null:
		_fail("D: 无法加载 %s" % ARENA_SCENE)
		return
	var arena: Node2D = packed.instantiate()
	var legacy: Array[Dictionary] = [{
		"enemy_scene": load(ENEMY_SCENE),
		"enemy_count": 1,
		"duration": 30.0,
	}]
	arena.level_config_path = ""
	arena.waves = legacy
	root.add_child(arena)
	await process_frame
	if arena.alive_count != 1:
		_fail("D: 手写 waves 兼容路径应生成 1 个敌人，实际 %d" % arena.alive_count)
	if not arena.get_config_errors().is_empty():
		_fail("D: 未配置 level_config_path 时不应报配置错误")
	arena.queue_free()
	await process_frame


# ---------- 辅助 ----------


func _base_config(level_id: String, waves: Array) -> Dictionary:
	return {
		"schema": {"id": "level_orchestration", "version": 1},
		"level": {"id": level_id, "arena_scene": ARENA_SCENE},
		"entities": {"enemy": {"scene": ENEMY_SCENE}},
		"waves": waves,
		"exit": {"unlock_when": "all_waves_cleared"},
		"victory": {"condition": "exit_reached_after_unlock"},
	}


func _wave(wave_id: String, count: int) -> Dictionary:
	return {"id": wave_id, "duration": 30.0, "entries": [{"entity": "enemy", "count": count}]}


func _load_arena(level_path: String = "") -> Node2D:
	var packed: PackedScene = load(ARENA_SCENE)
	if packed == null:
		_fail("无法加载竞技场场景 %s" % ARENA_SCENE)
		return null
	var arena: Node2D = packed.instantiate()
	if not level_path.is_empty():
		arena.level_config_path = level_path      # 必须在 _ready 之前设置
	arena.arena_finished.connect(_on_arena_finished)
	root.add_child(arena)
	await process_frame
	return arena


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


## 真实攻击输入路径击杀（与游戏内一致：空格攻击 → AttackTrigger → Health.take_damage）
func _kill_by_attack(enemy: Node) -> bool:
	var health: Health = enemy.get_node("Health")
	for _i: int in ATTACK_BUDGET:
		Input.action_press(ATTACK_ACTION)
		await physics_frame
		await physics_frame
		Input.action_release(ATTACK_ACTION)
		await physics_frame
		if not is_instance_valid(health) or health.is_dead():
			return true
	return false


func _on_arena_finished(success: bool) -> void:
	_finish_events.append(success)


func _write_json(path: String, data: Dictionary) -> bool:
	if _run_dir.is_empty():
		return false
	if DirAccess.open(_run_dir) == null:
		if DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(_run_dir)) != OK:
			return false
	var text := JSON.stringify(data, "  ") + "\n"
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return false
	file.store_string(text)
	file.close()
	_owned[path] = text.sha256_text()
	return true


func _cleanup() -> void:
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


func _fail(message: String) -> void:
	_failures.append(message)


func _report() -> void:
	for path in _temp_files:
		if FileAccess.file_exists(path):
			_failures.append("Z: 临时关卡配置未清理 %s" % path)
	if not _run_dir.is_empty() and DirAccess.dir_exists_absolute(ProjectSettings.globalize_path(_run_dir)):
		_failures.append("Z: 运行目录未清理 %s" % _run_dir)
	_report_foreign_leftovers()
	if _failures.is_empty():
		print("PASS: 关卡编排运行时验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
