class_name HealthBar
extends Node2D
## 血条显示组件：绑定宿主 Health，按当前/最大生命值比例绘制双色血条。
##
## 纯显示组件：不修改任何生命值状态，仅订阅 health_changed / died 信号刷新。
## 不依赖宿主节点类型，只要按 health_path 指向一个 Health 组件即可复用。

@export var health_path: NodePath
@export var bar_size := Vector2(32.0, 4.0)
@export var back_color := Color(0.6, 0.1, 0.1, 0.9)
@export var fill_color := Color(0.25, 0.85, 0.3, 1.0)

var _health: Health


func _ready() -> void:
	if not health_path.is_empty():
		_health = get_node_or_null(health_path) as Health
	if _health != null:
		_health.health_changed.connect(_on_health_changed)
		_health.died.connect(_on_died)
	queue_redraw()


func get_ratio() -> float:
	if _health == null or _health.max_health <= 0:
		return 0.0
	return float(_health.get_current_health()) / float(_health.max_health)


func _draw() -> void:
	draw_rect(Rect2(Vector2(-bar_size.x / 2.0, -bar_size.y / 2.0), bar_size), back_color)
	var ratio := get_ratio()
	if ratio > 0.0:
		var fill := Vector2(bar_size.x * ratio, bar_size.y)
		draw_rect(Rect2(Vector2(-bar_size.x / 2.0, -bar_size.y / 2.0), fill), fill_color)


func _on_health_changed(_current: int, _amount: int) -> void:
	queue_redraw()


func _on_died() -> void:
	queue_redraw()
