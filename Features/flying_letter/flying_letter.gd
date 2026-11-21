class_name FlyingLetter
extends Node2D
## 浮动文字效果：文字向上飘飞，带重力下落和旋转，常用于伤害数字/经验提示。
##
## 抽象自 cis-ash/TEXTREME (MIT)，简化：
## - 去掉 Effect 父类依赖，自建 Label 子节点
## - 保留物理运动：初速度 + 重力 + 角速度
## - 可配置速度/重力/旋转范围和生命周期
## - lifetime 到期后自动移除

@export var x_speed_min: float = -300.0
@export var x_speed_max: float = -100.0
@export var y_speed_min: float = -220.0
@export var y_speed_max: float = -108.0
@export var gravity_min: float = 300.0
@export var gravity_max: float = 400.0
@export var rotations_per_s_min: float = 7.0
@export var rotations_per_s_max: float = 13.0
@export var lifetime: float = 2.0

var _label: Label
var _velocity: Vector2
var _angular_velocity: float
var _gravity: float
var _elapsed: float = 0.0

signal letter_finished


func _ready() -> void:
	_label = Label.new()
	_label.name = "Label"
	add_child(_label)


## 初始化浮动文字。text 为显示内容，position 为起始位置，font 可选覆盖字体。
func setup(text: String, position: Vector2, font: Font = null) -> void:
	_label.text = text
	if font != null:
		_label.add_theme_font_override("font", font)
	_label.add_theme_font_size_override("font_size", 16)
	global_position = position

	_velocity = Vector2(
		randf_range(x_speed_min, x_speed_max),
		randf_range(y_speed_min, y_speed_max)
	)
	_gravity = randf_range(gravity_min, gravity_max)
	_angular_velocity = randf_range(rotations_per_s_min, rotations_per_s_max)
	_elapsed = 0.0


func _process(delta: float) -> void:
	_elapsed += delta
	position += _velocity * delta
	rotation += _angular_velocity * delta
	_velocity.y += _gravity * delta

	if _elapsed >= lifetime:
		letter_finished.emit()
		queue_free()


func get_label() -> Label:
	return _label
