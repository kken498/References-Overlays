import os
import time

import blf
import bpy
import bpy.app.handlers
import gpu
from gpu_extras.batch import batch_for_shader

from .defs import *

# Dictionary to track which viewports have overlays enabled (in-memory for fast polling)
# Key: Stable Viewport ID (e.g., "Layout_0"), Value: True/False
_viewport_toggle_states = {}

# Track when a user tries to move a position-locked image
_locked_move_attempt_index = -1

# Track the last active NON-FULLSCREEN viewport for redirection
_last_active_screen = None
_last_active_index = None


def get_vp_key(context):
	"""Returns the stable key for the current viewport's data."""
	global _last_active_screen, _last_active_index
	if context.area.type != "VIEW_3D":
		return None

	screen_name = context.screen.name

	# Calculate index of this 3D view in the current screen
	view_index = 0
	for area in context.screen.areas:
		if area.type == "VIEW_3D":
			if area == context.area:
				break
			view_index += 1

	current_key = f"{screen_name}_{view_index}"

	# If we are fullscreen (maximized), redirect to the last active normal viewport
	if context.screen.show_fullscreen:
		if _last_active_screen is not None:
			return f"{_last_active_screen}_{_last_active_index}"
		return current_key

	# Otherwise, update tracker and return this viewport's key
	_last_active_screen = screen_name
	_last_active_index = view_index

	return current_key


# --- Persistence Property Groups ---

def _mark_modified(self, context):
	"""Callback to update the last_modified timestamp whenever a property changes."""
	self.last_modified = time.time()

class ImageTransformState(bpy.types.PropertyGroup):
	last_modified: bpy.props.FloatProperty(default=0.0)

	x: bpy.props.FloatProperty(name="X", default=0, update=_mark_modified)
	y: bpy.props.FloatProperty(name="Y", default=0, update=_mark_modified)
	size: bpy.props.FloatProperty(name="Size", default=1, min=0.01, update=_mark_modified)
	rotation: bpy.props.FloatProperty(name="Rotation", default=0, subtype="ANGLE", update=_mark_modified)
	opacity: bpy.props.FloatProperty(name="Opacity", min=0, max=1, default=1, update=_mark_modified)
	flip_x: bpy.props.BoolProperty(name="Flip X", default=False, update=_mark_modified)
	flip_y: bpy.props.BoolProperty(name="Flip Y", default=False, update=_mark_modified)
	pivot_x: bpy.props.FloatProperty(name="Pivot X", default=0, update=_mark_modified)
	pivot_y: bpy.props.FloatProperty(name="Pivot Y", default=0, update=_mark_modified)
	zoom: bpy.props.FloatProperty(name="Zoom", default=0, min=0, max=1, update=_mark_modified)
	crop_left: bpy.props.FloatProperty(name="Crop Left", min=0, max=1, default=0, update=_mark_modified)
	crop_top: bpy.props.FloatProperty(name="Crop Top", min=0, max=1, default=0, update=_mark_modified)
	crop_right: bpy.props.FloatProperty(name="Crop Right", min=0, max=1, default=0, update=_mark_modified)
	crop_bottom: bpy.props.FloatProperty(name="Crop Bottom", min=0, max=1, default=0, update=_mark_modified)
	depth_set: bpy.props.EnumProperty(
		name="Depth",
		default="Default",
		items=[("Default", "Default", ""), ("Back", "Back", "")],
		update=_mark_modified
	)
	orthographic: bpy.props.BoolProperty(name="Orthographic", default=False, update=_mark_modified)
	front: bpy.props.BoolProperty(name="Front", default=True, update=_mark_modified)
	back: bpy.props.BoolProperty(name="Back", default=False, update=_mark_modified)
	left: bpy.props.BoolProperty(name="Left", default=False, update=_mark_modified)
	right: bpy.props.BoolProperty(name="Right", default=False, update=_mark_modified)
	top: bpy.props.BoolProperty(name="Top", default=False, update=_mark_modified)
	bottom: bpy.props.BoolProperty(name="Bottom", default=False, update=_mark_modified)

	# FIX: Default to True so new viewports hide it by default
	hide: bpy.props.BoolProperty(name="Hide", default=True, update=_mark_modified)

	grayscale: bpy.props.BoolProperty(name="Grayscale", default=False, update=_mark_modified)
	lock_position: bpy.props.BoolProperty(name="Lock Position", default=False, update=_mark_modified)


class ViewportState(bpy.types.PropertyGroup):
	# The stable ID (e.g., "Layout_0") this state belongs to
	viewport_id: bpy.props.StringProperty(default="")
	is_enabled: bpy.props.BoolProperty(default=False)
	transforms: bpy.props.CollectionProperty(type=ImageTransformState)


class References(bpy.types.PropertyGroup):
	def update_tag_name(self, context):
		name, _ = os.path.splitext(self.name)
		self.tag_name = name

	tag_name: bpy.props.StringProperty(
		name="References Tag Name", description="References Tag Name"
	)
	name: bpy.props.StringProperty(
		name="References Name", update=update_tag_name, description="References Name"
	)

	speed: bpy.props.FloatProperty(
		name="Speed", default=1.0, description="Sequence & Movie playing speed"
	)
	use_cyclic: bpy.props.BoolProperty(
		name="Cyclic", default=False, description="Sequence & Movie cyclic"
	)
	frame_offset: bpy.props.IntProperty(
		name="Frame Offset", default=0, description="Sequence & Movie frame offset"
	)
	fps: bpy.props.IntProperty(
		name="FPS Tempo", default=0, description="Sequence & Movie playing tempo"
	)
	hide: bpy.props.BoolProperty(
		name="Hide", default=False, description="Hide reference in viewport."
	)
	lock: bpy.props.BoolProperty(
		name="Lock", default=False, description="Lock reference to ignore mouse event"
	)


class Reference_Overlay_Props(bpy.types.PropertyGroup):
	reference: bpy.props.CollectionProperty(type=References, description="References")
	reference_index: bpy.props.IntProperty(
		name="References Index", description="References Index"
	)

	x: bpy.props.FloatProperty(
		name="References Global X", default=0, description="References Global X"
	)
	y: bpy.props.FloatProperty(
		name="References Global Y", default=0, description="References Global Y"
	)
	size: bpy.props.FloatProperty(
		name="References Global Size",
		default=1,
		min=0.01,
		description="References Global Size",
	)

	overlays_toggle: bpy.props.BoolProperty(
		name="References Overlay Toggle",
		default=True,
		description="References Overlay Toggle",
	)
	show_name: bpy.props.BoolProperty(
		name="Show Tag Name", default=False, description="Show References Tag Name"
	)
	resize_image: bpy.props.BoolProperty(
		name="Auto Reize Image",
		default=False,
		description="Resizes the image based on the average size.",
	)
	tweak_size: bpy.props.BoolProperty(
		name="Auto Tweak Size",
		default=False,
		description="Auto-tweak the size of the reference with the region.",
	)
	fit_view_distance: bpy.props.BoolProperty(
		name="Fit View Distance",
		default=False,
		description="Fit the image size to the 3D view distance",
	)
	full_lock: bpy.props.BoolProperty(
		name="Full Lock", default=False, description="Ignore mouse event"
	)

	# Store per-viewport states here
	viewport_states: bpy.props.CollectionProperty(type=ViewportState)


def get_current_viewport_state(context):
	"""Finds or creates the persistent state for the current Viewport."""
	vp_key = get_vp_key(context)
	if not vp_key:
		return None

	props = get_reference_prop(context)

	# Find existing state
	for vp_state in props.viewport_states:
		if vp_state.viewport_id == vp_key:
			return vp_state

	# Create new state
	try:
		vp_state = props.viewport_states.add()
		vp_state.viewport_id = vp_key
		return vp_state
	except AttributeError:
		return None


def initialize_transform_for_all_viewports(context, image_index, init_x=0, init_y=0):
	"""Ensures all 3D viewports in ALL workspaces have a transform state for the given image index."""
	props = get_reference_prop(context)

	# FIX: Iterate over ALL screens in the file, not just the active ones in windows.
	# This guarantees that pasting an image instantly creates its state for every workspace.
	for screen in bpy.data.screens:
		view_index = 0
		for area in screen.areas:
			if area.type == "VIEW_3D":
				vp_key = f"{screen.name}_{view_index}"
				view_index += 1

				vp_state = None
				for vp in props.viewport_states:
					if vp.viewport_id == vp_key:
						vp_state = vp
						break

				if not vp_state:
					try:
						vp_state = props.viewport_states.add()
						vp_state.viewport_id = vp_key
					except AttributeError:
						continue

				while len(vp_state.transforms) <= image_index:
					try:
						new_transform = vp_state.transforms.add()
						new_transform.x = init_x
						new_transform.y = init_y
					except AttributeError:
						break


def get_image_transform_state(context, image_index):
	"""Finds or creates the persistent transform state for a specific image."""
	vp_state = get_current_viewport_state(context)
	if not vp_state:
		return None

	if len(vp_state.transforms) <= image_index:
		try:
			props = get_reference_prop(context)

			# Find the transform for this image that was modified most recently
			best_source = None
			latest_time = -1.0

			for other_vp_state in props.viewport_states:
				if image_index < len(other_vp_state.transforms):
					other_t = other_vp_state.transforms[image_index]
					if other_t.last_modified > latest_time:
						latest_time = other_t.last_modified
						best_source = other_t

			while len(vp_state.transforms) <= image_index:
				new_t = vp_state.transforms.add()
				if best_source:
					# Inherit position from the most recently modified viewport
					new_t.x = best_source.x
					new_t.y = best_source.y
				else:
					# Fallback if no other viewport has it yet (e.g. first load)
					if image_index < len(props.reference):
						img_name = props.reference[image_index].name
						img = bpy.data.images.get(img_name)
						if img:
							new_t.x = img.size[0] / 4
							new_t.y = img.size[1] / 4
		except (AttributeError, RuntimeError):
			return None

	return vp_state.transforms[image_index]


@bpy.app.handlers.persistent
def restore_overlay_states(dummy):
	"""load_post handler to rebuild the in-memory visibility dict from the saved Scene data."""
	global _viewport_toggle_states
	global _last_active_screen, _last_active_index
	_viewport_toggle_states.clear()
	_last_active_screen = None
	_last_active_index = None

	context = bpy.context

	if context.screen.references_overlays_independent:
		if not hasattr(context.screen, "references_overlays"):
			return
	else:
		if not hasattr(context.scene, "references_overlays"):
			return

	props = get_reference_prop(context)

	# Rebuild toggle states from saved data (keys are stable strings like "Layout_0")
	for vp_state in props.viewport_states:
		if vp_state.is_enabled:
			_viewport_toggle_states[vp_state.viewport_id] = True

	# Initialize tracker with the first available 3D view
	for window in context.window_manager.windows:
		for area in window.screen.areas:
			if area.type == "VIEW_3D":
				_last_active_screen = window.screen.name
				view_index = 0
				for a in window.screen.areas:
					if a.type == "VIEW_3D":
						if a == area:
							break
						view_index += 1
				_last_active_index = view_index
				break
		if _last_active_screen:
			break


def draw_name(context, item, x, y):
	font_id = 0
	blf.enable(font_id, blf.SHADOW)
	color = (1, 1, 1, 1)
	blf.color(font_id, color[0], color[1], color[2], color[3])

	if get_reference_prop(context).tweak_size:
		region_size = map_range(
			3, 0, context.window.width / 2, 0, context.region.width
		) * map_range(3, 0, context.window.height / 2, 0, context.region.height)
		blf.size(font_id, region_size)
	else:
		blf.size(font_id, 16)

	dimensions = blf.dimensions(font_id, item.tag_name)
	blf.position(font_id, x, y + dimensions[1] / 2, 0)
	blf.draw(font_id, item.tag_name)
	blf.disable(font_id, blf.SHADOW)


def draw_outline(context, min_x, min_y, max_x, max_y, rotation_angle, color, thickness):
	references_overlays = get_reference_prop(context)
	center_x = (min_x + max_x) / 2
	center_y = (min_y + max_y) / 2

	offset_x = references_overlays.x
	offset_y = references_overlays.y

	vertices = [
		(min_x + 2 + offset_x, min_y + offset_y),
		(max_x + offset_x, min_y + offset_y),
		(max_x + offset_x, max_y + offset_y),
		(min_x + 2 + offset_x, max_y + offset_y),
		(min_x + 2 + offset_x, min_y + offset_y),
	]

	rotated_vertices = rotate_vertices(vertices, center_x, center_y, rotation_angle)

	if references_overlays.fit_view_distance:
		rotated_vertices = scale_vertices(
			rotated_vertices,
			context.region.width / 2,
			context.region.height / 2,
			1 / (context.area.spaces.active.region_3d.view_distance / 15),
		)

	rotated_vertices = scale_vertices(
		rotated_vertices,
		context.region.width / 2,
		context.region.height / 2,
		references_overlays.size,
	)

	shader = gpu.shader.from_builtin("UNIFORM_COLOR")
	gpu.state.blend_set("ALPHA")
	gpu.state.line_width_set(thickness)
	batch = batch_for_shader(shader, "LINE_STRIP", {"pos": rotated_vertices})

	shader.uniform_float("color", color)
	batch.draw(shader)
	gpu.state.blend_set("NONE")


class Overlay_Reference_Shape(bpy.types.Gizmo):
	bl_idname = "VIEW3D_GT_Overlay_Reference_Shape"
	bl_target_properties = ()
	index = None

	def draw_custom_shape(self, shader, index, select_id=None):
		context = bpy.context
		references_overlays = get_reference_prop(context)
		references = references_overlays.reference
		if index >= len(references) or len(references) == 0:
			return
		item = references[index]
		transform = get_image_transform_state(context, index)
		if not transform:
			return

		image = bpy.data.images.get(item.name)
		if not image or transform.hide == True:
			return

		if references_overlays.resize_image:
			img_x, img_y = resize_image(context, image)
		else:
			img_x = image.size[0]
			img_y = image.size[1]

		if transform.orthographic:
			view = get_view_orientations(context)
			if not (
				(transform.front and "Front" in view)
				or (transform.back and "Back" in view)
				or (transform.left and "Left" in view)
				or (transform.right and "Right" in view)
				or (transform.top and "Top" in view)
				or (transform.bottom and "Bottom" in view)
			):
				return

		region_x = map_range(
			transform.x, 0, context.window.width, 0, context.region.width
		)
		region_y = map_range(
			transform.y, 0, context.window.height, 0, context.region.height
		)

		if references_overlays.tweak_size:
			size = transform.size / (
				(context.window.width + context.region.width)
				/ (context.window.height + context.region.height)
			)
			region_size = map_range(
				size, 0, context.window.width / 2, 0, context.region.width
			) * map_range(size, 0, context.window.height / 2, 0, context.region.height)
		else:
			region_size = transform.size

		if image.source in {"SEQUENCE", "MOVIE"}:
			if image.pixels:
				image.update()

			fps = context.scene.render.fps / item.fps

			if item.use_cyclic:
				image.gl_load(
					frame=int(
						(context.scene.frame_current + item.frame_offset)
						* (item.speed / fps)
						% image.frame_duration
					)
				)
			else:
				image.gl_load(
					frame=int(
						(context.scene.frame_current + item.frame_offset)
						* (item.speed / fps)
					)
					if context.scene.frame_current > 0
					else item.frame_offset + 1
				)

		texture = gpu.texture.from_image(image)

		zoom = transform.zoom * -1 / 2

		if transform.flip_x:
			pivot_x = transform.pivot_x * -1
			left = transform.crop_right
			right = transform.crop_left
			min_x = region_x + img_x / 2 * region_size / 2 * (1 - left)
			max_x = region_x - img_x / 2 * region_size / 2 * (1 - right)
		else:
			pivot_x = transform.pivot_x
			left = transform.crop_left
			right = transform.crop_right
			min_x = region_x - img_x / 2 * region_size / 2 * (1 - left)
			max_x = region_x + img_x / 2 * region_size / 2 * (1 - right)

		if transform.flip_y:
			pivot_y = transform.pivot_y * -1
			top = transform.crop_bottom
			bottom = transform.crop_top
			min_y = region_y + img_y / 2 * region_size / 2 * (1 - bottom)
			max_y = region_y - img_y / 2 * region_size / 2 * (1 - top)
		else:
			pivot_y = transform.pivot_y
			top = transform.crop_top
			bottom = transform.crop_bottom
			min_y = region_y - img_y / 2 * region_size / 2 * (1 - bottom)
			max_y = region_y + img_y / 2 * region_size / 2 * (1 - top)

		center_x = (min_x + max_x) / 2
		center_y = (min_y + max_y) / 2
		rotation_angle = transform.rotation * -1
		opacity = transform.opacity

		offset_x = references_overlays.x
		offset_y = references_overlays.y

		pos = (
			(min_x + offset_x, min_y + offset_y),
			(max_x + offset_x, min_y + offset_y),
			(max_x + offset_x, max_y + offset_y),
			(min_x + offset_x, max_y + offset_y),
		)

		pos = rotate_vertices(pos, center_x, center_y, rotation_angle)

		if references_overlays.fit_view_distance:
			pos = scale_vertices(
				pos,
				context.region.width / 2,
				context.region.height / 2,
				1 / (context.area.spaces.active.region_3d.view_distance / 15),
			)

		pos = scale_vertices(
			pos,
			context.region.width / 2,
			context.region.height / 2,
			references_overlays.size,
		)

		batch = batch_for_shader(
			shader,
			"TRI_FAN",
			{
				"pos": pos,
				"texCoord": (
					(
						(0 + left / 2 + pivot_x) - zoom * (1 - left),
						(0 + bottom / 2 + pivot_y) - zoom * (1 - bottom),
					),
					(
						(1 - right / 2 + pivot_x) + zoom * (1 - right),
						(0 + bottom / 2 + pivot_y) - zoom * (1 - bottom),
					),
					(
						(1 - right / 2 + pivot_x) + zoom * (1 - right),
						(1 - top / 2 + pivot_y) + zoom * (1 - top),
					),
					(
						(0 + left / 2 + pivot_x) - zoom * (1 - left),
						(1 - top / 2 + pivot_y) + zoom * (1 - top),
					),
				),
			},
		)

		gpu.state.blend_set("ALPHA")

		shader.uniform_sampler("image", texture)
		shader.uniform_float("opacity", opacity)
		shader.uniform_float("grayscale", 1.0 if transform.grayscale else 0.0)
		if transform.depth_set == "Back":
			gpu.state.depth_test_set("LESS_EQUAL")
			shader.uniform_bool("depthSet", True)
		else:
			shader.uniform_bool("depthSet", False)

		batch.draw(shader)

		if select_id is not None:
			gpu.select.load_id(select_id)
		else:
			highlight_ortho = False
			addon_prefs = context.preferences.addons.get(__package__)
			if addon_prefs and hasattr(
				addon_prefs.preferences, "highlight_ortho_views"
			):
				highlight_ortho = addon_prefs.preferences.highlight_ortho_views

			is_locked_move = _locked_move_attempt_index == self.index

			if self.is_highlight or is_locked_move:
				if transform.lock_position and is_locked_move:
					color = (1, 0.5, 0.5, 1)
				else:
					color = (0.394198, 0.569371, 1, 1)

				draw_outline(
					context, min_x - 3, min_y, max_x, max_y, rotation_angle, color, 1.5
				)

			elif (
				highlight_ortho
				and transform.orthographic
				and (
					(transform.front and "Front" in view)
					or (transform.back and "Back" in view)
					or (transform.left and "Left" in view)
					or (transform.right and "Right" in view)
					or (transform.top and "Top" in view)
					or (transform.bottom and "Bottom" in view)
				)
			):
				draw_outline(
					context,
					min_x - 3,
					min_y,
					max_x,
					max_y,
					rotation_angle,
					(1, 0.6, 0, 1),
					1.5,
				)

		if references_overlays.show_name:
			if transform.flip_x:
				x = max_x
			else:
				x = min_x
			if transform.flip_y:
				y = min_y
			else:
				y = max_y
			draw_name(context, item, x, y)

	@staticmethod
	def new_custom_shape(self):
		vert_out = gpu.types.GPUStageInterfaceInfo("my_interface")
		vert_out.smooth("VEC2", "uv")

		shader_info = gpu.types.GPUShaderCreateInfo()

		shader_info.sampler(0, "FLOAT_2D", "image")
		shader_info.vertex_in(0, "VEC2", "pos")
		shader_info.vertex_in(1, "VEC2", "texCoord")
		shader_info.vertex_out(vert_out)

		shader_info.push_constant("MAT4", "ModelViewProjectionMatrix")
		shader_info.push_constant("FLOAT", "opacity")
		shader_info.push_constant("BOOL", "depthSet")
		shader_info.push_constant("BOOL", "grayscale")

		shader_info.fragment_out(0, "VEC4", "fragColor")

		shader_info.vertex_source(
			"void main()"
			"{"
			"   uv = texCoord;"
			"   gl_Position = ModelViewProjectionMatrix * vec4(pos, 0.0, 1.0);"
			"   if (depthSet) {"
			"       gl_Position.z = gl_Position.w - 2.4e-7;"
			"   }"
			"}"
		)

		shader_info.fragment_source(
			"void main()"
			"{"
			"  vec4 color = texture(image, uv);"
			"  if (grayscale) {"
			"    float luminance = dot(color.rgb, vec3(0.299, 0.587, 0.114));"
			"    fragColor = vec4(vec3(luminance), color.a * opacity);"
			"  } else {"
			"    fragColor = vec4(color.rgb, color.a * opacity);"
			"  }"
			"}"
		)

		shader = gpu.shader.create_from_info(shader_info)
		return shader

	def draw(self, context):
		self.draw_custom_shape(self.custom_shape, self.index)

	def draw_select(self, context, select_id):
		self.draw_custom_shape(self.custom_shape, self.index, select_id=select_id)

	def setup(self):
		self.custom_shape = self.new_custom_shape(self)

	def test_select(self, context, location):
		references_overlays = get_reference_prop(context)
		if references_overlays.full_lock or self.index >= len(
			references_overlays.reference
		):
			return -1

		item = references_overlays.reference[self.index]
		transform = get_image_transform_state(context, self.index)
		if not transform:
			return -1

		if not bpy.data.images.get(item.name) or transform.hide:
			return -1

		image = bpy.data.images[item.name]

		if references_overlays.resize_image:
			img_x, img_y = resize_image(context, image)
		else:
			img_x = image.size[0]
			img_y = image.size[1]

		if references_overlays.tweak_size:
			size = transform.size / (
				(context.window.width + context.region.width)
				/ (context.window.height + context.region.height)
			)
			region_size = map_range(
				size, 0, context.window.width / 2, 0, context.region.width
			) * map_range(size, 0, context.window.height / 2, 0, context.region.height)
		else:
			region_size = transform.size

		region_x = map_range(
			transform.x, 0, context.window.width, 0, context.region.width
		)
		region_y = map_range(
			transform.y, 0, context.window.height, 0, context.region.height
		)

		if transform.flip_x:
			left = transform.crop_right
			right = transform.crop_left
			min_x = region_x + img_x / 2 * region_size / 2 * (1 - left)
			max_x = region_x - img_x / 2 * region_size / 2 * (1 - right)
		else:
			left = transform.crop_left
			right = transform.crop_right
			min_x = region_x - img_x / 2 * region_size / 2 * (1 - left)
			max_x = region_x + img_x / 2 * region_size / 2 * (1 - right)
		if transform.flip_y:
			top = transform.crop_bottom
			bottom = transform.crop_top
			min_y = region_y + img_y / 2 * region_size / 2 * (1 - bottom)
			max_y = region_y - img_y / 2 * region_size / 2 * (1 - top)
		else:
			top = transform.crop_top
			bottom = transform.crop_bottom
			min_y = region_y - img_y / 2 * region_size / 2 * (1 - bottom)
			max_y = region_y + img_y / 2 * region_size / 2 * (1 - top)

		offset_x = references_overlays.x
		offset_y = references_overlays.y

		center_x = (min_x + max_x) / 2
		center_y = (min_y + max_y) / 2
		rotation_angle = transform.rotation * -1
		area = (
			(min_x + offset_x, min_y + offset_y),
			(max_x + offset_x, min_y + offset_y),
			(max_x + offset_x, max_y + offset_y),
			(min_x + offset_x, max_y + offset_y),
		)

		area = rotate_vertices(area, center_x, center_y, rotation_angle)

		if references_overlays.fit_view_distance:
			area = scale_vertices(
				area,
				context.region.width / 2,
				context.region.height / 2,
				1 / (context.area.spaces.active.region_3d.view_distance / 15),
			)

		area = scale_vertices(
			area,
			context.region.width / 2,
			context.region.height / 2,
			references_overlays.size,
		)

		if point_in_area(location, area):
			return 0
		else:
			return -1


class Overlay_Reference_UI_Control(bpy.types.GizmoGroup):
	bl_idname = "Overlay_Reference_UI_Control"
	bl_label = "Overlay Reference Control"
	bl_space_type = "VIEW_3D"
	bl_region_type = "WINDOW"
	bl_options = {"PERSISTENT", "SCALE"}

	def draw_gizmo(self, i):
		gizmo = self.gizmos.new(Overlay_Reference_Shape.bl_idname)
		gizmo.target_set_operator("screen.move_reference").index = i
		gizmo.use_draw_value = True
		gizmo.use_tooltip = True
		gizmo.index = i

	@classmethod
	def poll(cls, context):
		global _viewport_toggle_states
		vp_key = get_vp_key(context)
		if not vp_key or not _viewport_toggle_states.get(vp_key, False):
			return False
		return len(get_reference_prop(context).reference) > 0

	def draw_prepare(self, context):
		references_overlays = get_reference_prop(context)
		for i, item in enumerate(references_overlays.reference):
			if bpy.data.images.get(item.name):
				if i + 1 > len(self.gizmos):
					self.draw_gizmo(i)
				else:
					gizmo = self.gizmos[i]

					transform = get_image_transform_state(context, i)
					if not transform:
						continue

					gizmo.hide = transform.hide
					gizmo.hide_select = item.lock

					region_x = map_range(
						transform.x, 0, context.window.width, 0, context.region.width
					)
					region_y = map_range(
						transform.y, 0, context.window.height, 0, context.region.height
					)
					gizmo.matrix_basis[0][3] = region_x
					gizmo.matrix_basis[1][3] = region_y
			else:
				continue

	def setup(self, context):
		for i, item in enumerate(get_reference_prop(context).reference):
			self.draw_gizmo(i)


class REFERENCES_UL_Overlays(bpy.types.UIList):
	def draw_item(
		self, context, layout, data, item, icon, active_data, active_propname, index
	):
		if self.layout_type in {"DEFAULT"}:
			row = layout.row(align=True)

			# Check if the master overlay is enabled for this specific viewport
			from . import references_overlays
			vp_key = references_overlays.get_vp_key(context)
			is_overlay_enabled = references_overlays._viewport_toggle_states.get(vp_key, False) if vp_key else False

			transform = get_image_transform_state(context, index)

			if bpy.data.images.get(item.name):
				image = bpy.data.images[item.name]

				if transform:
					# FIX: Determine if the image is ACTUALLY visible in this viewport.
					# 1. Master overlay must be enabled.
					# 2. Specific image must not be hidden.
					# 3. Must pass orthographic filter.
					is_actually_visible = is_overlay_enabled and not transform.hide

					if is_actually_visible and transform.orthographic:
						view = get_view_orientations(context)
						if not (
							(transform.front and "Front" in view) or
							(transform.back and "Back" in view) or
							(transform.left and "Left" in view) or
							(transform.right and "Right" in view) or
							(transform.top and "Top" in view) or
							(transform.bottom and "Bottom" in view)
						):
							is_actually_visible = False

					# Always draw the eye icon, but force it to match the TRUE visibility state.
					icon_val = "HIDE_OFF" if is_actually_visible else "HIDE_ON"
					row.prop(
						transform,
						"hide",
						text="",
						icon=icon_val,
						emboss=False,
					)
				else:
					row.label(text="", icon="HIDE_OFF")

				# Dim the image name if it is not actually visible
				xrow = row.row()
				xrow.enabled = is_actually_visible

				if image.preview:
					xrow.prop(
						item,
						"tag_name",
						text="",
						icon_value=image.preview.icon_id,
						emboss=False,
					)
				else:
					xrow.prop(
						item, "tag_name", text="", icon="IMAGE_DATA", emboss=False
					)
			else:
				row.prop_search(item, "name", bpy.data, "images", text="")

			row.prop(
				item,
				"lock",
				text="",
				icon="LOCKED" if item.lock else "UNLOCKED",
				emboss=False,
			)
			row.operator(
				"screen.remove_references_slot", icon="X", text="", emboss=False
			).index = index

	def filter_items(self, context, data, propname):
		helper_funcs = bpy.types.UI_UL_list
		filtered = []
		ordered = []
		items = getattr(data, propname)
		filtered = helper_funcs.filter_items_by_name(
			self.filter_name,
			self.bitflag_filter_item,
			items,
			"name",
			reverse=self.use_filter_invert,
		)
		ordered = list(reversed(range(len(items))))
		return filtered, ordered


class OVERLAY_PT_Reference(bpy.types.Panel):
	bl_idname = "OVERLAY_PT_Reference"
	bl_options = {"DEFAULT_CLOSED"}
	bl_label = "References Overlay"
	bl_space_type = "VIEW_3D"
	bl_region_type = "HEADER"
	bl_ui_units_x = 16

	def draw(self, context):
		references_overlays = get_reference_prop(context)
		layout = self.layout
		layout.label(
			text="References Total " + str(len(references_overlays.reference)),
			icon="IMAGE_REFERENCE",
		)
		layout.prop(context.screen, "references_overlays_independent", text="Independent Screen")

		col = layout.column(align=True)

		row = col.row(align=True)
		row.prop(references_overlays, "full_lock", text="Full Lock")
		row.prop(references_overlays, "show_name", text="Show Tag Name")

		row = col.row(align=True)
		row.prop(references_overlays, "resize_image", text="Resize Image")
		row.prop(references_overlays, "tweak_size", text="Auto Tweak Size")

		row = col.row(align=True)
		row .prop(references_overlays, "fit_view_distance", text="Fit View Distance")

		row = layout.row(align=True)
		row.operator("screen.load_references", icon="FILEBROWSER", text="Load Image")
		row.operator("screen.paste_reference", icon="PASTEDOWN", text="")

		if context.screen.references_overlays_independent:

			active = False
			for screen in bpy.data.screens:
				if len(screen.references_overlays.reference) > 0 and screen.name != context.screen.name:
					active = True
					break

			if not active and len(context.scene.references_overlays.reference) > 0:
				active = True

			row = layout.row(align=True)
			row.enabled = active
			row.operator("wm.call_menu", text="Append", icon='PASTEDOWN').name='OVERLAY_MT_Append_References'
			row.operator("wm.call_menu", text="Override").name='OVERLAY_MT_Override_References'

		else:
			row = layout.row(align=True)
			row.operator(
				"scene.propagate_reference_transforms",
				text="Propagate Transforms to All Viewports",
				icon="FILE_REFRESH",
			)

		row = layout.row()
		row.template_list(
			"REFERENCES_UL_Overlays",
			"",
			references_overlays,
			"reference",
			references_overlays,
			"reference_index",
		)
		col = row.column(align=True)
		col.operator("screen.add_references_slot", icon="ADD", text="")
		col.operator(
			"screen.remove_references_slot", icon="REMOVE", text=""
		).index = references_overlays.reference_index
		col.separator()

		sub = col.column(align=True)
		sub.enabled = len(references_overlays.reference) > 0

		if context.screen.references_overlays_independent:
			list_path = "screen.references_overlays.reference"
			active_index_path = "screen.references_overlays.reference_index"
		else:
			list_path = "scene.references_overlays.reference"
			active_index_path = "scene.references_overlays.reference_index"

		up = sub.operator("uilist.list_move_reference", icon="TRIA_UP", text="")
		up.list_path = list_path
		up.active_index_path = active_index_path
		up.direction = "DOWN"

		down = sub.operator("uilist.list_move_reference", icon="TRIA_DOWN", text="")
		down.list_path = list_path
		down.active_index_path = active_index_path
		down.direction = "UP"

		col.separator()

		col.operator("screen.clear_references_slot", icon="TRASH", text="")

		if len(references_overlays.reference) == 0:
			return

		item = references_overlays.reference[references_overlays.reference_index]
		transform = get_image_transform_state(
			context, references_overlays.reference_index
		)
		if not transform:
			return

		image = bpy.data.images.get(item.name)
		if not image:
			return

		col = layout.column()
		row = col.row(align=True)
		xrow = row.row(align=True)
		xrow.alignment = "LEFT"
		xrow.prop(
			transform,
			"hide",
			text="",
			icon="HIDE_ON" if transform.hide else "HIDE_OFF",
			invert_checkbox=True,
		)
		xrow = row.row(align=True)
		xrow.prop(item, "tag_name", text="")
		xrow.prop(
			item,
			"lock",
			text="",
			icon="LOCKED" if item.lock else "UNLOCKED",
		)
		xrow.operator(
			"screen.rest_reference", icon="FILE_REFRESH", text=""
		).index = references_overlays.reference_index


		col = layout.column()
		col.use_property_split = True
		col.use_property_decorate = False

		if image.preview:
			header, panel = col.panel(idname="reference_preview", default_closed=False)
			header.label(text="Image Preview")
			if panel:
				panel.template_icon(image.preview.icon_id, scale=10.0)

		header, panel = col.panel(idname="reference_path", default_closed=False)
		header.label(text="Path")
		if panel:
			panel.use_property_split = True
			panel.use_property_decorate = False

			row = panel.row(align=True)
			row.prop_search(item, "name", bpy.data, "images", text="")

			row = panel.row(align=True)
			xrow = row.row(align=True)
			xrow.alignment = "LEFT"
			xrow.label(text="Path")
			xrow = row.row(align=True)
			xrow.prop(image, "filepath", text="")

		header, panel = col.panel(idname="reference_color", default_closed=False)
		header.label(text="Color")
		if panel:
			sub = panel.column()
			sub.prop(image.colorspace_settings, "name", text="Color Space")

			row = sub.row(align=True, heading="Color Mode")
			row.prop(
				transform, "grayscale", text="Color", toggle=True, invert_checkbox=True
			)
			row.prop(transform, "grayscale", text="Grayscale", toggle=True)

			sub.prop(transform, "opacity", text="Alpha", slider=True)

		if image.source in {"SEQUENCE", "MOVIE"}:
			header, panel = col.panel(idname="reference_sequence", default_closed=False)
			header.label(text="Sequence")
			if panel:
				sub = panel.column(align=True)
				sub.prop(item, "fps", text="FPS Tempo")
				sub.prop(item, "speed", text="Speed")
				sub.prop(item, "frame_offset", text="Offset")
				sub.prop(item, "use_cyclic", text="Cyclic")

		header, panel = col.panel(idname="reference_transform", default_closed=False)
		header.label(text="Transform")
		if panel:
			sub = panel.column()
			subcol = sub.column(align=True)
			subcol.prop(transform, "x", text="Position X")
			subcol.prop(transform, "y", text="Y")

			sub.prop(transform, "rotation", text="Rotation")
			sub.prop(transform, "size", text="Size")

		header, panel = col.panel(idname="reference_visual", default_closed=False)
		header.label(text="Visual")
		if panel:
			sub = panel.column()

			sub.row().prop(transform, "depth_set", text="Depth", expand=True)

			row = sub.row(align=True, heading="Flip")
			row.prop(transform, "flip_x", text="X", toggle=True)
			row.prop(transform, "flip_y", text="Y", toggle=True)

		header, panel = col.panel(idname="crop_reference", default_closed=True)
		header.label(text="Crop")
		if panel:
			sub = panel.column(align=True)
			sub.prop(transform, "crop_left", text="Left")
			sub.prop(transform, "crop_top", text="Top")
			sub.prop(transform, "crop_right", text="Right")
			sub.prop(transform, "crop_bottom", text="Bottom")

		header, panel = col.panel(idname="orthographic", default_closed=True)
		header.use_property_split = False
		header.use_property_decorate = False
		header.prop(transform, "orthographic", text="Only Orthographic")
		if panel:
			panel.active = transform.orthographic
			sub = panel.column(align=True)
			row = sub.row(align=True)
			row.prop(transform, "front", toggle=True)
			row.prop(transform, "left", toggle=True)
			row.prop(transform, "top", toggle=True)

			row = sub.row(align=True)
			row.prop(transform, "back", toggle=True)
			row.prop(transform, "right", toggle=True)
			row.prop(transform, "bottom", toggle=True)

		header, panel = col.panel(idname="align_reference", default_closed=True)
		header.label(text="Alignment")
		if panel:
			xrow = panel.row()
			xrow.label(text="Align")
			sub = xrow.column(align=True)
			colrow = sub.row(align=True)
			op = colrow.operator("screen.align_reference", icon="BLANK1", text="")
			op.align_x = "LEFT"
			op.align_y = "UP"
			op = colrow.operator("screen.align_reference", icon="TRIA_UP_BAR", text="")
			op.align_x = "CENTER"
			op.align_y = "UP"
			op = colrow.operator("screen.align_reference", icon="BLANK1", text="")
			op.align_x = "RIGHT"
			op.align_y = "UP"
			colrow = sub.row(align=True)
			op = colrow.operator("screen.align_reference", icon="TRIA_LEFT_BAR", text="")
			op.align_x = "LEFT"
			op.align_y = "CENTER"
			op = colrow.operator("screen.align_reference", icon="LAYER_ACTIVE", text="")
			op.align_x = "CENTER"
			op.align_y = "CENTER"
			op = colrow.operator("screen.align_reference", icon="TRIA_RIGHT_BAR", text="")
			op.align_x = "RIGHT"
			op.align_y = "CENTER"
			colrow = sub.row(align=True)
			op = colrow.operator("screen.align_reference", icon="BLANK1", text="")
			op.align_x = "LEFT"
			op.align_y = "DOWN"
			op = colrow.operator("screen.align_reference", icon="TRIA_DOWN_BAR", text="")
			op.align_x = "CENTER"
			op.align_y = "DOWN"
			op = colrow.operator("screen.align_reference", icon="BLANK1", text="")
			op.align_x = "RIGHT"
			op.align_y = "DOWN"

class OVERLAY_MT_Append_References(bpy.types.Menu):
	bl_idname = "OVERLAY_MT_Append_References"
	bl_label = "Append References"

	def draw(self, context):
		layout = self.layout

		op = layout.operator("screen.copy_references_from", icon = "PASTEDOWN", text = "Scene")
		op.name = ".*Scene"
		op.override = False

		layout.separator()

		for screen in bpy.data.screens:
			if len(screen.references_overlays.reference) > 0 and screen.name != context.screen.name:
				op = layout.operator("screen.copy_references_from", icon = "PASTEDOWN", text = screen.name)
				op.name = screen.name
				op.override = False

class OVERLAY_MT_Override_References(bpy.types.Menu):
	bl_idname = "OVERLAY_MT_Override_References"
	bl_label = "Override References"

	def draw(self, context):
		layout = self.layout

		op = layout.operator("screen.copy_references_from", icon = "PASTEDOWN", text = "Scene")
		op.name = ".*Scene"
		op.override = True

		layout.separator()

		for screen in bpy.data.screens:
			if len(screen.references_overlays.reference) > 0 and screen.name != context.screen.name:
				op = layout.operator("screen.copy_references_from", icon = "PASTEDOWN", text = screen.name)
				op.name = screen.name
				op.override = True

def references_overlays_header(self, context):
	global _viewport_toggle_states

	layout = self.layout
	row = layout.row(align=True)

	vp_key = get_vp_key(context)
	is_enabled = _viewport_toggle_states.get(vp_key, False) if vp_key else False

	op = row.operator(
		"screen.toggle_references_overlays",
		text="",
		icon="IMAGE_REFERENCE",
		depress=is_enabled,
	)

	sub = row.row(align=True)
	sub.popover(panel="OVERLAY_PT_Reference", text="")


class References_Overlays_OT_AddHotkey(bpy.types.Operator):
	bl_idname = "references_overlays.add_hotkey"
	bl_label = "Add Hotkey"
	bl_options = {"REGISTER", "INTERNAL"}

	def execute(self, context):
		add_hotkey()
		return {"FINISHED"}

def add_hotkey():
	wm = bpy.context.window_manager
	kc = wm.keyconfigs.addon

	if kc:
		km = kc.keymaps.new(name="3D View", space_type="VIEW_3D")
		kmi = km.keymap_items.new(
			"screen.toggle_references_overlays", "R", "PRESS", alt=True, shift=True
		)
		kmi.active = True
		addon_keymaps.append((km, kmi))

		km = kc.keymaps.new(name="3D View", space_type="VIEW_3D")
		kmi = km.keymap_items.new(
			"screen.toggle_lock_references_overlays", "T", "PRESS", ctrl=True
		)
		kmi.active = True
		addon_keymaps.append((km, kmi))

		km = kc.keymaps.new(name="3D View", space_type="VIEW_3D")
		kmi = km.keymap_items.new("screen.paste_reference", "V", "PRESS", shift=True)
		kmi.active = True
		addon_keymaps.append((km, kmi))

		km = kc.keymaps.new(name="3D View", space_type="VIEW_3D")
		kmi = km.keymap_items.new(
			"screen.global_move_reference", "W", "PRESS", ctrl=True
		)
		kmi.active = True
		addon_keymaps.append((km, kmi))


def remove_hotkey():
	wm = bpy.context.window_manager
	kc = wm.keyconfigs.addon

	keymaps_to_remove = ["3D View"]

	for keymap_name in keymaps_to_remove:
		keymap = kc.keymaps.get(keymap_name)
		if keymap:
			keymap_items = [kmi for kmi in keymap.keymap_items if kmi in addon_keymaps]
			for kmi in keymap_items:
				keymap.keymap_items.remove(kmi)
			kc.keymaps.remove(keymap)

	addon_keymaps.clear()


addon_keymaps = []

# IMPORTANT: Registration order matters! Dependencies must be registered first.
classes = (
	ImageTransformState,
	ViewportState,
	References,
	Reference_Overlay_Props,
	Overlay_Reference_Shape,
	Overlay_Reference_UI_Control,
	REFERENCES_UL_Overlays,
	OVERLAY_PT_Reference,
	OVERLAY_MT_Append_References,
	OVERLAY_MT_Override_References,
	References_Overlays_OT_AddHotkey,
)


def register():
	for cls in classes:
		bpy.utils.register_class(cls)

	bpy.types.Scene.references_overlays = bpy.props.PointerProperty(
		type=Reference_Overlay_Props
	)

	bpy.types.Screen.references_overlays = bpy.props.PointerProperty(
		type=Reference_Overlay_Props
	)

	bpy.types.Screen.references_overlays_independent = bpy.props.BoolProperty(
		name="Independent Screen",
		default=False,
	)

	add_hotkey()

	bpy.types.VIEW3D_HT_header.append(references_overlays_header)

	bpy.app.handlers.load_post.append(restore_overlay_states)


def unregister():
	if restore_overlay_states in bpy.app.handlers.load_post:
		bpy.app.handlers.load_post.remove(restore_overlay_states)

	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)

	bpy.types.VIEW3D_HT_header.remove(references_overlays_header)

	remove_hotkey()

	del bpy.types.Scene.references_overlays

	del bpy.types.Screen.references_overlays

	del bpy.types.Screen.references_overlays_independent
