# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/top_down/scripts/ui/game_over_screen/score_component.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  d5d8d1588742
extends Node

@export var score_resource:ScoreResource
@export var score_label:Label
@export var try_again_button:Button

func _ready()->void:
	try_again_button.grab_focus.call_deferred()
	try_again_button.pressed.connect(on_try_again_pressed)
	score_label.text = "Score: " + str(score_resource.value)

func on_try_again_pressed()->void:
	score_resource.reset_resource()
