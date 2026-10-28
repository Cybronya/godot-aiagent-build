class_name PatrolMovement
extends CharacterBody2D
## 巡逻移动组件：沿预设路径点循环（或往返）移动，与 player_controller（读输入）
## 和 chase_movement（追目标）互为镜像——本组件只沿 waypoints 走，不读输入、
## 不追目标，移动职责单一。必须作为 CharacterBody2D 实体的根脚本使用
## （与 ChaseMovement 相同的根脚本模式）。
##
## 设计抽象自 gdquest-demos/godot-open-rpg 的 path_loop_ai_controller
## （MIT，见 README 出处）：沿路径点循环行进 + 循环间可等待的思路。
## 合并取舍：去掉 Gameboard 寻路与 Line2D 依赖，改为导出本地偏移点数组——
## 场景里摆实体、填几个偏移即可工作，headless 可确定性测试。
##
## 语义：
## - points 为**相对初始位置**的本地偏移（实体摆好后无需换算全局坐标）
## - loop=true 绕圈（末点回到首点）；false 往返（端点折返）
## - 抵达判定带步长钳制（不因帧步长越过路径点）
## - points 为空时静止不报错

signal waypoint_reached(index: int)

@export var points: Array[Vector2] = []
@export var speed := 60.0
@export var loop := true

var _origin := Vector2.ZERO
var _index := 0
var _dir := 1          # 往返模式的方向（1 正向 / -1 反向）
var _target := Vector2.ZERO
var _last_emitted := -1  # 去重：驻留状态下不重复广播同一抵达


func _ready() -> void:
	_origin = global_position
	_advance_to(0)


func _physics_process(delta: float) -> void:
	if points.is_empty():
		return
	var to_target := _target - global_position
	var step := speed * delta
	if to_target.length() <= step:
		# 步长钳制：贴点而不是越过，避免高速抖动
		global_position = _target
		if _index != _last_emitted:
			_last_emitted = _index
			waypoint_reached.emit(_index)
		_advance_index()
		return
	velocity = to_target.normalized() * speed
	move_and_slide()


func _advance_index() -> void:
	if points.size() < 2:
		return  # 单点：原地驻留，反复抵达同一目标
	if loop:
		_advance_to((_index + 1) % points.size())
	elif _index + _dir >= points.size() or _index + _dir < 0:
		_dir = -_dir
		_advance_to(_index + _dir)
	else:
		_advance_to(_index + _dir)


func _advance_to(index: int) -> void:
	_index = index
	_target = _origin + (points[index] if index < points.size() else Vector2.ZERO)


func get_current_index() -> int:
	return _index
