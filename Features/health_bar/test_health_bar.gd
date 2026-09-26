extends SceneTree
## HealthBar 组件自身验证：初始比例正确、伤害后比例下降、恢复后比例上升
## 并不超过 1.0、血条随信号刷新。
##
## 用法：godot --headless --path . -s res://Features/health_bar/test_health_bar.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。
##
## 只依赖 health Feature（health_path 指向 Health 实例），不依赖游戏侧场景。
## 注意：Health 在 _ready 时才初始化生命值，入树后先等一帧再断言。

var _failures: PackedStringArray = []
var _bar: Node2D


func _initialize() -> void:
	var bar_scene: PackedScene = load("res://Features/health_bar/HealthBar.tscn")
	var health_scene: PackedScene = load("res://Features/health/Health.tscn")
	if bar_scene == null or health_scene == null:
		_failures.append("加载 HealthBar.tscn 或 Health.tscn 失败")
		_report()
		return

	var host := Node2D.new()
	root.add_child(host)
	var health: Node = health_scene.instantiate()
	health.name = "Health"
	host.add_child(health)
	_bar = bar_scene.instantiate()
	_bar.health_path = NodePath("../Health")
	host.add_child(_bar)
	_bar.position = Vector2(0, -34)
	await physics_frame

	# 1. 初始比例：满血为 1.0
	if not is_equal_approx(_bar.get_ratio(), 1.0):
		_failures.append("满血时血条比例应为 1.0，实际 %.2f" % _bar.get_ratio())

	# 2. 受伤后比例下降（health_changed 信号驱动刷新）
	health.take_damage(2)
	await physics_frame
	if not is_equal_approx(_bar.get_ratio(), 0.6):
		_failures.append("5 点生命受 2 点伤害后比例应为 0.6，实际 %.2f" % _bar.get_ratio())

	# 3. 恢复后比例上升，且钳制不超过 1.0（heal 上限 + 显示比例双重保证）
	health.heal(1)
	await physics_frame
	if not is_equal_approx(_bar.get_ratio(), 0.8):
		_failures.append("恢复 1 点后比例应为 0.8，实际 %.2f" % _bar.get_ratio())
	health.heal(10)
	await physics_frame
	if not is_equal_approx(_bar.get_ratio(), 1.0):
		_failures.append("超量恢复后比例应钳制为 1.0，实际 %.2f" % _bar.get_ratio())

	# 4. 死亡信号后血条刷新为空
	health.take_damage(9999)
	await physics_frame
	if not is_equal_approx(_bar.get_ratio(), 0.0):
		_failures.append("死亡后血条比例应为 0.0，实际 %.2f" % _bar.get_ratio())

	host.queue_free()
	await physics_frame
	_report()


func _report() -> void:
	if _failures.is_empty():
		print("PASS: HealthBar 组件验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
