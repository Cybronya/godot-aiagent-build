# Source:  https://github.com/godot-fun/godot-start/blob/main/scene/demo16_http/script/httpRequest.gd
# Repo:    godot-fun/godot-start (star 1106) | License: MIT | Collected: 2026-10-29
# Commit:  115fc06e42f3
extends HTTPRequest


# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	httpRequest()
	pass

func httpRequest():
	var headers: Array[String] = []
	self.set_use_threads(true)
	self.connect("request_completed", Callable(self, "doSomething"))
	self.request("https://www.baidu.com/")
		
 
func doSomething(result, response_code, headers, body: PackedByteArray):
	
	if(response_code == 200):
		var data = body.get_string_from_utf8()
		print(data)
	else:
		print('response_code: ', response_code)
		print('problem on the server')
