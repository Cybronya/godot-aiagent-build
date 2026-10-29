# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/interface/gui/lifebar/LifebarsBuilder.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends Node

const Lifebar = preload("res://interface/gui/lifebar/HookableLifeBar.tscn")

func initialize(monsters, monster_spawners):
	for monster in monsters:
		create_lifebar(monster)
	for spawner in monster_spawners:
		monster_spawners.connect('spawned_monster', self, '_on_MonsterSpawner_spawned_monster')

func _on_MonsterSpawner_spawned_monster(monster_node):
	create_lifebar(monster_node)

func create_lifebar(actor):
	if not actor.has_node('InterfaceAnchor'):
		return
	var lifebar = Lifebar.instance()
	actor.add_child(lifebar)
	lifebar.initialize(actor)
