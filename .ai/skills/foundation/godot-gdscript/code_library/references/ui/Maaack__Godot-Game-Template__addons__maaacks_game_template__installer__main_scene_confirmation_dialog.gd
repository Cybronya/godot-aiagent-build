# Source:  https://github.com/Maaack/Godot-Game-Template/blob/main/addons/maaacks_game_template/installer/main_scene_confirmation_dialog.gd
# Repo:    Maaack/Godot-Game-Template (star 1709) | License: MIT | Collected: 2026-10-26
# Commit:  5cc611f7dfcd
@tool
extends ConfirmationDialog

const MAIN_SCENE_UPDATE_TEXT = "Would you like to update the project's main scene?\n\nCurrent:\n%s\n\nNew:\n%s\n"

func set_main_scene_text(new_scene_path):
	var current_scene_path : String = ProjectSettings.get_setting("application/run/main_scene", "")
	dialog_text = MAIN_SCENE_UPDATE_TEXT % [current_scene_path, new_scene_path]
