extends Node2D
## Runtime fixture: runtime script error with no more specific classification.


func _ready() -> void:
	var divisor := 0
	print(10 / divisor)
