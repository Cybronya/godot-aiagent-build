class_name MovingPlatform
extends AnimatableBody2D
## 移动平台：在起点与起点+travel 之间往返移动，重叠载客区的玩家随平台位移。
##
## top-down 渡载语义：平台不依赖重力；进入 RideZone 的目标组实体会被记录为
## 乘客，平台每帧的位移量直接应用到乘客位置（被平台携带）。离开载客区即下车。
## 本体可按需添加 CollisionShape2D 获得推挤能力（本 Feature 场景默认
## 不带实体碰撞，纯渡载语义）。
## 位置由内部时间驱动（三角波往返）：场景重载后从起点重新开始，无需 reset。

@export var travel := Vector2(200.0, 0.0)
@export var period := 4.0
@export var target_group := "players"

var _origin := Vector2.ZERO
var _time := 0.0
var _riders: Array[Node2D] = []
var _last_position := Vector2.ZERO


func _ready() -> void:
	_origin = global_position
	_last_position = global_position


func _physics_process(delta: float) -> void:
	_time += delta
	if period <= 0.0:
		return
	var cycle := fmod(_time, period) / period
	var phase := 1.0 - absf(cycle * 2.0 - 1.0)
	global_position = _origin + travel * phase
	var platform_delta := global_position - _last_position
	_last_position = global_position
	for rider in _riders:
		if is_instance_valid(rider):
			rider.global_position += platform_delta


func _on_ride_zone_body_entered(body: Node2D) -> void:
	if body.is_in_group(target_group) and not _riders.has(body):
		_riders.append(body)


func _on_ride_zone_body_exited(body: Node2D) -> void:
	_riders.erase(body)
