# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/escoria-dialog-simple/states/dialog_finish.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
extends State


# Owning dialog player
var _dialog_player


func initialize(dialog_player) -> void:
	_dialog_player = dialog_player


func enter():
	escoria.logger.trace(self, "Dialog State Machine: Entered 'finish'.")


func update(_delta):
	escoria.logger.trace(self, "Dialog State Machine: 'finish' -> 'idle'")
	finished.emit("idle")
	_dialog_player.say_finished.emit()
