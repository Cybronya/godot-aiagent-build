# Source:  https://github.com/godot-fun/godot-start/blob/main/scene/demo02_base/script/CReference.gd
# Repo:    godot-fun/godot-start (star 1106) | License: MIT | Collected: 2026-10-29
# Commit:  115fc06e42f3
# 如果没有继承任何类，则默认继承RefCounted
extends RefCounted

func _to_string():
	print("This is C Reference Counted!")
