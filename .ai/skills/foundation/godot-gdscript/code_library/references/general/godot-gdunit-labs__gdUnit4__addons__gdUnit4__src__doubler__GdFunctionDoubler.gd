# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/doubler/GdFunctionDoubler.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
@abstract class_name GdFunctionDoubler
extends RefCounted


@abstract func double(func_descriptor: GdFunctionDescriptor) -> PackedStringArray
