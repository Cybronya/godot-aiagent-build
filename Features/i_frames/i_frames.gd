class_name IFrames
extends Node
## 受击无敌帧组件：宿主受到伤害后自动开启一段无敌窗口（门在 Health 上），
## 窗口内再次 take_damage 被静默拒绝，到期自动恢复可受击状态。
##
## 设计抽象自 nezvers/Godot-GameTemplate（MIT，见 README 出处）的
## DamageCooldown（can_receive_damage 受击门控思路）与 VisualInvulnerability
## （无敌状态的反应式表现）。合并取舍：门控状态放回 Health（本项目伤害
## 唯一入口），计时复用本项目的 Cooldown Feature（组合而非重造），视觉表现
## 不掺和——闪白交给 hit_flash，本组件只管门。
##
## 触发方式（可并存）：
## - iframes_on_hit=true（默认）：订阅宿主 Health，受击即开窗（call_deferred
##   落地，与 Stun/hit_flash 同一套死亡时序防护）
## - 任意代码调用 grant(duration)（主动模式，如技能无敌）
##
## 语义：固定窗口——窗口内再次受击不刷新时长（与 Stun 长盖短、Cooldown 重启
## 都不同；无敌帧通常应当是确定的保护期）。宿主死亡后不再开窗。

signal protected(is_protected: bool)

@export var iframes_on_hit := true
@export var duration := 0.3     ## 单次无敌窗口时长（秒）
@export var health_path: NodePath  ## 宿主 Health 路径；为空按约定找父节点下 "Health"

@onready var _cooldown: Cooldown = $Cooldown

var _health: Health
var _active := false
var _last_health := -1


func _ready() -> void:
	if not health_path.is_empty():
		_health = get_node_or_null(health_path) as Health
	elif get_parent().get_node_or_null("Health") is Health:
		_health = get_parent().get_node_or_null("Health") as Health
	if _health == null:
		push_warning("IFrames 需要宿主带 Health 组件（命名 \"Health\" 或设 health_path），本实例不会自动开窗")
		set_physics_process(false)
		return
	_cooldown.cooldown_finished.connect(_on_window_end)
	if iframes_on_hit:
		_health.health_changed.connect(_on_health_changed)
		_last_health = _health.get_current_health()


## 主动开启无敌窗口；duration<=0 用本组件 duration 导出值（仍<=0 则忽略）。
## 已在保护中、无 Health、宿主已死均拒绝（固定窗口不刷新）。返回是否实际生效。
func grant(override_duration := -1.0) -> bool:
	var d := duration if override_duration < 0.0 else override_duration
	if _health == null or _active or _health.is_dead() or d <= 0.0:
		return false
	_health.set_invulnerable(true)
	_cooldown.start(d)
	_active = true
	protected.emit(true)
	return true


func is_protected() -> bool:
	return _active


func _on_health_changed(current: int, _amount: int) -> void:
	# health_changed 在伤害与恢复时都会发出；受击判定依据生命值快照下降。
	# 延迟一帧应用：击杀一击的 health_changed 在 _is_dead 置位前发出，
	# 直接调用会绕过死亡守卫（与 Stun / hit_flash 同一套模式）。
	var damaged := current < _last_health
	_last_health = current
	if damaged:
		grant.call_deferred()


func _on_window_end() -> void:
	if _health != null and _active:
		_health.set_invulnerable(false)
	_active = false
	protected.emit(false)


func _exit_tree() -> void:
	# 移除时归还门状态，避免宿主永久无敌（本组件开窗期间独占门的写权）。
	if _health != null and _active:
		_health.set_invulnerable(false)
		_active = false
		protected.emit(false)
