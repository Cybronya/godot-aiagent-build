# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/finite_state_machine/player/player_state.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends "res://state_machine/state.gd"

const PLAYER_STATE: Dictionary[StringName, StringName]= {
	&"previous": &"previous",
	&"jump": &"jump",
	&"idle": &"idle",
	&"move": &"move",
	&"stagger": &"stagger",
	&"attack": &"attack",
	&"die": &"die",
	&"dead": &"dead",
	&"walk": &"walk",
}
