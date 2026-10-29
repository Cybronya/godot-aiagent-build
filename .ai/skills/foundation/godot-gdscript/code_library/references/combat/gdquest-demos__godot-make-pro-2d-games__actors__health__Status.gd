# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/actors/health/Status.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends Node

signal added(status)
signal removed(status)

var statuses_active = {}

# Example status
const POISON = {
	'name': "Poison",
	'effect': {
		'periodic_damage': {
			'cycles': 5,
			'stat': 'health',
			'damage': 1,
		}
	}
}
const INVINCIBLE = {
	'name': "Invincible",
	'effect': {
		'stat_modifier': {
			'add': {
				'defense': 1000,
				'magic_defense': 1000
			}
		}
	}
}

func add(id, status):
	statuses_active[id] = status

func remove(id):
	statuses_active.erase(id)

func as_string():
	var string = ""
	for status in statuses_active.values():
		string += "%s.%s: %s" % [status['id'], status['name'], status['effect']]
	return string
