class_name OpenableDoor
extends StaticBody2D
## 状态门：接收激活信号切换「阻挡 ↔ 通行」，视觉同步反映当前状态。
##
## 纯被动组件：不知道信号来自开关、按钮还是脚本；通过 connect 任意
## activated(bool) 类信号驱动，无节点名依赖。collision 开关用 set_deferred，
## 安全用于信号回调（含物理回调）上下文。

signal state_changed(is_open: bool)

@export var start_open := false
@export var open_visual_color := Color(0.4, 0.8, 0.5, 0.25)
@export var closed_visual_color := Color(0.55, 0.4, 0.25, 1.0)

var _visual: Polygon2D
var _collision: CollisionShape2D
var _is_open := false


func _ready() -> void:
	_visual = get_node_or_null("Visual") as Polygon2D
	_collision = get_node_or_null("Collision") as CollisionShape2D
	_apply(start_open)


func is_open() -> bool:
	return _is_open


## 设置门状态：true 开（停止阻挡、变半透明绿），false 关（恢复阻挡、实体棕）。
## 任意来源（开关信号、脚本、测试）可重复调用，重复设置同值无副作用。
func set_open(value: bool) -> void:
	if _is_open == value:
		return
	_apply(value)


func _apply(value: bool) -> void:
	_is_open = value
	if _collision != null:
		_collision.set_deferred("disabled", value)
	if _visual != null:
		_visual.color = open_visual_color if value else closed_visual_color
	state_changed.emit(value)
