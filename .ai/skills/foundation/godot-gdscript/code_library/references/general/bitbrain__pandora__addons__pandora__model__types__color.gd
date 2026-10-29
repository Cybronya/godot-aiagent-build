# Source:  https://github.com/bitbrain/pandora/blob/godot-4.x/addons/pandora/model/types/color.gd
# Repo:    bitbrain/pandora (star 1129) | License: MIT | Collected: 2026-10-29
# Commit:  fa48e30e6609
extends PandoraPropertyType

const ICON_PATH = "res://addons/pandora/icons/Color.svg"

const SETTINGS = {}


func _init() -> void:
	super("color", SETTINGS, Color.WHITE, ICON_PATH)


func parse_value(variant: Variant, settings: Dictionary = {}) -> Variant:
	if variant is String:
		return Color.from_string(variant, Color.WHITE)
	return variant


func write_value(variant: Variant) -> Variant:
	var color = variant as Color
	return color.to_html()


func is_valid(variant: Variant) -> bool:
	return variant is Color or variant is String

func is_actual_type(variant: Variant) -> bool:
	return variant is Color
