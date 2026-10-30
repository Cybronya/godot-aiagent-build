class_name RaycastAttackEmitter
extends AttackEmitter
## 射线发射器：沿自身 +X 方向做一次瞬时射线判定，命中即结算伤害。
##
## 需要一个 RayCast2D 子节点（target_position 决定射程与方向，通常 (射程, 0)）。
## do_attack 时同步 force_raycast_update：
## - 命中可伤害目标（实现 take_damage 的节点）→ 结算 damage 并发 attack_hit；
## - attack_performed 总会发出（from_pos/to_pos/hit/point），
##   弹道线、命中特效等视觉反馈由组合层按这两个信号实现。
##
## 扇形（spray）、弧形（arc）等其他发射形态可按同样协议继承 AttackEmitter 扩展。

@onready var ray_cast_2d: RayCast2D = $RayCast2D


func set_bodies_to_exclude(bodies: Array) -> void:
	super(bodies)
	if ray_cast_2d == null:
		return
	for body in bodies:
		ray_cast_2d.add_exception(body)


func do_attack() -> void:
	super()
	if ray_cast_2d == null:
		push_error("RaycastAttackEmitter: 缺少 RayCast2D 子节点")
		return
	ray_cast_2d.force_raycast_update()
	var from_pos := global_position
	var to_pos := ray_cast_2d.to_global(ray_cast_2d.target_position)
	if ray_cast_2d.is_colliding():
		to_pos = ray_cast_2d.get_collision_point()
		var collider: Object = ray_cast_2d.get_collider()
		if collider is Node and collider.has_method("take_damage"):
			_apply_damage(collider)
			attack_hit.emit(collider, to_pos)
	attack_performed.emit(from_pos, to_pos, ray_cast_2d.is_colliding(), to_pos)
