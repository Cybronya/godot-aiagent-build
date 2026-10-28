class_name Health
extends Node
## 通用生命值组件：管理当前生命值、伤害处理、恢复处理与死亡状态。
##
## 通过 take_damage() 受到伤害；通过 heal() 恢复生命值（上限钳制，不超过 max_health）；
## 通过 health_changed / died 信号对外暴露变化，
## 死亡后的具体表现由订阅方决定，本组件不实现任何视觉或实体删除逻辑。
## 不依赖父节点类型，可挂在任意实体节点下复用。
##
## 无敌门（加性扩展）：_invulnerable 为 true 时 take_damage 静默拒绝（heal 不受影响）。
## 默认关闭，直接复用行为与历史完全一致；窗口的开启/关闭由组合组件驱动
## （如 i_frames 受击自动开窗），Health 只拥有门的当前状态，不自带计时。

signal health_changed(current: int, amount: int)
signal died

@export var max_health := 5

var _current_health := 0
var _is_dead := false
var _invulnerable := false


func _ready() -> void:
	_current_health = max_health


func take_damage(amount: int) -> void:
	if _is_dead or _invulnerable or amount <= 0:
		return
	_current_health = max(_current_health - amount, 0)
	health_changed.emit(_current_health, amount)
	if _current_health == 0:
		_is_dead = true
		died.emit()


func heal(amount: int) -> void:
	if _is_dead or amount <= 0:
		return
	_current_health = min(_current_health + amount, max_health)
	health_changed.emit(_current_health, amount)


func set_invulnerable(value: bool) -> void:
	_invulnerable = value


func is_invulnerable() -> bool:
	return _invulnerable


func get_current_health() -> int:
	return _current_health


func is_dead() -> bool:
	return _is_dead
