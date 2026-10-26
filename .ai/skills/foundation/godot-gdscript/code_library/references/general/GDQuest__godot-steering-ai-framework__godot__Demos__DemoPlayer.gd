# Source:  https://github.com/GDQuest/godot-steering-ai-framework/blob/master/godot/Demos/DemoPlayer.gd
# Repo:    GDQuest/godot-steering-ai-framework (star 1588) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends Node2D


func load_demo(scene_path: String) -> void:
	if not scene_path:
		return

	var demo = load(scene_path)
	if demo:
		add_child(demo.instantiate())


func unload() -> void:
	for node in get_children():
		call_deferred("remove_child", node)
		node.queue_free()
