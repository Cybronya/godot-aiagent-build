extends SceneTree
## MovingPlatform 组件自身验证：平台位置往返变化、载客区玩家被携带、
## 离开载客区后不再被携带。
##
## 用法：godot --headless --path . -s res://Features/moving_platform/test_moving_platform.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

const FRAME_BUDGET := 240

var _failures: PackedStringArray = []


func _initialize() -> void:
	var packed: PackedScene = load("res://Features/moving_platform/MovingPlatform.tscn")
	if packed == null:
		_failures.append("加载 res://Features/moving_platform/MovingPlatform.tscn 失败")
		_report()
		return

	# 1. 平台往返：位置随时间明显变化，且能回到接近起点的对称位置
	var platform: AnimatableBody2D = packed.instantiate()
	root.add_child(platform)
	await _wait_frames(2)
	var origin: Vector2 = platform.global_position
	var min_offset := 0.0
	var max_offset := 0.0
	for _i: int in 120:
		await physics_frame
		var offset := platform.global_position.x - origin.x
		min_offset = minf(min_offset, offset)
		max_offset = maxf(max_offset, offset)
	if max_offset < 80.0:
		_failures.append("平台应向 +travel 方向移动，实际最大偏移 %.1f" % max_offset)
	if min_offset > 1.0:
		_failures.append("平台应能回到起点附近（三角波对称），实际最小偏移 %.1f" % min_offset)

	# 2. 渡载：玩家进入载客区后被平台携带（位移量与平台一致量级）
	var player := CharacterBody2D.new()
	player.motion_mode = 1
	player.add_to_group("players")
	var shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(24, 24)
	shape.shape = rect
	player.add_child(shape)
	root.add_child(player)
	await _wait_frames(2)
	# 等平台回到起点附近再上车
	for _i: int in FRAME_BUDGET:
		if platform.global_position.distance_to(origin) < 8.0:
			break
		await physics_frame
	player.global_position = origin + Vector2(0, 32)
	await _wait_frames(10)
	var carried := false
	var pos_before: Vector2 = player.global_position
	for _i: int in 45:
		await physics_frame
		if player.global_position.distance_to(pos_before) > 20.0:
			carried = true
			break
	if not carried:
		_failures.append("载客区内的玩家应被平台携带移动，45 帧累积位移 %.1f" % player.global_position.distance_to(pos_before))

	# 3. 下车：玩家离开载客区后位置不再随平台变化
	player.global_position = origin + Vector2(300, 0)
	await _wait_frames(6)
	var stay := player.global_position
	for _i: int in 30:
		await physics_frame
	if player.global_position.distance_to(stay) > 2.0:
		_failures.append("离开载客区后玩家不应再被携带，实际位移 %s" % (player.global_position - stay))

	player.queue_free()
	platform.queue_free()
	await _wait_frames(2)
	_report()


func _wait_frames(count: int) -> void:
	for _i: int in count:
		await physics_frame


func _report() -> void:
	if _failures.is_empty():
		print("PASS: MovingPlatform 组件验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
