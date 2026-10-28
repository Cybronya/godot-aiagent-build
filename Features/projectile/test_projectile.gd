extends SceneTree
## Projectile 自身验证：发射位移、命中带 Health 实体并造成伤害、穿透数终止、
## 无限穿透、无 Health 物体穿过、生命期到期、发射前休眠、零向量方向忽略。
##
## 注意：GDScript lambda 对局部变量按值捕获，测试计数器必须用成员变量。
##
## 用法：godot --headless --path . -s res://Features/projectile/test_projectile.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

const FRAME_BUDGET := 240

var _failures: PackedStringArray = []
var _hits: Array[Node] = []       # 最近一次场景的命中目标
var _finish_count := 0            # 最近一次场景的 finished 计数


func _initialize() -> void:
	var packed: PackedScene = load("res://Features/projectile/Projectile.tscn")
	var health_packed: PackedScene = load("res://Features/health/Health.tscn")
	if packed == null or health_packed == null:
		_failures.append("加载 Projectile.tscn / Health.tscn 失败")
		_report()
		return

	# ---- 1. 发射前休眠：不 launch 不移动 ----
	var p1: Area2D = packed.instantiate()
	root.add_child(p1)
	await _wait_frames(5)
	if p1.position != Vector2.ZERO:
		_failures.append("未发射的抛射物不应移动，实际 %s" % str(p1.position))

	# ---- 2. 发射位移：方向恒定、速度正确 ----
	p1.launch(Vector2(10, 0))
	var start: Vector2 = p1.position
	await _wait_frames(10)  # 速度 300 px/s，10 帧 ≈ 50 px
	var moved: Vector2 = p1.position - start
	if absf(moved.x - 50.0) > 3.0 or absf(moved.y) > 0.5:
		_failures.append("10 帧位移应约 (50, 0)，实际 %s" % str(moved))
	p1.queue_free()
	await _wait_frames(1)

	# ---- 3. 命中带 Health 实体：造成伤害 + hit 信号 + 穿透耗尽终止 ----
	_hits.clear()
	_finish_count = 0
	var p2: Area2D = packed.instantiate()
	p2.max_hits = 1
	p2.damage = 2
	root.add_child(p2)
	p2.hit.connect(_on_hit)
	p2.finished.connect(_on_finished)
	var enemy := _make_enemy(health_packed, 10, Vector2(120, 0))
	root.add_child(enemy)
	p2.launch(Vector2.RIGHT)
	await _wait_frames(30)  # 300px/s 接触点约 21 帧，余量充足
	if _hits.size() != 1:
		_failures.append("应恰好命中一次，实际 %d" % _hits.size())
	elif enemy.get_node("Health").get_current_health() != 8:
		_failures.append("命中应造成 2 点伤害，实际血量 %d"
				% enemy.get_node("Health").get_current_health())
	if _finish_count != 1:
		_failures.append("穿透耗尽应终止一次，实际 %d" % _finish_count)
	if is_instance_valid(p2) and not p2.is_queued_for_deletion():
		_failures.append("穿透耗尽后应 queue_free")
	enemy.queue_free()
	await _wait_frames(2)

	# ---- 4. 无限穿透（max_hits<1）：连续穿过两个敌人 ----
	_hits.clear()
	_finish_count = 0
	var p3: Area2D = packed.instantiate()
	p3.max_hits = -1
	p3.speed = 400.0
	root.add_child(p3)
	p3.hit.connect(_on_hit)
	p3.finished.connect(_on_finished)
	var e1 := _make_enemy(health_packed, 10, Vector2(80, 0))
	var e2 := _make_enemy(health_packed, 10, Vector2(160, 0))
	root.add_child(e1)
	root.add_child(e2)
	p3.launch(Vector2.RIGHT)
	await _wait_frames(30)
	if _hits.size() < 2:
		_failures.append("无限穿透应至少命中两个，实际 %d" % _hits.size())
	if _finish_count != 0:
		_failures.append("无限穿透不应因命中终止")
	if is_instance_valid(p3) and p3.is_queued_for_deletion():
		_failures.append("无限穿透不应被释放")
	p3.queue_free()
	e1.queue_free()
	e2.queue_free()
	await _wait_frames(2)

	# ---- 5. 无 Health 物体：直接穿过，无 hit 信号 ----
	_hits.clear()
	var p4: Area2D = packed.instantiate()
	root.add_child(p4)
	p4.hit.connect(_on_hit)
	var wall := StaticBody2D.new()
	var wall_shape := CollisionShape2D.new()
	var box := RectangleShape2D.new()
	box.size = Vector2(20, 60)
	wall_shape.shape = box
	wall.add_child(wall_shape)
	wall.position = Vector2(100, 0)
	root.add_child(wall)
	p4.launch(Vector2.RIGHT)
	await _wait_frames(30)  # 300px/s 30 帧 = 150px，越过墙（x≈100）仍在飞
	if _hits.size() != 0:
		_failures.append("无 Health 物体不应触发 hit，实际 %d" % _hits.size())
	if not is_instance_valid(p4):
		_failures.append("穿过无 Health 物体后不应被释放")
	p4.queue_free()
	wall.queue_free()
	await _wait_frames(2)

	# ---- 6. 生命期到期：finished 恰一次后自释放 ----
	_finish_count = 0
	var p5: Area2D = packed.instantiate()
	p5.lifetime = 0.2
	p5.speed = 100.0
	root.add_child(p5)
	p5.finished.connect(_on_finished)
	p5.launch(Vector2.RIGHT)
	await _wait_frames(20)
	if _finish_count != 1:
		_failures.append("生命期到期应终止恰好一次，实际 %d" % _finish_count)
	if is_instance_valid(p5) and not p5.is_queued_for_deletion():
		_failures.append("到期后应 queue_free")

	# ---- 7. 零向量方向：launch 忽略 ----
	var p6: Area2D = packed.instantiate()
	root.add_child(p6)
	p6.launch(Vector2.ZERO)
	await _wait_frames(3)
	if p6.position != Vector2.ZERO:
		_failures.append("零向量 launch 应被忽略")
	p6.queue_free()

	_report()


func _on_hit(target: Node) -> void:
	_hits.append(target)


func _on_finished() -> void:
	_finish_count += 1


func _make_enemy(health_packed: PackedScene, max_hp: int, pos: Vector2) -> Node2D:
	var body := CharacterBody2D.new()
	body.position = pos
	var shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(24, 24)
	shape.shape = rect
	body.add_child(shape)
	var health: Node = health_packed.instantiate()
	health.set("max_health", max_hp)
	health.name = "Health"
	body.add_child(health)
	return body


func _wait_frames(count: int) -> void:
	for _i: int in count:
		await physics_frame


func _report() -> void:
	if _failures.is_empty():
		print("PASS: projectile 全部检查通过")
		quit(0)
	else:
		for f in _failures:
			print("FAIL: ", f)
		quit(1)
