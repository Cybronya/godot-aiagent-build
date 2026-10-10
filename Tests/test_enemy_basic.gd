extends SceneTree
## 由 .ai/tools/test_generator/generate_scene_test.py 自动生成——Scene Blueprint 回归测试。
## 不要手工编辑；重新生成请运行:
##   python .ai/tools/test_generator/generate_scene_test.py <blueprint.yaml>
##
## 用法：godot --headless --path . -s res://Tests/test_enemy_basic.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

var _failures: PackedStringArray = []


func _initialize() -> void:
	var packed: PackedScene = load("res://Scenes/EnemyBasic.tscn")
	if packed == null:
		_failures.append("Scene Load: res://Scenes/EnemyBasic.tscn 加载失败")
		_report()
		return
	var entity: Node = packed.instantiate()
	# Feature Exists
	if entity.get_node_or_null("ChaseMovement") == null:
		_failures.append("Missing Feature node: ChaseMovement")
	if entity.get_node_or_null("ContactDamage") == null:
		_failures.append("Missing Feature node: ContactDamage")
	if entity.get_node_or_null("Health") == null:
		_failures.append("Missing Feature node: Health")

	# Signal Exists
	var health_node = entity.get_node_or_null("Health")
	if health_node != null:
		if not health_node.has_signal("health_changed"):
			_failures.append("Missing signal: Health.health_changed")
		if not health_node.has_signal("died"):
			_failures.append("Missing signal: Health.died")

	entity.free()
	_report()


func _report() -> void:
	if _failures.is_empty():
		print("PASS: EnemyBasic 场景组合验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
