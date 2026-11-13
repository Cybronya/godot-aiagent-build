# Source:  https://github.com/gdquest-demos/godot-platformer-2d/blob/master/game/src/Player/States/Stagger.gd
# Repo:    gdquest-demos/godot-platformer-2d (star 815) | License: MIT | Collected: 2026-10-31
# Commit:  0ea6cb6056dc
tool
extends State


onready var duration: Timer = $Duration


func _get_configuration_warning() -> String:
	return "" if $Duration else "%s requires a Timer child named Duration" % name


func enter(_msg: Dictionary = {}):
	duration.start()
	yield(duration, "timeout")
	_state_machine.transition_to("Move/Idle")
