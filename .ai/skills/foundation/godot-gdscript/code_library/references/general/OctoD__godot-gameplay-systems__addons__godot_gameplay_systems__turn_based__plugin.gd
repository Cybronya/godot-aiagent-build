# Source:  https://github.com/OctoD/godot-gameplay-systems/blob/main/addons/godot_gameplay_systems/turn_based/plugin.gd
# Repo:    OctoD/godot-gameplay-systems (star 746) | License: MIT | Collected: 2026-10-31
# Commit:  9349931cc7a5
extends EditorPlugin


const TurnBasedGameScript = preload("./nodes/TurnBasedGame.gd")
const TurnSubscriberScript = preload("./nodes/TurnSubscriber.gd")


func _enter_tree() -> void:
	add_autoload_singleton("TurnManager", "./autoloads/turn_manager.gd")
	add_custom_type("TurnBasedGame", "Node", TurnBasedGameScript, null)
	add_custom_type("TurnSubscriber", "Node", TurnSubscriberScript, null)


func _exit_tree() -> void:
	remove_autoload_singleton("TurnManager")
	remove_custom_type("TurnBasedGame")
	remove_custom_type("TurnSubscriber")

