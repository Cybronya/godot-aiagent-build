# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/finite_state_machine/player/states/debug/state_name_displayer.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends Label

var start_position := Vector2()

func _ready() -> void:
	start_position = position


func _physics_process(_delta: float) -> void:
	position = $"../BodyPivot".position + start_position


func _on_StateMachine_state_changed(current_state: Node) -> void:
	text = String(current_state.name)
