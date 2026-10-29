# Source:  https://github.com/protongraph/protongraph/blob/main/nodes/generators/vectors/create_vector2.gd
# Repo:    protongraph/protongraph (star 1749) | License: MIT | Collected: 2026-10-29
# Commit:  1e2411a29464
extends ProtonNode


func _init() -> void:
	type_id = "create_vector2"
	title = "Create Vector2"
	category = "Generators/Vectors"
	description = "Create a Vector2"

	create_input("in", "", DataType.VECTOR2)
	create_output("out", "Vector2", DataType.VECTOR2)


func _generate_outputs() -> void:
	set_output("out", get_input_single("in", Vector2.ZERO))
