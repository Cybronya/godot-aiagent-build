extends SceneTree
## 游戏级集成验证：基于真实 SurvivalArena.tscn，验证生存竞技场的完整行为链路。
##
## 覆盖：玩家组约定、初始状态、敌人接触伤害链路（组合层→Health）与 UI 同步、
## 拾取恢复与 max_health 上限、死亡后移动冻结与结束状态、重开轮询、
## 加速实例的胜利路径。
##
## 用法：godot --headless --path . -s res://Tests/test_survival_arena.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。
##
## 注意：GDScript lambda 对局部变量按值捕获，事件计数必须使用成员变量。

const FRAME_BUDGET := 240

var _failures: PackedStringArray = []
var _winner := -1


func _initialize() -> void:
	var packed: PackedScene = load("res://Scenes/SurvivalArena.tscn")
	if packed == null:
		_failures.append("加载 res://Scenes/SurvivalArena.tscn 失败")
		_report()
		return

	# ---- 阶段 A：竞技场就绪与初始状态 ----
	var arena: Node2D = packed.instantiate()
	root.add_child(arena)
	# -s 脚本模式无 current_scene，显式指定以覆盖重开逻辑（reload_current_scene）
	current_scene = arena
	await process_frame
	var player: CharacterBody2D = arena.get_node("Player")
	var player_health: Health = player.get_node("Health")
	var entities: Node2D = arena.get_node("Entities")

	if not player.is_in_group("players"):
		_failures.append("Player 实体应加入 players 组（ContactDamage/HealPickup 目标约定）")
	if player_health.get_current_health() != 10:
		_failures.append("Player 初始生命值应为 10，实际 %d" % player_health.get_current_health())
	if entities.get_child_count() != 1:
		_failures.append("开局应已生成 1 个拾取物，实际 %d 个" % entities.get_child_count())
	var timer_label: Label = arena.get_node("HUD/TimerLabel")
	if not timer_label.text.begins_with("生存时间: 0.0"):
		_failures.append("计时标签初始应显示 0.0，实际 %s" % timer_label.text)

	# ---- 阶段 B：敌人接触伤害链路（组合层 → Health → HUD/血条同步） ----
	var enemy: CharacterBody2D = load("res://Scenes/Enemy.tscn").instantiate()
	enemy.position = player.global_position + Vector2(30, 0)
	enemy.target_path = NodePath("../Player")
	entities.add_child(enemy)
	var hp_after_tick := await _wait_until(func() -> bool: return player_health.get_current_health() < 10)
	if hp_after_tick < 0:
		_failures.append("敌人接触后应造成伤害（等待超时）")
		_report()
		return
	enemy.set_physics_process(false)
	var health_label: Label = arena.get_node("HUD/HealthLabel")
	if health_label.text != "HP: %d / 10" % player_health.get_current_health():
		_failures.append("HUD 应同步显示当前生命值，实际 %s" % health_label.text)
	var bar_ratio: float = player.get_node("HealthBar").get_ratio()
	var expected_ratio: float = float(player_health.get_current_health()) / 10.0
	if absf(bar_ratio - expected_ratio) > 0.001:
		_failures.append("玩家血条比例应与生命值同步，实际 %.2f（期望 %.2f）" % [bar_ratio, expected_ratio])

	# ---- 阶段 C：拾取恢复 + max_health 上限钳制 ----
	var hp_before_pickup := player_health.get_current_health()
	var pickup: Area2D = load("res://Features/heal_pickup/HealPickup.tscn").instantiate()
	pickup.position = player.global_position
	entities.add_child(pickup)
	if not await _wait_pickup_gone(pickup):
		_failures.append("受伤状态下拾取物应被消费")
	if player_health.get_current_health() != mini(hp_before_pickup + 2, 10):
		_failures.append("拾取恢复应为 min(%d+2, 10)，实际 %d" % [hp_before_pickup, player_health.get_current_health()])
	if player_health.get_current_health() > player_health.max_health:
		_failures.append("恢复后生命值不得超过 max_health")
	# 满血时第二件拾取物不消费（若阶段 C 已回满）
	if player_health.get_current_health() == player_health.max_health:
		var pickup2: Area2D = load("res://Features/heal_pickup/HealPickup.tscn").instantiate()
		pickup2.position = player.global_position + Vector2(8, 0)
		entities.add_child(pickup2)
		await _wait_frames(40)
		if not is_instance_valid(pickup2) or pickup2.is_queued_for_deletion():
			_failures.append("满血状态下拾取物不应被消费")

	# ---- 阶段 D：玩家死亡 → 冻结移动 + 结束状态 ----
	player_health.take_damage(9999)
	await process_frame
	if arena.state != arena.State.Lost:
		_failures.append("玩家死亡后竞技场应进入 Lost 状态，实际 %d" % arena.state)
	var status_label: Label = arena.get_node("HUD/StatusLabel")
	if not status_label.text.contains("死亡"):
		_failures.append("死亡后状态栏应提示死亡，实际 %s" % status_label.text)
	var dead_pos: Vector2 = player.global_position
	Input.action_press("move_right")
	await _wait_frames(20)
	Input.action_release("move_right")
	await _wait_frames(2)
	if player.global_position.distance_to(dead_pos) > 1.0:
		_failures.append("玩家死亡后不应继续移动，实际位移 %s" % (player.global_position - dead_pos))

	# ---- 阶段 E2：敌人死亡后正确移除（died 信号接线；须在场景重载前验证） ----
	# 只有经 _spawn_enemy 生成的敌人才带组与接线，直接调用生成器保证确定性
	arena._spawn_enemy()
	var victim: CharacterBody2D = null
	var spawned_enemies := get_nodes_in_group("enemies")
	if not spawned_enemies.is_empty():
		victim = spawned_enemies[0]
	if victim == null:
		_failures.append("生成的敌人应加入 enemies 组")
	var victim_health: Health = victim.get_node("Health")
	victim_health.take_damage(9999)
	var enemy_removed := false
	for _i: int in FRAME_BUDGET:
		if not is_instance_valid(victim):
			enemy_removed = true
			break
		await process_frame
	if not enemy_removed:
		_failures.append("敌人死亡后应从场景移除（等待超时）")

	# ---- 阶段 E：结束状态下轮询重开 ----
	Input.action_press("restart")
	var reloaded := await _wait_until(func() -> bool:
		return root.get_tree().current_scene != null and root.get_tree().current_scene != arena)
	Input.action_release("restart")
	if not reloaded:
		_failures.append("结束状态下按重开应重新加载场景（等待超时）")
		_report()
		return
	await _wait_frames(3)
	var fresh_arena: Node2D = root.get_tree().current_scene
	var fresh_player: CharacterBody2D = fresh_arena.get_node("Player")
	var fresh_health: Health = fresh_player.get_node("Health")
	if fresh_arena.state != fresh_arena.State.Playing:
		_failures.append("重开后竞技场应回到 Playing 状态，实际 %d" % fresh_arena.state)
	if fresh_health.get_current_health() != 10:
		_failures.append("重开后玩家生命值应为 10，实际 %d" % fresh_health.get_current_health())
	if fresh_arena.get_node("Entities").get_child_count() != 1:
		_failures.append("重开后应重新生成开局拾取物")
	var fresh_timer: Label = fresh_arena.get_node("HUD/TimerLabel")
	if not fresh_timer.text.begins_with("生存时间: 0.0"):
		_failures.append("重开后计时应归零，实际 %s" % fresh_timer.text)

	# ---- 阶段 F：胜利路径（加速实例，不等待真实 30 秒） ----
	var fast: Node2D = packed.instantiate()
	fast.survival_duration = 0.5
	root.add_child(fast)
	fast.arena_finished.connect(func(won: bool) -> void: _winner = 1 if won else 0)
	var finished := await _wait_until(func() -> bool: return _winner != -1)
	if not finished:
		_failures.append("加速实例应在生存时长到达后进入结束状态（等待超时）")
	else:
		if _winner != 1:
			_failures.append("存活到达时限应以胜利结束，实际 winner=%d" % _winner)
		if fast.state != fast.State.Won:
			_failures.append("胜利时竞技场应处于 Won 状态，实际 %d" % fast.state)
		if not fast.get_node("HUD/StatusLabel").text.contains("生存成功"):
			_failures.append("胜利后状态栏应提示生存成功")

	_report()


## 逐帧等待谓词成立；返回等待期间最后一次采样值，超时返回 -1。
func _wait_until(predicate: Callable) -> int:
	for _i: int in FRAME_BUDGET:
		if predicate.call():
			return 1
		await process_frame
	return -1 if not predicate.call() else 1


func _wait_pickup_gone(pickup: Area2D) -> bool:
	for _i: int in FRAME_BUDGET:
		if not is_instance_valid(pickup) or pickup.is_queued_for_deletion():
			return true
		await physics_frame
	return false


func _wait_frames(count: int) -> void:
	for _i: int in count:
		await physics_frame


func _report() -> void:
	if _failures.is_empty():
		print("PASS: SurvivalArena 集成验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
