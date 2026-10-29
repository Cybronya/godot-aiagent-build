# Source:  https://github.com/protongraph/protongraph/blob/main/common/custom_types/noise/combiners/noise_overlay.gd
# Repo:    protongraph/protongraph (star 1749) | License: MIT | Collected: 2026-10-29
# Commit:  1e2411a29464
class_name NoiseOverlay
extends NoiseCombiner


func _combine_noise(x: float, y: float, z = null) -> float:
	var a
	var b
	if z == null:
		a = noise_a.get_noise_2d(x, y)
		b = noise_b.get_noise_2d(x, y)
	else:
		a = noise_a.get_noise_3d(x, y, z)
		b = noise_b.get_noise_3d(x, y, z)

	if a < 0.5:
		return 2 * a * b

	return 1 - 2 * (1 - a) * (1 - b)
