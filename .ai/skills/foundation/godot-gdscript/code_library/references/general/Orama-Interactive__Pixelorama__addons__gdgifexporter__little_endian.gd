# Source:  https://github.com/Orama-Interactive/Pixelorama/blob/master/addons/gdgifexporter/little_endian.gd
# Repo:    Orama-Interactive/Pixelorama (star 10855) | License: MIT | Collected: 2026-10-27
# Commit:  fae9327992f1
extends RefCounted


func int_to_word(value: int) -> PackedByteArray:
	return PackedByteArray([value & 255, (value >> 8) & 255])
