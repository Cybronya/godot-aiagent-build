# Source:  https://github.com/gdquest-demos/godot-open-rpg/blob/main/overworld/maps/opening_cutscene.gd
# Repo:    gdquest-demos/godot-open-rpg (star 3028) | License: MIT | Collected: 2026-10-26
# Commit:  main
extends Cutscene

@export var timeline: DialogicTimeline


func _execute() -> void:
	$Background/ColorRect.show()
	
	Dialogic.start_timeline(timeline)
	await Dialogic.timeline_ended
	
	await Transition.cover()
	$Background/ColorRect.hide()
	
	Music.play(load("res://assets/music/Apple Cider.mp3"))
	await Transition.clear(2.0)
	
	queue_free.call_deferred()
