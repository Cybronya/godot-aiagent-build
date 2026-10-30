# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/gdUnit4/src/doubler/GdUnitSpyFunctionDoubler.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
class_name GdUnitSpyFunctionDoubler
extends GdFunctionDoubler


func double(func_descriptor: GdFunctionDescriptor) -> PackedStringArray:
	return GdUnitFunctionDoublerBuilder.new(func_descriptor)\
		.with_verify_block()\
		.build()
