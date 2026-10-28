class_name ScreenShake
extends Node
## 屏幕震动组件：作为 Camera2D 的直接子节点，用 trauma 强度衰减 + 种子化噪声驱动
## 相机 offset，产生衰减式随机抖动。
##
## 设计抽象自外部参考片段（nezvers/Godot-GameTemplate 的 CameraShakeResource，MIT，
## 见 code_library references/animation/...CameraShakeResource.gd），去掉了其
## Resource 框架依赖（ReferenceNodeResource/TweenValueResource 等），改为：
## - 挂载即用：父节点必须是 Camera2D（与 Stun 的 get_parent() 宿主约定一致）
## - trauma 模型：add_trauma 叠加强度（0..1），每秒按 decay 线性衰减，偏移 = 噪声 ×
##   max_offset × trauma²（平方衰减符合手感惯例，参考 GDC "Math for Game Programmers:
##   Juicing Your Cameras With Math"）
## - 噪声种子化（noise_seed），测试与录像可复现
##
## 所有权：本组件独占宿主 Camera2D.offset（离开场景时归零）；不触碰相机的其它属性，
## 不订阅任何 Feature 状态——触发时机（受击/爆炸/眩晕）由组合层调用 add_trauma。

signal shaking(is_shaking: bool)

@export var decay := 2.0             ## trauma 每秒衰减量；0.2 强度约 6 帧衰减完
@export var max_offset := 12.0       ## 满 trauma 时的最大像素偏移
@export var noise_speed := 20.0      ## 噪声采样时间推进速度（越大抖动越急促）
@export var noise_seed := 1337       ## 噪声种子；同种子同输入序列结果一致

var _trauma := 0.0
var _active := false
var _camera: Camera2D
var _noise := FastNoiseLite.new()
var _time := 0.0


func _ready() -> void:
	_camera = get_parent() as Camera2D
	if _camera == null:
		push_warning("ScreenShake 必须作为 Camera2D 的直接子节点，本实例不会震动")
		set_physics_process(false)
		return
	_noise.seed = noise_seed
	_noise.frequency = 1.0


## 叠加震动强度（自动 clamp 到 0..1）。amount<=0 忽略。
## 从静止进入震动时广播一次 shaking(true)（重复叠加不重复广播，幂等）。
## 相机缺失（父节点不是 Camera2D）返回 false。返回是否实际生效。
func add_trauma(amount: float) -> bool:
	if _camera == null or amount <= 0.0:
		return false
	_trauma = clampf(_trauma + amount, 0.0, 1.0)
	if not _active:
		_active = true
		shaking.emit(true)
	return true


func _physics_process(delta: float) -> void:
	if _trauma <= 0.0:
		return
	_time += delta * noise_speed
	_trauma = maxf(_trauma - decay * delta, 0.0)
	if _trauma <= 0.0:
		_camera.offset = Vector2.ZERO
		_active = false
		shaking.emit(false)
	else:
		var strength := _trauma * _trauma
		_camera.offset = Vector2(
			_noise.get_noise_2d(_time, 0.0),
			_noise.get_noise_2d(0.0, _time),
		) * max_offset * strength


func _exit_tree() -> void:
	# 移除时归还 offset，避免残留偏移（本组件独占该属性）。
	if _camera != null:
		_camera.offset = Vector2.ZERO
