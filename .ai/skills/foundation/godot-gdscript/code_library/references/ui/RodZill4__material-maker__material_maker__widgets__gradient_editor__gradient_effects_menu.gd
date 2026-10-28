# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/widgets/gradient_editor/gradient_effects_menu.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  master
extends PanelContainer


func add_effects_button(text:String, callable: Callable) -> Button:
	var button := Button.new()
	button.text = text
	button.pressed.connect(callable)
	$VBox.add_child(button)
	return button
