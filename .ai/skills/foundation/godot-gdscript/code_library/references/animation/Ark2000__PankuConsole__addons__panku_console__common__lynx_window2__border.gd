# Source:  https://github.com/Ark2000/PankuConsole/blob/master/addons/panku_console/common/lynx_window2/border.gd
# Repo:    Ark2000/PankuConsole (star 1436) | License: MIT | Collected: 2026-10-28
# Commit:  863324dfb752
extends Panel

func hey_i_am_here():
	modulate.a = 0.0
	var t = create_tween()
	t.set_speed_scale(1.0 / Engine.time_scale)
	for i in range(2):
		t.tween_property(self, "modulate:a", 0.3, 0.1)
		t.tween_property(self, "modulate:a", 0.0, 0.1)
