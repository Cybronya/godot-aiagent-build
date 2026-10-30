extends Window


func _ready():
	pass


func _on_close_requested() -> void:
	queue_free()
