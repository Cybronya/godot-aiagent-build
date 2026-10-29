# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/top_down/scripts/actor/bots/ActiveEnemyResource.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  d5d8d1588742
## Tree like double linked data representing relationship between spawned enemies
class_name ActiveEnemyResource
extends Resource

var parent:ActiveEnemyResource

var children:Array[ActiveEnemyResource]

var nodes:Array[ActiveEnemy]

var clear_callback:Callable
