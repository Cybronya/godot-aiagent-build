# Source:  https://github.com/OctoD/godot-gameplay-systems/blob/main/addons/godot_gameplay_systems/turn_based/autoloads/turn_manager.gd
# Repo:    OctoD/godot-gameplay-systems (star 746) | License: MIT | Collected: 2026-10-31
# Commit:  9349931cc7a5
extends Node


## The [TurnBasedGame] node.
var turn_based_game: TurnBasedGame = null


## Called when the node enters the scene tree for the first time.
func _ready() -> void:
	get_turn_based_game()


## Ends the current turn sequence.
func end_turn_sequence() -> void:
	if get_turn_based_game():
		get_turn_based_game().end_turn_sequence()


## Gets the [TurnBasedGame] node.
func get_turn_based_game() -> TurnBasedGame:
	if turn_based_game:
		return turn_based_game

	for child in get_tree().get_nodes_in_group("ggs.turnbased"):
		if child is TurnBasedGame:
			turn_based_game = child
			return turn_based_game

	return null


## Starts a new turn sequence (aka, starts the turn based mode).
func start_turn_sequence() -> void:
	if get_turn_based_game():
		get_turn_based_game().start_turn_sequence()

