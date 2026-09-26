class_name HealPickup
extends Area2D
## 治疗拾取物：目标组实体接触时恢复其 Health，随后从场景移除自身。
##
## 恢复规则完全复用 Health.heal()（上限钳制不超过 max_health）；
## 满血或死亡目标不消费拾取物，拾取物保持在场。
## 需要场景在同节点下提供 CollisionShape2D 定义拾取范围。

@export var heal_amount := 2
@export var target_group := "players"


func _ready() -> void:
	body_entered.connect(_on_body_entered)


func _on_body_entered(body: Node2D) -> void:
	if not body.is_in_group(target_group):
		return
	var health := body.get_node_or_null("Health") as Health
	if health == null or health.is_dead():
		return
	if health.get_current_health() >= health.max_health:
		return
	health.heal(heal_amount)
	queue_free()
