extends "res://base_test.gd"

func setup():
	var adapter = NakamaHTTPAdapter.new()
	adapter.timeout = 1
	adapter.auto_retry = true
	adapter.auto_retry_count = 100
	adapter.max_total_timeout_ms = 300
	add_child(adapter)

	# Send a request to a bad port, keep failing and keep retrying. 
	# Should respect the total timeout.
	var start_ms = Time.get_ticks_msec()
	var result = await adapter.send_async("GET", "http://localhost:9999/", {}, PackedByteArray())
	var elapsed_ms = Time.get_ticks_msec() - start_ms

	if assert_cond(result is NakamaException):
		return
	if assert_cond(elapsed_ms <= 300):
		return

	done()

func _process(_delta):
	assert_time(5)
