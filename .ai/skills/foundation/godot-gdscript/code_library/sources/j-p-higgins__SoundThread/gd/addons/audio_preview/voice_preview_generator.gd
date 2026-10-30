@tool
extends Node

signal texture_ready(texture)
signal generation_progress(normalized_progress)

const MAX_FREQUENCY: float = 3000.0 # Maximum frequency captured
const IMAGE_HEIGHT: int = 64

var image_compression: float = 10.0 # How many samples in one pixel
var background_color = Color(0, 0, 0, 0)
var foreground_color







# =============================================================================


const SAMPLING_RATE = 2.0*MAX_FREQUENCY
const IMAGE_HEIGHT_FACTOR: float = float(IMAGE_HEIGHT) / 256.0 # Converts sample raw height to pixel
const IMAGE_CENTER_Y = int(round(IMAGE_HEIGHT / 2.0))

var is_working := false
var must_abort := false


func generate_preview(stream: AudioStreamWAV, image_max_width: int = 500):
	#set colour based on theme
	var interface_settings = ConfigHandler.load_interface_settings()
	#check if the theme is inverted
	if interface_settings.invert_theme:
		foreground_color = Color(0.102, 0.102, 0.102, 0.6)
	else:
		foreground_color = Color(0.898, 0.898, 0.898, 0.6)
	
	
	if not stream:
		return
	if stream.format == AudioStreamWAV.FORMAT_IMA_ADPCM:
		return
	if image_max_width <= 0:
		return

	# If already working, abort previous job first.
	if is_working:
		must_abort = true
		while is_working:
			await get_tree().process_frame

	is_working = true

	var data: PackedByteArray = stream.data
	var data_size: int = data.size()
	var is_stereo: bool = stream.stereo
	var is_16bit: bool = (stream.format == AudioStreamWAV.FORMAT_16_BITS)
	# Assume non-ADPCM, non-16-bit is 24-bit PCM for our preview purposes
	var bytes_per_sample: int = 2 if is_16bit else 3
	var channels: int = 2 if is_stereo else 1
	var frame_bytes: int = bytes_per_sample * channels

	if frame_bytes <= 0:
		is_working = false
		return

	var total_frames: int = int(floor(data_size / frame_bytes))
	if total_frames <= 0:
		is_working = false
		return

	# Decide how many frames contribute to each pixel column
	var frames_per_pixel: int = int(ceil(total_frames / float(image_max_width)))
	var img_width: int = int(floor(total_frames / float(frames_per_pixel)))
	if img_width <= 0:
		img_width = 1

	var img := Image.create(img_width, IMAGE_HEIGHT, true, Image.FORMAT_RGBA8)
	img.fill(background_color)

	# For speed, sample only a subset of frames in each pixel column.
	# Tweak this to trade accuracy for speed (e.g., 8 or 12 samples per column).
	var samples_per_pixel_target: int = 4
	var inner_step: int = max(1, int(floor(frames_per_pixel / float(samples_per_pixel_target))))

	var x: int = 0
	var frames_processed: int = 0

	while x < img_width:
		var start_frame: int = x * frames_per_pixel
		var end_frame: int = min(start_frame + frames_per_pixel, total_frames)

		var min_l := 128
		var max_l := 128
		var min_r := 128
		var max_r := 128

		var f: int = start_frame
		while f < end_frame:
			var base := f * frame_bytes

			# ---- Decode LEFT -> fast 8-bit signed, then map to 0..255
			var l_u8: int
			if is_16bit:
				var l_lo := data[base]
				var l_hi := data[base + 1]
				var l16 := (l_hi << 8) | l_lo
				if (l_hi & 0x80) != 0:
					l16 -= 0x10000
				l_u8 = ((l16 >> 8) + 128)
			else:
				var l_b0 := data[base]
				var l_b1 := data[base + 1]
				var l_b2 := data[base + 2]
				var l24 := (l_b2 << 16) | (l_b1 << 8) | l_b0
				if (l_b2 & 0x80) != 0:
					l24 -= 0x1000000
				l_u8 = ((l24 >> 16) + 128)
			l_u8 = clamp(l_u8, 0, 255)

			# ---- Decode RIGHT (or mirror left for mono)
			var r_u8: int = l_u8
			if is_stereo:
				var ro := bytes_per_sample # right channel offset inside frame
				if is_16bit:
					var r_lo := data[base + ro]
					var r_hi := data[base + ro + 1]
					var r16 := (r_hi << 8) | r_lo
					if (r_hi & 0x80) != 0:
						r16 -= 0x10000
					r_u8 = ((r16 >> 8) + 128)
				else:
					var r_b0 := data[base + ro]
					var r_b1 := data[base + ro + 1]
					var r_b2 := data[base + ro + 2]
					var r24 := (r_b2 << 16) | (r_b1 << 8) | r_b0
					if (r_b2 & 0x80) != 0:
						r24 -= 0x1000000
					r_u8 = ((r24 >> 16) + 128)
				r_u8 = clamp(r_u8, 0, 255)

			# Update min/max per channel
			if l_u8 < min_l: min_l = l_u8
			if l_u8 > max_l: max_l = l_u8
			if r_u8 < min_r: min_r = r_u8
			if r_u8 > max_r: max_r = r_u8

			f += inner_step
			frames_processed += inner_step

			if must_abort:
				is_working = false
				must_abort = false
				return

		# Draw column
		if is_stereo:
			_draw_half_waveform(img, x, min_l, max_l, 0, IMAGE_HEIGHT / 2)
			_draw_half_waveform(img, x, min_r, max_r, IMAGE_HEIGHT / 2, IMAGE_HEIGHT / 2)
		else:
			_draw_half_waveform(img, x, min_l, max_l, 0, IMAGE_HEIGHT)

		x += 1

		# Lightweight progress update
		if (x % 16) == 0:
			var progress := float(x) / float(img_width)
			emit_signal("generation_progress", progress)
			await get_tree().process_frame

	is_working = false
	emit_signal("texture_ready", ImageTexture.create_from_image(img))
	
func _draw_half_waveform(img: Image, x: int, min_val: int, max_val: int, y_offset: int, draw_height: int):
	var scale = draw_height / 256.0
	var center_y = y_offset + int(draw_height / 2)

	var min_y = int(center_y - (max_val - 128) * scale)
	var max_y = int(center_y - (min_val - 128) * scale)

	min_y = clamp(min_y, y_offset, y_offset + draw_height - 1)
	max_y = clamp(max_y, y_offset, y_offset + draw_height - 1)

	for y in range(min_y, max_y + 1):
		img.set_pixel(x, y, foreground_color)
		
func _reset_to_blank():
	var img = Image.create(1, IMAGE_HEIGHT, true, Image.FORMAT_RGBA8)
	img.fill(Color.DARK_SLATE_GRAY)
	emit_signal("texture_ready", ImageTexture.create_from_image(img))
	
