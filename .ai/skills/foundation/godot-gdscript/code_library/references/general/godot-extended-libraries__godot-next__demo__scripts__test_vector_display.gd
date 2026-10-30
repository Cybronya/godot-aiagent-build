# Source:  https://github.com/godot-extended-libraries/godot-next/blob/master/demo/scripts/test_vector_display.gd
# Repo:    godot-extended-libraries/godot-next (star 998) | License: MIT | Collected: 2026-10-29
# Commit:  4ac438abe5b4
extends Node

export(Vector2) var vector2 = Vector2(100, 200)
export(Vector3) var vector3 = Vector3(1, 2, 3)
export(PoolVector2Array) var pool_vector2_array = PoolVector2Array()
export(PoolVector3Array) var pool_vector3_array = PoolVector3Array()
export(Array) var array = [Vector2(100, 100), Vector3(0, 1, 2)]
