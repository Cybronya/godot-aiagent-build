# Source:  https://github.com/RodZill4/material-maker/blob/master/addons/material_maker/engine/nodes/gen_comment_line.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  7d6daae3c74c
@tool
class_name MMGenCommentLine
extends MMGenBase

# Comments to put in the graph

var text : String = "Enter something.."

func _ready() -> void:
	pass

func get_type() -> String:
	return "comment_line"

func get_type_name() -> String:
	return "Comment Line"

func get_parameter_defs() -> Array:
	return [{ name="label", type="enum", values=["small", "large", "huge"], default=0 }]

func get_input_defs() -> Array:
	return []

func get_output_defs(_show_hidden : bool = false) -> Array:
	return []

func _serialize(data : Dictionary) -> Dictionary:
	data.type = "comment_line"
	data.text = text
	return data

func _deserialize(data : Dictionary) -> void:
	if data.has("text"):
		text = data.text
