# Source:  https://github.com/protongraph/protongraph/blob/main/common/static/memory_util.gd
# Repo:    protongraph/protongraph (star 1749) | License: MIT | Collected: 2026-10-29
# Commit:  1e2411a29464
class_name MemoryUtil
extends RefCounted


static func safe_free(any) -> void:
	if any is RefCounted:
		return

	if any is Node and is_instance_valid(any):
		any.queue_free()

	elif any is Object:
		any.free()

	elif any is Array:
		for item in any:
			safe_free(item)

	# Other types don't need specific attention.
