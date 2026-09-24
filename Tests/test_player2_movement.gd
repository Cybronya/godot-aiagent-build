extends SceneTree
## 游戏级集成验证：确认第二角色 Player2 通过 p2_* 动作（WASD）四向移动。
##
## 用法：godot --headless --path . -s res://Tests/test_player2_movement.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

const FRAME_WAIT := 20
const MIN_DELTA := 8.0

var _player2: CharacterBody2D
var _failures: PackedStringArray = []


func _initialize() -> void:
	var packed: PackedScene = load("res://Scenes/Player2.tscn")
	if packed == null:
		_failures.append("加载 res://Scenes/Player2.tscn 失败")
		_report()
		return
	_player2 = packed.instantiate()
	root.add_child(_player2)
	_run()


func _run() -> void:
	var cases := {
		"p2_up": Vector2(0, -MIN_DELTA),
		"p2_down": Vector2(0, MIN_DELTA),
		"p2_left": Vector2(-MIN_DELTA, 0),
		"p2_right": Vector2(MIN_DELTA, 0),
	}
	for action: String in cases:
		var from: Vector2 = _player2.global_position
		Input.action_press(action)
		await _wait_frames(FRAME_WAIT)
		Input.action_release(action)
		await _wait_frames(2)
		var moved: Vector2 = _player2.global_position - from
		if moved.dot(cases[action]) < MIN_DELTA * MIN_DELTA:
			_failures.append("%s 未按预期移动，实际位移 %s" % [action, moved])
	_report()


func _wait_frames(count: int) -> void:
	for _i: int in count:
		await physics_frame


func _report() -> void:
	if _failures.is_empty():
		print("PASS: Player2 四向移动验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
