class_name InteractionAudio3D
extends AudioStreamPlayer3D
## 3D 交互音效：在交互事件（拿起/放下/碰撞）时播放不同音效，音量随速度衰减。
##
## 抽象自 GodotVR/godot-xr-tools (MIT)，简化：
## - 去掉 XRToolsPickable 依赖，改为信号驱动
## - 保留核心：碰撞/拿起/放下触发音效 + 速度衰减
## - 调用方在对应事件时调用 on_picked_up() / on_dropped() / on_body_entered()

@export var grab_sound: AudioStream = null
@export var drop_sound: AudioStream = null
@export var hit_sound: AudioStream = null
@export var velocity_attenuation: float = 0.1
@export var move_velocity: Vector3 = Vector3.ZERO


func _physics_process(delta: float) -> void:
	if move_velocity.length() > 5.0:
		volume_db = 0.0
	else:
		volume_db -= move_velocity.length() * velocity_attenuation


## 拿起时调用：播放 grab_sound。
func on_picked_up() -> void:
	volume_db = 0.0
	if playing:
		stop()
	if grab_sound != null:
		stream = grab_sound
		play()


## 放下时调用：停止当前播放。
func on_dropped() -> void:
	if playing:
		stop()


## 碰撞时调用：已拿起播放 hit_sound，未拿起播放 drop_sound。
func on_body_entered(_body: Node) -> void:
	if playing:
		stop()
	if is_picked_up():
		if hit_sound != null:
			stream = hit_sound
			play()
	else:
		if drop_sound != null:
			stream = drop_sound
			play()


## 是否被拿起。默认 false，子类或外部可覆盖。
func is_picked_up() -> bool:
	return false
