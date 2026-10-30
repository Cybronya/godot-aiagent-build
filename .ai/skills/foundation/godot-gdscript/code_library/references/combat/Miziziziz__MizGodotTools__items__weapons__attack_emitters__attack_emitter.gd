# Source:  https://github.com/Miziziziz/MizGodotTools/blob/main/items/weapons/attack_emitters/attack_emitter.gd
# Repo:    Miziziziz/MizGodotTools (star 987) | License: MIT | Collected: 2026-10-29
# Commit:  cb548f9035a3
class_name AttackEmitter extends Node2D

## Base class used for emitting attacks from weapons

signal attacked

var damage : int :
	set(v):
		damage = v
		for child in get_children():
			if child is AttackEmitter:
				child.damage = v

var source_of_attack : Node2D:
	set(s):
		source_of_attack = s
		for child in get_children():
			if child is AttackEmitter:
				child.source_of_attack = s


func set_bodies_to_exclude(bte: Array):
	for child in get_children():
		if child is AttackEmitter:
			child.set_bodies_to_exclude(bte)

func do_attack():
	for child in get_children():
		if child is AttackEmitter:
			child.do_attack()
	attacked.emit()
