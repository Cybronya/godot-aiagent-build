extends SceneTree
## Blackboard 组件验证：默认黑板、set/get/has/erase、命名黑板、duplicate 隔离。
## 用法：godot --headless --path . -s res://Features/blackboard/test_blackboard.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

var _failures: PackedStringArray = []


func _initialize() -> void:
	var bb := Blackboard.new()
	root.add_child(bb)
	await physics_frame

	# ---- 1. 默认有 1 个 "default" 黑板 ----
	if bb.keys().size() != 1:
		_failures.append("应有 1 个默认黑板，实际 %d" % bb.keys().size())
	if bb.keys()[0] != "default":
		_failures.append("默认黑板名应为 'default'，实际 '%s'" % bb.keys()[0])

	# ---- 2. set_value / get_value ----
	bb.set_value("health", 100)
	if bb.get_value("health") != 100:
		_failures.append("get_value 应返回 100，实际 %s" % str(bb.get_value("health")))

	# ---- 3. has_value ----
	if not bb.has_value("health"):
		_failures.append("has_value('health') 应返回 true")
	if bb.has_value("nonexistent"):
		_failures.append("has_value('nonexistent') 应返回 false")

	# ---- 4. get_value 默认值 ----
	if bb.get_value("nonexistent", "default_val") != "default_val":
		_failures.append("get_value 不存在键应返回默认值")

	# ---- 5. erase_value ----
	bb.erase_value("health")
	if bb.has_value("health"):
		_failures.append("erase 后 has_value 应返回 false")

	# ---- 6. 命名黑板 ----
	bb.set_value("key1", "val1", "custom")
	if bb.get_value("key1", null, "custom") != "val1":
		_failures.append("命名黑板 get_value 应返回 'val1'")
	if not bb.has_value("key1", "custom"):
		_failures.append("命名黑板 has_value 应返回 true")
	if bb.has_value("key1", "default"):
		_failures.append("命名黑板不应污染 default 板")

	# ---- 7. duplicate 隔离：setter 替换数据 ----
	bb.blackboard = {"test": 1}
	if bb.blackboard.size() != 1:
		_failures.append("blackboard setter 应替换为 1 个键，实际 %d" % bb.blackboard.size())

	# ---- 8. get_blackboard_names ----
	if bb.get_blackboard_names().size() != 2:
		_failures.append("应有 default + custom 两个黑板，实际 %d" % bb.get_blackboard_names().size())

	# ---- 9. get_blackboard 返回副本 ----
	var snap := bb.get_blackboard("custom")
	snap["key1"] = "modified"
	if bb.get_value("key1", null, "custom") != "val1":
		_failures.append("get_blackboard 应返回副本，不应影响原数据")

	_report()


func _report() -> void:
	if _failures.is_empty():
		print("PASS: blackboard 全部检查通过")
		quit(0)
	else:
		for f in _failures:
			print("FAIL: ", f)
		quit(1)
