# Source:  https://github.com/protongraph/protongraph/blob/main/nodes/helpers/comment.gd
# Repo:    protongraph/protongraph (star 1749) | License: MIT | Collected: 2026-10-29
# Commit:  1e2411a29464
extends ProtonNode


func _init() -> void:
	type_id = "comment"
	title = "Comment"
	category = "Helpers"
	description = "Insert a comment in the graph editor"
	comment = true

	var opts := SlotOptions.new()
	opts.accept_connections = false
	opts.show_header = false
	create_input("comment", "", DataType.STRING, opts)
