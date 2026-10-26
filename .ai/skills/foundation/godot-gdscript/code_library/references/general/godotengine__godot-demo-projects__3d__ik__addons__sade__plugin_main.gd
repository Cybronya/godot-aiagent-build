# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/3d/ik/addons/sade/plugin_main.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
@tool
extends EditorPlugin

func _enter_tree():
	# Plugin Initialization here!
	add_custom_type("IK_LookAt", "Node3D", preload("ik_look_at.gd"), preload("ik_look_at.png"))
	add_custom_type("IK_FABRIK", "Node3D", preload("ik_fabrik.gd"), preload("ik_fabrik.png"))


func _exit_tree():
	# Plugin Clean-up here!
	remove_custom_type("IK_LookAt")
	remove_custom_type("IK_FABRIK")
