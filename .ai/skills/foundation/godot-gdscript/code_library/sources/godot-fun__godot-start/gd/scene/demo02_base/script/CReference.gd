# 如果没有继承任何类，则默认继承RefCounted
extends RefCounted

func _to_string():
	print("This is C Reference Counted!")
