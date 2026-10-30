extends SceneTree
## EVAL136 probe — T3 条件判断 / 事件联动（collect_pickup ×2 → condition_gate → openable_door）
##
## 用法：godot --headless --path . -s res://Tests/eval136_key_door_probe.gd -- <scene> <full|partial>
##
## 断言真实运行时状态（门的通行状态 / 条件聚合结果 / 信号次数），不是连接声明存在：
##   full    —— 初始：未满足且门关闭；拿到第 1 把钥匙：仍未满足、门仍关闭（不得提前开门）；
##              拿到第 2 把钥匙：条件满足恰好广播 1 次、门打开、门的碰撞形状被禁用
##   partial —— 只拿第 1 把钥匙：条件永不满足、门始终关闭、fulfilled 一次都不发
##              （受控负向：证明「开门」断言依赖两把钥匙都真实收集，而非恒真）
## 退出码：0 = 断言全部通过；1 = 断言失败或前置条件不成立；2 = 参数/环境错误。

const PLAYER_SCENE := "res://Features/player_movement/Player.tscn"

var _failures: PackedStringArray = []
var _scene := ""
var _mode := "full"


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() < 2:
		printerr("FAIL: usage: -s <probe> -- <scene> <full|partial>")
		quit(2)
		return
	_scene = str(args[0])
	_mode = str(args[1])
	_run()


func _run() -> void:
	var packed: PackedScene = load(_scene)
	if packed == null:
		_fail("Scene Load: 无法加载被测场景 %s" % _scene)
		_report()
		return
	var scene: Node2D = packed.instantiate()
	root.add_child(scene)
	await physics_frame

	var pickups := _find_all(scene, "is_collected")
	var gate: Node = _find_method(scene, "is_fulfilled")
	var door: Node = _find_method(scene, "is_open")
	if pickups.size() != 2:
		_fail("Precondition: 场景应含 2 个拾取物，实际 %d 个" % pickups.size())
		_report()
		return
	if gate == null:
		_fail("Precondition: 场景中不存在 condition_gate 组件（无 is_fulfilled()）")
		_report()
		return
	if door == null:
		_fail("Precondition: 场景中不存在 openable_door 组件（无 is_open()）")
		_report()
		return
	if not gate.has_signal("fulfilled"):
		_fail("Precondition: 条件门缺少 fulfilled 信号")
		_report()
		return

	pickups.sort_custom(func(a: Node2D, b: Node2D) -> bool:
		return a.global_position.x < b.global_position.x)
	var first: Node2D = pickups[0]
	var second: Node2D = pickups[1]

	var player_packed: PackedScene = load(PLAYER_SCENE)
	if player_packed == null:
		_fail("Environment: 无法加载玩家场景 %s" % PLAYER_SCENE)
		_report()
		return
	var player: Node2D = player_packed.instantiate()
	player.position = Vector2(0.0, 600.0)
	root.add_child(player)
	player.add_to_group("players")

	var fulfilled_hits := {"count": 0}
	gate.connect("fulfilled", func(_value: bool) -> void:
		fulfilled_hits["count"] += 1)
	await _wait_frames(4)

	var door_collision: Node = door.get_node_or_null("Collision")
	print("KEY_DOOR: scene=%s mode=%s initial_fulfilled=%s initial_open=%s collision=%s"
		% [_scene, _mode, bool(gate.call("is_fulfilled")), bool(door.call("is_open")),
		(door_collision.name if door_collision != null else "<none>")])
	if bool(gate.call("is_fulfilled")):
		_fail("Initial: 初始状态条件不应已满足")
	if bool(door.call("is_open")):
		_fail("Initial: 初始状态门不应已打开")

	# ---- 第 1 把钥匙 ----
	player.position = first.global_position
	await _wait_frames(6)
	# 收集后拾取物自行 queue_free：以「实例已被释放」作为被收集的可观察证据
	var first_taken := not is_instance_valid(first)
	var after_first_fulfilled := bool(gate.call("is_fulfilled"))
	var after_first_open := bool(door.call("is_open"))
	print("KEY_DOOR: first_taken=%s fulfilled=%s open=%s hits=%d"
		% [first_taken, after_first_fulfilled, after_first_open, fulfilled_hits["count"]])
	if not first_taken:
		_fail("First Key: 玩家接触后第 1 把钥匙应被收集")
	if after_first_fulfilled:
		_fail("First Key: 只拿到 1 把钥匙时条件不得满足（AND 语义）")
	if after_first_open:
		_fail("First Key: 只拿到 1 把钥匙时门不得打开")
	if fulfilled_hits["count"] != 0:
		_fail("First Key: 条件未满足时不得广播 fulfilled，实际 %d 次" % fulfilled_hits["count"])

	if _mode == "partial":
		_report()
		return

	# ---- 第 2 把钥匙 ----
	player.position = second.global_position
	await _wait_frames(8)
	var second_taken := not is_instance_valid(second)
	var fulfilled := bool(gate.call("is_fulfilled"))
	var opened := bool(door.call("is_open"))
	var collision_disabled := false
	if door_collision != null and "disabled" in door_collision:
		collision_disabled = bool(door_collision.get("disabled"))
	print("KEY_DOOR: second_taken=%s fulfilled=%s open=%s hits=%d collision_disabled=%s"
		% [second_taken, fulfilled, opened, fulfilled_hits["count"], collision_disabled])
	if not second_taken:
		_fail("Second Key: 玩家接触后第 2 把钥匙应被收集")
	if not fulfilled:
		_fail("Gate: 两把钥匙都收集后条件应满足")
	if fulfilled_hits["count"] != 1:
		_fail("Signal: fulfilled 应恰好广播 1 次，实际 %d 次" % fulfilled_hits["count"])
	if not opened:
		_fail("Door: 条件满足后门应打开")
	if door_collision == null:
		_fail("Door: 门缺少 Collision 碰撞形状，无法验证通行状态")
	elif not collision_disabled:
		_fail("Door: 开门后碰撞形状应被禁用（否则玩家仍被挡住）")
	_report()


func _find_method(node: Node, method_name: String) -> Node:
	if node.has_method(method_name):
		return node
	for child in node.get_children():
		var found := _find_method(child, method_name)
		if found != null:
			return found
	return null


func _find_all(node: Node, method_name: String) -> Array[Node]:
	var found: Array[Node] = []
	if node.has_method(method_name):
		found.append(node)
	for child in node.get_children():
		found.append_array(_find_all(child, method_name))
	return found


func _wait_frames(count: int) -> void:
	for _i in count:
		await physics_frame


func _fail(message: String) -> void:
	_failures.append(message)


func _report() -> void:
	if _failures.is_empty():
		print("PASS: eval136 key door probe (%s)" % _mode)
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
