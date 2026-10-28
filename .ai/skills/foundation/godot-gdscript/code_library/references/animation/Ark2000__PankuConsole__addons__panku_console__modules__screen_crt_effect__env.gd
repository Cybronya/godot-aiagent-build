# Source:  https://github.com/Ark2000/PankuConsole/blob/master/addons/panku_console/modules/screen_crt_effect/env.gd
# Repo:    Ark2000/PankuConsole (star 1436) | License: MIT | Collected: 2026-10-28
# Commit:  master
var _module:PankuModule

const _HELP_toggle = "The good old days"
func toggle() -> void:
    _module.toggle_crt_effect()