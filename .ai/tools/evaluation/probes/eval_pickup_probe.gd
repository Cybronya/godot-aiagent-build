extends SceneTree
## EVAL136 probe — T1 单 Feature（collect_pickup）玩法行为探针
##
## 用法：godot --headless --path . -s res://Tests/eval136_pickup_probe.gd -- <scene> <positive|negative>
##
## 断言的是真实运行时状态变化（信号次数 / is_collected / 节点是否被释放），
## 不是「节点或脚本是否存在」。正负两种模式共用同一物理配置：
##   positive —— 玩家实体进入拾取范围 → collected 恰好发出、组件标记已收集、实例被移除
##   negative —— 玩家实体停在 400 px 外 → 不得发出信号、不得标记、实例仍在场
## 退出码：0 = 断言全部通过；1 = 断言失败或前置条件不成立；2 = 参数/环境错误。

const PLAYER_SCENE := "res://Features/player_movement/Player.tscn"
const NEGATIVE_DISTANCE := 400.0
const SETTLE_FRAMES := 6

var _failures: PackedStringArray = []
var _scene := ""
var _mode := "positive"


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() < 2:
		printerr("FAIL: usage: -s <probe> -- <scene> <positive|negative>")
		quit(2)
		return
	_scene = str(args[0])
	_mode = str(args[1])
	_run()


func _run() -> void:
	var packed: PackedScene = load(_scene)
	if packed == null:
		_fail("Scene Load: 无法加载被测场景 %s" % _scene)
		_report()
		return
	var entity: Node2D = packed.instantiate()
	root.add_child(entity)
	await physics_frame

	var pickup: Node = _find_method(entity, "is_collected")
	if pickup == null:
		_fail("Precondition: 场景 %s 中不存在 collect_pickup 组件（无 is_collected()）" % _scene)
		_report()
		return
	if not pickup.has_signal("collected"):
		_fail("Precondition: 拾取组件缺少 collected 信号")
		_report()
		return

	var player_packed: PackedScene = load(PLAYER_SCENE)
	if player_packed == null:
		_fail("Environment: 无法加载玩家场景 %s" % PLAYER_SCENE)
		_report()
		return
	var picker: Node2D = player_packed.instantiate()
	if _mode == "negative":
		picker.position = entity.global_position + Vector2(NEGATIVE_DISTANCE, 0.0)
	else:
		picker.position = entity.global_position
	root.add_child(picker)
	picker.add_to_group("players")

	var hits := {"count": 0}
	pickup.connect("collected", func(_value: bool, _id: String) -> void:
		hits["count"] += 1)

	await _wait_frames(SETTLE_FRAMES)
	# 收集后组件自行 queue_free：只能在实例仍有效时查询状态
	var alive := is_instance_valid(pickup)
	var collected_flag := false
	if alive:
		collected_flag = bool(pickup.call("is_collected"))
	print("PICKUP: scene=%s mode=%s hits=%d collected=%s alive=%s frames=%d"
		% [_scene, _mode, hits["count"], collected_flag, alive, SETTLE_FRAMES])

	if _mode == "positive":
		if hits["count"] != 1:
			_fail("Signal: 进入拾取范围后 collected 应恰好发出 1 次，实际 %d 次" % hits["count"])
		if alive:
			_fail("Removal: 拾取完成后组件实例应被释放，实际仍在场景树中")
	else:
		if hits["count"] != 0:
			_fail("Signal: 未接触时不得发出 collected，实际 %d 次" % hits["count"])
		if collected_flag:
			_fail("State: 未接触时 is_collected() 应为 false")
		if not alive:
			_fail("Removal: 未接触时拾取物不得消失")
	_report()


func _find_method(node: Node, method_name: String) -> Node:
	if node.has_method(method_name):
		return node
	for child in node.get_children():
		var found := _find_method(child, method_name)
		if found != null:
			return found
	return null


func _wait_frames(count: int) -> void:
	for _i in count:
		await physics_frame


func _fail(message: String) -> void:
	_failures.append(message)


func _report() -> void:
	if _failures.is_empty():
		print("PASS: eval136 pickup probe (%s)" % _mode)
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
