# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/role_playing_game/combat/combatants/combatant.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
class_name Combatant
extends Node

signal turn_finished

@export var damage := 1
@export var defense := 1

var active: bool = false: set = set_active

@onready var animation_playback: AnimationNodeStateMachinePlayback = $Sprite2D/AnimationTree.get(&"parameters/playback")

func set_active(value: bool) -> void:
	active = value
	set_process(value)
	set_process_input(value)

	if not active:
		return
	if $Health.armor >= $Health.base_armor + defense:
		$Health.armor = $Health.base_armor


func attack(target: Combatant) -> void:
	target.take_damage(damage)
	turn_finished.emit()


func defend() -> void:
	$Health.armor += defense
	turn_finished.emit()


func flee() -> void:
	turn_finished.emit()


func take_damage(damage_to_take: float) -> void:
	$Health.take_damage(damage_to_take)
	animation_playback.start(&"take_damage")
