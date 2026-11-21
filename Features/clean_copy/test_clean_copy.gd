extends SceneTree
## PathRegistry 组件验证：路径增删查、去重、替换字符串映射。
## 用法：godot --headless --path . -s res://Features/clean_copy/test_clean_copy.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

var _failures: PackedStringArray = []


func _initialize() -> void:
	# 清理：确保测试从空状态开始
	PathRegistry.set_paths("test_reg", [])

	# ---- 1. 初始空列表 ----
	if PathRegistry.get_paths("test_reg").size() != 0:
		_failures.append("初始应为空列表")

	# ---- 2. add_path ----
	PathRegistry.add_path("test_reg", "res://levels/level1")
	if not PathRegistry.has_path("test_reg", "res://levels/level1"):
		_failures.append("add_path 后应能找到")

	# ---- 3. 去重 ----
	PathRegistry.add_path("test_reg", "res://levels/level1")
	if PathRegistry.get_paths("test_reg").size() != 1:
		_failures.append("重复 add_path 不应增加数量")

	# ---- 4. remove_path ----
	PathRegistry.remove_path("test_reg", "res://levels/level1")
	if PathRegistry.has_path("test_reg", "res://levels/level1"):
		_failures.append("remove_path 后不应找到")

	# ---- 5. 多路径 ----
	PathRegistry.add_path("test_reg", "res://levels/level2")
	PathRegistry.add_path("test_reg", "res://levels/level3")
	if PathRegistry.get_paths("test_reg").size() != 2:
		_failures.append("应有 2 个路径，实际 %d" % PathRegistry.get_paths("test_reg").size())

	# ---- 6. 替换字符串 ----
	PathRegistry.set_replace_string("old_path", "new_path")
	var map := PathRegistry.get_replace_strings()
	if map.get("old_path") != "new_path":
		_failures.append("set_replace_string 应能读取")

	PathRegistry.remove_replace_string("old_path")
	map = PathRegistry.get_replace_strings()
	if map.has("old_path"):
		_failures.append("remove_replace_string 后不应存在")

	# ---- 7. 清理 ----
	PathRegistry.set_paths("test_reg", [])
	PathRegistry.remove_replace_string("old_path")

	_report()


func _report() -> void:
	if _failures.is_empty():
		print("PASS: clean_copy 全部检查通过")
		quit(0)
	else:
		for f in _failures:
			print("FAIL: ", f)
		quit(1)
