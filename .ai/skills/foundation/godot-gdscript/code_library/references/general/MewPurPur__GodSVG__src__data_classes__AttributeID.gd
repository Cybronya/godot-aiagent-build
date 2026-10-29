# Source:  https://github.com/MewPurPur/GodSVG/blob/main/src/data_classes/AttributeID.gd
# Repo:    MewPurPur/GodSVG (star 2784) | License: MIT | Collected: 2026-10-28
# Commit:  52ad7944fcf9
## An attribute representing an element's ID.
class_name AttributeID extends Attribute

func set_value(new_value: String) -> void:
	super(new_value if ParserID.get_id_validity(new_value) != ParserID.NameValidityLevel.INVALID else "")
