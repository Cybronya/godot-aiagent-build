# Source:  https://github.com/KenneyNL/Starter-Kit-3D-Platformer/blob/main/scripts/main.gd
# Repo:    KenneyNL/Starter-Kit-3D-Platformer (star 1264) | License: MIT | Collected: 2026-10-29
# Commit:  3fa8a04b1c01
extends Node3D


func _ready() -> void:
	if RenderingServer.get_current_rendering_method() == "gl_compatibility":
		# Reduce background and sun brightness when using the Compatibility renderer;
		# this tries to roughly match the appearance of Forward+.
		# This compensates for the different color space and light rendering for lights with shadows enabled.
		$Sun.light_energy = 0.24
		$Sun.shadow_opacity = 0.85
		$Environment.environment.background_energy_multiplier = 0.25
