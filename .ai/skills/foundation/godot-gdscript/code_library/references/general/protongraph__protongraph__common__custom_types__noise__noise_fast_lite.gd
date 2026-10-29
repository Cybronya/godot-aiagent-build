# Source:  https://github.com/protongraph/protongraph/blob/main/common/custom_types/noise/noise_fast_lite.gd
# Repo:    protongraph/protongraph (star 1749) | License: MIT | Collected: 2026-10-29
# Commit:  1e2411a29464
extends ProtonNoise
class_name ProtonNoiseFast


var _fast_noise: FastNoiseLite


func _init():
	_fast_noise = FastNoiseLite.new()


func get_noise_2d(x: float, y: float) -> float:
	return apply_curve(_fast_noise.get_noise_2d(x, y))


func get_noise_2dv(v: Vector2) -> float:
	return apply_curve(_fast_noise.get_noise_2dv(v))


func get_noise_3d(x: float, y: float, z: float) -> float:
	return apply_curve(_fast_noise.get_noise_3d(x, y, z))


func get_noise_3dv(v: Vector3) -> float:
	return apply_curve(_fast_noise.get_noise_3dv(v))


func get_noise_object() -> FastNoiseLite:
	return _fast_noise
