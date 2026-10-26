# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/misc/hdr_output/main/demo_scenes.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends Node

@export var scenes: Array[Control]


func _ready() -> void:
	_on_demo_scene_item_selected(0)


func _on_demo_scene_item_selected(index: int) -> void:
	for i in range(scenes.size()):
		scenes[i].visible = i == index
