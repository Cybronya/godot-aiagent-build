# Source:  https://github.com/ceceppa/anima/blob/main/tests/test.gd
# Repo:    ceceppa/anima (star 769) | License: MIT | Collected: 2026-10-31
# Commit:  f4a454ebd4d5
@tool
extends Control

@export var debug_animation: bool = false:
	set(value):
		debug_animation = value

		if not value or not %Label2:
			return

		_animate()

func _animate():
	pass

func _on_button_pressed():
	_animate()
