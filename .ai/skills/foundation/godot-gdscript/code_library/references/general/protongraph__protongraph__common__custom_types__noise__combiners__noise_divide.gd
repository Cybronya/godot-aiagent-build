# Source:  https://github.com/protongraph/protongraph/blob/main/common/custom_types/noise/combiners/noise_divide.gd
# Repo:    protongraph/protongraph (star 1749) | License: MIT | Collected: 2026-10-29
# Commit:  1e2411a29464
class_name NoiseDivide
extends NoiseCombiner


func _combine_noise(x: float, y: float, z = null) -> float:
	if z == null:
		return clamp(noise_a.get_noise_2d(x, y) / max(0.001, noise_a.get_noise_2d(x, y)), -1.0, 1.0)
	else:
		return clamp(noise_a.get_noise_3d(x, y, z) / max(0.001, noise_b.get_noise_3d(x, y, z)), -1.0, 1.0)
