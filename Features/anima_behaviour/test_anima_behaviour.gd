extends SceneTree
## MotionTrigger 组件验证：收集 AnimationPlayer、播放不崩溃、隐藏。
## 用法：godot --headless --path . -s res://Features/anima_behaviour/test_anima_behaviour.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

var _failures: PackedStringArray = []


func _initialize() -> void:
	var trigger := MotionTrigger.new()
	var ap := AnimationPlayer.new()
	trigger.add_child(ap)

	root.add_child(trigger)
	await physics_frame

	# ---- 1. 收集到 1 个 AnimationPlayer ----
	if trigger.get_players().size() != 1:
		_failures.append("应收集到 1 个 AnimationPlayer，实际 %d" % trigger.get_players().size())

	# ---- 2. play_motion_in 不崩溃（无 animation 时跳过） ----
	trigger.play_motion_in()

	# ---- 3. play_motion_out 不崩溃 ----
	trigger.play_motion_out()

	# ---- 4. hide_after_out 后不可见 ----
	trigger.hide_after_out = true
	trigger.play_motion_out()
	if trigger.visible:
		_failures.append("hide_after_out 后应不可见")

	# ---- 5. play_in_on_ready ----
	var trigger2 := MotionTrigger.new()
	trigger2.play_in_on_ready = true
	var ap2 := AnimationPlayer.new()
	trigger2.add_child(ap2)
	root.add_child(trigger2)
	await physics_frame
	if trigger2.get_players().size() != 1:
		_failures.append("play_in_on_ready 触发 _ready 后应收集到 AnimationPlayer")

	_report()


func _report() -> void:
	if _failures.is_empty():
		print("PASS: anima_behaviour 全部检查通过")
		quit(0)
	else:
		for f in _failures:
			print("FAIL: ", f)
		quit(1)
