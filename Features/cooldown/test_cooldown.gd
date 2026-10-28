extends SceneTree
## Cooldown 组件自身验证：初始就绪、启动与信号、到期广播、重启语义、
## 无效时长、auto_start、进度查询、duration=0 导出值拒绝。
##
## 用法：godot --headless --path . -s res://Features/cooldown/test_cooldown.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

const FRAME_BUDGET := 240

var _failures: PackedStringArray = []
var _starts: int = 0
var _finishes: int = 0


func _initialize() -> void:
	var packed: PackedScene = load("res://Features/cooldown/Cooldown.tscn")
	if packed == null:
		_failures.append("加载 res://Features/cooldown/Cooldown.tscn 失败")
		_report()
		return

	# ---- 1. 初始就绪；start(0.2) 生效：is_ready 翻转 + started 一次 ----
	var cd: Node = packed.instantiate()
	root.add_child(cd)
	cd.cooldown_started.connect(_on_started)
	cd.cooldown_finished.connect(_on_finished)
	await physics_frame
	if not cd.is_ready():
		_failures.append("初始应处于就绪")
	if not cd.start(0.2):
		_failures.append("有效 start 应返回 true")
	if cd.is_ready():
		_failures.append("冷却中不应就绪")
	if _starts != 1 or _finishes != 0:
		_failures.append("启动应广播 started 一次，实际 starts=%d finishes=%d" % [_starts, _finishes])
	await _wait_frames(2)   # 推进一帧后进度才离开 0
	var p: float = cd.get_progress()
	if p <= 0.0 or p >= 1.0:
		_failures.append("运行中进度应在 (0,1)，实际 %f" % p)
	if cd.get_remaining() <= 0.0 or cd.get_remaining() > 0.2:
		_failures.append("剩余时长应落在 (0, 0.2]，实际 %f" % cd.get_remaining())

	# ---- 2. 重启语义：冷却中再次 start 重置剩余时长并再次广播 started ----
	await _wait_frames(6)   # 已消耗约 0.1s
	if not cd.start(0.2):
		_failures.append("冷却中重启应返回 true")
	if _starts != 2:
		_failures.append("重启应再次广播 started，实际 %d" % _starts)
	var rem: float = cd.get_remaining()
	if rem < 0.19:
		_failures.append("重启应重置剩余时长到接近 0.2s，实际 %f" % rem)

	# ---- 3. 到期：finished 恰好一次，回到就绪，进度归 1 ----
	await _wait_frames(20)  # 0.2s = 12 帧，余量充足
	if not cd.is_ready():
		_failures.append("到期后应就绪")
	if _finishes != 1:
		_failures.append("到期应广播 finished 恰好一次，实际 %d" % _finishes)
	if cd.get_remaining() != 0.0:
		_failures.append("就绪后剩余应为 0，实际 %f" % cd.get_remaining())
	if cd.get_progress() != 1.0:
		_failures.append("就绪后进度应为 1.0，实际 %f" % cd.get_progress())

	# ---- 4. 无效时长与哨兵语义 ----
	_starts = 0
	_finishes = 0
	if cd.start(0.0):
		_failures.append("start(0) 应返回 false")
	if _starts != 0:
		_failures.append("无效时长不应发信号，实际 %d" % _starts)
	if not cd.start(-1.0):
		_failures.append("start(-1) 应作为「不覆盖」用默认 duration 生效")
	if _starts != 1:
		_failures.append("start(-1) 应广播 started 一次，实际 %d" % _starts)
	await _wait_frames(70)  # 默认 1.0s = 60 帧 + 余量，等冷却结束
	if _finishes != 1:
		_failures.append("默认时长冷却应正常到期，实际 %d" % _finishes)

	# ---- 5. duration=0 导出值：无参 start 拒绝；设置后恢复 ----
	cd.duration = 0.0
	if cd.start():
		_failures.append("duration=0 时无参 start 应返回 false")
	cd.duration = 0.1
	if not cd.start():
		_failures.append("设置 duration 后无参 start 应生效")
	await _wait_frames(10)

	# ---- 6. auto_start：挂载即自动进入冷却 ----
	_starts = 0
	_finishes = 0
	var auto: Node = packed.instantiate()
	auto.duration = 0.2
	auto.auto_start = true
	auto.cooldown_started.connect(_on_started)
	auto.cooldown_finished.connect(_on_finished)
	root.add_child(auto)   # _ready 里 auto_start 触发，必须先连信号再入树
	await _wait_frames(2)
	if auto.is_ready():
		_failures.append("auto_start 应在挂载后立即进入冷却")
	if _starts != 1:
		_failures.append("auto_start 应广播 started 一次，实际 %d" % _starts)
	await _wait_frames(20)
	if not auto.is_ready() or _finishes != 1:
		_failures.append("auto_start 冷却应正常到期，实际 finishes=%d" % _finishes)

	_report()


func _on_started() -> void:
	_starts += 1


func _on_finished() -> void:
	_finishes += 1


func _wait_frames(count: int) -> void:
	for _i: int in count:
		await physics_frame


func _report() -> void:
	if _failures.is_empty():
		print("PASS: cooldown 全部检查通过")
		quit(0)
	else:
		for f in _failures:
			print("FAIL: ", f)
		quit(1)
