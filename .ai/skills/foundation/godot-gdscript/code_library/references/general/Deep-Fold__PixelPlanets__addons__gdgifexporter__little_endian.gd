# Source:  https://github.com/Deep-Fold/PixelPlanets/blob/main/addons/gdgifexporter/little_endian.gd
# Repo:    Deep-Fold/PixelPlanets (star 1403) | License: MIT | Collected: 2026-10-28
# Commit:  main
extends RefCounted


func int_to_2bytes(value: int) -> PackedByteArray:
	return PackedByteArray([value & 255, (value >> 8) & 255])
