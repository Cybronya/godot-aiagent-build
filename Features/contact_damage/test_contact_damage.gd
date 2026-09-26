extends SceneTree
## ContactDamage 组件自身验证：组内目标按节拍受击、每次伤害量正确、
## 组外目标不受影响、死亡目标不再受击。
##
## 用法：godot --headless --path . -s res://Features/contact_damage/test_contact_damage.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。
##
## 目标实体用本地构建的 CharacterBody2D + Health.tscn 组合：
## 验证只依赖 health Feature（组约定 + "Health" 子节点约定），不依赖游戏侧场景。
## 注意：get_overlapping_bodies 存在一帧滞后，首次结算可能查不到重叠，
## 因此等待逻辑基于「伤害事件到达」而非固定帧数。

const FRAME_BUDGET := 120

var _failures: PackedStringArray = []
var _damage_events: Array[int] = []


func _initialize() -> void:
	var packed: PackedScene = load("res://Features/contact_damage/ContactDamage.tscn")
	var health_scene: PackedScene = load("res://Features/health/Health.tscn")
	if packed == null or health_scene == null:
		_failures.append("加载 ContactDamage.tscn 或 Health.tscn 失败")
		_report()
		return

	var attacker: Area2D = packed.instantiate()
	var shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(32, 32)
	shape.shape = rect
	attacker.add_child(shape)
	attacker.position = Vector2(20, 0)
	root.add_child(attacker)

	# 组内目标：与攻击者重叠，应按节拍受击
	var target := _make_target("Target", health_scene, true)
	root.add_child(target)
	var health: Health = target.get_node("Health")
	health.health_changed.connect(_on_health_changed)
	await _wait_frames(2)

	# 1. 节拍伤害：等待前两次伤害事件到达，金额与剩余生命值正确
	if not await _wait_for_events(2):
		_failures.append("等待 2 次节拍伤害超时，实际 %d 次" % _damage_events.size())
		_report()
		return
	if health.get_current_health() != 3:
		_failures.append("两次 1 点伤害后生命值应为 3，实际 %d" % health.get_current_health())
	for amount: int in [_damage_events[0], _damage_events[1]]:
		if amount != 1:
			_failures.append("每次伤害量应为 1（damage 导出值），实际 %d" % amount)

	# 2. 组外目标：重叠但不在目标组，不受任何伤害
	var outsider := _make_target("Outsider", health_scene, false)
	outsider.position = Vector2(40, 0)
	root.add_child(outsider)
	var outsider_health: Health = outsider.get_node("Health")
	await _wait_frames(60)
	if outsider_health.get_current_health() != 5:
		_failures.append("组外重叠目标不应受击，实际生命值 %d" % outsider_health.get_current_health())

	# 3. 死亡保护：调大伤害让节拍击杀目标，之后持续重叠不再产生新事件
	attacker.damage = 3
	if not await _wait_for_death(health):
		_failures.append("等待目标死亡超时")
		_report()
		return
	var events_at_death := _damage_events.size()
	await _wait_frames(60)
	if _damage_events.size() != events_at_death:
		_failures.append("死亡目标不应再受击，死亡后又收到 %d 次事件" % (_damage_events.size() - events_at_death))
	if health.get_current_health() != 0 or not health.is_dead():
		_failures.append("死亡目标状态应保持死亡且生命值为 0")

	target.queue_free()
	outsider.queue_free()
	attacker.queue_free()
	await _wait_frames(2)
	_report()


func _make_target(node_name: String, health_scene: PackedScene, in_group: bool) -> CharacterBody2D:
	var body := CharacterBody2D.new()
	body.name = node_name
	if in_group:
		body.add_to_group("players")
	var health: Node = health_scene.instantiate()
	health.name = "Health"
	body.add_child(health)
	var shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(32, 32)
	shape.shape = rect
	body.add_child(shape)
	return body


func _wait_frames(count: int) -> void:
	for _i: int in count:
		await physics_frame


## 逐帧等待直到伤害事件到达指定数量；超出帧预算返回 false。
func _wait_for_events(expected: int) -> bool:
	for _i: int in FRAME_BUDGET:
		if _damage_events.size() >= expected:
			return true
		await physics_frame
	return _damage_events.size() >= expected


func _wait_for_death(health: Health) -> bool:
	for _i: int in FRAME_BUDGET:
		if health.is_dead():
			return true
		await physics_frame
	return health.is_dead()


func _on_health_changed(_current: int, amount: int) -> void:
	_damage_events.append(amount)


func _report() -> void:
	if _failures.is_empty():
		print("PASS: ContactDamage 组件验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
