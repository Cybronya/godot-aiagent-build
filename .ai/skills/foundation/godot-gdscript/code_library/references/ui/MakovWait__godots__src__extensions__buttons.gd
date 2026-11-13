# Source:  https://github.com/MakovWait/godots/blob/main/src/extensions/buttons.gd
# Repo:    MakovWait/godots (star 816) | License: MIT | Collected: 2026-10-31
# Commit:  8e4eb2baa050
class_name buttons

static func simple(text: String, icon: Texture2D, on_pressed: Callable) -> Button:
	var btn := Button.new()
	btn.icon = icon
	btn.text = text
	btn.pressed.connect(on_pressed)
	return btn
