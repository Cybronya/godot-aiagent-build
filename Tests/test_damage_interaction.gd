extends SceneTree
## 游戏级伤害交互验证：基于真实 main.tscn，模拟攻击动作，
## 验证 Player2 按既有 Health 规则受击、死亡规则生效、事件实际触发。
##
## 用法：godot --headless --path . -s res://Tests/test_damage_interaction.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。
##
## 注意：GDScript lambda 对局部变量按值捕获，事件计数必须使用成员变量。

const ATTACK_ACTION := "p1_attack"

var _failures: PackedStringArray = []
var _died_count := 0


func _initialize() -> void:
	var packed: PackedScene = load("res://Scenes/main.tscn")
	if packed == null:
		_failures.append("加载 res://Scenes/main.tscn 失败")
		_report()
		return
	var main: Node = packed.instantiate()
	root.add_child(main)
	await process_frame

	var player: CharacterBody2D = main.get_node("Player")
	var player2: CharacterBody2D = main.get_node("Player2")
	var player_health: Health = player.get_node("Health")
	var player2_health: Health = player2.get_node("Health")
	player2_health.died.connect(_on_died)

	# 1. 初始生命值正确
	if player_health.get_current_health() != 10:
		_failures.append("Player 初始生命值应为 10（max_health 覆写），实际 %d" % player_health.get_current_health())
	if player2_health.get_current_health() != 8:
		_failures.append("Player2 初始生命值应为 8，实际 %d" % player2_health.get_current_health())

	# 2. 一次攻击：Player2 生命值按现有规则 -1
	await _press_attack()
	if player2_health.get_current_health() != 7:
		_failures.append("一次攻击后 Player2 生命值应为 7，实际 %d" % player2_health.get_current_health())

	# 3. 攻击者自身生命值不受影响
	if player_health.get_current_health() != 10:
		_failures.append("攻击者 Player 生命值不应变化，实际 %d" % player_health.get_current_health())

	# 4. 持续攻击到死亡：共需 8 次有效攻击，死亡规则与事件按现有系统生效
	for _i: int in 7:
		await _press_attack()
	if not player2_health.is_dead():
		_failures.append("8 次攻击后 Player2 应进入死亡状态")
	if player2_health.get_current_health() != 0:
		_failures.append("死亡时 Player2 生命值应为 0，实际 %d" % player2_health.get_current_health())
	if _died_count != 1:
		_failures.append("died 应恰好触发 1 次，实际 %d" % _died_count)

	# 5. 死亡后继续攻击：按现有规则被忽略
	await _press_attack()
	if player2_health.get_current_health() != 0 or _died_count != 1:
		_failures.append("死亡后攻击应被忽略")

	main.queue_free()
	await process_frame
	_report()


func _press_attack() -> void:
	Input.action_press(ATTACK_ACTION)
	await physics_frame
	await physics_frame
	Input.action_release(ATTACK_ACTION)
	await physics_frame


func _on_died() -> void:
	_died_count += 1


func _report() -> void:
	if _failures.is_empty():
		print("PASS: 角色间伤害交互验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
