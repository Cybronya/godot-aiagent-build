# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/interface/menus/shop/popups/AmountLabel.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends Label

var _max_value

func initialize(value, max_value):
	_max_value = max_value
	update_text(value)

func update_text(value):
	text = "%s/%s" % [value, _max_value]

func _on_HSlider_value_changed(value):
	update_text(value)
