# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/audio/rhythm_game/game_state/play_stats.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
class_name PlayStats
extends Resource

@export var mean_hit_error: float = 0.0:
	set(value):
		if mean_hit_error != value:
			mean_hit_error = value
			emit_changed()

@export var perfect_count: int = 0:
	set(value):
		if perfect_count != value:
			perfect_count = value
			emit_changed()

@export var good_count: int = 0:
	set(value):
		if good_count != value:
			good_count = value
			emit_changed()

@export var miss_count: int = 0:
	set(value):
		if miss_count != value:
			miss_count = value
			emit_changed()
