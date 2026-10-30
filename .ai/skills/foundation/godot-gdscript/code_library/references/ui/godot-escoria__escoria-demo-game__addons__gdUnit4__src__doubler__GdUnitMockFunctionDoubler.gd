# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/gdUnit4/src/doubler/GdUnitMockFunctionDoubler.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
class_name GdUnitMockFunctionDoubler
extends GdFunctionDoubler


func double(func_descriptor: GdFunctionDescriptor) -> PackedStringArray:
	return GdUnitFunctionDoublerBuilder.new(func_descriptor)\
		.with_prepare_block()\
		.with_verify_block()\
		.with_mocked_return_value()\
		.build()
