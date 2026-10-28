# Source:  https://github.com/RodZill4/material-maker/blob/master/addons/material_maker/engine/nodes/gen_context.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  master
@tool
extends RefCounted
class_name MMGenContext


var variants : Dictionary = {}
var parent_context : MMGenContext = null

func _init(p = null) -> void:
	parent_context = p

func has_variant(generator) -> bool:
	return variants.has(generator) or parent_context != null and parent_context.has_variant(generator)

func touch_variant(generator) -> void:
	if !variants.has(generator):
		variants[generator] = []
	if parent_context != null:
		parent_context.touch_variant(generator)

func get_variant(generator, variant) -> int:
	var rv = -1
	if variants.has(generator):
		rv = variants[generator].find(variant)
		if rv == -1:
			variants[generator].push_back(variant)
	else:
		variants[generator] = [variant]
	touch_variant(generator)
	return rv
