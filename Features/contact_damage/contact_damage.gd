class_name ContactDamage
extends Area2D
## 接触伤害组件：对与宿主重叠、属于目标组的实体按节拍造成伤害。
##
## 挂在实体根（或作为实体根脚本）下，需要场景提供 CollisionShape2D；
## 目标实体须满足两个约定：加入 target_group 指定的组、Health 组件节点命名为
## "Health"（本项目实体场景统一约定，见 AD-002 组件组合模式）。
## 伤害规则完全复用 Health.take_damage()，本组件不实现任何生命值逻辑。
## 死亡目标由 Health 自身的死亡保护兜底，不再受击。

@export var damage := 1
@export var tick_interval := 0.5
@export var target_group := "players"

var _cooldown := 0.0


func _physics_process(delta: float) -> void:
	_cooldown -= delta
	if _cooldown > 0.0:
		return
	_cooldown = tick_interval
	for body: Node2D in get_overlapping_bodies():
		_deal_damage_to(body)


func _deal_damage_to(node: Node) -> void:
	if not node.is_in_group(target_group):
		return
	var health := node.get_node_or_null("Health") as Health
	if health == null:
		return
	health.take_damage(damage)
