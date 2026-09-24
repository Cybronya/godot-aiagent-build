extends SceneTree
## 游戏级集成验证：Player / Player2 实体组合 Health 后的接口、复用与事件触发。
##
## 用法：godot --headless --path . -s res://Tests/test_health_integration.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。
##
## 注意：GDScript 的 lambda 对局部变量按值捕获，事件计数必须使用成员变量。

var _failures: PackedStringArray = []
var _changed_count := 0
var _died_count := 0


func _initialize() -> void:
	await _verify_player()
	await _verify_player2()
	if _failures.is_empty():
		print("PASS: Health 集成验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)


func _verify_player() -> void:
	var packed: PackedScene = load("res://Features/player_movement/Player.tscn")
	if packed == null:
		_failures.append("加载 Player.tscn 失败")
		return
	var player: CharacterBody2D = packed.instantiate()
	root.add_child(player)
	await process_frame
	var health: Health = player.get_node("Health")
	_died_count = 0
	health.died.connect(_on_died)
	if health.get_current_health() != 5:
		_failures.append("Player 初始生命值应为 5，实际 %d" % health.get_current_health())
	health.take_damage(2)
	if health.get_current_health() != 3:
		_failures.append("Player 受 2 点伤害后应为 3，实际 %d" % health.get_current_health())
	health.take_damage(9999)
	if health.get_current_health() != 0 or not health.is_dead() or _died_count != 1:
		_failures.append("Player 致命伤害后死亡状态/事件不正确")
	player.queue_free()
	await process_frame


func _verify_player2() -> void:
	var packed: PackedScene = load("res://Scenes/Player2.tscn")
	if packed == null:
		_failures.append("加载 Player2.tscn 失败")
		return
	var player2: CharacterBody2D = packed.instantiate()
	root.add_child(player2)
	await process_frame
	var health: Health = player2.get_node("Health")
	_changed_count = 0
	_died_count = 0
	health.health_changed.connect(_on_changed)
	health.died.connect(_on_died)
	if health.get_current_health() != 8:
		_failures.append("Player2 初始生命值应为 8（max_health 覆写），实际 %d" % health.get_current_health())
	health.take_damage(3)
	if health.get_current_health() != 5:
		_failures.append("Player2 受 3 点伤害后应为 5，实际 %d" % health.get_current_health())
	if _changed_count != 1:
		_failures.append("Player2 health_changed 应触发 1 次，实际 %d" % _changed_count)
	health.take_damage(9999)
	if health.get_current_health() != 0 or not health.is_dead() or _died_count != 1:
		_failures.append("Player2 致命伤害后死亡状态/事件不正确")
	player2.queue_free()
	await process_frame


func _on_changed(_current: int, _amount: int) -> void:
	_changed_count += 1


func _on_died() -> void:
	_died_count += 1
