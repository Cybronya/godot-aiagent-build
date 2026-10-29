# Source:  https://github.com/godot-fun/godot-start/blob/main/zfoo/util/ArrayUtils.gd
# Repo:    godot-fun/godot-start (star 1106) | License: MIT | Collected: 2026-10-29
# Commit:  115fc06e42f3
extends Object


static func isEmpty(array: Array) -> bool:
	return array == null or array.size() == 0
