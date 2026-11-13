# Source:  https://github.com/bukkbeek/GodotPixelRenderer/blob/main/PixelRenderer/data/scripts/github_button.gd
# Repo:    bukkbeek/GodotPixelRenderer (star 802) | License: MIT | Collected: 2026-10-31
# Commit:  078f2078fb9e
extends Button

func _ready():
	pressed.connect(_on_pressed)

func _on_pressed():
	OS.shell_open("https://github.com/bukkbeek/GodotPixelRenderer")
