class_name StateMachine
extends Node
## 通用有限状态机组件：子节点即状态（StateNode 派生），节点名即状态名。
##
## 状态机负责：状态注册、当前状态切换、把 _physics_process / _unhandled_input
## 转发给当前状态。状态切换由两种方式驱动：
## 1. 状态自身 emit finished(next_state_name)（由状态逻辑决定去向）；
## 2. 外部调用 transition_to(name)（由组合层强制切换）。
##
## 只拥有「当前状态」与「状态历史」两份状态；具体状态行为由 StateNode 派生类
## 实现，切换后的表现（动画、音效等）由状态 enter/exit 内部或订阅方决定。
## 不依赖父节点类型，可挂在任意实体下复用（敌人 AI、流程控制、UI 向导等）。
##
## 抽象来源片段：godot-escoria/escoria-demo-game patterns/state_machine（MIT），
## 剥除 escoria.logger 依赖；重写其 previous 弹栈的越界隐患为显式历史栈；
## 状态注册改为子节点自动注册，无需手工维护 states_map。

signal state_changed(current_state: StateNode)

@export var start_state_name: String = ""
## 为 true 时 _ready 自动以 start_state_name（或第一个子状态）启动状态机。
@export var autostart := true

var current_state: StateNode = null

var _states: Dictionary = {}
var _history: Array[StateNode] = []
var _active := false


func _ready() -> void:
	for child in get_children():
		if child is StateNode:
			_register_state(child)
	if autostart and not _states.is_empty():
		var first: StateNode = _states.get(start_state_name, _states.values()[0])
		if start_state_name != "" and _states.has(start_state_name):
			first = _states[start_state_name]
		start(first)


func _register_state(state: StateNode) -> void:
	_states[state.name] = state
	state.finished.connect(transition_to)


func start(first_state: StateNode) -> void:
	if first_state == null:
		push_error("StateMachine: start 状态不能为 null")
		return
	if not _states.has(first_state.name):
		_register_state(first_state)
	current_state = first_state
	_set_active(true)
	state_changed.emit(current_state)
	current_state.enter()


## 开关状态机。关闭时退出当前状态并停止转发；重新开启时重新进入当前状态。
func set_active(value: bool) -> void:
	if value == _active:
		return
	_set_active(value)
	if current_state == null:
		return
	if value:
		current_state.enter()
	else:
		current_state.exit()


func _set_active(value: bool) -> void:
	_active = value
	set_physics_process(value)
	set_process_unhandled_input(value)


## 切换状态。name 为 "previous" 时回退到上一个状态（历史栈）；
## 未知状态名记录错误并保持当前状态；重复切到当前状态幂等忽略。
func transition_to(next_state_name: String) -> void:
	if not _active:
		return
	if next_state_name == "previous":
		if _history.is_empty():
			return
		var previous: StateNode = _history.pop_back()
		_switch_to(previous, false)
		return
	if not _states.has(next_state_name):
		push_error("StateMachine: 未知状态 \"%s\"（子状态需为 StateNode 且名字唯一）" % next_state_name)
		return
	_switch_to(_states[next_state_name], true)


func _switch_to(next_state: StateNode, record_history: bool) -> void:
	if current_state == next_state:
		return
	if record_history and current_state != null:
		_history.append(current_state)
	current_state.exit()
	current_state = next_state
	state_changed.emit(current_state)
	current_state.enter()


func is_active() -> bool:
	return _active


func has_state(state_name: String) -> bool:
	return _states.has(state_name)


func _physics_process(delta: float) -> void:
	if current_state != null:
		current_state.update(delta)


func _unhandled_input(event: InputEvent) -> void:
	if current_state != null:
		current_state.handle_input(event)
