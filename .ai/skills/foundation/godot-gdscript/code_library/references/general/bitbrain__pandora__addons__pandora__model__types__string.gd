# Source:  https://github.com/bitbrain/pandora/blob/godot-4.x/addons/pandora/model/types/string.gd
# Repo:    bitbrain/pandora (star 1129) | License: MIT | Collected: 2026-10-29
# Commit:  fa48e30e6609
extends PandoraPropertyType

const ICON_PATH = "res://addons/pandora/icons/String.svg"

const SETTINGS = {}


func _init() -> void:
	super("string", SETTINGS, "", ICON_PATH)


func is_valid(variant: Variant) -> bool:
	return variant is String

func is_actual_type(variant: Variant) -> bool:
	return variant is String
