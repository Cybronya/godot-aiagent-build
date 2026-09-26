class_name TriggerSwitch
extends Area2D
## 触发开关：玩家（目标组实体）进入触发范围后改变自身状态并广播信号。
##
## 职责单一：只感知触发并维护自身状态，不知道也不关心谁在监听。
## 关系连接由使用场景完成：订阅 activated 信号去驱动任意门/平台/事件，
## 无节点名依赖；reset() 供场景重开等流程恢复初始状态。
## 默认一次性触发（触发后保持，玩家离开范围不回退）；
## trigger_mode = Repeat 表示每次进入范围都重新触发，需明确理由才使用。

signal activated(triggered: bool)

enum Mode { Latching, Repeat }

@export var trigger_mode: Mode = Mode.Latching
@export var target_group := "players"

var _triggered := false


func _ready() -> void:
	body_entered.connect(_on_body_entered)


func is_triggered() -> bool:
	return _triggered


## 恢复未触发状态并广播 false；由场景级重置流程调用，本组件不自行动重置。
func reset() -> void:
	_triggered = false
	activated.emit(false)


func _on_body_entered(body: Node2D) -> void:
	if not body.is_in_group(target_group):
		return
	if trigger_mode == Mode.Latching and _triggered:
		return
	_triggered = true
	activated.emit(true)
