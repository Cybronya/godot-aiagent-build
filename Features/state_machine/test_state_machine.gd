extends SceneTree
## StateMachine 组件自身验证：autostart、finished 驱动切换、previous 回退、
## 幂等、未知状态防护、active 开关语义、update 转发。
##
## 用法：godot --headless --path . -s res://Features/state_machine/test_state_machine.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

const StateMachineScript := preload("res://Features/state_machine/state_machine.gd")
const StateNodeScript := preload("res://Features/state_machine/state_node.gd")
const SCENE_PATH := "res://Features/state_machine/StateMachine.tscn"

var _failures: PackedStringArray = []
var _changed_events: Array = []


class TrackerState extends StateNode:
	var entered := 0
	var exited := 0
	var updates := 0

	func enter() -> void:
		entered += 1

	func exit() -> void:
		exited += 1

	func update(_delta: float) -> void:
		updates += 1


func _initialize() -> void:
	var packed: PackedScene = load(SCENE_PATH)
	if packed == null:
		_failures.append("加载 %s 失败" % SCENE_PATH)
		_report()
		return
	var machine: StateMachine = packed.instantiate()
	var idle := TrackerState.new()
	idle.name = "idle"
	var chase := TrackerState.new()
	chase.name = "chase"
	machine.add_child(idle)
	machine.add_child(chase)
	machine.start_state_name = "idle"
	machine.state_changed.connect(func(state: StateNode) -> void: _changed_events.append(state))
	root.add_child(machine)
	await process_frame
	await _run(machine, idle, chase)
	if _failures.is_empty():
		_run_second_phase(machine, idle, chase)
	_report()


func _run(machine: StateMachine, idle: TrackerState, chase: TrackerState) -> void:
	# 1. autostart：以 start_state_name 启动并进入
	if machine.current_state != idle:
		_failures.append("autostart 后当前状态应为 idle，实际 %s" % machine.current_state)
	if idle.entered != 1:
		_failures.append("idle.enter 应恰好 1 次，实际 %d" % idle.entered)
	if _changed_events.size() != 1:
		_failures.append("state_changed 应触发 1 次，实际 %d" % _changed_events.size())
	# 2. finished 驱动切换：idle -> chase
	idle.finished.emit("chase")
	if machine.current_state != chase:
		_failures.append("finished(chase) 后当前状态应为 chase")
	if idle.exited != 1:
		_failures.append("切换后 idle.exit 应恰好 1 次，实际 %d" % idle.exited)
	if chase.entered != 1:
		_failures.append("切换后 chase.enter 应恰好 1 次，实际 %d" % chase.entered)
	if _changed_events.size() != 2:
		_failures.append("state_changed 应累计 2 次，实际 %d" % _changed_events.size())
	# 3. previous 回退：chase -> idle（历史栈）
	machine.transition_to("previous")
	if machine.current_state != idle:
		_failures.append("previous 后应回退到 idle")
	if chase.exited != 1:
		_failures.append("回退时 chase.exit 应恰好 1 次，实际 %d" % chase.exited)
	if idle.entered != 2:
		_failures.append("回退时 idle.enter 应累计 2 次，实际 %d" % idle.entered)
	# 4. 幂等：切到当前状态被忽略
	machine.transition_to("idle")
	if idle.entered != 2 or idle.exited != 1:
		_failures.append("切到当前状态应幂等忽略（entered=%d exited=%d）" % [idle.entered, idle.exited])
	# 5. 未知状态防护：保持当前状态
	machine.transition_to("nope")
	if machine.current_state != idle:
		_failures.append("未知状态名应保持当前状态")
	# 6. 历史耗尽的 previous 防护：idle -> chase -> previous(idle) -> previous 保持 idle
	machine.transition_to("chase")
	machine.transition_to("previous")
	machine.transition_to("previous")
	if machine.current_state != idle:
		_failures.append("历史耗尽后 previous 应保持 idle，实际 %s" % machine.current_state)
	if idle.entered != 3 or chase.exited != 2:
		_failures.append("回退序列计数错误（idle.entered=%d chase.exited=%d）" % [idle.entered, chase.exited])
	# 7. 物理帧转发 update
	var updates_before := chase.updates
	machine.transition_to("chase")
	await physics_frame
	await physics_frame
	if chase.updates <= updates_before:
		_failures.append("当前状态应收到 update 转发（updates=%d -> %d）" % [updates_before, chase.updates])


func _run_second_phase(machine: StateMachine, idle: TrackerState, chase: TrackerState) -> void:
	# 8. set_active(false)：退出当前状态并屏蔽切换
	machine.set_active(false)
	if machine.is_active():
		_failures.append("set_active(false) 后 is_active 应为 false")
	if chase.exited < 3:
		_failures.append("关闭时应 exit 当前状态，实际 exited=%d" % chase.exited)
	var entered_before := idle.entered
	machine.transition_to("idle")
	if idle.entered != entered_before:
		_failures.append("关闭状态下 transition_to 应被忽略")
	# 9. set_active(true)：重新进入当前状态
	machine.set_active(true)
	if machine.current_state != chase:
		_failures.append("重新开启后当前状态应保持 chase")
	if chase.entered != 4:
		_failures.append("重新开启应重新 enter 当前状态，实际 %d" % chase.entered)
	# 10. has_state
	if not machine.has_state("idle") or machine.has_state("ghost"):
		_failures.append("has_state 判定错误")


func _report() -> void:
	if _failures.is_empty():
		print("PASS: StateMachine 组件验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
