extends Control

const FIXED_POINT_COUNT := 2

var points := []        # Stores Vector2 points
var point_size := 10
var dragged_point_index := -1
signal automation_updated(values: Array)


func _ready():
	set_process_unhandled_input(true)
	# these two are fixed: only Y-movable, not deletable
	var window = get_window().size
	var uiscale = get_window().content_scale_factor
	points.append(Vector2(0, (((window.y / 2) - (22 * uiscale)) / uiscale)))
	points.append(Vector2(window.x / uiscale, (((window.y / 2) - (22 * uiscale)) / uiscale)))
	

func _unhandled_input(event):
	var pos = get_local_mouse_position()

	if event is InputEventMouseButton:
		# --- double-click: delete only if not fixed, otherwise add new --
		if event.button_index == MOUSE_BUTTON_LEFT and event.double_click:
			var idx = get_point_at_pos(pos)
			if idx >= FIXED_POINT_COUNT:
				points.remove_at(idx)
			elif idx == -1:
				points.append(pos)
			queue_redraw()

		# --- begin drag on press ---
		elif event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
			dragged_point_index = get_point_at_pos(pos)

		# --- end drag on release ---
		elif event.button_index == MOUSE_BUTTON_LEFT and not event.pressed:
			dragged_point_index = -1

	elif event is InputEventMouseMotion and dragged_point_index != -1:
		# if it’s one of the first two, constrain to Y only:
		if dragged_point_index < FIXED_POINT_COUNT:
			points[dragged_point_index].y = clamp(pos.y, 0, get_window().size.y -45)
		else:
			points[dragged_point_index].x = clamp(pos.x, 0, get_window().size.x)
			points[dragged_point_index].y = clamp(pos.y, 0, get_window().size.y - 45)
		queue_redraw()

func _draw():
	var sorted = []
	sorted = points.duplicate()
	sorted.sort_custom(sort_points)
	for i in range(points.size() - 1):
		draw_dashed_line(sorted[i], sorted[i + 1], Color(0.1, 0.1, 0.1, 0.6), 2.0, 6.0, true, true)
	
	for point in points:
		draw_rect(Rect2(point.x - (point_size / 2), point.y - (point_size / 2), point_size, point_size), Color(0.1, 0.1, 0.1, 0.8))


func sort_points(a, b):
	return a.x < b.x

func get_point_at_pos(pos: Vector2) -> int:
	# find any point within radius + padding
	for i in range(points.size()):
		if points[i].distance_to(pos) <= point_size + 2:
			return i
	return -1
	
func emit_automation_data():
	emit_signal("automation_updated", points)


func _on_save_automation_button_down() -> void:
	emit_automation_data()

func read_automation(stored_points: Array):
	points = stored_points.duplicate()

func reset_automation():
	points = []
	var window = get_window().size
	points.append(Vector2(0, (window.y / 2) - 22))
	points.append(Vector2(window.x, (window.y / 2) - 22))
