extends SceneTree
## EVAL136 probe — 场景可加载性 / 结构存在性探针
##
## 用法：godot --headless --path . -s res://Tests/eval136_scene_load_probe.gd -- <scene> [node1,node2,...]
##
## 只回答一个问题：**这个场景能不能在真实 Godot 里加载并实例化，且声明的节点确实存在**。
## 它不替代行为证据（行为由玩法探针负责），失败时给出加载/实例化/缺节点的具体原因。
## 退出码：0 = 加载成功且节点齐全；1 = 加载/实例化失败或缺节点；2 = 参数错误。

var _failures: PackedStringArray = []
var _scene := ""
var _expected: PackedStringArray = []


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() < 1:
		printerr("FAIL: usage: -s <probe> -- <scene> [node1,node2,...]")
		quit(2)
		return
	_scene = str(args[0])
	if args.size() > 1 and str(args[1]) != "":
		_expected = str(args[1]).split(",", false)
	_run()


func _run() -> void:
	var packed: PackedScene = load(_scene)
	if packed == null:
		_fail("Scene Load: 无法加载 %s" % _scene)
		_report()
		return
	var instance: Node = packed.instantiate()
	if instance == null:
		_fail("Scene Instantiate: %s 实例化失败" % _scene)
		_report()
		return
	root.add_child(instance)
	await process_frame
	await process_frame

	var found: PackedStringArray = []
	for path in _expected:
		var node: Node = instance.get_node_or_null(NodePath(str(path).strip_edges()))
		if node == null:
			_fail("Structure: 场景缺少节点 %s" % path)
		else:
			found.append(str(path))
	print("LOAD: scene=%s expected=%d found=%d" % [_scene, _expected.size(), found.size()])
	instance.queue_free()
	await process_frame
	_report()


func _fail(message: String) -> void:
	_failures.append(message)


func _report() -> void:
	if _failures.is_empty():
		print("PASS: eval136 scene load probe (%s)" % _scene)
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
