extends SceneTree
## AttributeTable 组件验证：属性增删改查、范围验证、类型支持。
## 用法：godot --headless --path . -s res://Features/attribute_editor/test_attribute_editor.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

var _failures: PackedStringArray = []


func _initialize() -> void:
	var table := AttributeTable.new()

	# ---- 1. 初始空表 ----
	if table.attributes.size() != 0:
		_failures.append("初始应为空表")

	# ---- 2. add_attribute ----
	table.add_attribute("health", 100, 0, 200, "int")
	if table.get_attribute("health") == null:
		_failures.append("add_attribute 后应能找到")

	# ---- 3. 去重 ----
	table.add_attribute("health", 50)
	if table.attributes.size() != 1:
		_failures.append("重复 add_attribute 不应增加")

	# ---- 4. update_attribute ----
	if not table.update_attribute("health", 50):
		_failures.append("update_attribute 应返回 true")
	if table.get_attribute_value("health") != 50:
		_failures.append("get_attribute_value 应返回 50")

	# ---- 5. update 不存在的属性 ----
	if table.update_attribute("nonexistent", 1):
		_failures.append("update 不存在属性应返回 false")

	# ---- 6. is_value_valid ----
	if not table.is_value_valid("health"):
		_failures.append("health=50 应在 0-200 范围内")
	table.update_attribute("health", 250)
	if table.is_value_valid("health"):
		_failures.append("health=250 应超出 0-200 范围")

	# ---- 7. bool/string 类型恒为 true ----
	table.add_attribute("is_alive", true, 0, 1, "bool")
	if not table.is_value_valid("is_alive"):
		_failures.append("bool 类型应恒为 true")
	table.add_attribute("name", "hero", 0, 100, "string")
	if not table.is_value_valid("name"):
		_failures.append("string 类型应恒为 true")

	# ---- 8. remove_attribute ----
	table.remove_attribute("health")
	if table.get_attribute("health") != null:
		_failures.append("remove_attribute 后不应找到")

	# ---- 9. get_attribute_names ----
	var names := table.get_attribute_names()
	if names.size() != 2:
		_failures.append("应有 2 个属性名，实际 %d" % names.size())

	_report()


func _report() -> void:
	if _failures.is_empty():
		print("PASS: attribute_editor 全部检查通过")
		quit(0)
	else:
		for f in _failures:
			print("FAIL: ", f)
		quit(1)
