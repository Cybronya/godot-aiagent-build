# Source:  https://github.com/Ark2000/PankuConsole/blob/master/addons/panku_console/modules/interactive_shell/mini_repl_2.gd
# Repo:    Ark2000/PankuConsole (star 1436) | License: MIT | Collected: 2026-10-28
# Commit:  master
extends VBoxContainer

var console:PankuConsole

@export var input_area:Node
@export var repl:Node

func _ready() -> void:
	repl.output_result.connect(console.notify)
	repl.output_error.connect(console.notify)
	input_area.submitted.connect(
		func(_s): hide()
	)
