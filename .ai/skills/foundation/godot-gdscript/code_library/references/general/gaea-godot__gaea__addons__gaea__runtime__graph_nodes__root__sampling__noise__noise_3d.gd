# Source:  https://github.com/gaea-godot/gaea/blob/2.0/addons/gaea/runtime/graph_nodes/root/sampling/noise/noise_3d.gd
# Repo:    gaea-godot/gaea (star 1663) | License: MIT | Collected: 2026-10-28
# Commit:  79461f6491e7
@tool
class_name GaeaNodeNoise3D
extends GaeaNodeNoise


func _get_title() -> String:
	return "Noise3D"


func _get_noise_value(cell: Vector3i, noise: FastNoiseLite) -> float:
	return noise.get_noise_3d(cell.x, cell.y, cell.z)
