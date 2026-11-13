# Source:  https://github.com/MakovWait/godots/blob/main/src/objects/node_component/comp_scene.gd
# Repo:    MakovWait/godots (star 816) | License: MIT | Collected: 2026-10-31
# Commit:  8e4eb2baa050
class_name CompScene
extends _Component


func _init(scene: PackedScene, children=[]):
	super._init(func(): return scene.instantiate())
	self.children(children)
