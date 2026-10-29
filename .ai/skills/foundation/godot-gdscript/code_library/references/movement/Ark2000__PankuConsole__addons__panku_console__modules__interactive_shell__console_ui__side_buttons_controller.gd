# Source:  https://github.com/Ark2000/PankuConsole/blob/master/addons/panku_console/modules/interactive_shell/console_ui/side_buttons_controller.gd
# Repo:    Ark2000/PankuConsole (star 1436) | License: MIT | Collected: 2026-10-28
# Commit:  863324dfb752
extends PankuButton

func _ready():
	super._ready()
	set_meta("text", " Fold Menu")
	text = ""
	var img = Image.new()
	img.copy_from(icon.get_image())
	img.flip_x()
	var unfold_icon = ImageTexture.create_from_image(img)
	var fold_icon = icon
	
	icon = unfold_icon
	
	button.toggle_mode = true
	button.toggled.connect(
		func(button_pressed:bool):
			if button_pressed:
				icon = fold_icon
			else:
				icon = unfold_icon
				
			for node in get_parent().get_children():
				if not (node is PankuButton):
					continue
				if button_pressed:
					node.text = node.get_meta("text")
				else:
					node.text = ""
	)
