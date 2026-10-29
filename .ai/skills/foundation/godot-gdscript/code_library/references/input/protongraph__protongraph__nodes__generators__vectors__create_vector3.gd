# Source:  https://github.com/protongraph/protongraph/blob/main/nodes/generators/vectors/create_vector3.gd
# Repo:    protongraph/protongraph (star 1749) | License: MIT | Collected: 2026-10-29
# Commit:  1e2411a29464
extends ProtonNode


func _init() -> void:
	type_id = "create_vector3"
	title = "Create Vector3"
	category = "Generators/Vectors"
	description = "Create a Vector3"

	create_input("in", "", DataType.VECTOR3)
	create_output("out", "Vector3", DataType.VECTOR3)


func _generate_outputs() -> void:
	set_output("out", get_input_single("in", Vector3.ZERO))
