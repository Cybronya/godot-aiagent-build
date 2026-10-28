extends SceneTree
## IFrames 组件自身验证：受击自动开窗与门控生效、窗口内免伤、到期恢复、
## 治疗不触发、固定窗口不刷新、死亡豁免、主动 grant、移除归还门状态、
## Health 门与历史行为的兼容（默认关闭时不受影响）。
##
## 用法：godot --headless --path . -s res://Features/i_frames/test_i_frames.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

const FRAME_BUDGET := 240

var _failures: PackedStringArray = []
var _events: Array[bool] = []


func _initialize() -> void:
	var packed: PackedScene = load("res://Features/i_frames/IFrames.tscn")
	var health_packed: PackedScene = load("res://Features/health/Health.tscn")
	if packed == null or health_packed == null:
		_failures.append("加载 IFrames.tscn / Health.tscn 失败")
		_report()
		return

	# ---- 0. Health 门加性扩展兼容：默认关闭时行为与历史一致 ----
	var bare_health: Node = health_packed.instantiate()
	bare_health.set("max_health", 10)
	root.add_child(bare_health)
	await physics_frame
	bare_health.take_damage(1)
	if bare_health.get_current_health() != 9:
		_failures.append("默认关闭时 Health 应照常受伤")
	if bare_health.is_invulnerable():
		_failures.append("默认应非无敌")
	bare_health.queue_free()

	# ---- 1. 受击自动开窗：门打开 + 受击免伤 + 广播一次 true ----
	var host := Node2D.new()
	root.add_child(host)
	var health: Node = health_packed.instantiate()
	health.set("max_health", 10)
	health.name = "Health"
	host.add_child(health)
	var iframes: Node = packed.instantiate()
	iframes.duration = 0.3
	host.add_child(iframes)
	iframes.protected.connect(_on_protected)
	await physics_frame
	health.take_damage(1)
	await _wait_frames(3)   # call_deferred 落地 + Cooldown 启动
	if _events != [true]:
		_failures.append("受击应广播一次 true，实际 %s" % str(_events))
	if not health.is_invulnerable():
		_failures.append("窗口内 Health 应处于无敌")
	health.take_damage(1)   # 窗口内攻击被门拒绝
	if health.get_current_health() != 9:
		_failures.append("窗口内 take_damage 应被拒绝，实际血量 %d" % health.get_current_health())

	# ---- 2. 固定窗口：窗口内再次受击不刷新时长 ----
	await _wait_frames(10)  # 0.3s ≈ 18 帧，已过半
	if not iframes.is_protected():
		_failures.append("0.13s 处应仍在保护中")
	health.take_damage(1)
	if health.get_current_health() != 9:
		_failures.append("窗口中段攻击应被拒绝")

	# ---- 3. 到期恢复：门关闭 + 广播 false + 可再次受伤 ----
	await _wait_frames(15)  # 累计约 0.47s > 0.3s
	if health.is_invulnerable():
		_failures.append("到期后应恢复可受击")
	if _events != [true, false]:
		_failures.append("到期应恰好广播一次 false，实际 %s" % str(_events))
	health.take_damage(1)
	if health.get_current_health() != 8:
		_failures.append("到期后应能再次受伤，实际血量 %d" % health.get_current_health())
	await _wait_frames(25)  # 这次受击又开了一个新窗口，等它结束再测治疗
	if _events.size() < 2:
		_failures.append("前置：新窗口应已开启并结束，实际 %s" % str(_events))

	# ---- 4. 治疗不触发 ----
	_events.clear()
	health.heal(1)
	await _wait_frames(3)
	if _events != []:
		_failures.append("治疗不应触发保护，实际 %s" % str(_events))

	# ---- 5. 主动 grant：生效；保护中重复 grant 拒绝（固定窗口） ----
	if not iframes.grant(0.2):
		_failures.append("主动 grant 应生效")
	if iframes.grant(0.5):
		_failures.append("保护中 grant 应拒绝（固定窗口不刷新）")
	if not health.is_invulnerable():
		_failures.append("grant 后应无敌")
	await _wait_frames(20)  # 0.2s = 12 帧 + 余量
	if _events != [true, false]:
		_failures.append("grant 窗口应正常结束，实际 %s" % str(_events))

	# ---- 6. 死亡豁免：击杀后不再开窗 ----
	_events.clear()
	health.take_damage(10)
	await physics_frame
	if not health.is_dead():
		_failures.append("前置：宿主应已死亡")
	if iframes.grant():
		_failures.append("死亡宿主 grant 应拒绝")
	if _events != []:
		_failures.append("死亡宿主不应开窗，实际 %s" % str(_events))

	# ---- 7. 无 Health 宿主：自动模式不炸，grant 拒绝 ----
	var plain := Node2D.new()
	root.add_child(plain)
	var loner: Node = packed.instantiate()
	plain.add_child(loner)
	await physics_frame
	if loner.grant():
		_failures.append("无 Health 时 grant 应拒绝")

	# ---- 8. 保护中移除组件：门状态归还 ----
	var host2 := Node2D.new()
	root.add_child(host2)
	var health2: Node = health_packed.instantiate()
	health2.set("max_health", 10)
	health2.name = "Health"
	host2.add_child(health2)
	var iframes2: Node = packed.instantiate()
	host2.add_child(iframes2)
	await physics_frame
	iframes2.grant(0.5)
	await _wait_frames(2)
	iframes2.queue_free()
	await _wait_frames(2)
	if health2.is_invulnerable():
		_failures.append("组件移除后门应归还为可受击")

	_report()


func _on_protected(is_protected: bool) -> void:
	_events.append(is_protected)


func _wait_frames(count: int) -> void:
	for _i: int in count:
		await physics_frame


func _report() -> void:
	if _failures.is_empty():
		print("PASS: i_frames 全部检查通过")
		quit(0)
	else:
		for f in _failures:
			print("FAIL: ", f)
		quit(1)
