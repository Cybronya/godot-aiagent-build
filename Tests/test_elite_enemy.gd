extends SceneTree
## Elite Enemy 集成验证：基于真实 SurvivalArena.tscn 与 EliteEnemy.tscn。
##
## 覆盖：参数覆写（高血量/高接触伤害/慢速）、零行为复制结构断言（与普通
## Enemy 共用同一批 Feature 脚本实例）、追踪玩家、接触伤害为 2、死亡后
## 移除、结束状态冻结、生成时序接入且不破坏胜利路径。
##
## 用法：godot --headless --path . -s res://Tests/test_elite_enemy.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。
##
## 注意：GDScript lambda 对局部变量按值捕获，事件计数必须使用成员变量。

const FRAME_BUDGET := 240

var _failures: PackedStringArray = []
var _player_damage_amounts: Array[int] = []


func _initialize() -> void:
	var packed: PackedScene = load("res://Scenes/SurvivalArena.tscn")
	var elite_scene: PackedScene = load("res://Scenes/EliteEnemy.tscn")
	var normal_scene: PackedScene = load("res://Scenes/Enemy.tscn")
	if packed == null or elite_scene == null or normal_scene == null:
		_failures.append("加载 SurvivalArena/EliteEnemy/Enemy 场景失败")
		_report()
		return

	# ---- A. 参数覆写：精英差异全部由场景实例参数表达 ----
	var elite_preview: CharacterBody2D = elite_scene.instantiate()
	root.add_child(elite_preview)
	var normal_preview: CharacterBody2D = normal_scene.instantiate()
	root.add_child(normal_preview)
	await process_frame
	var elite_health: Health = elite_preview.get_node("Health")
	if elite_health.max_health != 15 or elite_health.get_current_health() != 15:
		_failures.append("精英血量覆写应为 15，实际 max=%d current=%d" % [elite_health.max_health, elite_health.get_current_health()])
	var elite_contact: Area2D = elite_preview.get_node("ContactDamage")
	if elite_contact.damage != 2:
		_failures.append("精英接触伤害覆写应为 2，实际 %d" % elite_contact.damage)
	if elite_preview.speed != 50.0:
		_failures.append("精英速度覆写应为 50，实际 %s" % elite_preview.speed)

	# ---- B. 零行为复制结构断言：与普通 Enemy 实例化同一批 Feature 脚本 ----
	if elite_preview.get_script() != normal_preview.get_script():
		_failures.append("精英与普通敌人根脚本应为同一 chase_movement.gd 实例")
	if elite_preview.get_script().resource_path != "res://Features/chase_movement/chase_movement.gd":
		_failures.append("精英根脚本应来自 Features/chase_movement，实际 %s" % elite_preview.get_script().resource_path)
	var elite_contact_script: Script = elite_contact.get_script()
	var normal_contact_script: Script = normal_preview.get_node("ContactDamage").get_script()
	if elite_contact_script != normal_contact_script:
		_failures.append("精英与普通敌人 ContactDamage 应为同一组件脚本实例")
	if elite_preview.get_scene_file_path() == normal_preview.get_scene_file_path():
		_failures.append("精英与普通敌人应是两个独立场景（组合差异），不应共享同一场景资源")
	elite_preview.queue_free()
	normal_preview.queue_free()
	await _wait_frames(2)

	# ---- C. 真实场景生成：追踪玩家（计入 enemies 组） ----
	var arena: Node2D = packed.instantiate()
	root.add_child(arena)
	current_scene = arena
	await process_frame
	arena.spawn_interval = 9999.0
	arena._spawn_enemy(elite_scene)
	var spawned := get_nodes_in_group("enemies")
	if spawned.size() != 1:
		_failures.append("通过生成器生成精英后 enemies 组应有 1 个成员，实际 %d" % spawned.size())
		_report()
		return
	var elite: CharacterBody2D = spawned[0]
	var player: CharacterBody2D = arena.get_node("Player")
	var player_health: Health = player.get_node("Health")
	player_health.health_changed.connect(_on_player_health_changed)
	var distance_before: float = elite.global_position.distance_to(player.global_position)
	await _wait_frames(40)
	var distance_after: float = elite.global_position.distance_to(player.global_position)
	if distance_after > distance_before - 20.0:
		_failures.append("精英应追踪玩家：距离从 %.1f 只变为 %.1f" % [distance_before, distance_after])

	# ---- D. 接触伤害为 2（事件驱动等待第一次伤害结算） ----
	elite.global_position = player.global_position + Vector2(20, 0)
	var damaged := false
	for _i: int in FRAME_BUDGET:
		if not _player_damage_amounts.is_empty():
			damaged = true
			break
		await physics_frame
	if not damaged:
		_failures.append("精英接触后应对玩家造成伤害（等待超时）")
		_report()
		return
	for amount: int in _player_damage_amounts:
		if amount != 2:
			_failures.append("精英每次接触伤害应为 2（普通敌人为 1），实际 %d" % amount)
	if player_health.get_current_health() >= 10 or player_health.is_dead():
		_failures.append("玩家应受伤但不应死亡，实际 HP=%d" % player_health.get_current_health())
	# 立即冻结该精英，避免后续断言被持续伤害干扰
	elite.set_physics_process(false)
	elite.get_node("ContactDamage").set_physics_process(false)

	# ---- E. 死亡后正确移除（与普通敌人共用 died → queue_free 接线） ----
	var victim_health: Health = elite.get_node("Health")
	victim_health.take_damage(9999)
	var removed := false
	for _i: int in FRAME_BUDGET:
		if not is_instance_valid(elite):
			removed = true
			break
		await process_frame
	if not removed:
		_failures.append("精英死亡后应从场景移除（等待超时）")

	# ---- F. 结束状态冻结精英（enemies 组统一冻结覆盖精英） ----
	arena._spawn_enemy(elite_scene)
	var elite2: CharacterBody2D = get_nodes_in_group("enemies")[0]
	arena._finish(true)
	if arena.state != arena.State.Won:
		_failures.append("调用 _finish(true) 后应进入 Won 状态，实际 %d" % arena.state)
	var frozen_pos: Vector2 = elite2.global_position
	await _wait_frames(20)
	if elite2.global_position.distance_to(frozen_pos) > 1.0:
		_failures.append("结束状态后精英应停止追踪，实际位移 %s" % (elite2.global_position - frozen_pos))

	# ---- G. 生成时序：elite_spawn_delay 到点后自动生成精英，且不破坏胜利路径 ----
	var fast: Node2D = packed.instantiate()
	fast.survival_duration = 2.0
	fast.elite_spawn_delay = 0.5
	root.add_child(fast)
	current_scene = fast
	var elite_spawned := false
	for _i: int in FRAME_BUDGET:
		if _has_elite(fast):
			elite_spawned = true
			break
		await process_frame
	if not elite_spawned:
		_failures.append("elite_spawn_delay 到点后应自动生成精英（等待超时）")
	for _i: int in FRAME_BUDGET:
		if fast.state != fast.State.Playing:
			break
		await process_frame
	if fast.state != fast.State.Won:
		_failures.append("存在精英时存活到时限仍应以胜利结束，实际状态 %d" % fast.state)

	_report()


func _has_elite(arena: Node2D) -> bool:
	for entity: Node in arena.get_node("Entities").get_children():
		if entity.name.begins_with("EliteEnemy"):
			return true
	return false


func _wait_frames(count: int) -> void:
	for _i: int in count:
		await physics_frame


func _on_player_health_changed(_current: int, amount: int) -> void:
	_player_damage_amounts.append(amount)


func _report() -> void:
	if _failures.is_empty():
		print("PASS: Elite Enemy 集成验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
