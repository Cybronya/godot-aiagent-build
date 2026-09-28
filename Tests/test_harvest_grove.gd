extends SceneTree
## Harvest Grove 集成验证：资源收集区域全链路。
##
## 覆盖：静止晶体（collect_pickup 直用）接触收集与消失；
## 移动晶体（moving_platform + collect_pickup 纯组合，无 Feature 修改）
## 按三角波规则移动、随底座位移、玩家仍可收集；两种配置独立上报
## ConditionGate，集齐开门并触发完成文案；完成前门不可穿越；
## R 重开后机制复现。
##
## 用法：godot --headless --path . -s res://Tests/test_harvest_grove.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

const FRAME_BUDGET := 240

var _failures: PackedStringArray = []


func _initialize() -> void:
	var packed: PackedScene = load("res://Scenes/HarvestGrove.tscn")
	if packed == null:
		_failures.append("加载 res://Scenes/HarvestGrove.tscn 失败")
		_report()
		return

	# ---- A. 结构与初始状态：两种资源配置，聚合未满足 ----
	var scene: Node2D = packed.instantiate()
	root.add_child(scene)
	current_scene = scene
	await process_frame
	var player: CharacterBody2D = scene.get_node("Player")
	var gem_a: Area2D = scene.get_node("Resources/GemA")
	var gem_float: AnimatableBody2D = scene.get_node("Resources/GemFloat")
	var gem_b: Area2D = scene.get_node("Resources/GemFloat/GemB")
	var gate: Node = scene.get_node("Mechanism/CollectGate")
	var chest: StaticBody2D = scene.get_node("Mechanism/Chest")

	if gem_a.get("pickup_id") != "gem_static":
		_failures.append("GemA 应为静止晶体配置")
	if gem_b.get("pickup_id") != "gem_moving":
		_failures.append("GemB 应为移动晶体配置")
	if gem_b.get_parent() != gem_float:
		_failures.append("GemB 应为移动浮台的子节点（父变换传播组合）")
	if gate.get("condition_count") != 2:
		_failures.append("聚合门应配置两个条件")
	if gate.is_fulfilled():
		_failures.append("初始聚合不应满足")
	if chest.is_open():
		_failures.append("宝箱初始应关闭")
	if scene.is_completed():
		_failures.append("初始不应处于完成状态")

	# ---- B. 需求A：静止晶体接触收集，消失且聚合推进到 1/2 ----
	player.global_position = gem_a.global_position
	var collected_a := false
	for _i: int in FRAME_BUDGET:
		if not is_instance_valid(gem_a) or gem_a.is_collected():
			collected_a = true
			break
		await process_frame
	if not collected_a:
		_failures.append("接触静止晶体后应被收集")
	await process_frame
	if is_instance_valid(gem_a):
		_failures.append("收集后晶体应从场景移除")
	if gate.is_fulfilled():
		_failures.append("仅收集一个晶体时聚合不应满足")
	if chest.is_open() or scene.is_completed():
		_failures.append("未集齐时不应开门或完成")

	# ---- C. 需求B：移动晶体按空间规则移动、随底座位移、仍可收集 ----
	var float_start := gem_float.global_position
	var offset_start: Vector2 = gem_b.global_position - gem_float.global_position
	await _wait_frames(100)
	var moved := gem_float.global_position.distance_to(float_start)
	if moved < 50.0:
		_failures.append("浮台应按 travel/period 持续移动，实际位移 %.1f" % moved)
	var offset_now: Vector2 = gem_b.global_position - gem_float.global_position
	if offset_now.distance_to(offset_start) > 0.01:
		_failures.append("晶体应随底座一起位移（父子变换传播）")
	player.global_position = gem_b.global_position
	var collected_b := false
	for _i: int in FRAME_BUDGET:
		if not is_instance_valid(gem_b) or gem_b.is_collected():
			collected_b = true
			break
		await process_frame
	if not collected_b:
		_failures.append("接触移动晶体后应被收集（移动不阻碍获取）")

	# ---- D. 集齐 → 聚合满足 → 开门 + 完成文案（单信号双消费者） ----
	if not gate.is_fulfilled():
		_failures.append("两晶体集齐后聚合应满足")
	if not chest.is_open():
		_failures.append("聚合满足后宝箱应开启")
	if not scene.is_completed():
		_failures.append("聚合满足后场景应进入完成状态")
	var label: Label = scene.get_node("HUD/StatusLabel")
	if label.text != "采集完成！按 R 重新开始":
		_failures.append("完成后状态文案应更新，实际：%s" % label.text)

	# ---- E. 成功条件：穿过开启的宝箱门到达最右侧 ----
	player.global_position = Vector2(500, 0)
	await process_frame
	Input.action_press("move_right")
	for _i: int in 60:
		await physics_frame
	Input.action_release("move_right")
	if player.global_position.x < 555.0:
		_failures.append("门开后玩家应能穿过宝箱位置到达右侧，实际 x=%.1f" % player.global_position.x)

	# ---- F. R 重开（真实重开路径） ----
	Input.action_press("restart")
	var reloaded := false
	for _i: int in FRAME_BUDGET:
		if current_scene != scene:
			reloaded = true
			break
		await process_frame
	Input.action_release("restart")
	if not reloaded:
		_failures.append("按 R 应重新加载场景（等待超时）")
		_report()
		return
	await process_frame
	var fresh: Node2D = current_scene
	if fresh == scene or fresh == null:
		_failures.append("重开后应得到全新场景实例")
		_report()
		return
	var fresh_gate: Node = fresh.get_node("Mechanism/CollectGate")
	var fresh_chest: StaticBody2D = fresh.get_node("Mechanism/Chest")
	var fresh_gem_a: Area2D = fresh.get_node("Resources/GemA")
	var fresh_gem_b: Area2D = fresh.get_node("Resources/GemFloat/GemB")
	if fresh_chest.is_open() or fresh_gate.is_fulfilled():
		_failures.append("重开后宝箱与聚合应恢复初始")
	if fresh_gem_a.get("pickup_id") != "gem_static":
		_failures.append("重开后静止晶体应恢复")
	if fresh_gem_b.get("pickup_id") != "gem_moving":
		_failures.append("重开后移动晶体应恢复")
	if fresh.is_completed():
		_failures.append("重开后不应处于完成状态")

	# ---- G. 机制复现：新实例中移动与收集再次工作 ----
	var fresh_float: AnimatableBody2D = fresh.get_node("Resources/GemFloat")
	var float_pos := fresh_float.global_position
	await _wait_frames(60)
	if fresh_float.global_position.distance_to(float_pos) < 20.0:
		_failures.append("重开后浮台应继续移动")
	var fresh_player: CharacterBody2D = fresh.get_node("Player")
	fresh_player.global_position = fresh_gem_a.global_position
	for _i: int in FRAME_BUDGET:
		if not is_instance_valid(fresh_gem_a) or fresh_gem_a.is_collected():
			break
		await process_frame
	if is_instance_valid(fresh_gem_a) and not fresh_gem_a.is_collected():
		_failures.append("重开后静止晶体应可再次收集")
	fresh_player.global_position = fresh_gem_b.global_position
	var recollected := false
	for _i: int in FRAME_BUDGET:
		if not is_instance_valid(fresh_gem_b) or fresh_gem_b.is_collected():
			recollected = true
			break
		await process_frame
	if not recollected:
		_failures.append("重开后移动晶体应可再次收集")
	if not fresh_gate.is_fulfilled() or not fresh_chest.is_open():
		_failures.append("重开后集齐应再次开门")

	_report()


func _wait_frames(count: int) -> void:
	for _i: int in count:
		await physics_frame


func _report() -> void:
	if _failures.is_empty():
		print("PASS: Harvest Grove 集成验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
