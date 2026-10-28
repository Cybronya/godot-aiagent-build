extends SceneTree
## PatrolMovement 自身验证：空路径静止、循环模式抵达路径点并绕回、
## 往返模式端点折返、waypoint_reached 信号、单点驻留（不重复广播）。
##
## 等待策略：以 waypoint_reached 信号计数为等待条件（位置断言在其后），
## 不依赖固定帧数换算——headless 下 physics tick 与 await 节奏不严格 1:1。
##
## 用法：godot --headless --path . -s res://Features/patrol_movement/test_patrol_movement.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

var _failures: PackedStringArray = []
var _arrivals: Array[int] = []


func _initialize() -> void:
	var packed: PackedScene = load("res://Features/patrol_movement/PatrolMovement.tscn")
	if packed == null:
		_failures.append("加载 res://Features/patrol_movement/PatrolMovement.tscn 失败")
		_report()
		return

	# ---- 1. 空路径：静止不报错 ----
	var empty: CharacterBody2D = packed.instantiate()
	empty.position = Vector2(500, 500)
	root.add_child(empty)
	await _wait_frames(5)
	if empty.position != Vector2(500, 500):
		_failures.append("空路径应静止，实际 %s" % str(empty.position))
	empty.queue_free()
	await _wait_frames(1)

	# ---- 2. 循环模式：抵达点 0 → 绕回点 1 → 再回点 0 ----
	var host: CharacterBody2D = packed.instantiate()
	host.speed = 100.0
	var pts: Array[Vector2] = [Vector2(100, 0), Vector2(0, 0)]
	host.set("points", pts)
	root.add_child(host)
	host.waypoint_reached.connect(_on_waypoint)
	if not await _wait_until(func() -> bool: return _arrivals.size() >= 1, 300):
		_failures.append("应抵达并广播 waypoint_reached(0)，实际 %s pos=%s" % [str(_arrivals), str(host.position)])
	else:
		if host.position.distance_to(Vector2(100, 0)) > 2.0:
			_failures.append("抵达点应为 (100,0)，实际 %s" % str(host.position))
		if _arrivals != [0]:
			_failures.append("首次抵达应为 index 0，实际 %s" % str(_arrivals))
	if not await _wait_until(func() -> bool: return _arrivals.size() >= 2, 300):
		_failures.append("循环应绕回点 1 (0,0)，实际 %s pos=%s" % [str(_arrivals), str(host.position)])
	elif host.position.distance_to(Vector2.ZERO) > 2.0:
		_failures.append("第二抵达点应为原点，实际 %s" % str(host.position))
	if not await _wait_until(func() -> bool: return _arrivals.size() >= 3, 300):
		_failures.append("循环应完成完整一圈回到点 0，实际 %s pos=%s" % [str(_arrivals), str(host.position)])
	elif _arrivals[2] != 0:
		_failures.append("第三次抵达应为 index 0（绕回），实际 %s" % str(_arrivals))
	host.queue_free()
	await _wait_frames(1)

	# ---- 3. 往返模式（loop=false）：端点折返 ----
	_arrivals.clear()
	var pingpong: CharacterBody2D = packed.instantiate()
	pingpong.speed = 100.0
	pingpong.set("loop", false)
	var pts2: Array[Vector2] = [Vector2(80, 0), Vector2(160, 0)]
	pingpong.set("points", pts2)
	root.add_child(pingpong)
	pingpong.waypoint_reached.connect(_on_waypoint)
	if not await _wait_until(func() -> bool: return _arrivals.size() >= 2, 300):
		_failures.append("往返应依次抵达点 0 和点 1，实际 %s pos=%s" % [str(_arrivals), str(pingpong.position)])
	if not await _wait_until(func() -> bool: return _arrivals.size() >= 3, 300):
		_failures.append("端点应折返（第三次抵达），实际 %s pos=%s" % [str(_arrivals), str(pingpong.position)])
	elif pingpong.position.distance_to(Vector2(80, 0)) > 2.0:
		_failures.append("折返后应回到点 0，实际 %s" % str(pingpong.position))
	pingpong.queue_free()
	await _wait_frames(1)

	# ---- 4. 单点驻留：抵达一次后停住，不重复广播 ----
	_arrivals.clear()
	var single: CharacterBody2D = packed.instantiate()
	single.speed = 100.0
	var pts3: Array[Vector2] = [Vector2(50, 0)]
	single.set("points", pts3)
	root.add_child(single)
	single.waypoint_reached.connect(_on_waypoint)
	if not await _wait_until(func() -> bool: return _arrivals.size() >= 1, 300):
		_failures.append("单点应抵达并广播一次，实际 %s pos=%s" % [str(_arrivals), str(single.position)])
	var settled: Vector2 = single.position
	var arrivals_snapshot: int = _arrivals.size()
	await _wait_frames(15)
	if single.position.distance_to(settled) > 0.01:
		_failures.append("单点驻留后不应再移动，实际 %s" % str(single.position))
	if _arrivals.size() != arrivals_snapshot:
		_failures.append("驻留期间不应重复广播，实际 %s" % str(_arrivals))
	single.queue_free()

	_report()


func _on_waypoint(index: int) -> void:
	_arrivals.append(index)


func _wait_until(cond: Callable, max_frames: int) -> bool:
	for _i: int in max_frames:
		if cond.call():
			return true
		await physics_frame
	return false


func _wait_frames(count: int) -> void:
	for _i: int in count:
		await physics_frame


func _report() -> void:
	if _failures.is_empty():
		print("PASS: patrol_movement 全部检查通过")
		quit(0)
	else:
		for f in _failures:
			print("FAIL: ", f)
		quit(1)
