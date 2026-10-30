# Source:  https://github.com/KenneyNL/Starter-Kit-FPS/blob/main/objects/impact.gd
# Repo:    KenneyNL/Starter-Kit-FPS (star 1010) | License: MIT | Collected: 2026-10-29
# Commit:  185fd2326d74
extends AnimatedSprite3D

# Remove this impact effect after the animation has completed


func _on_animation_finished():
	queue_free()
