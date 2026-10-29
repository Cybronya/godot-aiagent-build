# Source:  https://github.com/derkork/godot-statecharts/blob/main/godot_state_charts_examples/automatic_transitions/stamina_bar.gd
# Repo:    derkork/godot-statecharts (star 1623) | License: MIT | Collected: 2026-10-26
# Commit:  76d226a3efac
extends ProgressBar


@onready var the_frog:Node = %TheFrog


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(_delta:float) -> void:
	value = the_frog.stamina
