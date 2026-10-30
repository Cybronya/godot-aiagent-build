# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/escoria-ui-keyboard-9verbs/tooltip/tooltip_action_target.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
extends ESCTooltip

@export var prepositions = {"use": "with", "give": "to"}

func update_tooltip_text():
	text = "[center]"
	text += "[color=#" + color.to_html(false) + "]"
	if !current_action.is_empty():
		text += current_action + "\t"
	text += current_target

	if waiting_for_target2 and current_target2.is_empty():
		current_prep = prepositions.get(current_action, current_prep)
		text += "\t" + current_prep + " \t"

	if !current_target2.is_empty():
		text += "\t" + current_prep + " \t" + current_target2

	text += "[/color]"
	text += "[/center]"

#	push_align(RichTextLabel.ALIGN_CENTER)
#	if !current_action.empty():
#		add_text(current_action + "\t")
#
#	add_text(current_target)
#
#	if waiting_for_target2 and current_target2.empty():
#		add_text("\t" + current_prep)
#
#	if !current_target2.empty():
#		add_text("\t" + current_prep + "\t" + current_target2)
#
#	pop()
