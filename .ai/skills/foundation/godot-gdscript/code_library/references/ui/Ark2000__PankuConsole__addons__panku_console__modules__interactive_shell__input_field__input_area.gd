# Source:  https://github.com/Ark2000/PankuConsole/blob/master/addons/panku_console/modules/interactive_shell/input_field/input_area.gd
# Repo:    Ark2000/PankuConsole (star 1436) | License: MIT | Collected: 2026-10-28
# Commit:  863324dfb752
extends HBoxContainer

@onready var console:PankuConsole = get_node(PankuConsole.SingletonPath)

signal submitted(exp:String)
signal update_hints(exp:String)
signal next_hint()
signal prev_hint()
signal navigate_histories(histories:Array, cur:int)

@export var input:LineEdit
@export var btn:PankuButton

func _ready():
	input.text_submitted.connect(
		func(s):
			submitted.emit(s)
	)
	input.text_changed.connect(
		func(s):
			update_hints.emit(s)
	)
	btn.pressed.connect(
		func():
			submitted.emit(input.text)
			input.on_text_submitted(input.text)
	)

	#get focus automatically.
	visibility_changed.connect(
		func():
			if is_visible_in_tree():
				input.call_deferred("grab_focus")
	)
