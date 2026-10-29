# Source:  https://github.com/bitbrain/beehave/blob/godot-4.x/addons/beehave/nodes/leaves/blackboard_set.gd
# Repo:    bitbrain/beehave (star 3312) | License: MIT | Collected: 2026-10-26
# Commit:  fe589153fa78
## Sets the specified key to the specified value.
## Returns [code]FAILURE[/code] if expression execution fails, otherwise [code]SUCCESS[/code].
@tool
class_name BlackboardSetAction extends ActionLeaf

## Expression representing a blackboard key.
@export_placeholder(EXPRESSION_PLACEHOLDER) var key: String = ""
## Expression representing a blackboard value to assign to the specified key.
@export_placeholder(EXPRESSION_PLACEHOLDER) var value: String = ""

@onready var _key_expression: Expression = _parse_expression(key)
@onready var _value_expression: Expression = _parse_expression(value)


func tick(actor: Node, blackboard: Blackboard) -> int:
	var key_value: Variant = _key_expression.execute([], blackboard)

	if _key_expression.has_execute_failed():
		return FAILURE

	var value_value: Variant = _value_expression.execute([], blackboard)

	if _value_expression.has_execute_failed():
		return FAILURE

	blackboard.set_value(key_value, value_value)

	return SUCCESS


func _get_expression_sources() -> Array[String]:
	return [key, value]
