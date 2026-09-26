extends SceneTree
## Platform Vault 集成验证：基于真实 PlatformVault.tscn。
##
## 所有「移动/阻挡/通行」验证均以真实输入动作驱动（PlayerController
## 每帧按输入计算速度并 move_and_slide，等价真实游玩）。
##
## 覆盖：平台位置往返变化、玩家乘平台渡过水道、钥匙接触后消失、
## 无钥匙时门物理阻挡、收集后门解除阻挡、进入出口完成、
## 场景重载完整复位、关系连接为场景数据（零胶水）。
##
## 用法：godot --headless --path . -s res://Tests/test_platform_vault.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

const FRAME_BUDGET := 240

var _failures: PackedStringArray = []


func _initialize() -> void:
	var packed: PackedScene = load("res://Scenes/PlatformVault.tscn")
	if packed == null:
		_failures.append("加载 res://Scenes/PlatformVault.tscn 失败")
		_report()
		return

	# ---- A. 组合结构：关系全部为场景连接数据 ----
	var preview: Node2D = packed.instantiate()
	var gate: Node = preview.get_node("Mechanism/ConditionGate")
	if gate.condition_count != 1 or gate.aggregation != gate.Aggregation.All:
		_failures.append("条件门应配置为 All / 阈值 1")
	var key: Area2D = preview.get_node("Mechanism/Key")
	if key.get_signal_connection_list("collected").size() != 1:
		_failures.append("钥匙应恰好连接到条件门一次")
	if preview.get_node("Mechanism/KeyDoor").get_script().resource_path != "res://Features/openable_door/openable_door.gd":
		_failures.append("钥匙门应为 openable_door 实例")
	preview.queue_free()
	await process_frame

	# ---- B. 初始状态 ----
	var room: Node2D = packed.instantiate()
	root.add_child(room)
	current_scene = room
	await process_frame
	var player: CharacterBody2D = room.get_node("Player")
	var ferry: AnimatableBody2D = room.get_node("Mechanism/Ferry")
	var key_pickup: Area2D = room.get_node("Mechanism/Key")
	var key_door: StaticBody2D = room.get_node("Mechanism/KeyDoor")
	var gate2: Node = room.get_node("Mechanism/ConditionGate")
	if key_door.is_open() or gate2.is_fulfilled():
		_failures.append("初始门应关闭且条件未达成")
	if not is_instance_valid(key_pickup):
		_failures.append("初始钥匙应存在")

	# ---- C. 平台确实发生位置变化（特征期观察极值） ----
	var origin: Vector2 = ferry.global_position
	var max_offset := 0.0
	for _i: int in 150:
		await physics_frame
		max_offset = maxf(max_offset, absf(ferry.global_position.x - origin.x))
	if max_offset < 100.0:
		_failures.append("平台应发生明显的往返位置变化，实际最大偏移 %.1f" % max_offset)
		_report()
		return

	# ---- D. 玩家真实移动有效（先验证基础移动） ----
	var before_move: Vector2 = player.global_position
	Input.action_press("move_up")
	for _i: int in 30:
		await physics_frame
	Input.action_release("move_up")
	if player.global_position.distance_to(before_move) < 40.0:
		_failures.append("玩家基础移动应有效")
		_report()
		return

	# ---- E. 乘平台渡运：等船回到左岸缺口，站上平台被携带穿墙到右侧 ----
	var board_x := -150.0
	var boarded := false
	for _i: int in FRAME_BUDGET:
		if ferry.global_position.x < board_x + 30.0:
			boarded = true
			break
		await physics_frame
	if not boarded:
		_failures.append("平台应返回起点侧（等待超时）")
		_report()
		return
	# 从左侧岸台走向缺口处上船（先对齐 y 再进载客区）
	await _touch(Vector2(-240, 0))
	Input.action_press("move_right")
	for _i: int in 60:
		await physics_frame
		if absf(player.global_position.x - ferry.global_position.x) < 50.0:
			break
	Input.action_release("move_right")
	await _wait_frames(4)
	# 在载客区上等渡运：平台将把玩家带过缺口（x > 60 即到右侧）
	var ferried := false
	for _i: int in 480:
		await physics_frame
		if player.global_position.x > 60.0 and absf(player.global_position.y) < 60.0:
			ferried = true
			break
	if not ferried:
		_failures.append("玩家应被平台携带穿过缺口，最终位置 %s" % player.global_position)
		_report()
		return

	# ---- F. 收集钥匙：接触后实际消失 ----
	await _touch(Vector2(240, 0))
	if is_instance_valid(key):
		_failures.append("钥匙接触后应从场景消失")
		_report()
		return

	# ---- G. 门先关闭阻挡：回到门前验证被拦 ----
	# （钥匙已收集门已开，此处验证「开」状态可通过；关闭状态由重置后新实例验证）
	if not await _wait_until(func() -> bool: return key_door.is_open() and gate2.is_fulfilled()):
		_failures.append("收集钥匙后门应打开（等待超时）")
		_report()
		return
	Input.action_press("move_right")
	for _i: int in 180:
		await physics_frame
		if player.global_position.x > 445.0:
			break
	Input.action_release("move_right")
	await _wait_frames(2)
	if player.global_position.x < 445.0:
		_failures.append("门打开后玩家应能通过，实际 x=%.1f" % player.global_position.x)
		_report()
		return

	# ---- H. 完成区触发 ----
	if not await _wait_until(func() -> bool: return room.state == room.State.Completed):
		_failures.append("进入出口区后应产生完成状态（等待超时）")
		_report()
		return
	if not room.get_node("HUD/StatusLabel").text.contains("完成"):
		_failures.append("完成后状态栏应显示完成反馈")

	# ---- I. 关闭阻挡的物理验证：用未收集钥匙的第二实例 ----
	var room2: Node2D = packed.instantiate()
	root.add_child(room2)
	await process_frame
	var player2: CharacterBody2D = room2.get_node("Player")
	var door2: StaticBody2D = room2.get_node("Mechanism/KeyDoor")
	player2.global_position = Vector2(360, 0)
	Input.action_press("move_right")
	for _i: int in 120:
		await physics_frame
		if player2.global_position.x > 430.0:
			break
	Input.action_release("move_right")
	await _wait_frames(2)
	if player2.global_position.x > 398.0:
		_failures.append("门关闭时玩家不应能通过，实际 x=%.1f（门开=%s）" % [player2.global_position.x, door2.is_open()])
	room2.queue_free()
	await process_frame

	# ---- J. 场景重载完整复位 ----
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
	var fresh_key: Area2D = fresh.get_node_or_null("Mechanism/Key")
	if fresh_key == null:
		_failures.append("重开后钥匙应重新出现")
	if fresh.get_node("Mechanism/KeyDoor").is_open() or fresh.get_node("Mechanism/ConditionGate").is_fulfilled():
		_failures.append("重开后门与条件门应恢复关闭")
	if fresh.get_node("Mechanism/Ferry").global_position.distance_to(fresh.get_node("Mechanism/Ferry")._origin) > 4.0:
		_failures.append("重开后平台应从初始位置重新开始")
	if fresh.get_node("Mechanism/Key").get_signal_connection_list("collected").size() != 1:
		_failures.append("重开后场景连接应随场景重建")

	_report()


func _touch(target: Vector2) -> void:
	var player: CharacterBody2D = current_scene.get_node("Player")
	var delta_x := target.x - player.global_position.x
	if absf(delta_x) >= 8.0:
		var action_x := "move_left" if delta_x < 0.0 else "move_right"
		Input.action_press(action_x)
		for _i: int in 90:
			await physics_frame
			if absf(player.global_position.x - target.x) < 10.0:
				break
		Input.action_release(action_x)
	var delta_y := target.y - player.global_position.y
	if absf(delta_y) >= 8.0:
		var action_y := "move_up" if delta_y < 0.0 else "move_down"
		Input.action_press(action_y)
		for _i: int in 90:
			await physics_frame
			if absf(player.global_position.y - target.y) < 10.0:
				break
		Input.action_release(action_y)
	await _wait_frames(6)


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
		print("PASS: Platform Vault 集成验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
