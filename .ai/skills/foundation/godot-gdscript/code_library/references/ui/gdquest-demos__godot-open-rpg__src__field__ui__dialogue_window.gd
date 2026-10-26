# Source:  https://github.com/gdquest-demos/godot-open-rpg/blob/main/src/field/ui/dialogue_window.gd
# Repo:    gdquest-demos/godot-open-rpg (star 3028) | License: MIT | Collected: 2026-10-26
# Commit:  main
extends DialogicNode_StyleLayer


func _ready():
	super._ready()
	
	Dialogic.timeline_started.connect(func(): show())
	Dialogic.timeline_ended.connect(func(): hide())
	hide()
