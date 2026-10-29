# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/interface/menus/shop/popups/HSlider.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends HSlider

func initialize(current, maximum):
	max_value = maximum
	value = current
