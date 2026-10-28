class_name Cooldown
extends Node
## 通用冷却组件：start() 开始/重启一段倒计时，期间 is_ready() 为 false，
## 到期广播 cooldown_finished 后回到就绪。用于攻击间隔、技能 CD、受击无敌等
## 任何「用一次 → 等一段」的节流场景。
##
## 设计抽象自代码库参考片段（见 README 出处）：bitbrain/beehave 的 cooldown
## 装饰器（行为树门控思路）+ nezvers/Godot-GameTemplate 的 DamageCooldown
## （cooldown_started/finished 信号对）。合并取舍：脱离行为树 blackboard 与
## ResourceNode 框架，Tween 延迟改为 _physics_process 倒计时——独立挂载、
## headless 下可确定性测试。
##
## 语义选择（与 Stun 的长盖短不同）：start() 是**重启**语义——冷却中再次
## start 会重置剩余时长并再次广播 cooldown_started（攻击 CD 的自然语义）。
## 所有权：本组件只拥有自己的计时状态，不触碰宿主任何属性。

signal cooldown_started
signal cooldown_finished

@export var duration := 1.0        ## 默认冷却时长（秒）；start() 不带参数时使用
@export var auto_start := false    ## true 时 _ready 即自动开始一次冷却

var _remaining := 0.0
var _peak := 0.0
var _running := false


func _ready() -> void:
	if auto_start:
		start()


## 开始/重启冷却。override_duration<0（或不传）用本组件 duration 导出值；
## 显式传入 0 或负值以外的无效时长（<=0）一律拒绝。
## 冷却中再次 start 为重启语义（重置剩余时长，再次广播 started）。
## 返回是否实际生效。
func start(override_duration := -1.0) -> bool:
	var d := duration if override_duration < 0.0 else override_duration
	if d <= 0.0:
		return false
	_remaining = d
	_peak = d
	if not _running:
		_running = true
	cooldown_started.emit()
	return true


func is_ready() -> bool:
	return not _running


## 剩余秒数；就绪/未运行时为 0.0。
func get_remaining() -> float:
	return _remaining if _running else 0.0


## 冷却进度：1.0 = 就绪/未运行；运行中为 0.0（刚开始）.. 接近 1.0（将就绪）。
func get_progress() -> float:
	if not _running:
		return 1.0
	return 1.0 - _remaining / maxf(_peak, 0.0001)


func _physics_process(delta: float) -> void:
	if not _running:
		return
	_remaining = maxf(_remaining - delta, 0.0)
	if _remaining <= 0.0:
		_remaining = 0.0
		_running = false
		_peak = 0.0
		cooldown_finished.emit()
