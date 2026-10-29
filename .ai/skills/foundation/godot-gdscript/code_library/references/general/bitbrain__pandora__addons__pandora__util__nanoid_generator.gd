# Source:  https://github.com/bitbrain/pandora/blob/godot-4.x/addons/pandora/util/nanoid_generator.gd
# Repo:    bitbrain/pandora (star 1129) | License: MIT | Collected: 2026-10-29
# Commit:  fa48e30e6609
# inspired by github.com/eth0net/nanoid-godot (MIT) v0.2.0
class_name PandoraNanoIDGenerator
extends RefCounted

const ALPHABET := "useandom-26T198340PX75pxJACKVERYMINDBUSHWOLF_GQZbfghjklqvwyzrict"
const DEFAULT_LENGTH := 21

var default_length := DEFAULT_LENGTH


func _init(length := DEFAULT_LENGTH) -> void:
	default_length = length


func generate(length := default_length) -> String:
	var id: String
	for i in range(length):
		id += ALPHABET[randi() % ALPHABET.length()]
	return id
