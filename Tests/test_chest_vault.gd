extends SceneTree
## Chest Vault 集成验证：基于真实 ChestVault.tscn。
##
## 所有「通过/被阻挡/移动」验证均以真实输入动作驱动（PlayerController
## 每帧按输入计算速度并 move_and_slide，等价真实游玩）。
##
## 覆盖：三钥匙独立收集（顺序不限）、收集后实际消失、1/2 把时宝箱关闭、
## 3 把打开、关闭阻挡/打开真实穿行、完成区触发、场景重载复位、
## 关系连接为场景数据（零胶水）。
##
## 用法：godot --headless --path . -s res://Tests/test_chest_vault.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

const FRAME_BUDGET := 120

var _failures: PackedStringArray = []


func _initialize() -> void:
	var packed: PackedScene = load("res://Scenes/ChestVault.tscn")
	if packed == null:
		_failures.append("加载 res://Scenes/ChestVault.tscn 失败")
		_report()
		return

	# ---- A. 组合结构：关系全部为场景连接数据 ----
	var preview: Node2D = packed.instantiate()
	var gate: Node = preview.get_node("Mechanism/ConditionGate")
	if gate.condition_count != 3 or gate.aggregation != gate.Aggregation.All:
		_failures.append("条件门应配置为 All / 阈值 3，实际 %s / %s" % [gate.aggregation, gate.condition_count])
	var key_a: Area2D = preview.get_node("Mechanism/KeyA")
	var conns: Array = key_a.get_signal_connection_list("collected")
	if conns.size() != 1:
		_failures.append("每把钥匙应恰好连接到条件门一次，实际 %d" % conns.size())
	if preview.get_node("Mechanism/Chest").get_script().resource_path != "res://Features/openable_door/openable_door.gd":
		_failures.append("宝箱应为 openable_door 实例（参数化变体），不是新行为代码")
	preview.queue_free()
	await process_frame

	# ---- B. 初始状态 ----
	var room: Node2D = packed.instantiate()
	root.add_child(room)
	current_scene = room
	await process_frame
	var player: CharacterBody2D = room.get_node("Player")
	var chest: StaticBody2D = room.get_node("Mechanism/Chest")
	var gate2: Node = room.get_node("Mechanism/ConditionGate")
	var keys := {
		"KeyA": room.get_node("Mechanism/KeyA"),
		"KeyB": room.get_node("Mechanism/KeyB"),
		"KeyC": room.get_node("Mechanism/KeyC"),
	}
	if chest.is_open() or gate2.is_fulfilled():
		_failures.append("初始宝箱应为关闭且条件未达成")
	if keys.size() != 3:
		_failures.append("场景应存在三把钥匙")

	# ---- C. 顺序无关收集前两把：宝箱保持关闭，钥匙实际消失 ----
	await _touch(Vector2(-200, -170))
	if not await _wait_gone(keys["KeyA"]):
		_failures.append("钥匙 A 收集后应从场景消失（等待超时）")
		_report()
		return
	await _touch(Vector2(0, -170))
	if not await _wait_gone(keys["KeyB"]):
		_failures.append("钥匙 B 收集后应从场景消失（等待超时）")
		_report()
		return
	if gate2.is_fulfilled() or chest.is_open():
		_failures.append("两把钥匙时宝箱应保持关闭")
		_report()
		return

	# ---- D. 第三把（不同顺序路径的最后一把）：宝箱打开 ----
	await _touch(Vector2(0, 170))
	if not await _wait_gone(keys["KeyC"]):
		_failures.append("钥匙 C 收集后应从场景消失（等待超时）")
		_report()
		return
	if not await _wait_until(func() -> bool: return gate2.is_fulfilled() and chest.is_open()):
		_failures.append("三把钥匙收集后宝箱应打开（等待超时）")
		_report()
		return

	# ---- E. 宝箱关闭状态已过；打开后真实物理穿行进宝箱到完成区 ----
	var reached := false
	Input.action_press("move_right")
	for _i: int in 300:
		await physics_frame
		if player.global_position.x > 345.0:
			reached = true
			break
		if player.global_position.x > 240.0 and absf(player.global_position.y) > 24.0:
			Input.action_release("move_right")
			if player.global_position.y > 0:
				Input.action_press("move_up")
			else:
				Input.action_press("move_down")
			await _wait_frames(8)
			Input.action_release("move_up")
			Input.action_release("move_down")
			Input.action_press("move_right")
	Input.action_release("move_right")
	await _wait_frames(2)
	if not reached:
		_failures.append("宝箱打开后玩家应能真实进入宝箱区域，最终位置 %s" % player.global_position)
		_report()
		return

	# ---- F. 完成区触发完成状态 ----
	if not await _wait_until(func() -> bool: return room.state == room.State.Completed):
		_failures.append("进入宝箱完成区后应产生完成状态（等待超时）")
		_report()
		return
	if not room.get_node("HUD/StatusLabel").text.contains("完成"):
		_failures.append("完成后状态栏应显示完成反馈，实际 %s" % room.get_node("HUD/StatusLabel").text)

	# ---- G. 场景重载恢复初始状态 ----
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
	var fresh_chest: StaticBody2D = fresh.get_node("Mechanism/Chest")
	var fresh_gate: Node = fresh.get_node("Mechanism/ConditionGate")
	if fresh_chest.is_open() or fresh_gate.is_fulfilled():
		_failures.append("重开后宝箱与条件门应恢复初始状态")
	for key_name: String in ["KeyA", "KeyB", "KeyC"]:
		if fresh.get_node_or_null("Mechanism/" + key_name) == null:
			_failures.append("重开后 %s 应重新出现" % key_name)
	if fresh.get_node("Mechanism/KeyA").get_signal_connection_list("collected").size() != 1:
		_failures.append("重开后场景连接应随场景重建")

	_report()


## 以真实输入驱动移动到目标点：两阶段轴对齐移动。
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


## 形参保持无类型：拾取物被释放后传入 freed 引用，类型化形参会直接报错中断协程；
## 用 is_instance_valid 判定（传值前可能已释放）。
func _wait_gone(pickup) -> bool:
	for _i: int in FRAME_BUDGET:
		if not is_instance_valid(pickup):
			return true
		await physics_frame
	return false


func _wait_frames(count: int) -> void:
	for _i: int in count:
		await physics_frame


func _report() -> void:
	if _failures.is_empty():
		print("PASS: Chest Vault 集成验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
