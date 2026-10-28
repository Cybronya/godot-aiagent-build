class_name HitFlash
extends Node
## 受击闪白组件：宿主生命值下降时，把宿主（或指定 CanvasItem）的 modulate
## 抬到 flash_color 并在 flash_duration 内线性衰减回原色。
##
## 设计抽象自代码库参考片段（见 README 出处）：nezvers/Godot-GameTemplate 的
## color_flash.gdshader（混色闪白思路）+ godot-demo-projects 的 color_flash.gd
## （flash 后按时间衰减回基色的模式）。合并取舍：不改 shader、不要求材质配置，
## 用 modulate 实现——任意 CanvasItem 即插即用，headless 下可确定性测试。
##
## 触发方式（可并存，至少配置其一）：
## - flash_on_hit=true：订阅宿主 Health 的 health_changed，生命值下降（受击）即触发
##   （与 Stun 的 stun_on_hit 同一套判定：current < 上次值，治疗不触发）
## - 任意代码调用 flash(duration)（主动模式）
##
## 所有权：闪白期间独占目标的 modulate（离开场景时若仍在闪白则归还基色）；
## 死亡宿主不再触发；时长内再次触发取较大值刷新剩余时长（长盖短，与 Stun 一致）。

signal flashing(is_flashing: bool)

@export var flash_on_hit := true
@export var flash_color := Color(4.0, 4.0, 4.0)  ## SDR 下被钳制为白，HDR 下为过曝白
@export var flash_duration := 0.15
@export var health_path: NodePath                 ## 宿主 Health 路径；为空按约定找父节点下 "Health"
@export var flash_target_path: NodePath           ## 闪白目标；为空用父节点（须为 CanvasItem）

var _target: CanvasItem
var _health: Health
var _base := Color.WHITE
var _remaining := 0.0
var _total := 0.0
var _active := false
var _last_health := -1


func _ready() -> void:
	if not flash_target_path.is_empty():
		_target = get_node_or_null(flash_target_path) as CanvasItem
	elif get_parent() is CanvasItem:
		_target = get_parent() as CanvasItem
	if _target == null:
		push_warning("HitFlash 需要 CanvasItem 宿主（或设置 flash_target_path），本实例不会闪白")
		set_physics_process(false)
		return
	_base = _target.modulate

	if not health_path.is_empty():
		_health = get_node_or_null(health_path) as Health
	elif get_parent().get_node_or_null("Health") is Health:
		_health = get_parent().get_node_or_null("Health") as Health
	if flash_on_hit and _health != null:
		_health.health_changed.connect(_on_health_changed)
		_last_health = _health.get_current_health()


## 触发一次闪白；duration<=0 用 flash_duration（再<=0 则忽略）。
## 死亡宿主拒绝；时长内再次触发长盖短（不提前结束）。返回是否实际生效。
func flash(duration := -1.0) -> bool:
	if _target == null or _health != null and _health.is_dead():
		return false
	var d := duration if duration > 0.0 else flash_duration
	if d <= 0.0:
		return false
	if not _active:
		_active = true
		flashing.emit(true)
	_total = maxf(_total, d)
	_remaining = _total
	return true


func _physics_process(delta: float) -> void:
	if not _active:
		return
	_remaining = maxf(_remaining - delta, 0.0)
	if _remaining <= 0.0:
		_target.modulate = _base
		_active = false
		_total = 0.0
		flashing.emit(false)
	else:
		_target.modulate = _base.lerp(flash_color, _remaining / _total)


func _exit_tree() -> void:
	# 仍在闪白时移除：归还基色（本组件在闪白期间独占该属性）。
	if _target != null and _active:
		_target.modulate = _base


func _on_health_changed(current: int, _amount: int) -> void:
	# health_changed 在伤害与恢复时都会发出且 amount 均为正值，
	# 受击判定依据生命值快照下降；恢复不触发闪白。
	# 延迟一帧应用：击杀一击的 health_changed 在 _is_dead 置位前发出，
	# 直接调用会绕过死亡守卫；延迟落地时 flash() 内的死亡检查成为唯一拒绝点
	# （与 Stun 的 stun_on_hit 同一套模式）。
	var damaged := current < _last_health
	_last_health = current
	if damaged:
		flash.call_deferred()
