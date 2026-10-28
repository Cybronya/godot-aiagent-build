# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/widgets/curve_edit/settings_panel.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  master
extends PanelContainer


func _on_ready() -> void:
	%GridDensity.value = %CurveEditor.axes_density - 1.0


func _on_grid_density_value_changed(value: Variant) -> void:
	%CurveEditor.axes_density = value + 1.0
	%CurveEditor.queue_redraw()
