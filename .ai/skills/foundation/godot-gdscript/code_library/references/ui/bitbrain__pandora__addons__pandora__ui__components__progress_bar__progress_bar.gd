# Source:  https://github.com/bitbrain/pandora/blob/godot-4.x/addons/pandora/ui/components/progress_bar/progress_bar.gd
# Repo:    bitbrain/pandora (star 1129) | License: MIT | Collected: 2026-10-29
# Commit:  fa48e30e6609
@tool
class_name ImportProgressBar
extends MarginContainer

@onready var progress_bar = $ProgressBar

var total_steps: int = 100


# Called when the node enters the scene tree for the first time.
func _ready():
	visible = false


func init(total_steps: int):
	total_steps = total_steps
	progress_bar.step = progress_bar.max_value / total_steps
	visible = true


func advance():
	progress_bar.value += progress_bar.step


func finish():
	total_steps = 100
	progress_bar.step = 0.01
	visible = false
