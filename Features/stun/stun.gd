class_name Stun
extends Node
## 眩晕/硬直组件：使宿主 CharacterBody2D 的物理行为暂停一段时长后自动恢复。
##
## 触发方式（可并存，至少配置其一）：
## - stun_on_hit=true：订阅宿主 Health 的 health_changed，生命值下降（受击）即触发
## - 任意代码调用 stun(duration)：陷阱、技能、机关等外部效果（主动模式）
##
## 暂停范围：宿主根节点的物理处理（set_physics_process(false)）+ 速度清零；
## 与 player_death 的死亡表现同源（AD-002：受击/死亡后的表现由订阅方决定）。
## 子组件（ContactDamage 等）各自独立驱动，不受本组件影响，组合层可自行取舍。
## 时长内再次触发取剩余与新时长的较大值（长盖短，不提前解除）；
## 状态跨越时广播 stunned(bool)，重复同值不广播（幂等）。
## 宿主死亡后不再触发、恢复时不复活物理（死亡表现由死亡订阅方负责，不越权）。

signal stunned(is_stunned: bool)

@export var stun_on_hit := false
@export var stun_duration := 0.4
@export var health_path: NodePath

var _host: CharacterBody2D
var _health: Health
var _remaining := 0.0
var _last_health := -1


func _ready() -> void:
	_host = get_parent() as CharacterBody2D
	if not health_path.is_empty():
		_health = get_node_or_null(health_path) as Health
	elif _host != null:
		_health = _host.get_node_or_null("Health") as Health
	if stun_on_hit and _health != null:
		_health.health_changed.connect(_on_host_health_changed)
		_last_health = _health.get_current_health()


## 使宿主眩晕指定时长；duration<=0 忽略，宿主已死亡忽略。
## 时长内再次调用取较大值刷新剩余时长，不提前解除（不重复广播）。返回是否实际生效。
func stun(duration: float) -> bool:
	if duration <= 0.0 or _host == null:
		return false
	if _health != null and _health.is_dead():
		return false
	if _remaining <= 0.0:
		_host.set_physics_process(false)
		_host.velocity = Vector2.ZERO
		stunned.emit(true)
	_remaining = maxf(_remaining, duration)
	return true


func is_stunned() -> bool:
	return _remaining > 0.0


func _exit_tree() -> void:
	# 生命周期：组件在眩晕未结束时被移除（宿主仍存活），恢复宿主物理，
	# 避免留下永久停摆；死亡宿主不越权（死亡表现由死亡订阅方负责）。
	if _host == null or not is_instance_valid(_host):
		return
	if _remaining > 0.0 and (_health == null or not _health.is_dead()):
		_host.set_physics_process(true)
	_remaining = 0.0


func _process(delta: float) -> void:
	if _remaining <= 0.0:
		return
	_remaining -= delta
	if _remaining <= 0.0:
		_remaining = 0.0
		# 宿主死亡期间由死亡订阅方冻结物理，恢复时不越权复活
		if _health == null or not _health.is_dead():
			_host.set_physics_process(true)
		stunned.emit(false)


func _on_host_health_changed(current: int, _amount: int) -> void:
	# health_changed 在伤害与恢复时都会发出且 amount 均为正值，
	# 受击判定依据生命值快照下降；恢复不触发眩晕。
	# 延迟一帧应用：击杀一击的 health_changed 在 _is_dead 置位前发出，
	# 直接调用会绕过死亡守卫留下死后残留眩晕；延迟落地时
	# stun() 内的死亡检查成为唯一拒绝点。
	var damaged := current < _last_health
	_last_health = current
	if damaged:
		stun.call_deferred(stun_duration)
