# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/escoria-dialog-simple/states/dialog_idle.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
extends State


func enter():
	escoria.logger.trace(self, "Dialog State Machine: Entered 'idle'.")
