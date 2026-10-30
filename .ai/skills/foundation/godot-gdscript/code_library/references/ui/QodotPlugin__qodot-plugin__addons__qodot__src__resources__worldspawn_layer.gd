# Source:  https://github.com/QodotPlugin/qodot-plugin/blob/master/addons/qodot/src/resources/worldspawn_layer.gd
# Repo:    QodotPlugin/qodot-plugin (star 982) | License: MIT | Collected: 2026-10-29
# Commit:  4731a36dec69
class_name QodotWorldspawnLayer
extends Resource

export(String) var name := ""
export(String) var texture := ""
export(String) var node_class := ""
export(bool) var build_visuals := true
export(QodotFGDSolidClass.CollisionShapeType) var collision_shape_type := QodotFGDSolidClass.CollisionShapeType.CONVEX
export(Script) var script_class = null

func _init() -> void:
	resource_name = "Worldspawn Layer"
