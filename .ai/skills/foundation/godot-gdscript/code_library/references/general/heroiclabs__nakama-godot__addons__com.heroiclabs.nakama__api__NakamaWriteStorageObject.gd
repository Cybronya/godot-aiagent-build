# Source:  https://github.com/heroiclabs/nakama-godot/blob/master/addons/com.heroiclabs.nakama/api/NakamaWriteStorageObject.gd
# Repo:    heroiclabs/nakama-godot (star 783) | License: Apache-2.0 | Collected: 2026-10-31
# Commit:  6dc7b3951d98
extends RefCounted
class_name NakamaWriteStorageObject

var collection : String
var key : String
var permission_read : int = 0
var permission_write : int = 0
var value : String
var version : String

func _init(p_collection : String, p_key : String, p_permission_read : int,
		p_permission_write : int, p_value : String, p_version : String):
	collection = p_collection
	key = p_key
	permission_read = p_permission_read
	permission_write = p_permission_write
	value = p_value
	version = p_version

func as_write():
	return NakamaAPI.ApiWriteStorageObject.create(NakamaAPI, {
		"collection": collection,
		"key": key,
		"permission_read": permission_read,
		"permission_write": permission_write,
		"value": value,
		"version": version
	})
