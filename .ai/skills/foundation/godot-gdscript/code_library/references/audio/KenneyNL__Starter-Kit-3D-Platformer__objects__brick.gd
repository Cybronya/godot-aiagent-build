# Source:  https://github.com/KenneyNL/Starter-Kit-3D-Platformer/blob/main/objects/brick.gd
# Repo:    KenneyNL/Starter-Kit-3D-Platformer (star 1264) | License: MIT | Collected: 2026-10-29
# Commit:  3fa8a04b1c01
extends StaticBody3D

@onready var bottom_detector = $BottomDetector
@onready var mesh = $Mesh
@onready var particles = $Particles

var exploded = false

func _ready():
	bottom_detector.body_entered.connect(_on_bottom_hit)

func _on_bottom_hit(body: Node3D) -> void:
	if body.is_in_group("player"):
		explode()

func explode():
	
	if exploded:
		return
		
	exploded = true
	
	Audio.play("res://sounds/break.ogg") # Play sound
	
	particles.restart()
	
	mesh.hide()
	$CollisionShape3D.disabled = true
	bottom_detector.set_deferred("monitoring", false)
	
	await get_tree().create_timer(1).timeout
	queue_free()
