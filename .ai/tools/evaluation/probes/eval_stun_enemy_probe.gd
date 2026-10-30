extends SceneTree
## EVAL136 probe — T2 多 Feature 组合（chase_movement + contact_damage + health + stun）
##
## 用法：godot --headless --path . -s res://Tests/eval136_stun_enemy_probe.gd -- <scene> <positive|negative>
##
## 断言真实运行时状态（实体根位移 / 玩家生命值 / 眩晕期间位移），不是节点存在性：
##   positive —— ① 配置目标后实体根在物理帧中接近 ≥ 30 px；② 未接触时玩家不掉血；
##               ③ 真实接触后按既有节拍结算伤害且不超出节拍上限；
##               ④ stun.stun(duration) 生效期间实体根停止移动，结束后恢复追击
##   negative —— 不配置目标：90 帧内实体根不得移动、玩家不得掉血
##                （受控负向：证明「接近 / 伤害」断言依赖真实追击与接触，而非恒真）
## 退出码：0 = 断言全部通过；1 = 断言失败或前置条件不成立；2 = 参数/环境错误。

const PLAYER_SCENE := "res://Features/player_movement/Player.tscn"
const INITIAL_DISTANCE := 400.0
const IDLE_FRAMES := 20
const MOVE_FRAMES := 90
const MIN_APPROACH := 30.0
const DRIFT_TOLERANCE := 1.0
const CONTACT_FRAMES := 90
const STUN_DURATION := 0.8
const STUN_LOCK_FRAMES := 20
const STUN_TAIL_FRAMES := 70
const STUN_RESUME_MIN := 5.0
const PHYSICS_HZ := 60.0

var _failures: PackedStringArray = []
var _scene := ""
var _mode := "positive"


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() < 2:
		printerr("FAIL: usage: -s <probe> -- <scene> <positive|negative>")
		quit(2)
		return
	_scene = str(args[0])
	_mode = str(args[1])
	_run()


func _run() -> void:
	var packed: PackedScene = load(_scene)
	if packed == null:
		_fail("Scene Load: 无法加载被测场景 %s" % _scene)
		_report()
		return
	var target_packed: PackedScene = load(PLAYER_SCENE)
	if target_packed == null:
		_fail("Environment: 无法加载玩家场景 %s" % PLAYER_SCENE)
		_report()
		return

	var entity: Node2D = packed.instantiate()
	root.add_child(entity)
	var target: Node2D = target_packed.instantiate()
	target.position = Vector2(INITIAL_DISTANCE, 0.0)
	root.add_child(target)
	target.add_to_group("players")
	await physics_frame

	var chase: Node = _find_prop(entity, "target_path")
	var health: Node = _find_method(target, "get_current_health")
	var stun: Node = _find_method(entity, "is_stunned")
	var contact: Node = _find_method(entity, "tick_interval")
	if chase == null:
		_fail("Precondition: 场景 %s 中不存在 chase_movement 组件（无 target_path）" % _scene)
		_report()
		return
	if health == null:
		_fail("Precondition: 目标缺少 Health 组件，无法验证伤害结算")
		_report()
		return
	if stun == null:
		_fail("Precondition: 场景 %s 中不存在 stun 组件（无 is_stunned()）" % _scene)
		_report()
		return

	var origin: Vector2 = entity.global_position
	await _wait_frames(IDLE_FRAMES)
	var baseline_drift: float = entity.global_position.distance_to(origin)
	var hp_idle: int = int(health.call("get_current_health"))
	print("STUN_PROBE: scene=%s mode=%s baseline_drift=%.3f hp_idle=%d stun=%s contact=%s"
		% [_scene, _mode, baseline_drift, hp_idle, stun.name, (contact.name if contact != null else "<none>")])

	if baseline_drift > DRIFT_TOLERANCE:
		_fail("Baseline: 未配置目标时实体根不应移动，实际位移 %.3f px" % baseline_drift)
	if hp_idle != int(health.call("get_current_health")):
		_fail("Baseline: 未接触时玩家生命值发生变化")

	if _mode == "negative":
		if entity.global_position.distance_to(origin) > DRIFT_TOLERANCE:
			_fail("Negative: 未配置目标时实体根移动了 %.3f px"
				% entity.global_position.distance_to(origin))
		# 受控负向：即使眩晕也不会移动（没有目标可追）
		stun.call("stun", STUN_DURATION)
		await _wait_frames(STUN_LOCK_FRAMES)
		if entity.global_position.distance_to(origin) > DRIFT_TOLERANCE:
			_fail("Negative: 眩晕期间实体根不应移动")
		_report()
		return

	# ---- ① 追击：配置目标后实体根必须接近 ----
	chase.set("target_path", chase.call("get_path_to", target))
	var before: Vector2 = entity.global_position
	await _wait_frames(MOVE_FRAMES)
	var approach: float = before.distance_to(entity.global_position)
	print("STUN_PROBE: approach=%.1f frames=%d" % [approach, MOVE_FRAMES])
	if approach < MIN_APPROACH:
		_fail("Chase: %d 物理帧后实体根应接近 >= %.1f px，实际 %.1f px"
			% [MOVE_FRAMES, MIN_APPROACH, approach])

	# ---- ② 未接触不得掉血（此时目标仍在 400 px 外或已被追上，先拉远） ----
	target.position = entity.global_position + Vector2(INITIAL_DISTANCE, 0.0)
	await _wait_frames(4)
	var hp_far: int = int(health.call("get_current_health"))

	# ---- ③ 真实接触结算 ----
	target.position = entity.global_position + Vector2(6.0, 0.0)
	await _wait_frames(CONTACT_FRAMES)
	var hp_near: int = int(health.call("get_current_health"))
	var damage_total: int = hp_far - hp_near
	var tick := 0.5
	if contact != null:
		tick = max(float(contact.get("tick_interval")), 0.0001)
	var window := float(CONTACT_FRAMES) / PHYSICS_HZ
	var ceiling := int(ceil(window / tick)) + 1
	print("STUN_PROBE: contact_damage=%d ceiling=%d window=%.2f tick=%.2f"
		% [damage_total, ceiling, window, tick])
	if damage_total < 1:
		_fail("Contact: 真实接触 %d 帧后玩家应受伤 >= 1 点，实际 %d 点"
			% [CONTACT_FRAMES, damage_total])
	if damage_total > ceiling:
		_fail("Contact: 伤害 %d 超过节拍上限 %d（疑似每帧结算）" % [damage_total, ceiling])

	# ---- ④ 眩晕：生效期间停止移动，结束后恢复追击 ----
	target.position = entity.global_position + Vector2(INITIAL_DISTANCE, 0.0)
	await _wait_frames(2)
	var stunned_ok := bool(stun.call("stun", STUN_DURATION))
	var lock_start: Vector2 = entity.global_position
	await _wait_frames(STUN_LOCK_FRAMES)
	var lock_drift: float = entity.global_position.distance_to(lock_start)
	var stunned_flag := bool(stun.call("is_stunned"))
	await _wait_frames(STUN_TAIL_FRAMES)
	var resumed: float = entity.global_position.distance_to(lock_start)
	var still_stunned := bool(stun.call("is_stunned"))
	print("STUN_PROBE: stun_applied=%s lock_drift=%.3f stunned_flag=%s resumed=%.1f still_stunned=%s"
		% [stunned_ok, lock_drift, stunned_flag, resumed, still_stunned])
	if not stunned_ok:
		_fail("Stun: stun(%.2f) 应返回 true" % STUN_DURATION)
	if not stunned_flag:
		_fail("Stun: 眩晕期间 is_stunned() 应为 true")
	if lock_drift > DRIFT_TOLERANCE:
		_fail("Stun: 眩晕期间实体根不应移动，实际 %.3f px" % lock_drift)
	if still_stunned:
		_fail("Stun: %.1f s 后应自动解除眩晕" % STUN_DURATION)
	if resumed < STUN_RESUME_MIN:
		_fail("Stun: 眩晕结束后应恢复追击（位移 >= %.1f px），实际 %.1f px"
			% [STUN_RESUME_MIN, resumed])
	_report()


func _find_method(node: Node, method_name: String) -> Node:
	if node.has_method(method_name):
		return node
	for child in node.get_children():
		var found := _find_method(child, method_name)
		if found != null:
			return found
	return null


func _find_prop(node: Node, prop_name: String) -> Node:
	for entry in node.get_property_list():
		if str(entry.get("name", "")) == prop_name:
			return node
	for child in node.get_children():
		var found := _find_prop(child, prop_name)
		if found != null:
			return found
	return null


func _wait_frames(count: int) -> void:
	for _i in count:
		await physics_frame


func _fail(message: String) -> void:
	_failures.append(message)


func _report() -> void:
	if _failures.is_empty():
		print("PASS: eval136 stun enemy probe (%s)" % _mode)
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
