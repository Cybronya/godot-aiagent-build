# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/role_playing_game/combat/turn_queue.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends Node

signal active_combatant_changed(active_combatant: Combatant)

@export var combatants_list: Node

var queue: Array[Node] = []: set = set_queue
var active_combatant: Combatant = null: set = _set_active_combatant

func initialize() -> void:
	set_queue(combatants_list.get_children())
	play_turn()


func play_turn() -> void:
	await active_combatant.turn_finished
	get_next_in_queue()
	play_turn()


func get_next_in_queue() -> Node:
	var current_combatant: Node = queue.pop_front()
	current_combatant.active = false
	queue.append(current_combatant)
	active_combatant = queue[0]
	return active_combatant


func remove(combatant: Combatant) -> void:
	var new_queue := []
	for n in queue:
		new_queue.append(n)
	new_queue.remove_at(new_queue.find(combatant))
	combatant.queue_free()
	queue = new_queue


func set_queue(new_queue: Array[Node]) -> void:
	queue.clear()
	for node in new_queue:
		if node is not Combatant:
			continue
		queue.append(node)
		node.active = false
	if queue.size() > 0:
		active_combatant = queue[0]


func _set_active_combatant(new_combatant: Combatant) -> void:
	active_combatant = new_combatant
	active_combatant.active = true
	active_combatant_changed.emit(active_combatant)
