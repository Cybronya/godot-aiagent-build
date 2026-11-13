# Source:  https://github.com/gdquest-demos/godot-platformer-2d/blob/master/game/src/AI/EnemyCharger.gd
# Repo:    gdquest-demos/godot-platformer-2d (star 815) | License: MIT | Collected: 2026-10-31
# Commit:  0ea6cb6056dc
extends KinematicBody2D

onready var target_detector: Area2D = $TargetDetector