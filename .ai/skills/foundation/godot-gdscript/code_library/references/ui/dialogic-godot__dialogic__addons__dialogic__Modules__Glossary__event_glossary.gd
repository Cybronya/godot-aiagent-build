# Source:  https://github.com/dialogic-godot/dialogic/blob/main/addons/dialogic/Modules/Glossary/event_glossary.gd
# Repo:    dialogic-godot/dialogic (star 6121) | License: MIT | Collected: 2026-10-26
# Commit:  701b67bbe601
@tool
class_name DialogicGlossaryEvent
extends DialogicEvent

## Event that does nothing right now.



#region EXECUTE
################################################################################

func _execute() -> void:
	pass

#endregion


#region INITIALIZE
################################################################################

func _init() -> void:
	event_name = "Glossary"
	set_default_color('Color6')
	event_category = "Other"
	event_sorting_index = 0

#endregion


#region SAVING/LOADING
################################################################################
func get_shortcode() -> String:
	return "glossary"

func get_shortcode_parameters() -> Dictionary:
	return {
	}

#endregion


#region EDITOR REPRESENTATION
################################################################################

func build_event_editor() -> void:
	pass

#endregion
