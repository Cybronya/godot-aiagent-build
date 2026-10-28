# Source:  https://github.com/RodZill4/material-maker/blob/master/addons/material_maker/engine/logger.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  master
extends Node
class_name MMLogger

var logger : Object = null

func set_logger(l : Object):
	logger = l

# Called when the node enters the scene tree for the first time.
func write(l: String, m : String):
	if logger:
		logger.write(l, m)
	elif l == "":
		print(m)
	else:
		print(l+": "+m)

func debug(m : String):
	write("DEBUG", m)

func message(m : String):
	write("", m)

func warning(m : String):
	write("WARNING", m)

func error(m : String):
	write("ERROR", m)
