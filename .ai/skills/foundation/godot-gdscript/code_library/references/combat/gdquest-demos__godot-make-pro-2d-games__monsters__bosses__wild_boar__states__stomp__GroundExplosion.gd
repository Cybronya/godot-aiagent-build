# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/monsters/bosses/wild_boar/states/stomp/GroundExplosion.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends "res://actors/DamageSource.gd"

func _ready():
	$AnimationPlayer.play('explode')

func _physics_process(delta):
	position = position
