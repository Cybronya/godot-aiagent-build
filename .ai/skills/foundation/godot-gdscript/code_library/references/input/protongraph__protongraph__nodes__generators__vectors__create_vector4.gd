# Source:  https://github.com/protongraph/protongraph/blob/main/nodes/generators/vectors/create_vector4.gd
# Repo:    protongraph/protongraph (star 1749) | License: MIT | Collected: 2026-10-29
# Commit:  1e2411a29464
extends ProtonNode


func _init() -> void:
	type_id = "create_vector4"
	title = "Create Vector4"
	category = "Generators/Vectors"
	description = "Create a Vector4"

	create_input("in", "", DataType.VECTOR4)
	create_output("out", "Vector4", DataType.VECTOR4)


func _generate_outputs() -> void:
	set_output("out", get_input_single("in", Vector4.ZERO))
