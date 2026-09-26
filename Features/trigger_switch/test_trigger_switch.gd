extends SceneTree
## TriggerSwitch 组件自身验证：一次性触发语义（离开不回退、重进不重复触发）、
## Repeat 模式、组过滤、reset 恢复初始状态。
##
## 用法：godot --headless --path . -s res://Features/trigger_switch/test_trigger_switch.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。
##
## 目标实体用本地构建的 CharacterBody2D（players 组），不依赖游戏侧场景。

const FRAME_BUDGET := 120

var _failures: PackedStringArray = []
var _events: Array[bool] = []


func _initialize() -> void:
	var packed: PackedScene = load("res://Features/trigger_switch/TriggerSwitch.tscn")
	if packed == null:
		_failures.append("加载 res://Features/trigger_switch/TriggerSwitch.tscn 失败")
		_report()
		return
	var shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(48, 48)
	shape.shape = rect
	var intruder := _make_player(true)
	root.add_child(intruder)

	# 1. Latching 模式：首次进入触发；离开后重新进入不重复触发
	var sw: Area2D = packed.instantiate()
	sw.add_child(shape.duplicate())
	sw.position = Vector2(0, 0)
	root.add_child(sw)
	sw.activated.connect(_on_activated)
	intruder.global_position = Vector2(0, 0)
	if not await _wait_for_events(1):
		_failures.append("Latching 开关首次进入应触发（等待超时）")
		_report()
		return
	if not sw.is_triggered():
		_failures.append("触发后 is_triggered 应为 true")
	intruder.global_position = Vector2(300, 300)
	await _wait_frames(20)
	intruder.global_position = Vector2(0, 0)
	await _wait_frames(20)
	if _events.size() != 1:
		_failures.append("Latching 开关重进范围不应重复触发，实际 %d 次" % _events.size())

	# 2. reset()：状态回 false 并广播 false；之后可再次触发
	var count_before := _events.size()
	sw.reset()
	if sw.is_triggered():
		_failures.append("reset 后 is_triggered 应为 false")
	if _events.size() != count_before + 1 or _events[_events.size() - 1] != false:
		_failures.append("reset 应广播一次 activated(false)")
	intruder.global_position = Vector2(300, 300)
	await _wait_frames(10)
	intruder.global_position = Vector2(0, 0)
	if not await _wait_for_events(count_before + 2):
		_failures.append("reset 后再次进入应重新触发（等待超时）")

	# 3. Repeat 模式：每次进入范围都触发
	var sw2: Area2D = packed.instantiate()
	sw2.add_child(shape.duplicate())
	sw2.set("trigger_mode", 1)
	sw2.position = Vector2(600, 0)
	root.add_child(sw2)
	sw2.activated.connect(_on_activated)
	var repeat_baseline := _events.size()
	intruder.global_position = Vector2(600, 0)
	await _wait_frames(10)
	intruder.global_position = Vector2(900, 0)
	await _wait_frames(10)
	intruder.global_position = Vector2(600, 0)
	await _wait_frames(10)
	if _events.size() != repeat_baseline + 2:
		_failures.append("Repeat 开关两次进入应触发 2 次，实际 %d 次" % (_events.size() - repeat_baseline))

	# 4. 组外实体进入：不触发（使用全新 Latching 开关）
	var outsider := _make_player(false)
	root.add_child(outsider)
	var sw3: Area2D = packed.instantiate()
	sw3.add_child(shape.duplicate())
	sw3.position = Vector2(1200, 0)
	root.add_child(sw3)
	sw3.activated.connect(_on_activated)
	var group_baseline := _events.size()
	outsider.global_position = Vector2(1200, 0)
	await _wait_frames(30)
	if _events.size() != group_baseline:
		_failures.append("组外实体进入不应触发开关")

	intruder.queue_free()
	outsider.queue_free()
	sw.queue_free()
	sw2.queue_free()
	sw3.queue_free()
	await _wait_frames(2)
	_report()


func _make_player(in_group: bool) -> CharacterBody2D:
	var body := CharacterBody2D.new()
	body.motion_mode = 1
	if in_group:
		body.add_to_group("players")
	var body_shape := CollisionShape2D.new()
	var body_rect := RectangleShape2D.new()
	body_rect.size = Vector2(24, 24)
	body_shape.shape = body_rect
	body.add_child(body_shape)
	return body


func _wait_for_events(expected: int) -> bool:
	for _i: int in FRAME_BUDGET:
		if _events.size() >= expected:
			return true
		await physics_frame
	return _events.size() >= expected


func _wait_frames(count: int) -> void:
	for _i: int in count:
		await physics_frame


func _on_activated(triggered: bool) -> void:
	_events.append(triggered)


func _report() -> void:
	if _failures.is_empty():
		print("PASS: TriggerSwitch 组件验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
