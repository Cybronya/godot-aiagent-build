# Source:  https://github.com/Miziziziz/MizGodotTools/blob/main/example_scenes/npc_vision_example/npc_vision_example.gd
# Repo:    Miziziziz/MizGodotTools (star 987) | License: MIT | Collected: 2026-10-29
# Commit:  cb548f9035a3
extends Node2D


@onready var vision_manager : VisionManager = $NPC/VisionManager
@onready var target_sprite_2d = $MovementBase/VisionTarget/Sprite2D
@onready var vision_target = $MovementBase/VisionTarget

func _process(_delta):
	target_sprite_2d.modulate = Color.RED
	if vision_manager.can_see_point(vision_target.global_position):
		target_sprite_2d.modulate = Color.GREEN
