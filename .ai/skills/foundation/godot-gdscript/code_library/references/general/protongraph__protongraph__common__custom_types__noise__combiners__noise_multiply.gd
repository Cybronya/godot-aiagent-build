# Source:  https://github.com/protongraph/protongraph/blob/main/common/custom_types/noise/combiners/noise_multiply.gd
# Repo:    protongraph/protongraph (star 1749) | License: MIT | Collected: 2026-10-29
# Commit:  1e2411a29464
class_name NoiseMultiply
extends NoiseCombiner


func _combine_noise(x: float, y: float, z = null) -> float:
	if z == null:
		return noise_a.get_noise_2d(x, y) * noise_b.get_noise_2d(x, y)
	else:
		return noise_a.get_noise_3d(x, y, z) * noise_b.get_noise_3d(x, y, z)
