# Source:  https://github.com/crystal-bit/godot-game-template/blob/main/addons/ggt-core/config.gd
# Repo:    crystal-bit/godot-game-template (star 993) | License: MIT | Collected: 2026-10-29
# Commit:  e9dc8926d156
extends Resource

@export_group("Transitions")
@export var pause_scenes_on_transitions = true
@export var prevent_input_on_transitions = true
@export_range(0.0, 3000.0, 50.0) var transitions_minimum_duration_ms = 300.0

@export_group("Scenes")
@export_range(0, 10, 1) var max_history_length = 5
