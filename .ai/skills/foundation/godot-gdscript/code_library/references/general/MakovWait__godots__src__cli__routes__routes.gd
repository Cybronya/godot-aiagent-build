# Source:  https://github.com/MakovWait/godots/blob/main/src/cli/routes/routes.gd
# Repo:    MakovWait/godots (star 816) | License: MIT | Collected: 2026-10-31
# Commit:  8e4eb2baa050
class_name Routes

class List extends Item:
	var _items: Array[Item] = []

	func route(cmd: CliParser.ParsedCommandResult, user_args: PackedStringArray) -> void:
		for item in _items:
			if item.match(cmd, user_args):
				item.route(cmd, user_args)
				break

	func match(cmd: CliParser.ParsedCommandResult, user_args: PackedStringArray) -> bool:
		for item in _items:
			if item.match(cmd, user_args):
				return true
		return false

class Item:
	func route(cmd: CliParser.ParsedCommandResult, user_args: PackedStringArray) -> void:
		return

	func match(cmd: CliParser.ParsedCommandResult, user_args: PackedStringArray) -> bool:
		return false
