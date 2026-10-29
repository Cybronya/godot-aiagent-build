# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/audio/rhythm_game/globals/enums.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
## Global enums.
class_name Enums

enum TimeType {
	FILTERED,
	RAW,
}

enum HitType {
	MISS_EARLY,
	GOOD_EARLY,
	PERFECT,
	GOOD_LATE,
	MISS_LATE,
}
