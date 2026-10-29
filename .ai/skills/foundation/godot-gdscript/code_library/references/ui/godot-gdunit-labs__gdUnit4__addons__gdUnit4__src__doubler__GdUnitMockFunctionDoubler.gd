# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/doubler/GdUnitMockFunctionDoubler.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
class_name GdUnitMockFunctionDoubler
extends GdFunctionDoubler


func double(func_descriptor: GdFunctionDescriptor) -> PackedStringArray:
	return GdUnitFunctionDoublerBuilder.new(func_descriptor)\
		.with_prepare_block()\
		.with_verify_block()\
		.with_mocked_return_value()\
		.build()
