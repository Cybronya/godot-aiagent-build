# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/platformer/gui/coins_counter.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
class_name CoinsCounter
extends Panel

var _coins_collected: int = 0

@onready var _coins_label := $Label as Label


func _ready() -> void:
	_coins_label.set_text(str(_coins_collected))
	($AnimatedSprite2D as AnimatedSprite2D).play()


func collect_coin() -> void:
	_coins_collected += 1
	_coins_label.set_text(str(_coins_collected))
