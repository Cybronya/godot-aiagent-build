# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/3d/voxel/world/environment.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends WorldEnvironment
# This script controls fog based on the VoxelWorld's effective render distance.

@onready var voxel_world: Node = $"../VoxelWorld"

func _process(delta: float) -> void:
	environment.fog_enabled = Settings.fog_enabled

	var target_distance := clampi(voxel_world.effective_render_distance, 2, voxel_world.render_distance - 1) * Chunk.CHUNK_SIZE
	var rate := delta * 4
	Settings.fog_distance = move_toward(Settings.fog_distance, target_distance, rate)
	environment.fog_density = 0.5 / Settings.fog_distance
