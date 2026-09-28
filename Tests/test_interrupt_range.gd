extends SceneTree
## InterruptRange 集成验证：验证既有能力（stun/chase/health/attack_trigger）
## 在新场景中的组合复用，不引入任何新 Feature。
##
## 覆盖：消费者A（EnemyInstance）受击硬直被动自触发与恢复；
## 消费者B（ReactiveTarget，chase 移动）被绊线机关第三方定身与恢复
## （机关不晕触发者自身）；硬直中击杀不被恢复逻辑复活；
## died→door 数据连接毕业；R 重开；新实例机制复现。
##
## 用法：godot --headless --path . -s res://Tests/test_interrupt_range.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

const FRAME_BUDGET := 240

var _failures: PackedStringArray = []


func _initialize() -> void:
	var packed: PackedScene = load("res://Scenes/InterruptRange.tscn")
	if packed == null:
		_failures.append("加载 res://Scenes/InterruptRange.tscn 失败")
		_report()
		return

	# ---- A. 结构与初始状态：两个消费者各自组合 Stun，配置独立 ----
	var scene: Node2D = packed.instantiate()
	root.add_child(scene)
	current_scene = scene
	await process_frame
	var player: CharacterBody2D = scene.get_node("Player")
	var enemy: CharacterBody2D = scene.get_node("Enemies/EnemyInstance")
	var target: CharacterBody2D = scene.get_node("Mechanism/ReactiveTarget")
	var door: StaticBody2D = scene.get_node("Mechanism/ExitDoor")
	var tripwire: Area2D = scene.get_node("Mechanism/Tripwire")
	var enemy_stun: Node = enemy.get_node("Stun")
	var target_stun: Node = target.get_node("Stun")

	if not enemy.is_in_group("enemies"):
		_failures.append("敌人应处于 enemies 组（攻击目标解析前提）")
	if target.is_in_group("enemies"):
		_failures.append("ReactiveTarget 不应在 enemies 组（避免被攻击选中）")
	if not enemy_stun.get("stun_on_hit"):
		_failures.append("敌人 Stun 应为受击自触发模式")
	if target_stun.get("stun_on_hit"):
		_failures.append("ReactiveTarget Stun 应为纯主动模式（机关触发）")
	if door.is_open():
		_failures.append("出口门初始应关闭")
	if not target.is_physics_processing():
		_failures.append("ReactiveTarget 初始应可移动（chase 根脚本）")

	# ---- B. 消费者A：敌人受击 → 硬直停摆追击；到时恢复追击 ----
	player.global_position = Vector2(0, 0)
	enemy.global_position = Vector2(240, 0)
	target.global_position = Vector2(150, -150)
	await _wait_frames(10)
	var enemy_start := enemy.global_position
	await _wait_frames(30)
	if enemy.global_position.distance_to(enemy_start) < 10.0:
		_failures.append("敌人应正常追击玩家（对照基准）")
	enemy.get_node("Health").take_damage(1)
	await process_frame
	if not enemy_stun.is_stunned():
		_failures.append("敌人受击后应进入硬直")
	if enemy.is_physics_processing():
		_failures.append("硬直期间追击应停摆")
	var stunned_pos := enemy.global_position
	await _wait_frames(15)
	if enemy.global_position != stunned_pos:
		_failures.append("硬直期间敌人不应移动")
	await _wait_frames(30)
	if enemy_stun.is_stunned() or not enemy.is_physics_processing():
		_failures.append("硬直结束后追击应恢复")
	var enemy_recover_pos := enemy.global_position
	await _wait_frames(20)
	if enemy.global_position.distance_to(enemy_recover_pos) < 5.0:
		_failures.append("恢复后敌人应继续追击")

	# ---- C. 消费者B：玩家踩绊线 → 机关对第三方目标定身（不晕触发者） ----
	player.global_position = tripwire.global_position
	var triggered := false
	for _i: int in FRAME_BUDGET:
		if target_stun.is_stunned():
			triggered = true
			break
		await process_frame
	if not triggered:
		_failures.append("踩中绊线后牵引目标应被定身（第三方路由）")
	var player_stun: Node = player.get_node("Stun")
	if player.has_node("Stun") and player_stun.is_stunned():
		_failures.append("绊线不应定身触发者自身（与 paralyze_trap 语义区分）")
	if target.is_physics_processing():
		_failures.append("定身期间目标 chase 应停摆")
	var target_pos := target.global_position
	await _wait_frames(20)
	if target.global_position != target_pos:
		_failures.append("定身期间目标不应移动")
	# 目标定身 1.0s ≈ 60 帧，恢复后 chase 继续朝玩家移动
	await _wait_frames(50)
	if target_stun.is_stunned() or not target.is_physics_processing():
		_failures.append("定身结束后目标应恢复移动")
	var target_recover_pos := target.global_position
	await _wait_frames(20)
	if target.global_position == target_recover_pos:
		_failures.append("恢复后目标应继续追击（chase 复用验证）")

	# ---- D. 死亡竞态：硬直中击杀 → 恢复逻辑不得复活死亡实体 ----
	player.global_position = Vector2(-460, 0)
	await _wait_frames(5)
	enemy.get_node("Health").take_damage(1)
	await process_frame
	if not enemy_stun.is_stunned():
		_failures.append("死亡竞态前置：敌人应先进入硬直")
	enemy.get_node("Health").take_damage(9999)
	await process_frame
	if not enemy_stun.is_stunned():
		_failures.append("击杀命中不应解除既有硬直")
	# 硬直到点（0.6s ≈ 36 帧）：恢复逻辑不得重新启用死亡实体物理
	await _wait_frames(50)
	if enemy_stun.is_stunned():
		_failures.append("死亡后硬直应到时结束")
	if enemy.is_physics_processing():
		_failures.append("死亡实体不得被恢复逻辑重新启用物理")
	if not await _wait_until(func() -> bool: return door.is_open()):
		_failures.append("敌人死亡数据连接应打开出口门（等待超时）")

	# ---- E. 训练毕业：穿过打开的门到达右侧（先移开追击目标避免挤堵） ----
	target.global_position = Vector2(300, -220)
	player.global_position = Vector2(500, 0)
	await process_frame
	Input.action_press("move_right")
	for _i: int in 60:
		await physics_frame
	Input.action_release("move_right")
	if player.global_position.x < 555.0:
		_failures.append("门开后玩家应能穿过门到达右侧，实际 x=%.1f" % player.global_position.x)

	# ---- F. R 重开（真实重开路径） ----
	Input.action_press("restart")
	var reloaded := false
	for _i: int in FRAME_BUDGET:
		if current_scene != scene:
			reloaded = true
			break
		await process_frame
	Input.action_release("restart")
	if not reloaded:
		_failures.append("按 R 应重新加载场景（等待超时）")
		_report()
		return
	await process_frame
	var fresh: Node2D = current_scene
	if fresh == scene or fresh == null:
		_failures.append("重开后应得到全新场景实例")
		_report()
		return
	var fresh_door: StaticBody2D = fresh.get_node("Mechanism/ExitDoor")
	var fresh_enemy: CharacterBody2D = fresh.get_node("Enemies/EnemyInstance")
	if fresh_door.is_open():
		_failures.append("重开后出口门应恢复关闭")
	if fresh_enemy.get_node("Health").is_dead():
		_failures.append("重开后敌人应复活")
	if fresh_enemy.get_node("Stun").get("stun_duration") != 0.6:
		_failures.append("重开后敌人眩晕配置应随场景重建")

	# ---- G. 机制复现：新实例中两个消费者再次独立工作 ----
	var fresh_target: CharacterBody2D = fresh.get_node("Mechanism/ReactiveTarget")
	var fresh_tripwire: Area2D = fresh.get_node("Mechanism/Tripwire")
	fresh_enemy.get_node("Health").take_damage(1)
	await process_frame
	if not fresh_enemy.get_node("Stun").is_stunned():
		_failures.append("新实例中敌人受击硬直应再次生效")
	fresh.get_node("Player").global_position = fresh_tripwire.global_position
	var para2 := false
	for _i: int in FRAME_BUDGET:
		if fresh_target.get_node("Stun").is_stunned():
			para2 = true
			break
		await process_frame
	if not para2:
		_failures.append("新实例中绊线定身应再次生效")

	_report()


func _wait_until(predicate: Callable) -> bool:
	for _i: int in FRAME_BUDGET:
		if predicate.call():
			return true
		await process_frame
	return false


func _wait_frames(count: int) -> void:
	for _i: int in count:
		await physics_frame


func _report() -> void:
	if _failures.is_empty():
		print("PASS: InterruptRange 集成验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
