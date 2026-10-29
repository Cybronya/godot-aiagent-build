# Source:  https://github.com/TheDuckCow/godot-road-generator/blob/main/addons/road-generator/nodes/road_graph_node.gd
# Repo:    TheDuckCow/godot-road-generator (star 1249) | License: MIT | Collected: 2026-10-29
# Commit:  7cbefde04e57
@tool
@icon("res://addons/road-generator/resources/road_point.png")
class_name RoadGraphNode
extends Node3D
## Abstract base class for defining road points.
##
## @abstract
##
## Abstract base class for defining road points, existing mostly
## for typing reasons. As such, logic should remain to the strict minimum.


var container:RoadContainer ## The managing container node for this node (direct parent).
