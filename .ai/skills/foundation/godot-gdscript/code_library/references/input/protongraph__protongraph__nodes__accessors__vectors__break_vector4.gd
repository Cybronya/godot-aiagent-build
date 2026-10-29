# Source:  https://github.com/protongraph/protongraph/blob/main/nodes/accessors/vectors/break_vector4.gd
# Repo:    protongraph/protongraph (star 1749) | License: MIT | Collected: 2026-10-29
# Commit:  1e2411a29464
extends ProtonNode


func _init() -> void:
	type_id = "break_vector4"
	title = "Break Vector4"
	category =  "Accessors/Vectors"
	description = "Exposes a Vector4 (x,y,z,w) components"

	create_input("vector", "Vector", DataType.VECTOR4)
	create_output("x", "x", DataType.NUMBER)
	create_output("y", "y", DataType.NUMBER)
	create_output("z", "z", DataType.NUMBER)
	create_output("w", "w", DataType.NUMBER)


func _generate_outputs() -> void:
	var input_vector: Vector4 = get_input_single("vector", Vector4.ZERO)

	set_output("x", input_vector.x)
	set_output("y", input_vector.y)
	set_output("z", input_vector.z)
	set_output("w", input_vector.w)
