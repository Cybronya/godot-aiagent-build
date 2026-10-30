extends Button


# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	connect("toggled", Callable(self, "_on_toggle"))


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _on_toggle(toggled_on: bool):
	if toggled_on:
		text = "★"
	else:
		text = "☆"
