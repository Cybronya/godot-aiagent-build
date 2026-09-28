extends SceneTree
## Stun 组件自身验证：主动眩晕/恢复/幂等刷新与长盖短重入、无效输入、
## 受击自触发与恢复豁免、物理停摆与恢复、死亡保护（不再触发/恢复不越权）、多实例独立。
##
## 用法：godot --headless --path . -s res://Features/stun/test_stun.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

const FRAME_BUDGET := 240

var _failures: PackedStringArray = []
var _events: Array[bool] = []


func _initialize() -> void:
	var packed: PackedScene = load("res://Features/stun/Stun.tscn")
	if packed == null:
		_failures.append("加载 res://Features/stun/Stun.tscn 失败")
		_report()
		return

	# ---- 1. 主动眩晕：停摆物理 + 清速度 + 广播 true，到时恢复 ----
	var host := _make_host()
	root.add_child(host)
	var stun_component: Node = packed.instantiate()
	host.add_child(stun_component)
	stun_component.stunned.connect(_on_stunned)
	await process_frame
	host.velocity = Vector2(50, 0)
	if not stun_component.stun(0.3):
		_failures.append("有效眩晕应返回 true")
	if not stun_component.is_stunned():
		_failures.append("眩晕后应处于眩晕状态")
	if _events != [true]:
		_failures.append("眩晕开始应广播一次 true，实际 %s" % str(_events))
	if host.is_physics_processing():
		_failures.append("眩晕期间宿主物理应停摆")
	await _wait_frames(30)
	if stun_component.is_stunned():
		_failures.append("0.3s 眩晕应在 30 帧内恢复")
	if _events != [true, false]:
		_failures.append("恢复应广播一次 false，实际 %s" % str(_events))
	if not host.is_physics_processing():
		_failures.append("恢复后宿主物理应重新启用")

	# ---- 2. 幂等刷新：时长内再次眩晕只刷新不重复广播 ----
	stun_component.stun(0.3)
	stun_component.stun(0.3)
	if _events.size() != 3:
		_failures.append("时长内重复眩晕不应重复广播，实际 %d 次" % (_events.size() - 2))
	await _wait_frames(40)
	if _events != [true, false, true, false]:
		_failures.append("刷新后应单次恢复，实际 %s" % str(_events))

	# ---- 2b. 长盖短：剩余约 0.1s 时再晕 0.4s，不被旧剩余提前解除，到点恢复 ----
	stun_component.stun(0.3)
	await _wait_frames(12)
	var events_at_reentry := _events.size() # 新一轮眩晕的 true 已计入基准
	if not stun_component.is_stunned():
		_failures.append("长盖短前置：应仍在眩晕中")
	stun_component.stun(0.4)
	await _wait_frames(12)
	if not stun_component.is_stunned():
		_failures.append("长盖短：不应被旧剩余时长提前解除")
	if _events.size() != events_at_reentry:
		_failures.append("长盖短重入期间不应有状态广播")
	await _wait_frames(24)
	if stun_component.is_stunned():
		_failures.append("长盖短：新时长到点后应恢复")
	if _events.size() != events_at_reentry + 1:
		_failures.append("长盖短全程应恰好新增 true+false，实际 %s" % str(_events.slice(events_at_reentry - 1)))

	# ---- 3. 无效输入：非正时长忽略；宿主缺失时不报错 ----
	var size_before_invalid := _events.size()
	if stun_component.stun(0.0) or stun_component.stun(-1.0):
		_failures.append("非正时长应忽略并返回 false")
	if _events.size() != size_before_invalid:
		_failures.append("无效眩晕不应广播")
	var orphan: Node = packed.instantiate()
	root.add_child(orphan)
	await process_frame
	orphan.stun(0.3)
	if orphan.is_stunned():
		_failures.append("无宿主时眩晕不应进入状态")
	orphan.queue_free()

	# ---- 4. 受击自触发（stun_on_hit）：延迟一帧落地 + 治疗豁免 ----
	var hit_host := _make_host()
	root.add_child(hit_host)
	var hit_stun: Node = packed.instantiate()
	hit_stun.stun_on_hit = true
	hit_host.add_child(hit_stun)
	hit_stun.stunned.connect(_on_stunned)
	await process_frame
	var hit_health: Health = hit_host.get_node("Health")
	hit_health.take_damage(1)
	await process_frame
	if not hit_stun.is_stunned():
		_failures.append("受击后应自动眩晕")
	if hit_host.is_physics_processing():
		_failures.append("受击眩晕期间物理应停摆")
	# 眩晕期间被治疗：到时恢复，物理重新启用
	hit_health.heal(1)
	await _wait_frames(40)
	if hit_stun.is_stunned():
		_failures.append("受击眩晕应到时恢复")
	if not hit_host.is_physics_processing():
		_failures.append("恢复后物理应启用")
	# 恢复治疗（数值上升）不触发新眩晕
	if _events[-1] == true:
		_failures.append("治疗不应触发眩晕")

	# ---- 5. 死亡保护：击杀不触发；直接调用被拒；恢复不越权复活 ----
	hit_health.take_damage(9999)
	await process_frame
	if hit_stun.is_stunned():
		_failures.append("击杀的受击眩晕应被死亡守卫拒绝")
	if hit_stun.stun(0.3):
		_failures.append("死亡宿主的直接眩晕应被拒绝")
	# 死亡时正在眩晕中：到点恢复不应重新启用物理（由死亡订阅方负责）
	var dead_host := _make_host()
	root.add_child(dead_host)
	var dead_stun: Node = packed.instantiate()
	dead_host.add_child(dead_stun)
	await process_frame
	dead_stun.stun(1.0)
	dead_host.get_node("Health").take_damage(9999)
	await _wait_frames(70)
	if dead_stun.is_stunned():
		_failures.append("死亡后眩晕应到时结束")
	if dead_host.is_physics_processing():
		_failures.append("死亡宿主恢复时不应被本组件复活物理")
	dead_host.queue_free()

	# ---- 6. 多实例独立：两个宿主眩晕互不影响 ----
	var host_a := _make_host()
	var host_b := _make_host()
	root.add_child(host_a)
	root.add_child(host_b)
	var stun_a: Node = packed.instantiate()
	var stun_b: Node = packed.instantiate()
	host_a.add_child(stun_a)
	host_b.add_child(stun_b)
	await process_frame
	stun_a.stun(0.4)
	if not stun_a.is_stunned() or stun_b.is_stunned():
		_failures.append("多实例眩晕应相互独立")

	host_a.queue_free()
	host_b.queue_free()
	await process_frame
	_report()


func _make_host() -> CharacterBody2D:
	var body := CharacterBody2D.new()
	body.motion_mode = 1
	var shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(24, 24)
	shape.shape = rect
	body.add_child(shape)
	body.add_child(load("res://Features/health/Health.tscn").instantiate())
	return body


func _on_stunned(value: bool) -> void:
	_events.append(value)


func _wait_frames(count: int) -> void:
	for _i: int in count:
		await physics_frame


func _report() -> void:
	if _failures.is_empty():
		print("PASS: Stun 组件验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
