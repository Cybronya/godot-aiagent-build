# Source:  https://github.com/bitbrain/godot-gamejam/blob/main/godot/scenes/node_example.gd
# Repo:    bitbrain/godot-gamejam (star 815) | License: MIT | Collected: 2026-10-31
# Commit:  159f2c47196a
extends Sprite2D

# specify in nodes to load data
# from save game for this node
func load_data(data:Dictionary) -> void:
	print(data.hello) 
	
# specify in nodes to save data
# of this node to the save game
func save_data() -> Dictionary:
	return {
		"hello": "Hello Godot!"
	}
	
func _process(delta):
	if Input.is_action_pressed("ui_right"):
		position.x += 100 * delta
	if Input.is_action_pressed("ui_left"):
		position.x -= 100 * delta
	if Input.is_action_pressed("ui_up"):
			position.y -= 100 * delta
	if Input.is_action_pressed("ui_down"):
		position.y += 100 * delta
