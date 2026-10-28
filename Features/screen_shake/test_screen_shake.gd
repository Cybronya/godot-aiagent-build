extends SceneTree
## ScreenShake 组件自身验证：叠加与幂等广播、噪声偏移生效、衰减归零、
## 无效输入、错误宿主（父节点非 Camera2D）拒绝、移除时归还 offset、种子可复现。
##
## 用法：godot --headless --path . -s res://Features/screen_shake/test_screen_shake.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

const FRAME_BUDGET := 240

var _failures: PackedStringArray = []
var _events: Array[bool] = []


func _initialize() -> void:
	var packed: PackedScene = load("res://Features/screen_shake/ScreenShake.tscn")
	if packed == null:
		_failures.append("加载 res://Features/screen_shake/ScreenShake.tscn 失败")
		_report()
		return

	# ---- 1. 正常宿主：add_trauma 生效、广播一次 true、下一帧产生非零偏移 ----
	var camera := Camera2D.new()
	root.add_child(camera)
	var shake: Node = packed.instantiate()
	camera.add_child(shake)
	shake.shaking.connect(_on_shaking)
	await physics_frame
	if not shake.add_trauma(0.5):
		_failures.append("有效 add_trauma 应返回 true")
	if _events != [true]:
		_failures.append("首次触发应广播一次 true，实际 %s" % str(_events))
	await _wait_frames(2)
	var offset: Vector2 = camera.offset
	if offset == Vector2.ZERO:
		_failures.append("震动期间相机偏移不应为零")

	# ---- 2. 震动中再次叠加：不重复广播 true（幂等） ----
	if not shake.add_trauma(0.3):
		_failures.append("震动中叠加应返回 true")
	if _events != [true]:
		_failures.append("震动中叠加不应重复广播，实际 %s" % str(_events))

	# ---- 3. 衰减归零：offset 归零 + 恰好广播一次 false ----
	# decay=2.0、叠加后 trauma=0.8：清零需 0.4s ≈ 24 帧；40 帧余量充足。
	await _wait_frames(40)
	if camera.offset != Vector2.ZERO:
		_failures.append("衰减结束后偏移应归零，实际 %s" % str(camera.offset))
	if _events != [true, false]:
		_failures.append("衰减结束应恰好广播一次 false，实际 %s" % str(_events))

	# ---- 4. 无效输入：amount<=0 忽略，不触发广播 ----
	_events.clear()
	if shake.add_trauma(0.0):
		_failures.append("amount=0 应返回 false")
	if shake.add_trauma(-0.5):
		_failures.append("负 amount 应返回 false")
	if _events != []:
		_failures.append("无效输入不应广播，实际 %s" % str(_events))

	# ---- 5. 移除组件：offset 归还为零 ----
	shake.add_trauma(0.5)
	await _wait_frames(1)
	shake.queue_free()
	await _wait_frames(2)
	if camera.offset != Vector2.ZERO:
		_failures.append("组件移除后偏移应归还为零，实际 %s" % str(camera.offset))

	# ---- 6. 错误宿主：父节点不是 Camera2D 时拒绝触发 ----
	var plain := Node.new()
	root.add_child(plain)
	var misfit: Node = packed.instantiate()
	plain.add_child(misfit)
	await physics_frame
	if misfit.add_trauma(0.5):
		_failures.append("父节点非 Camera2D 时 add_trauma 应返回 false")

	# ---- 7. 种子可复现：同种子同 trauma，偏移序列一致 ----
	var cam_a := Camera2D.new()
	var cam_b := Camera2D.new()
	root.add_child(cam_a)
	root.add_child(cam_b)
	var shake_a: Node = packed.instantiate()
	var shake_b: Node = packed.instantiate()
	cam_a.add_child(shake_a)
	cam_b.add_child(shake_b)
	await physics_frame
	shake_a.add_trauma(0.6)
	shake_b.add_trauma(0.6)
	await _wait_frames(3)
	if cam_a.offset != cam_b.offset:
		_failures.append("同种子下偏移序列应一致：%s vs %s"
				% [str(cam_a.offset), str(cam_b.offset)])

	_report()


func _on_shaking(is_shaking: bool) -> void:
	_events.append(is_shaking)


func _wait_frames(count: int) -> void:
	for _i: int in count:
		await physics_frame


func _report() -> void:
	if _failures.is_empty():
		print("PASS: screen_shake 全部检查通过")
		quit(0)
	else:
		for f in _failures:
			print("FAIL: ", f)
		quit(1)
