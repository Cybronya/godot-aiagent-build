# Source:  https://github.com/bitbrain/godot-gamejam/blob/main/godot/scenes/game_settings_scene.gd
# Repo:    bitbrain/godot-gamejam (star 815) | License: MIT | Collected: 2026-10-31
# Commit:  159f2c47196a
extends Node2D

@onready var overlay := %FadeOverlay
@onready var return_button := %ReturnButton

func _ready():
	overlay.on_complete_fade_out.connect(_on_fade_overlay_on_complete_fade_out)
	return_button.pressed.connect(_on_return_button_pressed)
	
	overlay.visible = true
	return_button.grab_focus()

func _on_fade_overlay_on_complete_fade_out():
	get_tree().change_scene_to_file("res://scenes/main_menu_scene.tscn")

func _on_return_button_pressed():
	overlay.fade_out()
