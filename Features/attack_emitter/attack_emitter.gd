class_name AttackEmitter
extends Node2D
## 攻击发射器基类：描述「从武器发出一次攻击」的可组合单元。
##
## 发射器可嵌套：子发射器自动继承 damage / source_of_attack / 排除列表，
## do_attack() 会沿链向下传播（一把武器可同时含直线、扇形多个发射器）。
## 命中协议：对可伤害目标（实现 take_damage(amount: int) 的节点，如 Health
## 组件宿主）直接结算伤害；视觉反馈（弹道、命中特效、音效）不属于本组件，
## 由组合层订阅 attacked / attack_performed / attack_hit 信号实现。
##
## 抽象来源片段：Miziziziz/MizGodotTools items/weapons/attack_emitters（MIT），
## 剥除原工程 HitBox/DamageData 类依赖与特效场景预载，
## 命中结算改接本项目的 Health.take_damage 约定。

## 攻击发起（do_attack 被调用，无论是否命中）。
signal attacked
## 一次具体发射完成（仅派生类发出）：起点、终点、是否命中可伤害目标、命中点。
signal attack_performed(from_pos: Vector2, to_pos: Vector2, hit: bool, point: Vector2)
## 命中可伤害目标（目标已实际承受伤害）。
signal attack_hit(target: Node, point: Vector2)

var damage := 1:
	set(value):
		damage = value
		_propagate("damage", value)

var source_of_attack: Node2D = null:
	set(value):
		source_of_attack = value
		_propagate("source_of_attack", value)


## 声明本次攻击应排除的物理体（通常是攻击者自身）。
func set_bodies_to_exclude(_bodies: Array) -> void:
	pass


## 发起攻击：沿链调用所有子发射器，并广播 attacked。
func do_attack() -> void:
	for child in get_children():
		if child is AttackEmitter:
			child.do_attack()
	attacked.emit()


func _propagate(property: String, value: Variant) -> void:
	for child in get_children():
		if child is AttackEmitter:
			child.set(property, value)


## 对目标结算伤害：目标实现 take_damage(amount: int) 即视为可伤害
## （与 health Feature 的公开接口对接）。
func _apply_damage(target: Node) -> void:
	if target.has_method("take_damage"):
		target.take_damage(damage)
