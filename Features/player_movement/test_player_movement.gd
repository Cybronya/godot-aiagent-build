extends SceneTree
## 无头运行时验证：模拟方向键输入，确认 Player 四向移动符合预期。
##
## 用法：godot --headless --path . -s res://Features/player_movement/test_player_movement.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

const FRAME_WAIT := 20
const MIN_DELTA := 8.0

var _player: CharacterBody2D
var _failures: PackedStringArray = []


func _initialize() -> void:
	var packed: PackedScene = load("res://Features/player_movement/Player.tscn")
	if packed == null:
		_failures.append("加载 res://Features/player_movement/Player.tscn 失败")
		_report()
		return
	_player = packed.instantiate()
	root.add_child(_player)
	_run()


func _run() -> void:
	var origin: Vector2 = _player.global_position
	var cases := {
		"move_up": Vector2(0, -MIN_DELTA),
		"move_down": Vector2(0, MIN_DELTA),
		"move_left": Vector2(-MIN_DELTA, 0),
		"move_right": Vector2(MIN_DELTA, 0),
	}
	for action: String in cases:
		var from: Vector2 = _player.global_position
		Input.action_press(action)
		await _wait_frames(FRAME_WAIT)
		Input.action_release(action)
		await _wait_frames(2)
		var moved: Vector2 = _player.global_position - from
		if moved.dot(cases[action]) < MIN_DELTA * MIN_DELTA:
			_failures.append("%s 未按预期移动，实际位移 %s" % [action, moved])
	_player.global_position = origin
	await _wait_frames(2)
	_report()


func _wait_frames(count: int) -> void:
	for _i: int in count:
		await physics_frame


func _report() -> void:
	if _failures.is_empty():
		print("PASS: 方向键四向移动验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
