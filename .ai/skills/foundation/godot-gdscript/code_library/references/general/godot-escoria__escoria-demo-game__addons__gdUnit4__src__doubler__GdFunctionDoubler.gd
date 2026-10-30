# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/gdUnit4/src/doubler/GdFunctionDoubler.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
@abstract class_name GdFunctionDoubler
extends RefCounted

@abstract func double(func_descriptor: GdFunctionDescriptor) -> PackedStringArray
