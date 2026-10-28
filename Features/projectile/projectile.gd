class_name Projectile
extends Area2D
## 直线抛射物：launch(direction) 后按恒定速度飞行，命中带 Health 的实体
## （"Health" 子节点约定，与 ContactDamage 同一套）造成伤害；受穿透数上限与
## 生命期双重终止约束。
##
## 设计抽象自代码库参考片段（见 README 出处）：nezvers/Godot-GameTemplate
## 武器系统的 Projectile2D/HitLimit（穿透计数与终止生命周期）+ 
## gdquest-demos/godot-open-rpg 的 battler_action_projectile（发射动作 spawns
## 抛射物并传入方向）。合并取舍：去掉 DataChannelTransmitter/ProjectileMover/
## ShapeCastTransmitter 框架链，用本项目 Area2D.body_entered + "Health" 约定
## 直连；伤害入口统一走 Health.take_damage（i_frames 无敌门自然生效）。
##
## 所有权：本组件拥有自身位移与生命周期，不写宿主/目标任何属性；
## 命中判定交给物理（body_entered），不主动扫组。

signal hit(target: Node)          ## 每次命中带 Health 的实体时发出
signal finished                   ## 因穿透耗尽或生命期到期而终止时发出（恰一次）

@export var speed := 300.0        ## 飞行速度（像素/秒）
@export var damage := 1           ## 每次命中造成的伤害
@export var lifetime := 3.0       ## 生命期（秒），到期自动终止
@export var max_hits := 1         ## 最大命中数；<1 表示无限穿透
@export var launch_on_ready := false  ## true 时 _ready 自动朝自身旋转方向（+X）发射

var _direction := Vector2.ZERO
var _launched := false
var _remaining := 0.0
var _hit_count := 0
var _finished := false


func _ready() -> void:
	body_entered.connect(_on_body_entered)
	if launch_on_ready:
		launch(Vector2.RIGHT.rotated(rotation))


## 发射：direction 会被归一化；重复发射重置方向（不重置已计命中数）。
func launch(direction: Vector2) -> void:
	if direction == Vector2.ZERO:
		return
	_direction = direction.normalized()
	_launched = true
	_remaining = lifetime


func _physics_process(delta: float) -> void:
	if not _launched or _finished:
		return
	position += _direction * speed * delta
	_remaining -= delta
	if _remaining <= 0.0:
		_expire()


func _on_body_entered(body: Node) -> void:
	if _finished or not _launched:
		return
	var health := body.get_node_or_null("Health") as Health
	if health == null:
		return  # 无 Health 的物体直接穿过（墙体等由物理层屏蔽）
	health.take_damage(damage)
	hit.emit(body)
	_hit_count += 1
	if max_hits >= 1 and _hit_count >= max_hits:
		_finish()


func _expire() -> void:
	_remaining = 0.0
	_finish()


func _finish() -> void:
	if _finished:
		return
	_finished = true
	finished.emit()
	queue_free()
