extends Node
## 玩家死亡表现：冻结移动、隐藏外观、关闭碰撞。
## 死亡判定复用 health Feature（订阅宿主 Health 的 died 信号），
## 本脚本只负责死亡后的表现，不实现任何生命值逻辑。

@export var visual_path := NodePath("../Visual")
@export var collision_path := NodePath("../Collision")

var _applied := false


func _ready() -> void:
	var player := get_parent()
	var health := player.get_node("Health") as Health
	health.died.connect(_on_died)


func _on_died() -> void:
	if _applied:
		return
	_applied = true
	var player := get_parent()
	player.set_physics_process(false)
	player.velocity = Vector2.ZERO
	var visual := get_node_or_null(visual_path) as CanvasItem
	if visual != null:
		visual.visible = false
	var collision := get_node_or_null(collision_path) as CollisionShape2D
	if collision != null:
		collision.set_deferred("disabled", true)
