extends SceneTree
## HealPickup 组件自身验证：组内受伤目标拾取后恢复并移除、恢复量钳制在
## max_health 之内、满血目标不消费、组外目标不消费。
##
## 用法：godot --headless --path . -s res://Features/heal_pickup/test_heal_pickup.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。
##
## 目标实体用本地构建的 CharacterBody2D + Health.tscn 组合：
## 验证只依赖 health Feature（组约定 + "Health" 子节点约定），不依赖游戏侧场景。
## 注意：Health 在 _ready 时才初始化生命值，实体入树后必须先等一帧再扣血。

const FRAME_BUDGET := 120

var _failures: PackedStringArray = []
var _pickup_scene: PackedScene
var _health_scene: PackedScene
var _pickup_shape: Shape2D


func _initialize() -> void:
	_pickup_scene = load("res://Features/heal_pickup/HealPickup.tscn")
	_health_scene = load("res://Features/health/Health.tscn")
	var rect := RectangleShape2D.new()
	rect.size = Vector2(32, 32)
	_pickup_shape = rect
	if _pickup_scene == null or _health_scene == null:
		_failures.append("加载 HealPickup.tscn 或 Health.tscn 失败")
		_report()
		return

	# 1. 组内受伤目标接触：恢复 heal_amount，拾取物被消费移除
	var consumer := await _spawn_target("Consumer", true, Vector2(30, 0))
	var consumer_health: Health = consumer.get_node("Health")
	consumer_health.take_damage(3)
	var pickup := await _spawn_pickup(2, Vector2(30, 0))
	if not await _wait_for_pickup_gone(pickup):
		_failures.append("拾取物应在被消费后从场景移除")
	if consumer_health.get_current_health() != 4:
		_failures.append("拾取后生命值应为 4（5-3+2），实际 %d" % consumer_health.get_current_health())
	consumer.queue_free()
	await _wait_frames(2)

	# 2. 超量恢复钳制：受伤 1 点但恢复量大于缺口，恢复后不得超过 max_health
	var consumer2 := await _spawn_target("OverhealTarget", true, Vector2(0, 120))
	var health2: Health = consumer2.get_node("Health")
	health2.take_damage(1)
	var pickup2 := await _spawn_pickup(99, consumer2.position + Vector2(10, 0))
	await _wait_for_pickup_gone(pickup2)
	if health2.get_current_health() != 5:
		_failures.append("超量恢复应钳制在 max_health 5，实际 %d" % health2.get_current_health())
	consumer2.queue_free()
	await _wait_frames(2)

	# 3. 满血目标接触：不消费，拾取物保持在场，生命值不变
	var full_target := await _spawn_target("FullTarget", true, Vector2(0, 240))
	var full_health: Health = full_target.get_node("Health")
	var pickup3 := await _spawn_pickup(2, full_target.position + Vector2(10, 0))
	await _wait_frames(40)
	if full_health.get_current_health() != 5:
		_failures.append("满血目标生命值不应变化，实际 %d" % full_health.get_current_health())
	if not is_instance_valid(pickup3) or pickup3.is_queued_for_deletion():
		_failures.append("满血目标不应消费拾取物")
	pickup3.queue_free()
	full_target.queue_free()
	await _wait_frames(2)

	# 4. 组外目标接触：不消费
	var outsider := await _spawn_target("Outsider", false, Vector2(0, 360))
	var pickup4 := await _spawn_pickup(2, outsider.position + Vector2(10, 0))
	await _wait_frames(40)
	if not is_instance_valid(pickup4) or pickup4.is_queued_for_deletion():
		_failures.append("组外目标不应消费拾取物")
	pickup4.queue_free()
	outsider.queue_free()
	await _wait_frames(2)

	_report()


## 构建目标实体并入树，等待一帧让 Health 完成 _ready 初始化。
func _spawn_target(node_name: String, in_group: bool, position: Vector2) -> CharacterBody2D:
	var body := CharacterBody2D.new()
	body.name = node_name
	body.position = position
	if in_group:
		body.add_to_group("players")
	var health: Node = _health_scene.instantiate()
	health.name = "Health"
	body.add_child(health)
	var shape := CollisionShape2D.new()
	shape.shape = _pickup_shape
	body.add_child(shape)
	root.add_child(body)
	await physics_frame
	return body


## 构建拾取物并入树。
func _spawn_pickup(heal_amount: int, position: Vector2) -> Area2D:
	var pickup: Area2D = _pickup_scene.instantiate()
	pickup.heal_amount = heal_amount
	pickup.position = position
	var shape := CollisionShape2D.new()
	shape.shape = _pickup_shape
	pickup.add_child(shape)
	root.add_child(pickup)
	return pickup


## 逐帧等待拾取物被消费（离开树）；超时返回 false。
func _wait_for_pickup_gone(pickup: Area2D) -> bool:
	for _i: int in FRAME_BUDGET:
		if not is_instance_valid(pickup):
			return true
		await physics_frame
	return not is_instance_valid(pickup)


func _wait_frames(count: int) -> void:
	for _i: int in count:
		await physics_frame


func _report() -> void:
	if _failures.is_empty():
		print("PASS: HealPickup 组件验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
