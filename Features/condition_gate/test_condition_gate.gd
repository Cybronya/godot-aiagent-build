extends SceneTree
## ConditionGate 组件自身验证：AND 聚合、条件数量约束、未声明条件不满足、
## 幂等广播、reset 恢复、再次满足、多实例独立。
##
## 用法：godot --headless --path . -s res://Features/condition_gate/test_condition_gate.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

var _failures: PackedStringArray = []
var _events: Array[bool] = []


func _initialize() -> void:
	var packed: PackedScene = load("res://Features/condition_gate/ConditionGate.tscn")
	if packed == null:
		_failures.append("加载 res://Features/condition_gate/ConditionGate.tscn 失败")
		_report()
		return

	# 1. 双条件 AND：单条件满足不触发，双条件齐才触发
	var gate: Node = packed.instantiate()
	root.add_child(gate)
	gate.fulfilled.connect(_on_fulfilled)
	gate.set_condition(true, "a")
	if gate.is_fulfilled() or not _events.is_empty():
		_failures.append("仅一个条件满足时不应聚合达成")
	gate.set_condition(true, "b")
	if not gate.is_fulfilled() or _events != [true]:
		_failures.append("两个条件满足后应聚合达成并广播一次 true，实际 %s" % str(_events))

	# 2. 重复上报同值：幂等，不重复广播
	gate.set_condition(true, "b")
	gate.set_condition(true, "a")
	if _events.size() != 1:
		_failures.append("重复上报同值不应重复广播，实际 %d 次" % _events.size())

	# 3. 已上报条件的回落在保持型语义下仍会使聚合回落：
	# set_condition 是绝对值上报，任何已上报条件为 false 都使聚合回到未达成
	gate.set_condition(false, "c")
	if gate.is_fulfilled() or _events != [true, false]:
		_failures.append("任何已上报条件为 false 都应使聚合回落，实际 %s" % str(_events))
	gate.set_condition(true, "c")
	if not gate.is_fulfilled() or _events != [true, false, true]:
		_failures.append("条件恢复后应再次达成，实际 %s" % str(_events))

	# 4. reset：清空全部条件并广播 false；之后可重新达成
	gate.reset()
	if gate.is_fulfilled() or _events != [true, false, true, false]:
		_failures.append("reset 后应恢复未达成并广播 false，实际 %s" % str(_events))
	gate.set_condition(true, "a")
	gate.set_condition(true, "b")
	if not gate.is_fulfilled() or _events != [true, false, true, false, true]:
		_failures.append("reset 后重新满足应再次广播 true，实际 %s" % str(_events))
	gate.queue_free()

	# 5. 三条件聚合 + 任一条件 false 保持未达成
	var gate3: Node = packed.instantiate()
	gate3.condition_count = 3
	root.add_child(gate3)
	gate3.fulfilled.connect(_on_fulfilled)
	var baseline := _events.size()
	gate3.set_condition(true, "x")
	gate3.set_condition(true, "y")
	if gate3.is_fulfilled():
		_failures.append("三条件门在两个条件满足时不应达成")
	gate3.set_condition(false, "y")
	gate3.set_condition(true, "z")
	if gate3.is_fulfilled():
		_failures.append("任一条件为 false 时三条件门不应达成")
	if _events.size() != baseline:
		_failures.append("未达成过程中不应有广播，实际新增 %d" % (_events.size() - baseline))
	gate3.set_condition(true, "y")
	if not gate3.is_fulfilled() or _events.size() != baseline + 1:
		_failures.append("三条件齐后应达成并广播一次")

	# 6. 多实例独立
	var gate_a: Node = packed.instantiate()
	var gate_b: Node = packed.instantiate()
	root.add_child(gate_a)
	root.add_child(gate_b)
	gate_a.set_condition(true, "a")
	gate_a.set_condition(true, "b")
	if not gate_a.is_fulfilled() or gate_b.is_fulfilled():
		_failures.append("多实例应各自独立聚合")

	gate_a.queue_free()
	gate_b.queue_free()
	gate3.queue_free()
	await process_frame
	_report()


func _on_fulfilled(value: bool) -> void:
	_events.append(value)


func _report() -> void:
	if _failures.is_empty():
		print("PASS: ConditionGate 组件验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
