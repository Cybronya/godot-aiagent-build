# Source:  https://github.com/QodotPlugin/qodot-plugin/blob/master/addons/qodot/src/resources/game-definitions/trenchbroom/trenchbroom_tag.gd
# Repo:    QodotPlugin/qodot-plugin (star 982) | License: MIT | Collected: 2026-10-29
# Commit:  4731a36dec69
class_name TrenchBroomTag
extends Resource

enum TagMatchType {
	TEXTURE,
	CONTENT_FLAG,
	SURFACE_FLAG,
	SURFACE_PARAM,
	CLASSNAME
}

export(String) var tag_name : String
export(Array, String) var tag_attributes : Array
export(TagMatchType) var tag_match_type : int
export(String) var tag_pattern : String
export(String) var texture_name : String
