extends SceneTree
## OpenableDoor 组件自身验证：初始关闭与阻挡、开启后通行、视觉同步、
## 重复设置同值无副作用、再次关闭恢复阻挡、start_open 实例。
##
## 用法：godot --headless --path . -s res://Features/openable_door/test_openable_door.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

const PUSH_FRAMES := 90
const PUSH_SPEED := 120.0

var _failures: PackedStringArray = []
var _events: Array[bool] = []


func _initialize() -> void:
	var packed: PackedScene = load("res://Features/openable_door/OpenableDoor.tscn")
	if packed == null:
		_failures.append("加载 res://Features/openable_door/OpenableDoor.tscn 失败")
		_report()
		return
	var door: StaticBody2D = packed.instantiate()
	door.position = Vector2(0, 0)
	root.add_child(door)
	door.state_changed.connect(_on_state_changed)
	var walker := _make_walker()
	root.add_child(walker)
	await process_frame

	# 1. 初始状态：关闭、广播 false、视觉为关闭色
	if door.is_open():
		_failures.append("初始门应为关闭状态")
	if _events != [false]:
		_failures.append("初始应广播一次 activated 状态 false，实际 %s" % str(_events))
	if door.get_node("Visual").color != door.closed_visual_color:
		_failures.append("关闭状态视觉应为关闭色")

	# 2. 关闭的门阻挡：向门推进行走体，应停在门表面
	await _push_through(walker)
	if walker.global_position.x > -15.0:
		_failures.append("关闭的门应阻挡通行，实际 walker x=%.1f" % walker.global_position.x)

	# 3. set_open(true)：广播 true、碰撞停用、视觉切换、可以穿过
	door.set_open(true)
	await process_frame
	if not door.is_open() or _events != [false, true]:
		_failures.append("set_open(true) 状态/广播不正确，实际 %s" % str(_events))
	if not door.get_node("Collision").disabled:
		_failures.append("门打开后碰撞应停用")
	if door.get_node("Visual").color != door.open_visual_color:
		_failures.append("门打开后视觉应为开启色")
	walker.global_position = Vector2(-120, 0)
	await _push_through(walker)
	if walker.global_position.x < 15.0:
		_failures.append("门打开后应可穿过，实际 walker x=%.1f" % walker.global_position.x)

	# 4. 重复设置同值：无副作用、不重复广播
	var events_before := _events.size()
	door.set_open(true)
	await process_frame
	if _events.size() != events_before:
		_failures.append("重复 set_open(同值) 不应重复广播")

	# 5. set_open(false)：恢复阻挡
	door.set_open(false)
	await process_frame
	if door.is_open():
		_failures.append("set_open(false) 后应为关闭状态")
	if door.get_node("Collision").disabled:
		_failures.append("门关闭后碰撞应恢复启用")
	walker.global_position = Vector2(-120, 0)
	await _push_through(walker)
	if walker.global_position.x > -15.0:
		_failures.append("重新关闭后应恢复阻挡，实际 walker x=%.1f" % walker.global_position.x)

	# 6. start_open 实例：入树即开启
	var door2: StaticBody2D = packed.instantiate()
	door2.start_open = true
	root.add_child(door2)
	await process_frame
	if not door2.is_open() or not door2.get_node("Collision").disabled:
		_failures.append("start_open 实例入树应为开启且不阻挡")

	door.queue_free()
	door2.queue_free()
	walker.queue_free()
	await _wait_frames(2)
	_report()


func _make_walker() -> CharacterBody2D:
	var body := CharacterBody2D.new()
	body.motion_mode = 1
	var shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(24, 24)
	shape.shape = rect
	body.add_child(shape)
	# 裸 CharacterBody2D 只设 velocity 不会移动，必须有脚本调用 move_and_slide()
	#（与 PlayerController 同一驱动语义）；这里动态挂一个最小移动脚本。
	var mover := GDScript.new()
	mover.source_code = "extends CharacterBody2D\n\nfunc _physics_process(_delta: float) -> void:\n\tmove_and_slide()\n"
	mover.reload()
	body.set_script(mover)
	return body


## 从门左侧向右匀速推进 walker，观察阻挡/通行行为。
func _push_through(walker: CharacterBody2D) -> void:
	walker.global_position = Vector2(-120, 0)
	walker.velocity = Vector2(PUSH_SPEED, 0)
	for _i: int in PUSH_FRAMES:
		await physics_frame
	walker.velocity = Vector2.ZERO


func _wait_frames(count: int) -> void:
	for _i: int in count:
		await physics_frame


func _on_state_changed(is_open: bool) -> void:
	_events.append(is_open)


func _report() -> void:
	if _failures.is_empty():
		print("PASS: OpenableDoor 组件验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
