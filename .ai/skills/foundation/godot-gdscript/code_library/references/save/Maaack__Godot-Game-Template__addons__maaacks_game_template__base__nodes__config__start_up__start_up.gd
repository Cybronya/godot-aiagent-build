# Source:  https://github.com/Maaack/Godot-Game-Template/blob/main/addons/maaacks_game_template/base/nodes/config/start_up/start_up.gd
# Repo:    Maaack/Godot-Game-Template (star 1709) | License: MIT | Collected: 2026-10-26
# Commit:  5cc611f7dfcd
## This node sets up the application and should be one of the first things run.
## It can either be included in the Project's main scene, or set as an autoload.
extends Node

func _ready() -> void:
	AppSettings.set_from_config_and_window(get_window())
