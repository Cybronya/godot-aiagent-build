# Source:  https://github.com/pablogila/TileMapDual/blob/main/examples/rotating_light.gd
# Repo:    pablogila/TileMapDual (star 1292) | License: MIT | Collected: 2026-10-29
# Commit:  b4dc77500354
extends DirectionalLight2D


func _process(delta: float) -> void:
	rotation += delta # intentional indefinitely increasing floating point value
