extends SceneTree
## Escape Room 集成验证：基于真实 EscapeRoom.tscn。
##
## 所有「通过/被阻挡/移动」验证均以真实输入动作驱动（PlayerController
## 每帧按输入计算速度并 move_and_slide，等价真实游玩）。
##
## 覆盖：初始状态、第一条件满足仍关闭、双条件打开、真实穿出、离开不重置、
## 逃脱成功状态、场景重载复位、关系连接为场景数据（零胶水）。
##
## 用法：godot --headless --path . -s res://Tests/test_escape_room.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

const FRAME_BUDGET := 120

var _failures: PackedStringArray = []


func _initialize() -> void:
	var packed: PackedScene = load("res://Scenes/EscapeRoom.tscn")
	if packed == null:
		_failures.append("加载 res://Scenes/EscapeRoom.tscn 失败")
		_report()
		return

	# ---- A. 组合结构：关系全部为场景连接数据，无胶水脚本 ----
	var preview: Node2D = packed.instantiate()
	var gate: Node = preview.get_node("Mechanism/ConditionGate")
	var switch_conns: Array = preview.get_node("Mechanism/SwitchA").get_signal_connection_list("activated")
	if switch_conns.size() != 1:
		_failures.append("SwitchA 应连接到 ConditionGate，实际 %d 条" % switch_conns.size())
	var gate_conns: Array = gate.get_signal_connection_list("fulfilled")
	if gate_conns.size() != 1:
		_failures.append("ConditionGate 应连接到出口门，实际 %d 条" % gate_conns.size())
	preview.queue_free()
	await process_frame

	# ---- B. 初始状态：门关、未达成、房间封闭 ----
	var room: Node2D = packed.instantiate()
	root.add_child(room)
	current_scene = room
	await process_frame
	var player: CharacterBody2D = room.get_node("Player")
	var exit_door: StaticBody2D = room.get_node("Mechanism/ExitDoor")
	var switch_a: Area2D = room.get_node("Mechanism/SwitchA")
	var switch_b: Area2D = room.get_node("Mechanism/SwitchB")
	var condition_gate: Node = room.get_node("Mechanism/ConditionGate")
	if exit_door.is_open() or condition_gate.is_fulfilled() or switch_a.is_triggered() or switch_b.is_triggered():
		_failures.append("初始状态应全部为关闭/未触发/未达成")

	# ---- C. 第一个条件满足：出口仍关闭 ----
	player.global_position = switch_a.global_position
	if not await _wait_until(func() -> bool: return switch_a.is_triggered()):
		_failures.append("玩家踩上开关 A 应触发（等待超时）")
		_report()
		return
	if condition_gate.is_fulfilled() or exit_door.is_open():
		_failures.append("仅完成第一个条件时出口不应打开")
		_report()
		return

	# ---- C2. 出口关闭时真实物理阻挡：输入驱动向右推，应被门拦住 ----
	player.global_position = Vector2(-240, 0)
	Input.action_press("move_right")
	for _i: int in 300:
		await physics_frame
		if player.global_position.x > 320.0:
			break
	Input.action_release("move_right")
	await _wait_frames(2)
	if player.global_position.x > 336.0:
		_failures.append("出口关闭时玩家不应能穿出房间，实际 x=%.1f" % player.global_position.x)
		_report()
		return

	# ---- D. 第二个条件满足：出口打开 ----
	player.global_position = switch_b.global_position
	if not await _wait_until(func() -> bool: return switch_b.is_triggered() and exit_door.is_open()):
		_failures.append("双条件满足后出口应打开（等待超时）")
		_report()
		return

	# ---- E. 离开机关区域不重置（Latching + 保持型聚合） ----
	player.global_position = Vector2(-240, 140)
	await _wait_frames(20)
	if not switch_a.is_triggered() or not switch_b.is_triggered() or not condition_gate.is_fulfilled() or not exit_door.is_open():
		_failures.append("离开机关区域后状态应全部保持")

	# ---- F. 真实物理穿出：输入驱动走出缺口，抵达逃逸区 ----
	# 从缺口正对的 y=0 出发，全程右移；若被墙围挡则向缺口中心修正
	player.global_position = Vector2(-240, 0)
	var escaped := false
	Input.action_press("move_right")
	for _i: int in 300:
		await physics_frame
		if player.global_position.x > 384.0 and absf(player.global_position.y) < 40.0:
			escaped = true
			break
		if player.global_position.x > 290.0 and absf(player.global_position.y) > 40.0:
			Input.action_release("move_right")
			if player.global_position.y > 0:
				Input.action_press("move_up")
			else:
				Input.action_press("move_down")
			await _wait_frames(10)
			Input.action_release("move_up")
			Input.action_release("move_down")
			Input.action_press("move_right")
	Input.action_release("move_right")
	await _wait_frames(2)
	if not escaped:
		_failures.append("出口打开后玩家应能真实穿出房间，最终位置 %s" % player.global_position)
		_report()
		return

	# ---- G. 逃脱成功状态 ----
	if room.state != room.State.Escaped:
		_failures.append("到达逃逸区后应进入 Escaped 状态，实际 %d" % room.state)
	if not room.get_node("HUD/StatusLabel").text.contains("逃脱成功"):
		_failures.append("逃脱后状态栏应显示成功反馈，实际 %s" % room.get_node("HUD/StatusLabel").text)

	# ---- H. 场景重载恢复初始状态 ----
	Input.action_press("restart")
	var reloaded := false
	for _i: int in FRAME_BUDGET:
		if current_scene != room:
			reloaded = true
			break
		await process_frame
	Input.action_release("restart")
	if not reloaded:
		_failures.append("按 R 后应重新加载场景（等待超时）")
		_report()
		return
	await _wait_frames(3)
	var fresh: Node2D = current_scene
	if fresh == room or fresh == null:
		_failures.append("重开后应得到全新场景实例")
		_report()
		return
	var fresh_door: StaticBody2D = fresh.get_node("Mechanism/ExitDoor")
	var fresh_gate: Node = fresh.get_node("Mechanism/ConditionGate")
	var fresh_switch_a: Area2D = fresh.get_node("Mechanism/SwitchA")
	var fresh_switch_b: Area2D = fresh.get_node("Mechanism/SwitchB")
	if fresh_door.is_open() or fresh_gate.is_fulfilled() or fresh_switch_a.is_triggered() or fresh_switch_b.is_triggered():
		_failures.append("重开后机关与出口应全部恢复初始状态")
	if fresh.get_node("Mechanism/SwitchA").get_signal_connection_list("activated").size() != 1:
		_failures.append("重开后场景连接应随场景重建")

	_report()


func _wait_until(predicate: Callable) -> bool:
	for _i: int in FRAME_BUDGET:
		if predicate.call():
			return true
		await process_frame
	return predicate.call()


func _wait_frames(count: int) -> void:
	for _i: int in count:
		await physics_frame


func _report() -> void:
	if _failures.is_empty():
		print("PASS: Escape Room 集成验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
