# Source:  https://github.com/gaea-godot/gaea/blob/2.0/addons/gaea/runtime/graph_nodes/root/sampling/noise/noise_2d.gd
# Repo:    gaea-godot/gaea (star 1663) | License: MIT | Collected: 2026-10-28
# Commit:  79461f6491e7
@tool
class_name GaeaNodeNoise2D
extends GaeaNodeNoise


func _get_title() -> String:
	return "Noise2D"


func _get_description() -> String:
	return super() + "\n[b]Ignores the z axis.[/b]"


func _get_noise_value(cell: Vector3i, noise: FastNoiseLite) -> float:
	return noise.get_noise_2d(cell.x, cell.y)
