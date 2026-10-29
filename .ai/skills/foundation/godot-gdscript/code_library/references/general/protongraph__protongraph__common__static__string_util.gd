# Source:  https://github.com/protongraph/protongraph/blob/main/common/static/string_util.gd
# Repo:    protongraph/protongraph (star 1749) | License: MIT | Collected: 2026-10-29
# Commit:  1e2411a29464
class_name StringUtil


static func remove_line_breaks(text: String) -> String:
	# Remove tabs
	text = text.replace("\t", "")
	# Remove line breaks
	text = text.replace("\n", " ")
	# Remove occasional double space caused by the line above
	return text.replace("  ", " ")
