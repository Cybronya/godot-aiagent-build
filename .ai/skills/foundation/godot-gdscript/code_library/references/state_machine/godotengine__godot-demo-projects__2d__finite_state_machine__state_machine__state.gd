# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/finite_state_machine/state_machine/state.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends Node
# Base interface for all states: it doesn't do anything by itself,
# but forces us to pass the right arguments to the methods below
# and makes sure every State object had all of these methods.

@warning_ignore("unused_signal")
signal finished(next_state_name: StringName)

# Initialize the state. E.g. change the animation.
func enter() -> void:
	pass


# Clean up the state. Reinitialize values like a timer.
func exit() -> void:
	pass


func handle_input(_input_event: InputEvent) -> void:
	pass


func update(_delta: float) -> void:
	pass


func _on_animation_finished(_anim_name: String) -> void:
	pass
