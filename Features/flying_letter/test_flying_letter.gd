extends SceneTree
## FlyingLetter 组件验证：Label 创建、setup 初始化、物理运动、生命周期。
## 用法：godot --headless --path . -s res://Features/flying_letter/test_flying_letter.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

var _failures: PackedStringArray = []


func _initialize() -> void:
	var letter := FlyingLetter.new()
	letter.lifetime = 10.0  # 测试中调大，避免提前移除
	root.add_child(letter)
	await physics_frame

	# ---- 1. setup 创建 Label 子节点 ----
	letter.setup("100", Vector2(100, 100))
	if not letter.has_node("Label"):
		_failures.append("setup 应创建 Label 子节点")
		_report()
		return

	var label := letter.get_node("Label") as Label
	if label.text != "100":
		_failures.append("Label 文字应为 '100'，实际 '%s'" % label.text)

	# ---- 2. 初始位置 ----
	if letter.global_position != Vector2(100, 100):
		_failures.append("初始位置应为 (100,100)，实际 %s" % str(letter.global_position))

	# ---- 3. 物理量已初始化 ----
	if letter._velocity == Vector2():
		_failures.append("速度应已初始化")
	if letter._gravity == 0.0:
		_failures.append("重力应已初始化")
	if letter._angular_velocity == 0.0:
		_failures.append("角速度应已初始化")

	# ---- 4. 速度方向：x 向左(负), y 向上(负) ----
	if letter._velocity.x >= 0:
		_failures.append("x 速度应为负（向左飘），实际 %.1f" % letter._velocity.x)
	if letter._velocity.y >= 0:
		_failures.append("y 速度应为负（向上飘），实际 %.1f" % letter._velocity.y)

	# ---- 5. _process 更新位置 ----
	var old_pos := letter.position
	letter._process(0.1)
	if letter.position == old_pos:
		_failures.append("_process 应更新位置")

	# ---- 6. lifetime 到期后移除 ----
	letter.lifetime = 0.1
	letter._elapsed = 0.0
	letter._process(0.15)  # 超过 lifetime
	if not letter.is_queued_for_deletion():
		_failures.append("lifetime 到期后应 queue_free")

	_report()


func _report() -> void:
	if _failures.is_empty():
		print("PASS: flying_letter 全部检查通过")
		quit(0)
	else:
		for f in _failures:
			print("FAIL: ", f)
		quit(1)
