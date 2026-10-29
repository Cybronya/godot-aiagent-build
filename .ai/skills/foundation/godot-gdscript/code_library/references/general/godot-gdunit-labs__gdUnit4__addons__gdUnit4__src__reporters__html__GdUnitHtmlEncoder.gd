# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/reporters/html/GdUnitHtmlEncoder.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
class_name GdUnitHtmlEncoder
extends RefCounted


static func encode(value: String) -> String:
	# & must be replaced first to avoid double-encoding the entities we insert
	return value\
		.replace("&", "&amp;")\
		.replace("<", "&lt;")\
		.replace(">", "&gt;")\
		.replace('"', "&quot;")\
		.replace("'", "&#39;")
