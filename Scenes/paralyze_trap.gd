extends Area2D
## 麻痹陷阱（场景胶水）：对踩入的目标组实体调用其 Stun 组件的主动 API。
##
## 本脚本是 Stun Feature 主动模式的参考消费者：不实现任何眩晕逻辑，
## 只做「接触 → 查找宿主 Stun 组件 → 调用 stun(duration)」的路由。
## Stun 组件按 AD-004 同类命名约定挂在实体根下（节点名 "Stun"）。

@export var stun_duration := 1.0
@export var cooldown := 0.5
@export var target_group := "players"

var _cooldown := 0.0


func _ready() -> void:
	body_entered.connect(_on_body_entered)


func _physics_process(delta: float) -> void:
	_cooldown = maxf(_cooldown - delta, 0.0)


func _on_body_entered(body: Node2D) -> void:
	if _cooldown > 0.0 or not body.is_in_group(target_group):
		return
	var stun_component := body.get_node_or_null("Stun") as Stun
	if stun_component == null:
		return
	if stun_component.stun(stun_duration):
		_cooldown = cooldown
