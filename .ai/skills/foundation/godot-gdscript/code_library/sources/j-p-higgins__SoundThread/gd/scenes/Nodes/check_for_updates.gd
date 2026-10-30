extends HTTPRequest

const GITHUB_API_URL := "https://api.github.com/repos/j-p-higgins/SoundThread/releases/latest"
var current_version 

func _ready():
	$UpdatePopup.hide()
	
	#get current version from export presets
	var export_config = ConfigFile.new()
	export_config.load("res://export_presets.cfg")
	current_version =  export_config.get_value("preset.0.options", "application/product_version", "version unknown")
	
	#call github api
	if not is_connected("request_completed", Callable(self, "_on_request_completed")):
		connect("request_completed", Callable(self, "_on_request_completed"))
	request(GITHUB_API_URL, ["User-Agent: SoundThread0"])

func _on_request_completed(result, response_code, headers, body):
	if response_code != 200:
		print("Failed to check for updates.")
		return

	var response = JSON.parse_string(body.get_string_from_utf8())
	if typeof(response) != TYPE_DICTIONARY:
		print("Invalid JSON in GitHub response.")
		return

	var latest_version = response.get("tag_name", "")
	
	var update_notes = response.get("body", "")

	if _version_is_newer(latest_version, current_version):
		_show_update_popup(latest_version, update_notes)
		
func _version_is_newer(latest: String, current: String) -> bool:
	#clean up version tags remove -alpha -beta and v and split the number sup
	latest = trim_suffix(latest, "-alpha")
	latest = trim_suffix(latest, "-beta")
	var latest_parts = latest.trim_prefix("v").split(".")
	
	current = trim_suffix(current, "-alpha")
	current = trim_suffix(current, "-beta")
	var current_parts = current.trim_prefix("v").split(".")
	
	#check if current version < latest
	for i in range(min(latest_parts.size(), current_parts.size())):
		var l = int(latest_parts[i])
		var c = int(current_parts[i])
		if l > c:
			return true
		elif l < c:
			return false
	return latest_parts.size() > current_parts.size()
	
func trim_suffix(text: String, suffix: String) -> String:
	#used to remove -alpha and -beta tags
	if text.ends_with(suffix):
		return text.substr(0, text.length() - suffix.length())
	return text
	
func _show_update_popup(new_version: String, update_notes: String):
	$UpdatePopup/Label.text = "A new version of SoundThread (" + new_version + ") is available to download."
	$UpdatePopup/UpdateNotes.text = "[b]Update Details[/b] \n" + update_notes
	$UpdatePopup.popup_centered()

func _on_open_audio_settings_button_down() -> void:
	$UpdatePopup.hide()
	OS.shell_open("https://github.com/j-p-higgins/SoundThread/releases/latest")


func _on_update_popup_close_requested() -> void:
	$UpdatePopup.hide()
