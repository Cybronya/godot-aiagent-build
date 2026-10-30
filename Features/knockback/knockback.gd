class_name Knockback
extends Node
## 击退组件：作为 CharacterBody2D 实体根的直接子节点，施加一段随时间线性衰减的
## 位移脉冲，用于受击反馈（敌人被打退、玩家被爆炸推开等）。
##
## 设计抽象自外部参考片段（Miziziziz/MizGodotTools 的 damage_data.gd，MIT，
## 见 code_library references/combat/...damage_data.gd——它把 damage_direction /
## knockback_modifier 打包进伤害载荷）。本组件只保留击退本体：
## - 位置位移式：每物理帧把宿主 global_position 前进 _velocity * delta，**不碰宿主
##   velocity**——因此与 chase/patrol 等直接写 velocity 的根脚本移动天然无冲突，
##   移动逻辑照常工作，击退叠加在位移上。
## - 线性衰减：_velocity 按 decay（px/s²）线性衰减到零；力 F、衰减 D 时的总位移
##   = F² / (2D)，全程确定（固定物理帧）。
## - 重启语义：激活中再次 apply 覆盖当前击退速度（从新值重新衰减），不重复广播
##   knockback_changed(true)（幂等，与 ScreenShake 的 shaking 同型）。
##
## 所有权：本组件独占「击退位移」这一增量——position 改变是永久的（击退本就该
## 改变位置），离开场景无需归还；不触碰宿主 velocity / 碰撞 / 其它属性。

signal knockback_changed(is_active: bool)

@export var decay := 800.0             ## 击退速度每秒衰减量（px/s²）

var _velocity := Vector2.ZERO
var _active := false
var _body: CharacterBody2D


func _ready() -> void:
	_body = get_parent() as CharacterBody2D
	if _body == null:
		push_warning("Knockback 必须作为 CharacterBody2D 的直接子节点，本实例不会生效")
		set_physics_process(false)


## 施加一次击退脉冲。direction 自动归一化（零向量拒绝），force 为初速度（px/s）。
## 从静止进入击退时广播一次 knockback_changed(true)（激活中重复 apply 不重复广播）。
## 宿主缺失（父节点不是 CharacterBody2D）、force<=0 或零方向返回 false。
func apply(direction: Vector2, force: float) -> bool:
	if _body == null or force <= 0.0 or direction == Vector2.ZERO:
		return false
	_velocity = direction.normalized() * force
	if not _active:
		_active = true
		knockback_changed.emit(true)
	return true


func is_active() -> bool:
	return _active


func current_velocity() -> Vector2:
	return _velocity


func _physics_process(delta: float) -> void:
	if not _active:
		return
	_body.global_position += _velocity * delta
	_velocity = _velocity.move_toward(Vector2.ZERO, decay * delta)
	if _velocity == Vector2.ZERO:
		_active = false
		knockback_changed.emit(false)
