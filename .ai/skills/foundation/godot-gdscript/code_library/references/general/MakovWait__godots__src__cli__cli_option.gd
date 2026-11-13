# Source:  https://github.com/MakovWait/godots/blob/main/src/cli/cli_option.gd
# Repo:    MakovWait/godots (star 816) | License: MIT | Collected: 2026-10-31
# Commit:  8e4eb2baa050
class_name CliOption

var description: String
var usage: String
var short: String
var long: String

func _init(long: String, short: String, description: String, usage: String) -> void:
	self.long = "--%s" % long
	self.short = "-%s" % short
	self.description = description
	self.usage = usage

func to_help_string() -> String:
	return "%s|%s \t %s" % [long, short, description]
