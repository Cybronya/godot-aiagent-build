# Source:  https://github.com/gdquest-demos/godot-open-rpg/blob/main/overworld/maps/forest/game_end_trigger.gd
# Repo:    gdquest-demos/godot-open-rpg (star 3028) | License: MIT | Collected: 2026-10-26
# Commit:  d59f2f71bc04
@tool
extends Trigger

@export var timeline: DialogicTimeline
@export var ghost_animation_player: AnimationPlayer

var gamepiece: Gamepiece

@onready var _timer: = $Timer as Timer


func _execute() -> void:
	gamepiece.move_to(Gameboard.cell_to_pixel(Vector2i(53, 30)))
	await gamepiece.arrived
	
	_timer.start()
	await _timer.timeout
	
	Dialogic.start_timeline(timeline)
	await Dialogic.timeline_ended
	
	_timer.start()
	await _timer.timeout
	
	# Note that the lunge animation also includes a screen transition and some text.
	ghost_animation_player.play("lunge")
	await ghost_animation_player.animation_finished
	
	# Lock input by waiting for a signal that won't trigger.
	await ready


func _on_area_entered(area: Area2D) -> void:
	if not Engine.is_editor_hint():
		gamepiece = area.owner as Gamepiece
	super._on_area_entered(area)
