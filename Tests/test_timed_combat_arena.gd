extends SceneTree
## Timed Combat Arena 集成验证：基于真实 TimedCombatArena.tscn 的完整行为链路。
##
## 覆盖：初始阶段与敌人生成、两套敌人配置共用同一机制（普通/精英混编）、
## 敌人死亡计数与退出战斗、提前清场立即进入下一阶段、倒计时推进、
## 超时失败、下一阶段重新生成（不同配置）、最终阶段清场打开出口、
## 出口完成、玩家死亡失败、R 重开恢复初始状态、机制在新实例中复现。
##
## 用法：godot --headless --path . -s res://Tests/test_timed_combat_arena.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

const FRAME_BUDGET := 240

var _failures: PackedStringArray = []
var _finish_events: Array = []


func _initialize() -> void:
	var packed: PackedScene = load("res://Scenes/TimedCombatArena.tscn")
	if packed == null:
		_failures.append("加载 res://Scenes/TimedCombatArena.tscn 失败")
		_report()
		return

	# ---- A. 初始阶段：第一波敌人生成、计数、HUD 就绪 ----
	var arena: Node2D = packed.instantiate()
	root.add_child(arena)
	current_scene = arena
	arena.arena_finished.connect(func(success: bool) -> void: _finish_events.append(success))
	await process_frame
	var player: CharacterBody2D = arena.get_node("Player")
	var player_health: Health = player.get_node("Health")
	var entities: Node2D = arena.get_node("Entities")
	var exit_door: StaticBody2D = arena.get_node("Mechanism/ExitDoor")

	if not player.is_in_group("players"):
		_failures.append("玩家应加入 players 组（组件契约）")
	if player_health.get_current_health() != 10:
		_failures.append("玩家初始生命值应为 10，实际 %d" % player_health.get_current_health())
	if arena.state != arena.State.Playing:
		_failures.append("初始应处于 Playing 状态")
	if arena.wave_index != 0:
		_failures.append("初始应为第 1 阶段（index 0），实际 %d" % arena.wave_index)
	if arena.alive_count != 3:
		_failures.append("第一波应生成 3 个敌人，实际存活 %d" % arena.alive_count)
	if not arena.get_node("HUD/AliveLabel").text.contains("3"):
		_failures.append("存活标签应显示 3，实际 %s" % arena.get_node("HUD/AliveLabel").text)
	if exit_door.is_open():
		_failures.append("出口门初始应关闭")

	# ---- B. 敌人配置一：第一波全部为普通敌人 ----
	var wave1_enemies: Array[Node] = []
	for child in entities.get_children():
		if child.is_in_group("enemies"):
			wave1_enemies.append(child)
	if wave1_enemies.size() != 3:
		_failures.append("第一波应实例化 3 个敌人节点，实际 %d" % wave1_enemies.size())
	for enemy in wave1_enemies:
		if String(enemy.name).begins_with("Elite"):
			_failures.append("第一波不应包含精英敌人")
		var enemy_health: Health = enemy.get_node("Health")
		if enemy_health.max_health != 5:
			_failures.append("普通敌人 max_health 应为 5（Enemy.tscn 配置），实际 %d" % enemy_health.max_health)

	# ---- C. 敌人死亡 → 计数递减 + 退出战斗（died 驱动，同一机制覆盖所有配置） ----
	var victim: CharacterBody2D = wave1_enemies[0]
	var victim_health: Health = victim.get_node("Health")
	victim_health.take_damage(9999)
	if arena.alive_count != 2:
		_failures.append("一个敌人死亡后存活数应为 2，实际 %d" % arena.alive_count)
	if not arena.get_node("HUD/AliveLabel").text.contains("2"):
		_failures.append("存活标签应更新为 2，实际 %s" % arena.get_node("HUD/AliveLabel").text)
	var removed := false
	for _i: int in FRAME_BUDGET:
		if not is_instance_valid(victim) or victim.is_queued_for_deletion():
			removed = true
			break
		await process_frame
	if not removed:
		_failures.append("被击败的敌人应从战斗中退出（等待超时）")

	# ---- D. 提前清场 → 立即进入下一阶段（不等待倒计时） ----
	# died 回调同步推进波次：最后一个敌人死亡的同一帧内第二波已生成，
	# 因此可观测的是「波次立即推进 + 新波计数」，递减中间态已由 C 阶段验证
	for enemy in [wave1_enemies[1], wave1_enemies[2]]:
		enemy.get_node("Health").take_damage(9999)
	if arena.wave_index != 1:
		_failures.append("提前清场应立即（同帧）进入第 2 阶段（index 1），实际 %d" % arena.wave_index)
	if not arena.get_node("HUD/WaveLabel").text.contains("2"):
		_failures.append("阶段标签应显示 2，实际 %s" % arena.get_node("HUD/WaveLabel").text)
	if arena.alive_count != 3:
		_failures.append("第二波生成后存活数应为 3，实际 %d" % arena.alive_count)
	var timer_text: String = arena.get_node("HUD/TimerLabel").text
	if timer_text.begins_with("倒计时: 30.0"):
		_failures.append("新阶段倒计时应重置，实际 %s" % timer_text)

	# ---- E. 敌人配置二：第二波为普通+精英混编，共用同一套生成/计数机制 ----
	# 等待上一波 queue_free 尸体真正出树，并过滤仍在删除队列中的节点
	await process_frame
	var wave2_enemies: Array[Node] = []
	var elite: CharacterBody2D = null
	for child in entities.get_children():
		if child.is_in_group("enemies") and not child.is_queued_for_deletion():
			wave2_enemies.append(child)
			if String(child.name).begins_with("Elite"):
				elite = child
	if wave2_enemies.size() != 3:
		_failures.append("第二波应生成 2 普通 + 1 精英 = 3 个敌人，实际 %d" % wave2_enemies.size())
	if elite == null:
		_failures.append("第二波应包含精英敌人（Enemy 场景之外的第二种配置）")
	else:
		var elite_health: Health = elite.get_node("Health")
		if elite_health.max_health != 15:
			_failures.append("精英敌人 max_health 应为 15（EliteEnemy.tscn 配置），实际 %d" % elite_health.max_health)
	if arena.alive_count != 3:
		_failures.append("第二波开始后存活数应为 3，实际 %d" % arena.alive_count)

	# ---- F. 倒计时推进（HUD 累计显示） ----
	var timer_before: String = arena.get_node("HUD/TimerLabel").text
	await _wait_frames(40)
	var timer_after: String = arena.get_node("HUD/TimerLabel").text
	if timer_before == timer_after:
		_failures.append("倒计时标签应随时间推进变化")

	# ---- G. 第二波清场 → 第三波；第三波清场 → 出口门打开（最终阶段） ----
	for enemy in wave2_enemies:
		if is_instance_valid(enemy):
			enemy.get_node("Health").take_damage(9999)
	await process_frame
	if arena.wave_index != 2:
		_failures.append("第二波清场应进入第 3 阶段（index 2），实际 %d" % arena.wave_index)
	var wave3_enemies: Array[Node] = []
	for child in entities.get_children():
		if child.is_in_group("enemies") and is_instance_valid(child) and not child.is_queued_for_deletion():
			wave3_enemies.append(child)
	if wave3_enemies.size() != 5:
		_failures.append("第三波应生成 4 普通 + 1 精英 = 5 个敌人，实际 %d" % wave3_enemies.size())
	for enemy in wave3_enemies:
		if is_instance_valid(enemy):
			enemy.get_node("Health").take_damage(9999)
	await process_frame
	if not exit_door.is_open():
		_failures.append("最终阶段清场后出口门应打开")
	if arena.state != arena.State.Playing:
		_failures.append("出口门打开但未进出口区时仍应为 Playing，实际 %d" % arena.state)

	# ---- H. 玩家进入出口 → 挑战完成（真实输入驱动穿门） ----
	player.global_position = Vector2(560, 0)
	await process_frame
	Input.action_press("move_right")
	var finished := false
	for _i: int in FRAME_BUDGET:
		if arena.state == arena.State.Completed:
			finished = true
			break
		await physics_frame
	Input.action_release("move_right")
	if not finished:
		_failures.append("玩家穿出口门进入出口区应完成挑战，实际 state=%d x=%.1f" % [arena.state, player.global_position.x])
	else:
		if not arena.get_node("HUD/StatusLabel").text.contains("挑战完成"):
			_failures.append("完成后状态栏应提示挑战完成")
		if _finish_events != [true]:
			_failures.append("arena_finished 应以 success=true 发出一次，实际 %s" % str(_finish_events))

	# ---- I. 玩家死亡 → 挑战失败（新实例） ----
	var arena2: Node2D = packed.instantiate()
	root.add_child(arena2)
	arena2.arena_finished.connect(func(success: bool) -> void: _finish_events.append(false if not success else true))
	await process_frame
	var health2: Health = arena2.get_node("Player/Health")
	health2.take_damage(9999)
	await process_frame
	if arena2.state != arena2.State.Failed:
		_failures.append("玩家死亡后应进入 Failed 状态，实际 %d" % arena2.state)
	arena2.queue_free()
	await process_frame

	# ---- J. 超时失败：倒计时耗尽仍有敌人存活（加速实例，真实计时路径） ----
	var arena3: Node2D = packed.instantiate()
	root.add_child(arena3)
	arena3.waves[0]["duration"] = 0.5
	await process_frame
	if arena3.alive_count != 3:
		_failures.append("加速实例第一波应生成 3 个敌人，实际 %d" % arena3.alive_count)
	var timed_out := false
	for _i: int in FRAME_BUDGET:
		if arena3.state == arena3.State.Failed:
			timed_out = true
			break
		await process_frame
	if not timed_out:
		_failures.append("倒计时耗尽且仍有敌人存活应进入 Failed 状态，实际 %d" % arena3.state)
	arena3.queue_free()
	await process_frame

	# ---- K. R 重开恢复初始状态（真实重开路径） ----
	Input.action_press("restart")
	var reloaded := false
	for _i: int in FRAME_BUDGET:
		if current_scene != arena:
			reloaded = true
			break
		await process_frame
	Input.action_release("restart")
	if not reloaded:
		_failures.append("结束状态下按 R 应重新加载场景（等待超时）")
		_report()
		return
	await process_frame
	var fresh: Node2D = current_scene
	if fresh == arena or fresh == null:
		_failures.append("重开后应得到全新场景实例")
		_report()
		return
	if fresh.state != fresh.State.Playing:
		_failures.append("重开后应回到 Playing 状态，实际 %d" % fresh.state)
	if fresh.wave_index != 0:
		_failures.append("重开后应回到第 1 阶段，实际 %d" % fresh.wave_index)
	if fresh.alive_count != 3:
		_failures.append("重开后第一波应重新生成 3 个敌人，实际 %d" % fresh.alive_count)
	if fresh.get_node("Mechanism/ExitDoor").is_open():
		_failures.append("重开后出口门应恢复关闭")
	if fresh.get_node("Player/Health").get_current_health() != 10:
		_failures.append("重开后玩家生命值应恢复 10")

	# ---- L. 机制复现：新实例中两套敌人配置 + 提前完成再次工作 ----
	var fresh_enemies: Array[Node] = []
	for child in fresh.get_node("Entities").get_children():
		if child.is_in_group("enemies"):
			fresh_enemies.append(child)
	for enemy in fresh_enemies:
		enemy.get_node("Health").take_damage(9999)
	await process_frame
	if fresh.wave_index != 1:
		_failures.append("新实例中提前清场应再次立即进入第 2 阶段，实际 %d" % fresh.wave_index)
	var has_elite := false
	var fresh_wave2 := 0
	for child in fresh.get_node("Entities").get_children():
		if child.is_in_group("enemies") and is_instance_valid(child) and not child.is_queued_for_deletion():
			fresh_wave2 += 1
			if String(child.name).begins_with("Elite"):
				has_elite = true
	if fresh_wave2 != 3 or not has_elite:
		_failures.append("新实例第二波应再次生成 2 普通 + 1 精英，实际 %d 个，精英 %s" % [fresh_wave2, has_elite])

	_report()


func _wait_frames(count: int) -> void:
	for _i: int in count:
		await physics_frame


func _report() -> void:
	if _failures.is_empty():
		print("PASS: TimedCombatArena 集成验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
