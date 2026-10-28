extends SceneTree
## HitFlash 组件自身验证：受击触发与基色记录、衰减归零、长盖短重入、
## 治疗不触发、死亡豁免、主动 flash、无效时长、错误宿主拒绝、移除归还基色。
##
## 用法：godot --headless --path . -s res://Features/hit_flash/test_hit_flash.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

const FRAME_BUDGET := 240

var _failures: PackedStringArray = []
var _events: Array[bool] = []


func _initialize() -> void:
	var packed: PackedScene = load("res://Features/hit_flash/HitFlash.tscn")
	var health_packed: PackedScene = load("res://Features/health/Health.tscn")
	if packed == null or health_packed == null:
		_failures.append("加载 HitFlash.tscn / Health.tscn 失败")
		_report()
		return

	# ---- 1. 受击触发：modulate 被抬到 flash_color，广播一次 true ----
	var host := Node2D.new()
	root.add_child(host)
	var health: Node = health_packed.instantiate()
	health.set("max_health", 10)
	health.name = "Health"
	host.add_child(health)
	var flash_comp: Node = packed.instantiate()
	host.add_child(flash_comp)
	flash_comp.flashing.connect(_on_flashing)
	await physics_frame
	var base: Color = host.modulate
	health.take_damage(1)
	await _wait_frames(3)   # call_deferred 落地 + 下一帧 _physics_process 写入 modulate
	if _events != [true]:
		_failures.append("受击应广播一次 true，实际 %s" % str(_events))
	if host.modulate == base:
		_failures.append("闪白期间 modulate 应偏离基色")

	# ---- 2. 衰减归零：modulate 回基色，恰好广播一次 false ----
	# flash_duration=0.15s ≈ 9 帧；30 帧余量充足。
	await _wait_frames(30)
	if host.modulate != base:
		_failures.append("衰减结束后应回基色，实际 %s" % str(host.modulate))
	if _events != [true, false]:
		_failures.append("衰减结束应恰好广播一次 false，实际 %s" % str(_events))

	# ---- 3. 治疗不触发 ----
	_events.clear()
	health.heal(1)
	await _wait_frames(3)
	if _events != []:
		_failures.append("治疗不应触发闪白，实际 %s" % str(_events))

	# ---- 4. 闪白中再次受击：长盖短，不重复广播 true ----
	health.take_damage(1)
	await physics_frame
	flash_comp.flash(0.4)   # 手动叠加 0.4s > 剩余 0.15s → 剩余时长被拉长
	if _events != [true]:
		_failures.append("重入不应重复广播 true，实际 %s" % str(_events))
	await _wait_frames(12)  # 已超过默认 0.15s，但长盖短后仍在闪白
	if host.modulate == base:
		_failures.append("长盖短后 0.15s 处应仍在闪白")
	await _wait_frames(20)  # 0.4s 共 24 帧，余量充足
	if host.modulate != base or _events != [true, false]:
		_failures.append("拉长后的闪白应正常结束，实际 events=%s" % str(_events))

	# ---- 5. 死亡豁免：击杀后受击不再触发 ----
	_events.clear()
	health.take_damage(10)
	await physics_frame
	if not health.is_dead():
		_failures.append("前置：宿主应已死亡")
	if flash_comp.flash():
		_failures.append("死亡宿主 flash() 应返回 false")
	if _events != []:
		_failures.append("死亡宿主不应触发闪白，实际 %s" % str(_events))

	# ---- 6. 主动模式：无 Health 的宿主可手动 flash，无效时长忽略 ----
	var plain := Node2D.new()
	root.add_child(plain)
	var manual: Node = packed.instantiate()
	plain.add_child(manual)
	manual.flashing.connect(_on_flashing)
	await physics_frame
	var plain_base: Color = plain.modulate
	if not manual.flash(0.2):
		_failures.append("主动 flash 应返回 true")
	manual.flash_duration = 0.0
	if manual.flash():
		_failures.append("flash_duration=0 时 flash() 应返回 false")
	manual.flash_duration = 0.15
	await _wait_frames(3)   # 等 _physics_process 写入 modulate
	if plain.modulate == plain_base:
		_failures.append("主动 flash 应改变 modulate")
	if _events.size() < 1 or not _events.has(true):
		_failures.append("主动 flash 应广播 true")
	await _wait_frames(20)

	# ---- 7. 错误宿主：父节点非 CanvasItem 时拒绝 ----
	var bare := Node.new()
	root.add_child(bare)
	var misfit: Node = packed.instantiate()
	bare.add_child(misfit)
	await physics_frame
	if misfit.flash():
		_failures.append("父节点非 CanvasItem 时 flash 应返回 false")

	# ---- 8. 闪白中移除组件：基色归还 ----
	manual.flash(0.3)
	await _wait_frames(2)
	manual.queue_free()
	await _wait_frames(2)
	if plain.modulate != plain_base:
		_failures.append("组件移除后应归还基色，实际 %s" % str(plain.modulate))

	_report()


func _on_flashing(is_flashing: bool) -> void:
	_events.append(is_flashing)


func _wait_frames(count: int) -> void:
	for _i: int in count:
		await physics_frame


func _report() -> void:
	if _failures.is_empty():
		print("PASS: hit_flash 全部检查通过")
		quit(0)
	else:
		for f in _failures:
			print("FAIL: ", f)
		quit(1)
