extends Node

var outfile = "no_file" #bad name for the output directory
var cdpoutput = "no_file" #output from running thread used for recycling output files

func check_for_invalid_chars(file: String) -> Dictionary:
	var output = {
		"contains_invalid_characters" = false,
		"invalid_characters_found" = [],
		"string_without_invalid_characters" = ""
	}
	#check path and file name do not contain special characters
	var check_characters = []
	if file.contains("/"):
		check_characters = file.get_basename().split("/")
	else:
		check_characters.append(file)
		
	var invalid_chars:= []
	var regex = RegEx.new()
	regex.compile("[^a-zA-Z0-9\\-_ :+]")
	for string in check_characters:
		if string != "":
			var result = regex.search_all(string)
			for matches in result:
				var character = matches.get_string()
				if invalid_chars.has(character) == false:
					invalid_chars.append(character)
	
	if invalid_chars.size() == 0:
		output["contains_invalid_characters"] = false
	else:
		output["contains_invalid_characters"] = true
		output["invalid_characters_found"] = invalid_chars
		var cleaned_string = file
		for character in invalid_chars:
			cleaned_string = cleaned_string.replace(character, "")
		output["string_without_invalid_characters"] = cleaned_string
	return output
