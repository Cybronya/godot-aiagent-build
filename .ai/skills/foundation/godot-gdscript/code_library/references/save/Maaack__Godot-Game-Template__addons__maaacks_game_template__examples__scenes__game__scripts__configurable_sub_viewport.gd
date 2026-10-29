# Source:  https://github.com/Maaack/Godot-Game-Template/blob/main/addons/maaacks_game_template/examples/scenes/game/scripts/configurable_sub_viewport.gd
# Repo:    Maaack/Godot-Game-Template (star 1709) | License: MIT | Collected: 2026-10-26
# Commit:  5cc611f7dfcd
extends SubViewport
## Script to apply the anti-aliasing setting from [PlayerConfig] to a [SubViewport].

## The name of the anti-aliasing variable in the [ConfigFile].
@export var anti_aliasing_key : StringName = "Anti-aliasing"
## The name of the section of the anti-aliasing variable in the [ConfigFile].
@export var video_section : StringName = AppSettings.VIDEO_SECTION

func _ready() -> void:
	var anti_aliasing : int = PlayerConfig.get_config(video_section, anti_aliasing_key, Viewport.MSAA_DISABLED)
	msaa_2d = anti_aliasing as MSAA
	msaa_3d = anti_aliasing as MSAA
