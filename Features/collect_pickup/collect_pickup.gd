class_name CollectPickup
extends Area2D
## 接触拾取组件：目标组实体接触后广播 collected 并从场景移除自身。
##
## 与 heal_pickup 的边界：本组件不与 Health 交互、无数值结算——只表达
## 「接触 → 收集事件 → 消失」的一次性拾取语义（钥匙、金币、碎片）。
## collected 信号签名 (value: bool, pickup_id: String) 与 ConditionGate
## 的 set_condition(value, id) 绑定兼容：场景连接 binds=[pickup_id] 即可
## 把收集事件直接接入条件聚合，无需胶水脚本。
## 需要场景在同节点下提供 CollisionShape2D 定义拾取范围。

signal collected(value: bool, pickup_id: String)

@export var pickup_id := ""
@export var target_group := "players"

var _collected := false


func _ready() -> void:
	body_entered.connect(_on_body_entered)


func is_collected() -> bool:
	return _collected


func _on_body_entered(body: Node2D) -> void:
	if _collected or not body.is_in_group(target_group):
		return
	_collected = true
	collected.emit(true, pickup_id)
	queue_free()
