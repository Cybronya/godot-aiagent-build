# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/3d/voxel/menu/ingame/pause_menu.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends Control

@onready var crosshair: CenterContainer = $Crosshair
@onready var pause: VBoxContainer = $Pause
@onready var options: Control = $Options
@onready var voxel_world: Node = $"../VoxelWorld"

func _process(_delta: float) -> void:
	if Input.is_action_just_pressed(&"pause"):
		pause.visible = crosshair.visible
		crosshair.visible = not crosshair.visible
		options.visible = false
		if crosshair.visible:
			Input.set_mouse_mode(Input.MOUSE_MODE_CAPTURED)
		else:
			Input.set_mouse_mode(Input.MOUSE_MODE_VISIBLE)


func _on_Resume_pressed() -> void:
	Input.set_mouse_mode(Input.MOUSE_MODE_CAPTURED)
	crosshair.visible = true
	pause.visible = false


func _on_Options_pressed() -> void:
	options.prev_menu = pause
	options.visible = true
	pause.visible = false


func _on_MainMenu_pressed() -> void:
	voxel_world.clean_up()
	get_tree().change_scene_to_packed(load("res://menu/main/main_menu.tscn"))


func _on_Exit_pressed() -> void:
	voxel_world.clean_up()
	get_tree().quit()
