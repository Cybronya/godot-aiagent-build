# Source:  https://github.com/gdquest-demos/godot-platformer-2d/blob/master/game/src/AI/SwarmerEnemy.gd
# Repo:    gdquest-demos/godot-platformer-2d (star 815) | License: MIT | Collected: 2026-10-31
# Commit:  0ea6cb6056dc
extends Node2D
# Basic controller for a node2D - its behavior checks the heatmap and points
# its directional vector towards the less heat (the 'goal')


onready var behavior: FollowHeatmapBehavior2D = $BehaviorController2D/FollowHeatmapBehavior2D

var _motion: SteeringMotion2D = SteeringMotion2D.new()
var speed: float = 250


func _physics_process(delta: float) -> void:
	var desired_velocity := behavior.calculate_steering(_motion)
	position += _motion.velocity.normalized() * speed * delta
