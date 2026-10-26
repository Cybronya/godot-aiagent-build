# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/top_down/scripts/ui/boot_screen/boot_screen_manager.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends Node

@export var next_screen:String
@export var animation_player:AnimationPlayer
@export var boot_preloader:BootPreloader

func _ready()->void:
	animation_player.play("idle")
	boot_preloader.preload_finished.connect(_transition_out)
	# Allow visuals appear on screen
	get_tree().create_timer(0.1).timeout.connect(boot_preloader.start)


func _transition_out()->void:
	animation_player.play("transition_out", 0.5)
	animation_player.animation_finished.connect(_switch_scene)

func _switch_scene(_anim:StringName)->void:
	get_tree().change_scene_to_file(next_screen)
