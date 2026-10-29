# Source:  https://github.com/MewPurPur/GodSVG/blob/main/src/data_classes/AttributeEnum.gd
# Repo:    MewPurPur/GodSVG (star 2784) | License: MIT | Collected: 2026-10-28
# Commit:  52ad7944fcf9
## An attribute with only a set of meaningful values.
class_name AttributeEnum extends Attribute

func set_value(new_value: String) -> void:
	super(new_value if (new_value.is_empty() or new_value in DB.ATTRIBUTE_ENUM_VALUES[name]) else "")
