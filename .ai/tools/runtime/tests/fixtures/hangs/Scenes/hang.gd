extends Node2D
## Runtime fixture: never returns from _ready, so the process must be killed by timeout.


func _ready() -> void:
	while true:
		pass
