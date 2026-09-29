extends SceneTree
## Siege Gate 集成验证：多机制同时作用于同一实体的状态所有权实验。
##
## 覆盖：基础组合（Health/Stun/ContactDamage/ChaseMovement 同体）；
## 双 Stun 来源（受击被动 + 绊线主动 API）共用同一 Stun 实例、长盖短
## 不提前解除、无第二套状态；杀死一击无新增眩晕、死亡后主动请求被拒、
## 死亡宿主不被恢复逻辑复活；died→set_open 数据连接；R 重开复现。
##
## 用法：godot --headless --path . -s res://Tests/test_siege_gate.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

const FRAME_BUDGET := 240

var _failures: PackedStringArray = []
var _stun_events: Array[bool] = []


func _initialize() -> void:
	var packed: PackedScene = load("res://Scenes/SiegeGate.tscn")
	if packed == null:
		_failures.append("加载 res://Scenes/SiegeGate.tscn 失败")
		_report()
		return

	# ---- A. 基础组合：四个组件共存于 Guard 实体 ----
	var scene: Node2D = packed.instantiate()
	root.add_child(scene)
	current_scene = scene
	await process_frame
	var player: CharacterBody2D = scene.get_node("Player")
	var guard: CharacterBody2D = scene.get_node("Guard")
	var door: StaticBody2D = scene.get_node("Mechanism/ExitDoor")
	var tripwire: Area2D = scene.get_node("Mechanism/Tripwire")
	var guard_health: Health = guard.get_node("Health")
	var guard_stun: Node = guard.get_node("Stun")

	if not guard.is_in_group("enemies"):
		_failures.append("Guard 应处于 enemies 组（攻击解析前提）")
	if guard.get_script() == null or not guard is ChaseMovement:
		_failures.append("Guard 根脚本应为 chase_movement（移动线）")
	if guard_health == null or guard_health.max_health != 5:
		_failures.append("Guard 应组合 Health（HP/死亡状态所有者）")
	if guard.get_node_or_null("ContactDamage") == null:
		_failures.append("Guard 应组合 ContactDamage（伤害线）")
	if guard_stun == null:
		_failures.append("Guard 应组合 Stun（行动限制状态所有者）")
	if not guard_stun.get("stun_on_hit"):
		_failures.append("Guard Stun 应为受击自触发模式")
	if door.is_open():
		_failures.append("出口门初始应关闭")
	guard_stun.stunned.connect(_on_stun_event)

	# ---- B. 双 Stun 来源：被动受击 + 绊线主动 API 共用同一实例 ----
	player.global_position = Vector2(-460, 0)
	guard.global_position = Vector2(240, 0)
	await _wait_frames(10)
	# B1 被动：受击 → stun_on_hit 延迟一帧落地
	guard_health.take_damage(1)
	await process_frame
	if not guard_stun.is_stunned():
		_failures.append("受击后应进入硬直（被动路径）")
	if guard.is_physics_processing():
		_failures.append("硬直期间追击应停摆")
	# B2 主动：绊线对同一 Stun 调用 stun(1.0)；长盖短，不提前解除
	player.global_position = tripwire.global_position
	await _wait_frames(5) # body_entered 触发并落地
	var stun_children := 0
	for child in guard.get_children():
		if child is Stun:
			stun_children += 1
	if stun_children != 1:
		_failures.append("Guard 应只有一个 Stun 实例（无第二套状态），实际 %d" % stun_children)
	await _wait_frames(12) # 距被动触发已 0.78s > 0.6s：若无长盖短应已恢复
	if not guard_stun.is_stunned():
		_failures.append("长盖短：主动 1.0s 不应被旧剩余提前解除")
	if _stun_events != [true]:
		_failures.append("重入期间不应有新广播（单状态域），实际 %s" % str(_stun_events))
	await _wait_frames(70) # 距绊线触发 > 1.0s：到点恢复
	if guard_stun.is_stunned():
		_failures.append("1.0s 到点后应恢复")
	if not guard.is_physics_processing():
		_failures.append("恢复后追击应重新启用")
	if _stun_events != [true, false]:
		_failures.append("全程应恰好一次 true + 一次 false，实际 %s" % str(_stun_events))

	# ---- C. Death 与 Stun 竞态：杀死一击无新增眩晕、死后请求被拒 ----
	player.global_position = Vector2(-460, 0)
	await _wait_frames(5)
	guard_health.take_damage(1) # 存活期受击 → 进入硬直
	await process_frame
	if not guard_stun.is_stunned():
		_failures.append("死亡竞态前置：守卫应先进入硬直")
	guard_health.take_damage(9999) # 击杀一击：health_changed 早于 died
	await process_frame
	if not guard_health.is_dead():
		_failures.append("击杀后 Health 应进入 dead")
	await _wait_frames(50) # 既有硬直到点：恢复逻辑不得复活死亡宿主
	if guard.is_physics_processing():
		_failures.append("死亡宿主不得被恢复逻辑重新启用物理")
	if guard_stun.stun(0.3):
		_failures.append("死亡后的直接 stun 请求应被拒绝")
	player.global_position = tripwire.global_position # 死后绊线路径同样被拒
	await _wait_frames(10)
	if guard_stun.is_stunned():
		_failures.append("死亡后的绊线 stun 请求应被拒绝")

	# ---- D. Death → Door：门状态由 Door Feature 拥有，Glue 只连接信号 ----
	if not await _wait_until(func() -> bool: return door.is_open()):
		_failures.append("守卫死亡应经数据连接打开大门（等待超时）")

	# ---- E. R 重开：实体/门/眩晕配置全部随场景重建 ----
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
	var fresh_door: StaticBody2D = fresh.get_node("Mechanism/ExitDoor")
	var fresh_guard: CharacterBody2D = fresh.get_node("Guard")
	var fresh_health: Health = fresh_guard.get_node("Health")
	var fresh_stun: Node = fresh_guard.get_node("Stun")
	if fresh_door.is_open():
		_failures.append("重开后大门应恢复关闭")
	if fresh_health.is_dead() or fresh_health.get_current_health() != 5:
		_failures.append("重开后守卫应满血复活")
	if fresh_stun.get("stun_duration") != 0.6:
		_failures.append("重开后眩晕配置应随场景重建")
	if not fresh_guard.is_physics_processing():
		_failures.append("重开后守卫物理应可用（追击恢复）")
	# 机制复现：新实例双路径再次工作（先被动，再主动，同一状态域）
	if fresh_stun.is_stunned():
		_failures.append("重开后守卫初始不应处于眩晕")
	fresh_health.take_damage(1)
	await process_frame
	if not fresh_stun.is_stunned():
		_failures.append("重开后受击硬直应再次生效（被动路径复现）")
	var fresh_tripwire: Area2D = fresh.get_node("Mechanism/Tripwire")
	fresh.get_node("Player").global_position = fresh_tripwire.global_position
	await _wait_frames(5)
	if not fresh_stun.is_stunned():
		_failures.append("重开后绊线麻痹应再次生效（主动路径复现）")

	_report()


func _on_stun_event(value: bool) -> void:
	_stun_events.append(value)


func _wait_until(predicate: Callable) -> bool:
	for _i: int in FRAME_BUDGET:
		if predicate.call():
			return true
		await process_frame
	return false


func _wait_frames(count: int) -> void:
	for _i: int in count:
		await physics_frame


func _report() -> void:
	if _failures.is_empty():
		print("PASS: Siege Gate 集成验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
