# Source:  https://github.com/Miziziziz/MizGodotTools/blob/main/globals/fps_display/fps_display.gd
# Repo:    Miziziziz/MizGodotTools (star 987) | License: MIT | Collected: 2026-10-29
# Commit:  cb548f9035a3
extends Label


var fps_display_visible : int :
		set(b):
			set_process(b)
			fps_display_visible = b
			visible = b

func _ready() -> void:
	hide()

func _process(_delta: float) -> void:
	text = str(roundi(Engine.get_frames_per_second()))
