class_name FixtureTarget
extends StaticBody2D
## attack_emitter 行为夹具目标：静态物理体 + take_damage 协议实现。
## 承受的伤害转发给子节点真实 Health 组件（与 health Feature 联动），
## 同时保留本地计数供测试断言。

var damage_taken := 0
var last_amount := 0


func take_damage(amount: int) -> void:
	damage_taken += 1
	last_amount = amount
	var health := get_node_or_null("Health") as Health
	if health != null:
		health.take_damage(amount)
