# Source:  https://github.com/gdquest-demos/godot-platformer-2d/blob/master/game/src/AI/EnemyPassivePatrol.gd
# Repo:    gdquest-demos/godot-platformer-2d (star 815) | License: MIT | Collected: 2026-10-31
# Commit:  0ea6cb6056dc
extends KinematicBody2D
# A passive enemy; simply patrols side to side and bumps into the player for damage.
# Can be hooked onto, and will be damaged.


onready var collider: CollisionShape2D = $CollisionShape2D setget ,get_collider
onready var hook_target: Area2D = $HookTarget
onready var body: Node2D = $Body
onready var hitbox: Area2D = $Hitbox

export var can_be_hooked_while_stunned := false
export var move_speed := 200
export var direction := -1

func _ready() -> void:
	if can_be_hooked_while_stunned:
		hook_target.is_one_shot = false


func get_collider() -> CollisionShape2D:
	return collider
