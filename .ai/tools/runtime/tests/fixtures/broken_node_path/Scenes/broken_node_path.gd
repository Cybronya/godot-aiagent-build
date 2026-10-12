extends CharacterBody2D
## Runtime fixture: hardcoded node path typo (Helth -> Health).


func _ready() -> void:
	var health := get_node("Helth")
	print("health node: ", health.name)
