extends SceneTree
## Health 组件自身验证：初始值、伤害扣减、下限保护、死亡状态与事件触发。
##
## 用法：godot --headless --path . -s res://Features/health/test_health.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

var _failures: PackedStringArray = []
var _changed_events: Array = []
var _died_count := 0


func _initialize() -> void:
	var packed: PackedScene = load("res://Features/health/Health.tscn")
	if packed == null:
		_failures.append("加载 res://Features/health/Health.tscn 失败")
		_report()
		return
	var health: Health = packed.instantiate()
	health.health_changed.connect(func(current: int, amount: int) -> void: _changed_events.append([current, amount]))
	health.died.connect(_on_died)
	root.add_child(health)
	await process_frame
	_run(health)


func _run(health: Health) -> void:
	# 1. 初始生命值正确
	if health.get_current_health() != 5:
		_failures.append("初始生命值应为 5，实际 %d" % health.get_current_health())
	# 2. 受到伤害后正确减少
	health.take_damage(2)
	if health.get_current_health() != 3:
		_failures.append("受 2 点伤害后应为 3，实际 %d" % health.get_current_health())
	if _changed_events.size() != 1:
		_failures.append("health_changed 应触发 1 次，实际 %d" % _changed_events.size())
	# 3. 无效伤害被忽略
	health.take_damage(0)
	health.take_damage(-1)
	if health.get_current_health() != 3:
		_failures.append("0/负数伤害不应扣血，实际 %d" % health.get_current_health())
	# 4. 致命伤害：归零但不为负，进入死亡状态
	health.take_damage(9999)
	if health.get_current_health() != 0:
		_failures.append("致命伤害后应为 0，实际 %d" % health.get_current_health())
	if not health.is_dead():
		_failures.append("生命值归零后应进入死亡状态")
	# 5. died 事件恰好触发一次
	if _died_count != 1:
		_failures.append("died 应恰好触发 1 次，实际 %d" % _died_count)
	# 6. 死亡后不再受伤、不再重复触发
	health.take_damage(1)
	if health.get_current_health() != 0 or _died_count != 1:
		_failures.append("死亡后应忽略后续伤害")
	_report()


func _on_died() -> void:
	_died_count += 1


func _report() -> void:
	if _failures.is_empty():
		print("PASS: Health 组件验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
