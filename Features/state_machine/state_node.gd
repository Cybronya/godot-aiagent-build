class_name StateNode
extends Node
## 状态机状态基类：StateMachine 的子节点继承本类实现具体状态行为。
##
## 生命周期约定：
## - enter()：进入状态时调用一次（启动动画、计时器等）；
## - exit()：离开状态时调用一次（清理临时状态）；
## - update(delta)：状态机 _physics_process 转发，仅当前状态收到；
## - handle_input(event)：状态机 _unhandled_input 转发，仅当前状态收到。
##
## 状态通过 emit finished(next_state_name) 请求切换；
## 目标状态名对应 StateMachine 的子节点名，"previous" 表示回退上一个状态。
## 状态自身不持有状态机引用；需要宿主上下文时通过 owner/get_parent() 获取。

signal finished(next_state_name: String)


func enter() -> void:
	pass


func exit() -> void:
	pass


func update(_delta: float) -> void:
	pass


func handle_input(_event: InputEvent) -> void:
	pass
