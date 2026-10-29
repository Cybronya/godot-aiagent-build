# Source:  https://github.com/MewPurPur/GodSVG/blob/main/src/data_classes/ElementStop.gd
# Repo:    MewPurPur/GodSVG (star 2784) | License: MIT | Collected: 2026-10-28
# Commit:  52ad7944fcf9
## A <stop> element.
class_name ElementStop extends Element

const name = "stop"
const possible_conversions: PackedStringArray = []

func _get_own_default(attribute_name: String) -> String:
	match attribute_name:
		"offset": return "0"
		"stop-color": return "black"
		"stop-opacity": return "1"
		_: return ""
