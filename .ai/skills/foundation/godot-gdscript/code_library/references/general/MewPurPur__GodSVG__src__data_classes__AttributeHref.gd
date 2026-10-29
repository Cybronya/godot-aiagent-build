# Source:  https://github.com/MewPurPur/GodSVG/blob/main/src/data_classes/AttributeHref.gd
# Repo:    MewPurPur/GodSVG (star 2784) | License: MIT | Collected: 2026-10-28
# Commit:  52ad7944fcf9
## An attribute representing a reference to an ID.
class_name AttributeHref extends Attribute

func set_value(new_value: String) -> void:
	super(new_value if ParserID.get_href_validity(new_value) != ParserID.NameValidityLevel.INVALID else "")
