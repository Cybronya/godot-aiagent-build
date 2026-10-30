extends PopupMenu


# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	#Check export config for version number and set about menu to current version
	#Assumes version of mac + linux builds is the same as windows
	#Requires manual update for alpha and beta builds but once the -beta is removed will be fully automatic so long as version is updated on export
	var export_config = ConfigFile.new()
	export_config.load("res://export_presets.cfg")
	set_item_text(0, "SoundThread v" + export_config.get_value("preset.0.options", "application/product_version", "version unknown") + "-beta") 
