extends SceneTree
## AttackEmitter 组件自身验证：属性传播、攻击链、射线命中结算、排除列表、
## 未命中信号、attacked 广播。
##
## 用法：godot --headless --path . -s res://Features/attack_emitter/test_attack_emitter.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

const FIXTURE_PATH := "res://Features/attack_emitter/AttackEmitterFixture.tscn"
const EMITTER_SCRIPT := preload("res://Features/attack_emitter/raycast_attack_emitter.gd")
const BASE_SCRIPT := preload("res://Features/attack_emitter/attack_emitter.gd")

var _failures: PackedStringArray = []


func _initialize() -> void:
	var fixture: Node2D = load(FIXTURE_PATH).instantiate()
	if fixture == null:
		_failures.append("加载 %s 失败" % FIXTURE_PATH)
		_report()
		return
	root.add_child(fixture)
	await physics_frame
	await physics_frame
	_run(fixture)
	_report()


func _run(fixture: Node2D) -> void:
	var emitter: RaycastAttackEmitter = fixture.get_node("Emitter")
	var target: FixtureTarget = fixture.get_node("Target")

	# 1. 命中：伤害结算 + attack_hit + attack_performed(hit=true)
	var hit_events: Array = []
	var performed: Array = []
	emitter.attack_hit.connect(func(t: Node, p: Vector2) -> void: hit_events.append([t, p]))
	emitter.attack_performed.connect(func(f: Vector2, t: Vector2, h: bool, p: Vector2) -> void:
		performed.append([f, t, h, p]))
	emitter.damage = 3
	emitter.do_attack()
	if target.damage_taken != 1:
		_failures.append("命中时目标应承受 1 次伤害，实际 %d" % target.damage_taken)
	if target.last_amount != 3:
		_failures.append("目标承受的伤害值应为 3，实际 %d" % target.last_amount)
	if hit_events.size() != 1:
		_failures.append("attack_hit 应触发 1 次，实际 %d" % hit_events.size())
	if performed.size() != 1 or not performed[0][2]:
		_failures.append("attack_performed 应以 hit=true 触发 1 次")

	# 2. 排除列表：被排除后同位置不再命中
	emitter.set_bodies_to_exclude([target])
	emitter.do_attack()
	if target.damage_taken != 1:
		_failures.append("被排除的目标不应再次受伤，实际 %d" % target.damage_taken)
	if performed.size() != 2 or performed[1][2]:
		_failures.append("排除后 attack_performed 应以 hit=false 触发")

	# 3. attacked 广播计数
	var attacked_events: Array = []
	emitter.attacked.connect(func() -> void: attacked_events.append(true))
	emitter.do_attack()
	if attacked_events.size() != 1:
		_failures.append("attacked 应触发 1 次，实际 %d" % attacked_events.size())

	# 4. 属性与攻击链传播：父发射器 damage / source 沿链传播到子与孙
	var parent := AttackEmitter.new()
	parent.name = "ParentEmitter"
	var child_ray: RaycastAttackEmitter = EMITTER_SCRIPT.new()
	child_ray.name = "ChildRay"
	var ray := RayCast2D.new()
	ray.target_position = Vector2(100, 0)
	child_ray.add_child(ray)
	var child_plain: AttackEmitter = BASE_SCRIPT.new()
	var grand_child: AttackEmitter = BASE_SCRIPT.new()
	child_plain.add_child(grand_child)
	parent.add_child(child_ray)
	parent.add_child(child_plain)
	parent.position = Vector2(1000, 0)  # 远离夹具目标，避免干扰命中计数
	fixture.add_child(parent)
	await physics_frame

	parent.damage = 9
	if child_ray.damage != 9 or grand_child.damage != 9:
		_failures.append("damage 应沿发射器链传播（ray=%d grand=%d）" % [child_ray.damage, grand_child.damage])
	var plain_attacked := 0
	grand_child.attacked.connect(func() -> void: plain_attacked += 1)
	parent.source_of_attack = parent
	if child_ray.source_of_attack != parent:
		_failures.append("source_of_attack 应沿链传播")
	parent.do_attack()
	if plain_attacked != 1:
		_failures.append("do_attack 应沿链传播到孙级发射器")
	if target.damage_taken != 1:
		_failures.append("远端发射器不应误伤夹具目标，实际 %d" % target.damage_taken)

	# 5. 传播的 damage 在子级实际结算：挪回夹具原点，damage=5 命中目标
	child_ray.position = Vector2.ZERO
	child_ray.damage = 5
	child_ray.do_attack()
	if target.damage_taken != 2 or target.last_amount != 5:
		_failures.append("传播后的 damage 应被实际结算（taken=%d amount=%d）" % [target.damage_taken, target.last_amount])


func _report() -> void:
	if _failures.is_empty():
		print("PASS: AttackEmitter 组件验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
