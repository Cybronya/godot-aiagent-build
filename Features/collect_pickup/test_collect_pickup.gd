extends SceneTree
## CollectPickup 组件自身验证：组内接触收集并消失、信号携带 pickup_id、
## 重复接触不重复收集、组外接触不收集、多实例独立。
##
## 用法：godot --headless --path . -s res://Features/collect_pickup/test_collect_pickup.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

const FRAME_BUDGET := 120

var _failures: PackedStringArray = []
var _events: Array = []


func _initialize() -> void:
	var packed: PackedScene = load("res://Features/collect_pickup/CollectPickup.tscn")
	if packed == null:
		_failures.append("加载 res://Features/collect_pickup/CollectPickup.tscn 失败")
		_report()
		return
	var player := _make_player(true)
	root.add_child(player)

	# 1. 组内接触：收集、广播 true + pickup_id、自移除
	var key_a: Area2D = packed.instantiate()
	key_a.pickup_id = "key_a"
	key_a.position = Vector2(0, 0)
	root.add_child(key_a)
	key_a.collected.connect(_on_collected)
	player.global_position = Vector2(0, 0)
	var gone := await _wait_pickup_gone(key_a)
	if not gone:
		_failures.append("接触后拾取物应被收集移除（等待超时）")
		_report()
		return
	if _events != [[true, "key_a"]]:
		_failures.append("collected 信号应广播 [true, pickup_id]，实际 %s" % str(_events))

	# 2. 已消失的拾取物：重复接触无第二次事件（节点已释放，天然幂等）
	var events_before := _events.size()

	# 3. 组外实体接触：不收集
	var outsider := _make_player(false)
	outsider.position = Vector2(400, 0)
	root.add_child(outsider)
	var key_b: Area2D = packed.instantiate()
	key_b.pickup_id = "key_b"
	key_b.position = Vector2(400, 0)
	root.add_child(key_b)
	key_b.collected.connect(_on_collected)
	await _wait_frames(30)
	if is_instance_valid(key_b) and key_b.is_collected():
		_failures.append("组外实体接触不应收集")
	if _events.size() != events_before:
		_failures.append("组外接触不应产生收集事件")
	key_b.queue_free()
	outsider.queue_free()
	await _wait_frames(2)

	# 4. 多实例独立 + 与 ConditionGate 的直连兼容性（与场景实际用法一致）
	var gate := Node.new()
	gate.set_script(load("res://Features/condition_gate/condition_gate.gd"))
	gate.condition_count = 2
	root.add_child(gate)
	gate.set_condition(true, "k1")
	var key_c: Area2D = packed.instantiate()
	key_c.pickup_id = "k2"
	key_c.position = Vector2(800, 0)
	root.add_child(key_c)
	# collected(value, pickup_id) 与 set_condition(value, id) 签名一致，直接连接
	key_c.collected.connect(Callable(gate, "set_condition"))
	player.global_position = Vector2(800, 0)
	await _wait_frames(10)
	if not gate.is_fulfilled():
		_failures.append("收集事件直连 set_condition 后应正确聚合（模拟场景直连）")

	player.queue_free()
	gate.queue_free()
	await _wait_frames(2)
	_report()


func _make_player(in_group: bool) -> CharacterBody2D:
	var body := CharacterBody2D.new()
	body.motion_mode = 1
	if in_group:
		body.add_to_group("players")
	var shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(24, 24)
	shape.shape = rect
	body.add_child(shape)
	return body


func _wait_pickup_gone(pickup: Area2D) -> bool:
	for _i: int in FRAME_BUDGET:
		if not is_instance_valid(pickup):
			return true
		await physics_frame
	return not is_instance_valid(pickup)


func _wait_frames(count: int) -> void:
	for _i: int in count:
		await physics_frame


func _on_collected(value: bool, pickup_id: String) -> void:
	_events.append([value, pickup_id])


func _report() -> void:
	if _failures.is_empty():
		print("PASS: CollectPickup 组件验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
