# Source:  https://github.com/MakovWait/godots/blob/main/src/objects/node_component/comp.gd
# Repo:    MakovWait/godots (star 816) | License: MIT | Collected: 2026-10-31
# Commit:  8e4eb2baa050
class_name Comp
extends _Component


func _init(script: Object, children:=[]) -> void:
	super._init(func() -> Node: return script.call("new"))
	self.children(children)
