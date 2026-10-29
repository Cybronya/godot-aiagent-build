# Source:  https://github.com/protongraph/protongraph/blob/main/nodes/generators/strings/create_string.gd
# Repo:    protongraph/protongraph (star 1749) | License: MIT | Collected: 2026-10-29
# Commit:  1e2411a29464
extends ProtonNode


func _init() -> void:
	type_id = "create_string"
	title = "Create String"
	category = "Generators/Strings"
	description = "Returns a string"

	create_input("in", "", DataType.STRING)
	create_output("out", "String", DataType.STRING)


func _generate_outputs() -> void:
	set_output("out", get_input_single("in", ""))
