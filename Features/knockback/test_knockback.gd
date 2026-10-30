extends SceneTree
## Knockback 组件自身验证：施加位移、幂等广播、线性衰减归零、重启覆盖、
## 方向归一化、无效输入、错误宿主（父节点非 CharacterBody2D）拒绝。
##
## 用法：godot --headless --path . -s res://Features/knockback/test_knockback.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

var _failures: PackedStringArray = []
var _events: Array[bool] = []


func _initialize() -> void:
	var packed: PackedScene = load("res://Features/knockback/Knockback.tscn")
	if packed == null:
		_failures.append("加载 res://Features/knockback/Knockback.tscn 失败")
		_report()
		return

	# ---- 1. 正常宿主：apply 生效、广播一次 true、随后帧产生位移 ----
	var body := CharacterBody2D.new()
	root.add_child(body)
	var knock: Node = packed.instantiate()
	body.add_child(knock)
	knock.knockback_changed.connect(_on_changed)
	await physics_frame
	if not knock.apply(Vector2(1, 0), 240.0):
		_failures.append("有效 apply 应返回 true")
	if _events != [true]:
		_failures.append("首次触发应广播一次 true，实际 %s" % str(_events))
	var start: Vector2 = body.global_position
	await _wait_frames(6)
	var moved: Vector2 = body.global_position - start
	if moved.x <= 0.0 or moved.y != 0.0:
		_failures.append("击退应沿 +x 位移，实际 %s" % str(moved))
	if not knock.is_active():
		_failures.append("force=240/decay=800 时 6 帧内应仍在激活中")

	# ---- 2. 激活中重复 apply：覆盖速度但不重复广播 true（幂等） ----
	if not knock.apply(Vector2(1, 0), 240.0):
		_failures.append("激活中 apply 应返回 true")
	if _events != [true]:
		_failures.append("激活中重复 apply 不应重复广播，实际 %s" % str(_events))

	# ---- 3. 衰减归零：恰好广播一次 false，位移随后停止 ----
	# 总位移 = F²/(2D) = 240²/1600 = 36px；30 帧 > 18 帧，必然归零。
	var pos_before: Vector2 = body.global_position
	await _wait_frames(30)
	if _events != [true, false]:
		_failures.append("衰减结束应恰好广播一次 false，实际 %s" % str(_events))
	if knock.is_active():
		_failures.append("衰减结束后 is_active 应为 false")
	var rest_pos: Vector2 = body.global_position
	await _wait_frames(5)
	if body.global_position != rest_pos:
		_failures.append("静止后位移应停止，实际 %s -> %s"
				% [str(rest_pos), str(body.global_position)])
	var total: float = rest_pos.x - pos_before.x
	# 第二次 apply 从 240 重新衰减（覆盖残余），位移仍是完整一段。
	# 离散帧和 = 连续积分 F²/(2D)=36 + 每帧先位移后衰减的 F·dt/2=2 → 38px。
	if absf(total - 38.0) > 1.0:
		_failures.append("重启语义下第二段总位移应约 38px，实际 %.2f" % total)

	# ---- 4. 无效输入：force<=0 / 零方向拒绝，不触发广播 ----
	_events.clear()
	if knock.apply(Vector2(1, 0), 0.0):
		_failures.append("force=0 应返回 false")
	if knock.apply(Vector2(1, 0), -5.0):
		_failures.append("负 force 应返回 false")
	if knock.apply(Vector2.ZERO, 10.0):
		_failures.append("零方向应返回 false")
	if _events != []:
		_failures.append("无效输入不应广播，实际 %s" % str(_events))

	# ---- 5. 方向归一化：非单位方向位移轨迹与单位方向一致 ----
	var body_b := CharacterBody2D.new()
	var body_c := CharacterBody2D.new()
	root.add_child(body_b)
	root.add_child(body_c)
	var kb: Node = packed.instantiate()
	var kc: Node = packed.instantiate()
	body_b.add_child(kb)
	body_c.add_child(kc)
	await physics_frame
	kb.apply(Vector2(3, 4), 100.0)
	kc.apply(Vector2(0.6, 0.8), 100.0)
	await _wait_frames(10)
	var db: Vector2 = body_b.global_position
	var dc: Vector2 = body_c.global_position
	if db.distance_to(dc) > 0.5:
		_failures.append("非单位方向 (3,4) 与 (0.6,0.8) 位移应一致：%s vs %s"
				% [str(db), str(dc)])
	if absf(kb.current_velocity().length() - kc.current_velocity().length()) > 0.5:
		_failures.append("两者当前击退速度长度应一致")

	# ---- 6. 错误宿主：父节点不是 CharacterBody2D 时拒绝触发 ----
	var plain := Node.new()
	root.add_child(plain)
	var misfit: Node = packed.instantiate()
	plain.add_child(misfit)
	await physics_frame
	if misfit.apply(Vector2(1, 0), 100.0):
		_failures.append("父节点非 CharacterBody2D 时 apply 应返回 false")

	_report()


func _on_changed(is_active: bool) -> void:
	_events.append(is_active)


func _wait_frames(count: int) -> void:
	for _i: int in count:
		await physics_frame


func _report() -> void:
	if _failures.is_empty():
		print("PASS: knockback 全部检查通过")
		quit(0)
	else:
		for f in _failures:
			print("FAIL: ", f)
		quit(1)
