# Source:  https://github.com/Miziziziz/MizGodotTools/blob/main/effects/muzzle_flash/muzzle_flash.gd
# Repo:    Miziziziz/MizGodotTools (star 987) | License: MIT | Collected: 2026-10-29
# Commit:  cb548f9035a3
class_name MuzzleFlash extends Node2D

## Muzzle flash for guns, call flash() to use

@export var flash_time = 0.1
@onready var flash_timer = Timer.new()
@onready var flash_sprite = $FlashSprite

func _ready():
	hide()
	add_child(flash_timer)
	flash_timer.wait_time = flash_time
	flash_timer.timeout.connect(end_flash)

func flash():
	show()
	flash_timer.start()
	flash_sprite.frame = randi_range(0, flash_sprite.hframes * flash_sprite.vframes - 1)

func end_flash():
	hide()
