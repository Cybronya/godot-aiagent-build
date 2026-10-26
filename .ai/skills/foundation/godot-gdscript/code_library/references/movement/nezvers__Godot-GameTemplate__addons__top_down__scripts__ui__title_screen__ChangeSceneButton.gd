# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/top_down/scripts/ui/title_screen/ChangeSceneButton.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  master
class_name ChangeSceneButton
extends Node

@export var button:Button
@export var scene_path:String

func _ready()->void:
	button.pressed.connect(pressed)

func pressed()->void:
	# Avoid triggering multiple times
	# Deffered because this function is called by that signal
	button.pressed.disconnect.call_deferred(pressed)
	
	Transition.change_scene(scene_path)
