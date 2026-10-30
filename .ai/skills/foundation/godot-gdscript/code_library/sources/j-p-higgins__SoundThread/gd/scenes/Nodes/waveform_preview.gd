extends Control

var left_channel: PackedFloat32Array = PackedFloat32Array()
var right_channel: PackedFloat32Array = PackedFloat32Array()
var samples_per_pixel: int = 10  # Number of samples to average per pixel for a more detailed waveform

# Function to set the audio stream
func set_audio_stream(stream: AudioStream) -> void:
	if stream is AudioStreamWAV:
		var byte_data: PackedByteArray = stream.data
		var is_stereo: bool = stream.stereo
		var bit_depth: int = stream.format  # 0 = 8-bit, 1 = 16-bit

		# Assuming the plugin outputs 16-bit audio (for this case)
		if bit_depth == 1:
			var total_samples: int = byte_data.size() / 2  # 2 bytes per 16-bit sample
			var raw_samples: PackedFloat32Array = PackedFloat32Array()
			raw_samples.resize(total_samples)

			# Manually process 16-bit PCM data (little endian assumption)
			for i in range(total_samples):
				var low = byte_data[i * 2]
				var high = byte_data[i * 2 + 1]
				var sample: int = (high << 8) | low  # Combine bytes to form a 16-bit sample
				raw_samples[i] = float(sample) / 32768.0  # Normalize to -1.0..1.0

			if is_stereo:
				left_channel.resize(total_samples / 2)
				right_channel.resize(total_samples / 2)
				for i in range(0, total_samples, 2):
					left_channel[i / 2] = raw_samples[i]
					right_channel[i / 2] = raw_samples[i + 1]
			else:
				left_channel = raw_samples
				right_channel = raw_samples

			queue_redraw()  # Trigger the redrawing of the waveform
		else:
			push_error("Unsupported bit depth. Only 16-bit PCM WAV files are supported.")
	else:
		push_error("Only AudioStreamWAV is supported for waveform preview.")

# Function to draw the waveform
func _draw() -> void:
	if left_channel.is_empty():
		return

	var width: int = int(size.x)
	var height: float = size.y
	var center_y: float = height / 2.0
	var half_height: float = height / 2.0
	var total_samples: int = left_channel.size()

	# Calculate samples per pixel
	samples_per_pixel = max(1, total_samples / width)  # Ensure at least 1 sample per pixel

	var left_points: PackedVector2Array = PackedVector2Array()
	var right_points: PackedVector2Array = PackedVector2Array()

	# Loop through each pixel (width)
	for x in range(width):
		var i: int = x * samples_per_pixel
		if i >= total_samples:
			break
		
		# Average the samples within the window defined by samples_per_pixel for each pixel
		var left_sample_avg: float = 0.0
		var right_sample_avg: float = 0.0
		var num_samples: int = samples_per_pixel

		# Sum samples over the window and calculate average
		for j in range(i, min(i + samples_per_pixel, total_samples)):
			left_sample_avg += left_channel[j]
			right_sample_avg += right_channel[j]

		left_sample_avg /= num_samples
		right_sample_avg /= num_samples

		# Clamp values to -1.0..1.0
		left_sample_avg = clamp(left_sample_avg, -1.0, 1.0)
		right_sample_avg = clamp(right_sample_avg, -1.0, 1.0)

		# Create points for drawing
		left_points.append(Vector2(x, center_y - left_sample_avg * half_height))
		right_points.append(Vector2(x, center_y - right_sample_avg * half_height))

	# Draw the waveform for the left channel
	draw_polyline(left_points, Color.CYAN, 1.5)
	# Draw the waveform for the right channel (stereo support)
	if right_channel.size() > 0:
		draw_polyline(right_points, Color.MAGENTA, 1.5)
