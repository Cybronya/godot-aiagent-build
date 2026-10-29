# Source:  https://github.com/Ark2000/PankuConsole/blob/master/addons/panku_console/modules/snake/env.gd
# Repo:    Ark2000/PankuConsole (star 1436) | License: MIT | Collected: 2026-10-28
# Commit:  863324dfb752
var _module:PankuModule

const _HELP_execute = "Play Snake Game"
func play() -> void:
	_module.add_snake_window()

func leader_board() -> String:
	var content = ""
	content += "== Learder Board ==\n"
	content += str(_module.leader_board_arr)
	return content
