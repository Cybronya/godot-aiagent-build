# Source:  https://github.com/protongraph/protongraph/blob/main/nodes/generators/numbers/scalar.gd
# Repo:    protongraph/protongraph (star 1749) | License: MIT | Collected: 2026-10-29
# Commit:  1e2411a29464
extends ProtonNode


func _init() -> void:
	type_id = "create_number"
	title = "Create Number"
	category = "Generators/Numbers"
	description = "Returns a number"

	var opts = SlotOptions.new()
	opts.max_value = 1000
	opts.min_value = -1000
	opts.allow_greater = true
	opts.allow_lesser = true
	create_input("n", "", DataType.NUMBER, opts)

	create_output("number", "Number", DataType.NUMBER)


func _generate_outputs() -> void:
	set_output("number", get_input_single("n", 0.0))
