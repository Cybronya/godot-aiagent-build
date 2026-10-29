# Source:  https://github.com/godot-fun/godot-start/blob/main/scene/demo08_path/script/tile.gd
# Repo:    godot-fun/godot-start (star 1106) | License: MIT | Collected: 2026-10-29
# Commit:  115fc06e42f3
extends Node2D


@onready var nav_2d : NavigationAgent2D = $Player/NavigationAgent2D
@onready var player : CharacterBody2D = $Player
@onready var line2D : Line2D = $Line2D

var speed = 250

func _physics_process(delta):
	if nav_2d.is_navigation_finished() || nav_2d.get_final_position() == Vector2.ZERO:
		return
	
	var next_location = nav_2d.get_next_path_position()
	var direction = player.global_position.direction_to(next_location)
	
	nav_2d.set_velocity(direction * speed)
	player.velocity = direction * speed
	player.move_and_slide()

func _unhandled_input(event: InputEvent) -> void:
	if not event is InputEventMouseButton:
		return
		
	var playerPosition = player.get_global_position()
	var mousePosition = event.get_global_position()
	nav_2d.set_target_position(mousePosition)
	nav_2d.get_next_path_position()
	var navPath = nav_2d.get_current_navigation_path()
	line2D.points = navPath

