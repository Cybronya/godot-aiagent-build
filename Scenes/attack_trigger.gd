extends Node
## 游戏侧伤害触发器：监听攻击动作，对解析出的目标 Health 调用既有接口。
##
## 本脚本属于游戏组合层，不是 Feature：目标与动作由场景配置决定，
## 受击与死亡规则完全复用 health Feature，本脚本不实现任何生命值逻辑。
## 目标解析两种模式（路径优先，可只配其一）：
## - target_health_path 非空：固定单一目标（PvP、Boss 等静态目标场景）
## - target_group 非空：攻击时解析组内距宿主最近且存活的实体目标
##   （波次/刷怪等动态目标场景；目标实体须满足 Health 子节点命名约定）

@export var attack_action := "p1_attack"
@export var target_health_path: NodePath
@export var target_group := ""
@export var damage := 1

var _fixed_target: Health


func _ready() -> void:
	if not target_health_path.is_empty():
		_fixed_target = get_node(target_health_path)


func _physics_process(_delta: float) -> void:
	if not Input.is_action_just_pressed(attack_action):
		return
	var target := _resolve_target()
	if target != null:
		target.take_damage(damage)


func _resolve_target() -> Health:
	if _fixed_target != null:
		return _fixed_target
	if target_group.is_empty():
		return null
	var host := get_parent() as Node2D
	if host == null:
		return null
	var nearest: Health = null
	var nearest_dist := INF
	for node in get_tree().get_nodes_in_group(target_group):
		var entity := node as Node2D
		var health := entity.get_node_or_null("Health") as Health
		if health == null or health.is_dead():
			continue
		var dist := host.global_position.distance_to(entity.global_position)
		if dist < nearest_dist:
			nearest_dist = dist
			nearest = health
	return nearest
