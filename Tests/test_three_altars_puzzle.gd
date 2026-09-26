extends SceneTree
## Three Altars Puzzle 集成验证：基于真实 ThreeAltarsPuzzle.tscn。
##
## 所有「通过/被阻挡/移动」验证均以真实输入动作驱动（PlayerController
## 每帧按输入计算速度并 move_and_slide，等价真实游玩）。
##
## 覆盖：三祭坛独立激活（Toggle 可取消）、1 个激活门关闭、2 个打开、
## 3 个保持打开、取消回落关闭、关闭阻挡/打开真实穿行、完成区触发、
## 场景重载复位、关系连接为场景数据（零胶水）。
##
## 用法：godot --headless --path . -s res://Tests/test_three_altars_puzzle.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

const FRAME_BUDGET := 120

var _failures: PackedStringArray = []


func _initialize() -> void:
	var packed: PackedScene = load("res://Scenes/ThreeAltarsPuzzle.tscn")
	if packed == null:
		_failures.append("加载 res://Scenes/ThreeAltarsPuzzle.tscn 失败")
		_report()
		return

	# ---- A. 组合结构：关系全部为场景连接数据 ----
	var preview: Node2D = packed.instantiate()
	var gate: Node = preview.get_node("Mechanism/ConditionGate")
	if gate.aggregation != gate.Aggregation.AtLeast or gate.condition_count != 2:
		_failures.append("条件门应配置为 AtLeast / 阈值 2，实际 %s / %s" % [gate.aggregation, gate.condition_count])
	var altar: Area2D = preview.get_node("Mechanism/AltarA")
	if altar.trigger_mode != altar.Mode.Toggle:
		_failures.append("祭坛应为 Toggle 模式")
	if preview.get_node("Mechanism/AltarA").get_signal_connection_list("activated").size() != 1:
		_failures.append("每个祭坛应恰好连接到条件门一次")
	preview.queue_free()
	await process_frame

	# ---- B. 场景就绪与初始状态 ----
	var room: Node2D = packed.instantiate()
	root.add_child(room)
	current_scene = room
	await process_frame
	var player: CharacterBody2D = room.get_node("Player")
	var exit_door: StaticBody2D = room.get_node("Mechanism/ExitDoor")
	var altar_a: Area2D = room.get_node("Mechanism/AltarA")
	var altar_b: Area2D = room.get_node("Mechanism/AltarB")
	var altar_c: Area2D = room.get_node("Mechanism/AltarC")
	var gate2: Node = room.get_node("Mechanism/ConditionGate")
	if exit_door.is_open() or gate2.is_fulfilled() or altar_a.is_triggered() or altar_b.is_triggered() or altar_c.is_triggered():
		_failures.append("初始状态应全部为关闭/未触发/未达成")

	# ---- C. 独立激活：三个祭坛各自响应，一个激活时门保持关闭 ----
	await _touch(altar_a.global_position)
	if not await _wait_until(func() -> bool: return altar_a.is_triggered() and not altar_b.is_triggered() and not altar_c.is_triggered()):
		_failures.append("祭坛 A 应独立激活且不影响其他祭坛（等待超时）")
		_report()
		return
	if gate2.is_fulfilled() or exit_door.is_open():
		_failures.append("仅 1 个祭坛激活时门应保持关闭")
		_report()
		return

	# ---- D. 两个激活：门打开；三个：保持打开 ----
	await _touch(altar_b.global_position)
	if not await _wait_until(func() -> bool: return altar_b.is_triggered() and exit_door.is_open()):
		_failures.append("两个祭坛激活后门应打开（等待超时）")
		_report()
		return
	await _touch(altar_c.global_position)
	await _wait_frames(20)
	if not (altar_a.is_triggered() and altar_b.is_triggered() and altar_c.is_triggered()):
		_failures.append("三个祭坛应全部处于激活状态")
	if not exit_door.is_open():
		_failures.append("三个祭坛激活时门应保持打开")

	# ---- E. 取消回落：从 3 → 2 门保持开；2 → 1 门关闭 ----
	# Toggle 语义要求离开后重进才能翻转，先移开再重触
	await _touch(Vector2(60, 150))
	await _touch(altar_c.global_position)
	if not await _wait_until(func() -> bool: return not altar_c.is_triggered()):
		_failures.append("再触祭坛 C 应取消激活（等待超时）")
		_report()
		return
	if not exit_door.is_open():
		_failures.append("回落到 2 个激活时门应保持打开")
	await _touch(altar_b.global_position)
	if not await _wait_until(func() -> bool: return not altar_b.is_triggered()):
		_failures.append("再触祭坛 B 应取消激活（等待超时）")
		_report()
		return
	if exit_door.is_open() or gate2.is_fulfilled():
		_failures.append("回落到 1 个激活时门应重新关闭")

	# ---- F. 门关闭时真实物理阻挡 ----
	player.global_position = Vector2(-150, 0)
	Input.action_press("move_right")
	for _i: int in 240:
		await physics_frame
		if player.global_position.x > 260.0:
			break
	Input.action_release("move_right")
	await _wait_frames(2)
	if player.global_position.x > 296.0:
		_failures.append("门关闭时玩家不应能穿出房间，实际 x=%.1f" % player.global_position.x)
		_report()
		return

	# ---- G. 重新激活两个：门打开后真实物理穿行到完成区 ----
	await _touch(altar_b.global_position)
	if not await _wait_until(func() -> bool: return altar_b.is_triggered() and exit_door.is_open()):
		_failures.append("重新激活第二个祭坛后门应打开（等待超时）")
		_report()
		return
	var reached := false
	Input.action_press("move_right")
	for _i: int in 300:
		await physics_frame
		if player.global_position.x > 370.0:
			reached = true
			break
		if player.global_position.x > 230.0 and absf(player.global_position.y) > 40.0:
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
	if not reached:
		_failures.append("门打开后玩家应能真实穿出房间，最终位置 %s" % player.global_position)
		_report()
		return

	# ---- H. 完成区触发完成状态 ----
	if not await _wait_until(func() -> bool: return room.state == room.State.Completed):
		_failures.append("进入完成区后应产生完成状态（等待超时）")
		_report()
		return
	if not room.get_node("HUD/StatusLabel").text.contains("谜题完成"):
		_failures.append("完成后状态栏应显示完成反馈，实际 %s" % room.get_node("HUD/StatusLabel").text)

	# ---- I. 场景重载恢复初始状态 ----
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
	if fresh_door.is_open() or fresh_gate.is_fulfilled():
		_failures.append("重开后门与条件门应恢复初始状态")
	for altar_name: String in ["AltarA", "AltarB", "AltarC"]:
		if fresh.get_node("Mechanism/" + altar_name).is_triggered():
			_failures.append("重开后 %s 应恢复未触发状态" % altar_name)
	if fresh.get_node("Mechanism/AltarA").get_signal_connection_list("activated").size() != 1:
		_failures.append("重开后场景连接应随场景重建")

	_report()


## 以真实输入驱动移动到目标点：两阶段轴对齐移动（先对齐 x 再对齐 y），
## 避免对角线直冲因 x/y 同速而错过目标。
func _touch(target: Vector2) -> void:
	var player: CharacterBody2D = current_scene.get_node("Player")
	var delta_x := target.x - player.global_position.x
	if absf(delta_x) >= 8.0:
		var action_x := "move_left" if delta_x < 0.0 else "move_right"
		Input.action_press(action_x)
		for _i: int in 90:
			await physics_frame
			if absf(player.global_position.x - target.x) < 8.0:
				break
		Input.action_release(action_x)
	var delta_y := target.y - player.global_position.y
	if absf(delta_y) >= 8.0:
		var action_y := "move_up" if delta_y < 0.0 else "move_down"
		Input.action_press(action_y)
		for _i: int in 90:
			await physics_frame
			if absf(player.global_position.y - target.y) < 8.0:
				break
		Input.action_release(action_y)
	await _wait_frames(4)


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
		print("PASS: Three Altars Puzzle 集成验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
