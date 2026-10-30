# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/game/rooms/room17/r_17_laptop_type.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
extends Control



@onready var say_command: SayCommand = SayCommand.new()
@onready var acceptinput_command: AcceptInputCommand = AcceptInputCommand.new()



func _ready():
	acceptinput_command.run(["NONE"])


func _on_cancel_button_pressed():
	acceptinput_command.run(["ALL"])
	escoria.current_state = escoria.GameState.DEFAULT
	queue_free()

func _on_ok_button_pressed():
	var text = $Panel/LineEdit.text
	queue_free()

	say_command.run(
		[
			"player",
			$Panel/LineEdit.text,
			"floating",
			""
		]
	)
	acceptinput_command.run(["ALL"])
	escoria.current_state = escoria.GameState.DEFAULT
