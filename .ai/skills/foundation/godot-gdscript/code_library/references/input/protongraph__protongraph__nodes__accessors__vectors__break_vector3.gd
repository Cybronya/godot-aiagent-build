# Source:  https://github.com/protongraph/protongraph/blob/main/nodes/accessors/vectors/break_vector3.gd
# Repo:    protongraph/protongraph (star 1749) | License: MIT | Collected: 2026-10-29
# Commit:  1e2411a29464
extends ProtonNode


func _init() -> void:
	type_id = "break_vector3"
	title = "Break Vector3"
	category =  "Accessors/Vectors"
	description = "Exposes a Vector (x,y,z) components"

	create_input("vector", "Vector", DataType.VECTOR3)
	create_output("x", "x", DataType.NUMBER)
	create_output("y", "y", DataType.NUMBER)
	create_output("z", "z", DataType.NUMBER)


func _generate_outputs() -> void:
	var input_vector: Vector3 = get_input_single("vector", Vector3.ZERO)

	set_output("x", input_vector.x)
	set_output("y", input_vector.y)
	set_output("z", input_vector.z)
