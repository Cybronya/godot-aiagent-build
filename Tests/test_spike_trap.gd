extends SceneTree
## Spike Trap 集成验证：基于真实 SurvivalArena.tscn 与 SpikeTrap.tscn。
##
## 覆盖：零行为复制结构断言（根节点无脚本，伤害由既有 ContactDamage 完成）、
## 陷阱无 Health、静态不移动、持续节拍伤害、伤害量与既有规则一致、
## 场景放置多实例、结束状态冻结陷阱。
##
## 用法：godot --headless --path . -s res://Tests/test_spike_trap.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。
##
## 注意：GDScript lambda 对局部变量按值捕获，事件计数必须使用成员变量。

const FRAME_BUDGET := 120

var _failures: PackedStringArray = []
var _player_damage_amounts: Array[int] = []


func _initialize() -> void:
	var packed: PackedScene = load("res://Scenes/SurvivalArena.tscn")
	var trap_scene: PackedScene = load("res://Scenes/SpikeTrap.tscn")
	if packed == null or trap_scene == null:
		_failures.append("加载 SurvivalArena.tscn 或 SpikeTrap.tscn 失败")
		_report()
		return

	# ---- A. 结构断言：组合复用，无行为复制 ----
	var trap_preview: Node2D = trap_scene.instantiate()
	root.add_child(trap_preview)
	await process_frame
	var root_script: Script = trap_preview.get_script()
	if root_script != null:
		_failures.append("陷阱根节点不应携带任何行为脚本，实际 %s" % root_script.resource_path)
	var contact: Area2D = trap_preview.get_node("ContactDamage")
	var contact_script: Script = contact.get_script()
	if contact_script == null or contact_script.resource_path != "res://Features/contact_damage/contact_damage.gd":
		_failures.append("陷阱伤害应完全由既有 ContactDamage Feature 完成，实际 %s" % (contact_script.resource_path if contact_script != null else "<null>"))
	if trap_preview.get_node_or_null("Health") != null:
		_failures.append("陷阱不应拥有 Health 组件")
	if not trap_preview.is_in_group("traps"):
		_failures.append("陷阱应加入 traps 组（供结束状态统一冻结）")
	trap_preview.queue_free()
	await _wait_frames(2)

	# ---- B. 行为验证（组件级）：对组内目标持续造成既有规则的节拍伤害 ----
	var trap: Node2D = trap_scene.instantiate()
	trap.position = Vector2(0, 0)
	root.add_child(trap)
	var proxy := CharacterBody2D.new()
	proxy.add_to_group("players")
	var health_scene: PackedScene = load("res://Features/health/Health.tscn")
	var proxy_health: Node = health_scene.instantiate()
	proxy_health.name = "Health"
	proxy.add_child(proxy_health)
	var shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(32, 32)
	shape.shape = rect
	proxy.add_child(shape)
	root.add_child(proxy)
	await _wait_frames(2)
	proxy_health.health_changed.connect(_on_health_changed)

	if not await _wait_for_events(1):
		_failures.append("进入地刺范围后应受到伤害（等待超时）")
		_report()
		return
	for amount: int in _player_damage_amounts:
		if amount != 1:
			_failures.append("陷阱每次伤害应为 1（tick_interval 覆写为 0.4s），实际 %d" % amount)
	var events_first := _player_damage_amounts.size()
	if not await _wait_for_events(events_first + 1):
		_failures.append("停留在地刺范围内应持续受到伤害（第二次伤害等待超时）")
		_report()
		return
	trap.get_node("ContactDamage").set_physics_process(false)
	await _wait_frames(40)
	if _player_damage_amounts.size() != events_first + 1:
		_failures.append("陷阱停摆后不应继续造成伤害，实际新增 %d 次" % (_player_damage_amounts.size() - events_first - 1))
	proxy.queue_free()
	trap.queue_free()
	await _wait_frames(2)

	# ---- C. 真实场景集成：多实例静态放置 + 伤害链路 ----
	var arena: Node2D = packed.instantiate()
	root.add_child(arena)
	current_scene = arena
	await process_frame
	var traps_node: Node2D = arena.get_node("Traps")
	var placed := 0
	for child: Node in traps_node.get_children():
		if child.is_in_group("traps"):
			placed += 1
	if placed < 3:
		_failures.append("场景应静态放置至少 3 个地刺实例，实际 %d" % placed)
	var player: CharacterBody2D = arena.get_node("Player")
	var player_health: Health = player.get_node("Health")
	player_health.health_changed.connect(_on_health_changed)
	_player_damage_amounts.clear()
	var trap_pos: Vector2 = traps_node.get_child(0).global_position
	player.global_position = trap_pos
	await _wait_frames(30)
	var moved: float = traps_node.get_child(0).global_position.distance_to(trap_pos)
	if moved > 1.0:
		_failures.append("地刺是静态陷阱，不应移动，实际位移 %.1f" % moved)
	if not await _wait_for_events(2):
		_failures.append("真实场景中玩家进入地刺范围应持续受击（等待超时）")
		_report()
		return
	if player_health.get_current_health() >= 10 or player_health.is_dead():
		_failures.append("玩家应受伤且生命值不低于 0，实际 HP=%d dead=%s" % [player_health.get_current_health(), player_health.is_dead()])

	# ---- D. 结束状态冻结陷阱：Won 状态下站入陷阱不再受击 ----
	arena._finish(true)
	if arena.state != arena.State.Won:
		_failures.append("调用 _finish(true) 后应进入 Won 状态，实际 %d" % arena.state)
	var events_at_finish := _player_damage_amounts.size()
	player.global_position = traps_node.get_child(1).global_position
	await _wait_frames(60)
	if _player_damage_amounts.size() != events_at_finish:
		_failures.append("结束状态后陷阱应停摆，实际新增 %d 次伤害" % (_player_damage_amounts.size() - events_at_finish))

	_report()


## 逐帧等待伤害事件到达指定数量；超时返回 false。
func _wait_for_events(expected: int) -> bool:
	for _i: int in FRAME_BUDGET:
		if _player_damage_amounts.size() >= expected:
			return true
		await physics_frame
	return _player_damage_amounts.size() >= expected


func _wait_frames(count: int) -> void:
	for _i: int in count:
		await physics_frame


func _on_health_changed(_current: int, amount: int) -> void:
	_player_damage_amounts.append(amount)


func _report() -> void:
	if _failures.is_empty():
		print("PASS: Spike Trap 集成验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
