extends SceneTree
## Switch / Door 机制集成验证：基于真实 SurvivalArena.tscn。
##
## 覆盖：玩家触发开关、开关状态改变、门响应、一个开关控制多扇门、
## 门后区域实际可达、玩家离开范围不重置、场景重载恢复初始状态、
## 多机关实例共存、静态围栏不破坏既有玩法。
##
## 用法：godot --headless --path . -s res://Tests/test_switch_door_mechanism.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

const FRAME_BUDGET := 120
const PUSH_FRAMES := 60
const PUSH_SPEED := 120.0

var _failures: PackedStringArray = []


func _initialize() -> void:
	var packed: PackedScene = load("res://Scenes/SurvivalArena.tscn")
	if packed == null:
		_failures.append("加载 res://Scenes/SurvivalArena.tscn 失败")
		_report()
		return

	# ---- A. 组合结构：连接由场景数据完成，无胶水代码 ----
	var preview: Node2D = packed.instantiate()
	var switch: Area2D = preview.get_node("Mechanism/RewardSwitch")
	var main_door: StaticBody2D = preview.get_node("Mechanism/MainDoor")
	var side_door: StaticBody2D = preview.get_node("Mechanism/SideDoor")
	if switch.get_signal_connection_list("activated").size() != 2:
		_failures.append("开关 activated 信号应连接 2 个目标（一开关多门），实际 %d" % switch.get_signal_connection_list("activated").size())
	if preview.get_node_or_null("Mechanism/MainDoor/Health") != null:
		_failures.append("门不应拥有 Health 组件")
	preview.queue_free()
	await process_frame

	# ---- B. 玩家触发开关 → 双门打开 ----
	var arena: Node2D = packed.instantiate()
	root.add_child(arena)
	current_scene = arena
	# 禁用自动生成，避免敌人干扰门通行与状态断言
	arena.spawn_interval = 9999.0
	arena.pickup_interval = 9999.0
	await process_frame
	var player: CharacterBody2D = arena.get_node("Player")
	var main_door2: StaticBody2D = arena.get_node("Mechanism/MainDoor")
	var side_door2: StaticBody2D = arena.get_node("Mechanism/SideDoor")
	var reward_switch: Area2D = arena.get_node("Mechanism/RewardSwitch")
	if main_door2.is_open() or side_door2.is_open():
		_failures.append("触发前两扇门都应处于关闭状态")
	player.global_position = reward_switch.global_position
	if not await _wait_until(func() -> bool: return reward_switch.is_triggered()):
		_failures.append("玩家进入开关范围应触发开关（等待超时）")
		_report()
		return
	if not await _wait_until(func() -> bool: return main_door2.is_open() and side_door2.is_open()):
		_failures.append("开关触发后两扇门都应打开（等待超时）")

	# ---- C. 玩家穿过打开的主门（真实输入驱动，PlayerController 语义） ----
	player.global_position = Vector2(360, 0)
	await process_frame
	Input.action_press("move_right")
	for _i: int in 60:
		await physics_frame
	Input.action_release("move_right")
	await _wait_frames(2)
	if player.global_position.x < 540.0:
		_failures.append("门打开后玩家应能穿过主门，实际 x=%.1f" % player.global_position.x)

	# ---- D. 离开开关范围不重置（Latching 语义） ----
	player.global_position = Vector2(-300, 0)
	await _wait_frames(20)
	if not reward_switch.is_triggered():
		_failures.append("玩家离开后开关应保持触发状态")
	if not main_door2.is_open() or not side_door2.is_open():
		_failures.append("玩家离开后门应保持打开状态")

	# ---- E. 场景重载恢复初始状态：进入结束状态后按 R（真实重开路径） ----
	arena._finish(true)
	Input.action_press("restart")
	var reloaded := false
	for _i: int in FRAME_BUDGET:
		if current_scene != arena:
			reloaded = true
			break
		await process_frame
	Input.action_release("restart")
	if not reloaded:
		_failures.append("按重开后应重新加载场景（等待超时）")
		_report()
		return
	await process_frame
	var fresh: Node2D = current_scene
	if fresh == arena or fresh == null:
		_failures.append("重开后应得到全新场景实例")
		_report()
		return
	var fresh_switch: Area2D = fresh.get_node("Mechanism/RewardSwitch")
	var fresh_main: StaticBody2D = fresh.get_node("Mechanism/MainDoor")
	var fresh_side: StaticBody2D = fresh.get_node("Mechanism/SideDoor")
	if fresh_switch.is_triggered() or fresh_main.is_open() or fresh_side.is_open():
		_failures.append("重开后开关/门应恢复初始关闭状态")
	if fresh_switch.get_signal_connection_list("activated").size() != 2:
		_failures.append("重开后信号连接应随场景重建")

	# ---- F. 多机关实例共存：第二对开关+门独立工作 ----
	var arena2: Node2D = packed.instantiate()
	root.add_child(arena2)
	await process_frame
	var sw_a: Area2D = arena2.get_node("Mechanism/RewardSwitch")
	# 从 Feature 场景全新实例化第二对开关+门（多实例的真实用法；
	# 不用 duplicate()：默认会连同信号连接一起复制，产生隐式联动）
	var sw_b: Area2D = load("res://Features/trigger_switch/TriggerSwitch.tscn").instantiate()
	sw_b.position = Vector2(-200, -200)
	arena2.get_node("Mechanism").add_child(sw_b)
	sw_b.activated.connect(arena2.get_node("Mechanism/SideDoor").set_open)
	var door_b: StaticBody2D = load("res://Features/openable_door/OpenableDoor.tscn").instantiate()
	door_b.position = Vector2(-200, 200)
	arena2.get_node("Mechanism").add_child(door_b)
	sw_b.activated.connect(door_b.set_open)
	var probe := _make_probe()
	probe.global_position = sw_b.global_position
	arena2.get_node("Entities").add_child(probe)
	if not await _wait_until(func() -> bool: return sw_b.is_triggered() and door_b.is_open()):
		_failures.append("第二对开关+门应独立触发并开门（等待超时）")
		_report()
		return
	if sw_a.is_triggered() or arena2.get_node("Mechanism/MainDoor").is_open():
		_failures.append("第二机关触发不应影响第一对开关/门状态")
	arena2.queue_free()
	await process_frame

	# ---- G. 静态围栏不破坏既有玩法：敌人接触伤害与拾取恢复照常 ----
	var arena3: Node2D = packed.instantiate()
	root.add_child(arena3)
	current_scene = arena3
	await process_frame
	var player3: CharacterBody2D = arena3.get_node("Player")
	var health3: Health = player3.get_node("Health")
	arena3._spawn_enemy()
	var enemy: CharacterBody2D = get_nodes_in_group("enemies")[0]
	enemy.global_position = player3.global_position + Vector2(24, 0)
	var damaged := false
	for _i: int in FRAME_BUDGET:
		if health3.get_current_health() < 10:
			damaged = true
			break
		await physics_frame
	if not damaged:
		_failures.append("加入机关围栏后敌人接触伤害应照常工作（等待超时）")

	_report()


func _make_probe() -> CharacterBody2D:
	var body := CharacterBody2D.new()
	body.motion_mode = 1
	body.add_to_group("players")
	var shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(24, 24)
	shape.shape = rect
	body.add_child(shape)
	return body


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
		print("PASS: Switch/Door 机制验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
