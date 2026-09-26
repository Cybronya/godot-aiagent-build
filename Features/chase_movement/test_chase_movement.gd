extends SceneTree
## ChaseMovement 组件自身验证：朝目标移动、目标释放后停止、无目标时静止。
##
## 用法：godot --headless --path . -s res://Features/chase_movement/test_chase_movement.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。
##
## 目标探针用本地构建的 StaticBody2D：Feature 验证自包含，
## 不依赖游戏侧实体场景（如 Player.tscn），保持复用边界。

const FRAME_WAIT := 20
const MIN_DELTA := 4.0

var _failures: PackedStringArray = []
var _chase: CharacterBody2D
var _probe: StaticBody2D


func _initialize() -> void:
	var packed: PackedScene = load("res://Features/chase_movement/ChaseMovement.tscn")
	if packed == null:
		_failures.append("加载 res://Features/chase_movement/ChaseMovement.tscn 失败")
		_report()
		return
	_probe = _make_probe()
	root.add_child(_probe)

	_chase = packed.instantiate()
	_chase.target_path = NodePath("../Probe")
	root.add_child(_chase)
	await _wait_frames(2)

	# 1. 朝目标移动：与目标的距离随时间明显缩短
	var distance_before: float = _probe.global_position.distance_to(_chase.global_position)
	await _wait_frames(FRAME_WAIT)
	var distance_after: float = _probe.global_position.distance_to(_chase.global_position)
	if distance_after > distance_before - MIN_DELTA:
		_failures.append("应朝目标接近：距离从 %.1f 只变为 %.1f" % [distance_before, distance_after])

	# 2. 目标被释放后停止移动（is_instance_valid 保护）
	_probe.queue_free()
	await _wait_frames(2)
	var stopped_at: Vector2 = _chase.global_position
	await _wait_frames(10)
	if _chase.global_position.distance_to(stopped_at) > 1.0:
		_failures.append("目标释放后应停止移动，实际位移 %s" % (_chase.global_position - stopped_at))

	# 3. 无目标配置时保持静止
	var idle: CharacterBody2D = packed.instantiate()
	root.add_child(idle)
	await _wait_frames(2)
	var idle_origin: Vector2 = idle.global_position
	await _wait_frames(10)
	if idle.global_position.distance_to(idle_origin) > 1.0:
		_failures.append("无目标时应保持静止，实际位移 %s" % (idle.global_position - idle_origin))

	idle.queue_free()
	_chase.queue_free()
	await _wait_frames(2)
	_report()


func _make_probe() -> StaticBody2D:
	var probe := StaticBody2D.new()
	probe.name = "Probe"
	probe.position = Vector2(200, 0)
	var visual := Polygon2D.new()
	visual.polygon = PackedVector2Array([Vector2(-12, -12), Vector2(12, -12), Vector2(12, 12), Vector2(-12, 12)])
	visual.color = Color(1, 0.9, 0.3)
	probe.add_child(visual)
	return probe


func _wait_frames(count: int) -> void:
	for _i: int in count:
		await physics_frame


func _report() -> void:
	if _failures.is_empty():
		print("PASS: ChaseMovement 组件验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
