# Source:  https://github.com/KenneyNL/Starter-Kit-FPS/blob/main/scripts/hud.gd
# Repo:    KenneyNL/Starter-Kit-FPS (star 1010) | License: MIT | Collected: 2026-10-29
# Commit:  185fd2326d74
extends CanvasLayer


func _on_health_updated(health):
	$Health.text = str(health) + "%"
