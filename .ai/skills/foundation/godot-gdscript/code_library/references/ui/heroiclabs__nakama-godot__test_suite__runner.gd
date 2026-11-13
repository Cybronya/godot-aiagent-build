# Source:  https://github.com/heroiclabs/nakama-godot/blob/master/test_suite/runner.gd
# Repo:    heroiclabs/nakama-godot (star 783) | License: Apache-2.0 | Collected: 2026-10-31
# Commit:  6dc7b3951d98
extends SceneTree

func _init():
	var me = ProjectSettings.localize_path(ProjectSettings.globalize_path(get_script().resource_path))
	var dir = ProjectSettings.localize_path(me.get_base_dir())

	if dir != "res://":
		print("Must be run with the script dir as the res:// path")
		print("Current path: ", ProjectSettings.globalize_path(dir))
		print("RES:// path: ", ProjectSettings.globalize_path("res://"))
		quit()
		return
	var n = load("res://tester.gd").new()
	root.add_child(n)
	current_scene = n
