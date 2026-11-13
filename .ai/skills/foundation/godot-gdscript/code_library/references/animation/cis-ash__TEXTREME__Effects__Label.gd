# Source:  https://github.com/cis-ash/TEXTREME/blob/master/Effects/Label.gd
# Repo:    cis-ash/TEXTREME (star 801) | License: MIT | Collected: 2026-10-31
# Commit:  673dc09d9132
extends Label

# class member variables go here, for example:
# var a = 2
# var b = "textvar"

#func _ready():
	# Called when the node is added to the scene for the first time.
	# Initialization here
#	pass

func _process(delta):
	text = get_parent().get_parent().letter
	pass
