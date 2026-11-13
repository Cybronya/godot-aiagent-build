# Source:  https://github.com/MakovWait/godots/blob/main/src/extensions/dict.gd
# Repo:    MakovWait/godots (star 816) | License: MIT | Collected: 2026-10-31
# Commit:  8e4eb2baa050
static func clear_and_free(dict: Dictionary) -> void:
	var old_values := dict.values()
	dict.clear()
	for x: Object in old_values:
		if not x is RefCounted:
			x.free()
		elif x.has_method('before_delete_as_ref_counted'):
			x.call("before_delete_as_ref_counted")
