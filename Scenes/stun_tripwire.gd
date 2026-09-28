extends Area2D
## 绊线机关（场景胶水）：玩家触发后，对指定目标实体调用其 Stun 组件的主动 API。
##
## 与 paralyze_trap.gd（晕踩入者自身）互为姊妹路由：本机关作用于
## target_path 指定的第三方目标（牵引目标定身、守护物锁止等场景语义）。
## 本脚本不实现任何眩晕逻辑，只做「触发 → 查找目标 Stun 组件 → 调用
## stun(duration)」的路由；Stun 组件按 AD-004 同类命名约定挂在目标根下。
## 目标缺失、被释放或无 Stun 组件时静默跳过，不报错。
## 提升条件（AD-003）：出现第二个「触发 → 指定目标行动限制」场景时再评估。

@export var stun_duration := 1.0
@export var cooldown := 0.5
@export var target_group := "players"
@export var target_path: NodePath

var _cooldown := 0.0
var _target: Node2D


func _ready() -> void:
	body_entered.connect(_on_body_entered)
	if not target_path.is_empty():
		_target = get_node_or_null(target_path) as Node2D


func _physics_process(delta: float) -> void:
	_cooldown = maxf(_cooldown - delta, 0.0)


func _on_body_entered(body: Node2D) -> void:
	if _cooldown > 0.0 or not body.is_in_group(target_group):
		return
	var target := _target
	if target == null or not is_instance_valid(target):
		# 惰性重解析：目标被释放后按路径重取，不可达则跳过
		target = get_node_or_null(target_path) as Node2D
		_target = target
	if target == null:
		return
	var stun_component := target.get_node_or_null("Stun") as Stun
	if stun_component == null:
		return
	if stun_component.stun(stun_duration):
		_cooldown = cooldown
