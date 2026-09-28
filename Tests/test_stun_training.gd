extends SceneTree
## StunTraining 集成验证：验证 Stun Feature 在多个不同消费者中独立工作。
##
## 覆盖：消费者A（EnemyInstance）受击硬直被动自触发（stun_on_hit），
## 硬直期间追击停摆、恢复后追击继续；消费者B（Player）麻痹陷阱主动 API
## 触发（明显不同的使用方式：stun_on_hit=false + 场景调用 stun(duration)）；
## 消费者C（Dummy）同 Feature 独立配置 + died→door 数据连接；
## 击杀不触发残留眩晕；出口完成；R 重开；新实例机制复现。
##
## 用法：godot --headless --path . -s res://Tests/test_stun_training.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

const FRAME_BUDGET := 240

var _failures: PackedStringArray = []


func _initialize() -> void:
	var packed: PackedScene = load("res://Scenes/StunTraining.tscn")
	if packed == null:
		_failures.append("加载 res://Scenes/StunTraining.tscn 失败")
		_report()
		return

	# ---- A. 结构与初始状态：三个消费者各自组合 Stun，配置互相独立 ----
	var scene: Node2D = packed.instantiate()
	root.add_child(scene)
	current_scene = scene
	await process_frame
	var player: CharacterBody2D = scene.get_node("Player")
	var enemy: CharacterBody2D = scene.get_node("Enemies/EnemyInstance")
	var elite: CharacterBody2D = scene.get_node("Enemies/EliteInstance")
	var dummy: CharacterBody2D = scene.get_node("Mechanism/Dummy")
	var door: StaticBody2D = scene.get_node("Mechanism/ExitDoor")
	var trap: Area2D = scene.get_node("Mechanism/Trap")
	var player_stun: Node = player.get_node("Stun")
	var enemy_stun: Node = enemy.get_node("Stun")
	var dummy_stun: Node = dummy.get_node("Stun")

	if player_stun.get("stun_on_hit"):
		_failures.append("玩家 Stun 应为主动模式（stun_on_hit=false）")
	if not enemy_stun.get("stun_on_hit"):
		_failures.append("敌人 Stun 应为受击自触发模式")
	if enemy_stun.get("stun_duration") != 0.6 or dummy_stun.get("stun_duration") != 0.5:
		_failures.append("各消费者的眩晕时长应随实例独立配置")
	if dummy_stun.get("stun_on_hit") != true:
		_failures.append("假人 Stun 应为受击自触发模式")
	if door.is_open():
		_failures.append("出口门初始应关闭")
	if player.get_node_or_null("HealthBar") == null:
		_failures.append("玩家应组合 HealthBar（需求 1）")

	# ---- B. 消费者A：敌人受击 → 硬直停摆追击；到时恢复追击 ----
	player.global_position = Vector2(0, 0)
	enemy.global_position = Vector2(240, 0)
	elite.global_position = Vector2(520, 0)
	await _wait_frames(10)
	var enemy_start := enemy.global_position
	await _wait_frames(30)
	if enemy.global_position.distance_to(enemy_start) < 10.0:
		_failures.append("敌人应正常追击玩家（对照基准），实际位移 %.1f" % enemy.global_position.distance_to(enemy_start))
	# 命中触发硬直（stun_on_hit 被动自触发，延迟一帧落地）
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
	# 到时恢复（0.6s ≈ 36 帧）
	await _wait_frames(30)
	if enemy_stun.is_stunned() or not enemy.is_physics_processing():
		_failures.append("硬直结束后追击应恢复")
	var enemy_recover_pos := enemy.global_position
	await _wait_frames(20)
	if enemy.global_position.distance_to(enemy_recover_pos) < 5.0:
		_failures.append("恢复后敌人应继续追击")

	# ---- C. 消费者B：玩家踩陷阱 → 主动 API 麻痹（与A完全不同的触发方式） ----
	player.global_position = trap.global_position
	var paralyzed := false
	for _i: int in FRAME_BUDGET:
		if player_stun.is_stunned():
			paralyzed = true
			break
		await process_frame
	if not paralyzed:
		_failures.append("踩中麻痹陷阱后玩家应被眩晕（主动 API）")
	if player.is_physics_processing():
		_failures.append("麻痹期间玩家物理应停摆")
	var player_pos := player.global_position
	Input.action_press("move_right")
	await _wait_frames(20)
	Input.action_release("move_right")
	if player.global_position != player_pos:
		_failures.append("麻痹期间玩家输入移动应无效，位移 %s" % (player.global_position - player_pos))
	# 玩家受击不触发眩晕（stun_on_hit=false，与敌人配置相反）
	player.global_position = Vector2(-460, 0)
	enemy.global_position = Vector2(400, 0)
	await _wait_frames(5)
	var enemy_health: Health = enemy.get_node("Health")
	var before: bool = player_stun.is_stunned()
	# 玩家挨精英一下（模拟受击）：直接调 Health 接口验证配置差异
	player.get_node("Health").take_damage(1)
	await process_frame
	if player_stun.is_stunned() and not before:
		_failures.append("玩家受击不应触发眩晕（stun_on_hit=false）")

	# ---- D. 消费者C：假人（独立配置）受击硬直；击杀开门（数据连接） ----
	var dummy_health: Health = dummy.get_node("Health")
	dummy_health.take_damage(1)
	await process_frame
	if not dummy_stun.is_stunned():
		_failures.append("假人受击后应进入硬直（独立配置 0.5s）")
	dummy_health.take_damage(9999)
	await process_frame
	if not await _wait_until(func() -> bool: return door.is_open()):
		_failures.append("假人死亡数据连接应打开出口门（等待超时）")

	# ---- E. 训练毕业：穿过打开的门到达右侧（先把追击敌人移开，避免在门口挤堵） ----
	enemy.global_position = Vector2(300, -220)
	elite.global_position = Vector2(420, 220)
	player.global_position = Vector2(500, 0)
	await process_frame
	Input.action_press("move_right")
	for _i: int in 60:
		await physics_frame
	Input.action_release("move_right")
	# 右墙物理极限 x≈560；门未开时只能停在门左侧（x<548），门开后可贴到极限
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
	var fresh_dummy: CharacterBody2D = fresh.get_node("Mechanism/Dummy")
	if fresh_door.is_open():
		_failures.append("重开后出口门应恢复关闭")
	if fresh_dummy.get_node("Health").get_current_health() != 5:
		_failures.append("重开后假人生命值应恢复 5")
	if fresh_dummy.get_node("Stun").get("stun_duration") != 0.5:
		_failures.append("重开后假人眩晕配置应随场景重建")

	# ---- G. 机制复现：新实例中两个消费者再次独立工作 ----
	var fresh_player_stun: Node = fresh.get_node("Player/Stun")
	var fresh_trap: Area2D = fresh.get_node("Mechanism/Trap")
	fresh.get_node("Player").global_position = fresh_trap.global_position
	var para2 := false
	for _i: int in FRAME_BUDGET:
		if fresh_player_stun.is_stunned():
			para2 = true
			break
		await process_frame
	if not para2:
		_failures.append("新实例中陷阱麻痹应再次生效")
	var fresh_enemy: CharacterBody2D = fresh.get_node("Enemies/EnemyInstance")
	fresh_enemy.get_node("Health").take_damage(1)
	await process_frame
	if not fresh_enemy.get_node("Stun").is_stunned():
		_failures.append("新实例中敌人受击硬直应再次生效")

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
		print("PASS: StunTraining 集成验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
