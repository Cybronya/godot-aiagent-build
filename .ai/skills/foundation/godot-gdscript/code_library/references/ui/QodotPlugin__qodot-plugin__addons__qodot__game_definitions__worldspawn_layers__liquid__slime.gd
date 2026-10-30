# Source:  https://github.com/QodotPlugin/qodot-plugin/blob/master/addons/qodot/game_definitions/worldspawn_layers/liquid/slime.gd
# Repo:    QodotPlugin/qodot-plugin (star 982) | License: MIT | Collected: 2026-10-29
# Commit:  4731a36dec69
class_name SlimeLayer
extends LiquidLayer

func _init().() -> void:
	buoyancy_factor = 6.0
	vertical_damping_factor = 3.0
	lateral_damping_factor = 0.4
