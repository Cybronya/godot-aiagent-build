# Source:  https://github.com/protongraph/protongraph/blob/main/nodes/generators/curves/create_line.gd
# Repo:    protongraph/protongraph (star 1749) | License: MIT | Collected: 2026-10-29
# Commit:  1e2411a29464
extends ProtonNode


func _init() -> void:
	type_id = "curve_generator_simple_line"
	title = "Create Line"
	category = "Generators/Curves"
	description = "Creates a straight 3D path made of two points."

	var opts := SlotOptions.new()
	opts.value = Vector3.ONE

	create_input("start", "Start", DataType.VECTOR3)
	create_input("end", "End", DataType.VECTOR3, opts)

	create_output("line", "Line", DataType.CURVE_3D)


func _generate_outputs() -> void:
	var start: Vector3 = get_input_single("start", Vector3.ZERO)
	var end: Vector3 = get_input_single("end", Vector3.ZERO)

	# Creates a 3D path, node origin is set to the starting point
	var path = Path3D.new()
	path.position = start

	path.curve = Curve3D.new()
	path.curve.add_point(Vector3.ZERO)
	path.curve.add_point(end - start)

	set_output("line", path)

