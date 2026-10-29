# Source:  https://github.com/gdquest-demos/godot-open-rpg/blob/main/src/field/cutscenes/templates/conversations/conversation_template.gd
# Repo:    gdquest-demos/godot-open-rpg (star 3028) | License: MIT | Collected: 2026-10-26
# Commit:  d59f2f71bc04
@tool

class_name InteractionTemplateConversation extends Interaction

@export var timeline: DialogicTimeline


func _execute() -> void:
	if timeline:
		Dialogic.start_timeline(timeline)
		
		Dialogic.signal_event.connect(_on_dialogic_signal_event)
		
		# Wait for the timeline to finish before ending the event.
		await Dialogic.timeline_ended
		
		Dialogic.signal_event.disconnect(_on_dialogic_signal_event)


func _on_dialogic_signal_event(_argument: String) -> void:
	pass
