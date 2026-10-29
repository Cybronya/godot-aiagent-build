# Source:  https://github.com/Ark2000/PankuConsole/blob/master/addons/panku_console/modules/interactive_shell/hints_list/hint.gd
# Repo:    Ark2000/PankuConsole (star 1436) | License: MIT | Collected: 2026-10-28
# Commit:  863324dfb752
extends PanelContainer

@export var label:RichTextLabel
@export var bg2:ColorRect

func set_highlight(b:bool):
	bg2.scale.x = 1.0 if b else 0.0
	bg2.visible = b
