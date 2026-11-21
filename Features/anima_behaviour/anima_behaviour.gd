class_name MotionTrigger
extends Node2D
## 动画触发器：节点进入/退出场景树时自动播放子 AnimationPlayer 的入场/退场动画。
##
## 抽象自 ceceppa/anima (MIT)，简化：
## - 去掉 Anima 运行时依赖，直接驱动子节点的 AnimationPlayer
## - 保留核心：入场/退场动画、自动播放、隐藏
## - 自动收集子节点中的 AnimationPlayer

@export var play_in_on_ready: bool = false
@export var hide_after_out: bool = false

var _players: Array[AnimationPlayer] = []


func _ready() -> void:
	_collect_players()
	if play_in_on_ready:
		play_motion_in()


func _exit_tree() -> void:
	play_motion_out()


func _collect_players() -> void:
	_players.clear()
	for child in get_children():
		if child is AnimationPlayer:
			_players.append(child)


func play_motion_in() -> void:
	for ap in _players:
		if ap.has_animation("motion_in"):
			ap.play("motion_in")


func play_motion_out() -> void:
	for ap in _players:
		if ap.has_animation("motion_out"):
			ap.play("motion_out")
	if hide_after_out:
		visible = false


func get_players() -> Array[AnimationPlayer]:
	return _players.duplicate()
