import bpy
import sys
import os
import math
import tempfile
import subprocess
from datetime import datetime
from bpy_extras.io_utils import ImportHelper
from .preference import ensure_pillow
from .defs import *

class Load_References_OT(bpy.types.Operator, ImportHelper):
	bl_idname = "screen.load_references"
	bl_label = "Load References"
	bl_description = "Load References"
	bl_options = {'REGISTER', 'UNDO'}
	
	filename_ext = '.bmp, .tiff, .png, .jpg, .jpeg, .gif, .mp4, .webm'  # List of acceptable image file extensions
	
	filter_glob: bpy.props.StringProperty(
		default='*.bmp;*.tiff;*.png;*.jpg;*.jpeg;*.gif;*.mp4;*.webm',  # Update the default filter to include multiple image types
		options={'HIDDEN'}
	)

	directory: bpy.props.StringProperty(
			subtype='DIR_PATH',
	)
	
	files: bpy.props.CollectionProperty(
			type=bpy.types.OperatorFileListElement,
	)

	def execute(self, context):
		references_overlays = context.screen.references_overlays

		directory = self.directory

		for file_elem in self.files:
			image_path = os.path.join(directory, file_elem.name)
			blend_dir = os.path.dirname(bpy.data.filepath)
			# Try common relative directory patterns
			if os.path.exists(blend_dir):
				folders = os.listdir(blend_dir)
				folders.extend(['..', '../..'])
				for relative_dir in folders:
					test_path = os.path.join(blend_dir, relative_dir, file_elem.name)
					if os.path.exists(test_path):
						image_path = os.path.join('//'+relative_dir, file_elem.name)
						break
				
			if bpy.data.images.get(file_elem.name):
				image =  bpy.data.images[file_elem.name]
			else:
				image = bpy.data.images.load(image_path)

			image.use_fake_user = True
			item = references_overlays.reference.add()
			item.name = image.name
			item.x = image.size[0]/4
			item.y = image.size[1]/4
			item.fps = context.scene.render.fps
			if image.source in {'SEQUENCE', 'MOVIE'}:
				item.use_cyclic = True

		references_overlays.reference_index = len(references_overlays.reference) - 1

		self.report({'INFO'}, f"Loaded {file_elem.name} Image.")

		return {'FINISHED'}
	
class Add_References_OT(bpy.types.Operator):
	bl_idname = "screen.add_references_slot"
	bl_label = "Add References Slots"
	bl_description = "Add References Slots"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		references_overlays = context.screen.references_overlays
		item = references_overlays.reference.add()
		item.fps = context.scene.render.fps
		references_overlays.reference_index = len(references_overlays.reference) - 1
		return{'FINISHED'}
	
class Rest_References_OT(bpy.types.Operator):
	bl_idname = "screen.rest_reference"
	bl_label = "Rest References"
	bl_description = "Rest References"
	bl_options = {'REGISTER', 'UNDO'}

	index : bpy.props.IntProperty(options={'HIDDEN'})

	def execute(self, context):

		references_overlays = context.screen.references_overlays
		item = references_overlays.reference[self.index]
		image = bpy.data.images[item.name]

		item.size = 1
		item.rotation = 0
		item.x = image.size[0]/4
		item.y = image.size[1]/4
		item.flip_x = False
		item.flip_y = False
		item.opacity = 1
		item.depth_set = 'Default'
		item.pivot_x = 0
		item.pivot_y = 0
		item.zoom = 0
		item.crop_left = 0
		item.crop_right = 0
		item.crop_top = 0
		item.crop_bottom = 0

		item.fps = context.scene.render.fps

		return{'FINISHED'}

class Remove_References_OT(bpy.types.Operator):
	bl_idname = "screen.remove_references_slot"
	bl_label = "Remove References Slots"
	bl_description = "Remove References Slots"
	bl_options = {'REGISTER', 'UNDO'}

	index : bpy.props.IntProperty(options={'HIDDEN'})

	def execute(self, context):
		references_overlays = context.screen.references_overlays
		references_overlays.reference.remove(self.index)

		if references_overlays.reference_index > len(references_overlays.reference) - 1:
			references_overlays.reference_index = references_overlays.reference_index - 1

		return{'FINISHED'}

class Clear_References_OT(bpy.types.Operator):
	bl_idname = "screen.clear_references_slot"
	bl_label = "Clear References Slots"
	bl_description = "Clear References Slots"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):

		references_overlays = context.screen.references_overlays
		references_overlays.reference.clear()

		references_overlays.reference_index = 0

		return{'FINISHED'}

class Copy_References_From_OT(bpy.types.Operator):
	bl_idname = "screen.copy_references_from"
	bl_label = "Copy References From Other Screen"
	bl_description = "Copy References From Other Screen"
	bl_options = {'REGISTER', 'UNDO'}

	name : bpy.props.StringProperty(options={'HIDDEN'})
	override : bpy.props.BoolProperty(name='Override References', default=False)

	def invoke(self, context, event):
		wm = context.window_manager
		return wm.invoke_props_dialog(self)

	def execute(self, context):
		current = context.screen.references_overlays
		target = bpy.data.screens[self.name].references_overlays

		if self.override:
			current.reference.clear()

		for target_item in target.reference:
			item = current.reference.add()
			item.name = target_item.name
			item.size = target_item.size
			item.flip_x = target_item.flip_x
			item.flip_y = target_item.flip_y
			item.rotation = target_item.rotation
			item.x = target_item.x
			item.y = target_item.y
			item.opacity = target_item.opacity
			item.depth_set = target_item.depth_set
			item.speed = target_item.speed
			item.use_cyclic = target_item.use_cyclic
			item.frame_offset = target_item.frame_offset
			item.hide = target_item.hide
			item.lock = target_item.lock
			item.fps = target_item.fps
			item.tag_name = target_item.tag_name
			item.pivot_x = target_item.pivot_x 
			item.pivot_y = target_item.pivot_y
			item.zoom = target_item.zoom
			item.crop_left = target_item.crop_left
			item.crop_right = target_item.crop_right
			item.crop_top = target_item.crop_top
			item.crop_bottom = target_item.crop_bottom

		if target.overlays_toggle == True:
			target.overlays_toggle = False
			target.overlays_toggle = True

		self.report({'INFO'}, f"Copyed {self.name} References.")

		return{'FINISHED'}

class Move_References_OT(bpy.types.Operator):
	bl_idname = "screen.move_reference"
	bl_label = "Move References"
	bl_description = "Move References"
	bl_options = {'REGISTER', 'UNDO'}

	index : bpy.props.IntProperty(options={'HIDDEN'})

	hide = None
	mouse_region_x = None
	mouse_region_y = None
	x = None
	y = None
	flip_x = None
	flip_y = None
	size = None
	rotation = None
	pivot_x = None
	pivot_y = None
	zoom = None
	opacity= None
	depth_set = None

	def modal(self, context, event):
		context.area.tag_redraw()
		references_overlays = context.screen.references_overlays
		item = references_overlays.reference[self.index]
		
		if event.type == 'ONE':
			item.depth_set = 'Default'
		elif event.type == 'TWO':
			item.depth_set = 'Back'

		if event.shift:
			value = 0.2
		else:
			value = 1

		if event.alt:
			
			if event.type == 'MOUSEMOVE':
				item.pivot_x = self.pivot_x + (event.mouse_region_x - self.mouse_region_x)/(context.window.width/2)*-1 * value
				item.pivot_y = self.pivot_y + (event.mouse_region_y - self.mouse_region_y)/(context.window.width/2)*-1 * value

			if event.type == 'WHEELUPMOUSE':
				# Handle mouse scroll up events
				item.zoom = item.zoom + 0.05 * value
				
			elif event.type == 'WHEELDOWNMOUSE':
				# Handle mouse scroll down events
				item.zoom = item.zoom - 0.05 * value

			elif event.type == 'S':
				item.zoom = 0

			elif event.type == 'R':
				item.pivot_x = 0
				item.pivot_y = 0
				self.mouse_region_x = event.mouse_region_x
				self.mouse_region_y = event.mouse_region_y

		else:

			if event.type == 'MOUSEMOVE':
				if references_overlays.fit_view_distance:
					view_distance = context.area.spaces.active.region_3d.view_distance/15
				else:
					view_distance = 1

				map_range_x = map_range(self.mouse_region_x, 0, context.region.width, 0, context.window.width*view_distance)
				map_range_y = map_range(self.mouse_region_y, 0, context.region.height, 0, context.window.height*view_distance)

				region_x = map_range(event.mouse_region_x, 0, context.region.width, 0, context.window.width*view_distance) + (map_range_x - self.x)*-1
				region_y = map_range(event.mouse_region_y, 0, context.region.height, 0, context.window.height*view_distance) + (map_range_y - self.y)*-1

				if event.ctrl:
					if event.shift:
						snap_value = 25
					else:
						snap_value = 50  # Grid size for snapping
					item.x = round(region_x / snap_value) * snap_value
					item.y = round(region_y / snap_value) * snap_value
				else:
					item.x = region_x 
					item.y = region_y

			elif event.type == 'WHEELUPMOUSE':
				# Handle mouse scroll up events
				if event.shift:
					item.size = item.size * 1.025
				else:
					item.size = item.size * 1.1
				
			elif event.type == 'WHEELDOWNMOUSE':
				# Handle mouse scroll down events
				if event.shift:
					item.size = item.size * 0.975
				else:
					item.size = item.size * 0.9

			elif event.type == 'S':
				item.size = 1

			elif event.type == 'R':
				item.rotation = 0

			elif event.type == 'C':
				item.opacity = item.opacity + 0.1
			elif event.type == 'Z':
				item.opacity = item.opacity - 0.1

			elif event.type == 'E':
				item.rotation += math.radians(5) * value # Default rotation increment

			elif event.type == 'Q':
				item.rotation -= math.radians(5) * value # Default rotation increment

			elif event.type in {'X','DEL'}:
				bpy.ops.screen.remove_references_slot(index = self.index)
				return {'FINISHED'}
			
		if event.type == 'LEFTMOUSE':
			return {'FINISHED'}

		if event.type in {'RIGHTMOUSE', 'ESC'}:
			item.x = self.x
			item.y = self.y 
			item.pivot_x = self.pivot_x
			item.pivot_y = self.pivot_y
			item.zoom = self.zoom
			item.size = self.size
			item.rotation = self.rotation
			item.opacity = self.opacity
			item.depth_set = self.depth_set
			item.hide = self.hide
			item.lock = self.lock
			return {'CANCELLED'}

		return {'RUNNING_MODAL'}
	
	def invoke(self, context, event):
		if context.area.type == 'VIEW_3D':
			references_overlays = context.screen.references_overlays
			references_overlays.reference_index = self.index
			item = references_overlays.reference[self.index]
			self.lock = item.lock
			self.hide = item.hide
			self.x = item.x
			self.y = item.y 
			self.size = item.size
			self.rotation = item.rotation 
			self.opacity = item.opacity
			self.depth_set = item.depth_set
			self.flip_x = item.flip_x
			self.flip_y = item.flip_y		
			self.pivot_x = item.pivot_x
			self.pivot_y = item.pivot_y
			self.zoom = item.zoom

			self.mouse_region_x = event.mouse_region_x
			self.mouse_region_y = event.mouse_region_y

			# The arguments we pass the callback.
			context.window_manager.modal_handler_add(self)
			return {'RUNNING_MODAL'}
		else:
			self.report({'WARNING'}, "View3D not found, cannot run operator")
			return {'CANCELLED'}

class Global_Move_References_OT(bpy.types.Operator):
	bl_idname = "screen.gobal_move_reference"
	bl_label = "Global Move References"
	bl_description = "Move References"
	bl_options = {'REGISTER', 'UNDO'}

	mouse_region_x = None
	mouse_region_y = None
	x = None
	y = None
	size = None
	pivot_x = None
	pivot_y = None

	def modal(self, context, event):
		context.area.tag_redraw()
		item = context.screen.references_overlays
		
		if event.type == 'MOUSEMOVE':
			region_x = self.x + event.mouse_region_x - self.mouse_region_x
			region_y = self.y + event.mouse_region_y - self.mouse_region_y

			if event.shift:
				if event.shift:
					snap_value = 25
				else:
					snap_value = 50  # Grid size for snapping
				item.x = round(region_x / snap_value) * snap_value
				item.y = round(region_y / snap_value) * snap_value
			else:
				item.x = region_x 
				item.y = region_y

		elif event.type == 'WHEELUPMOUSE':
			# Handle mouse scroll up events
			if event.shift:
				item.size = item.size * 1.025
			else:
				item.size = item.size * 1.1
			
		elif event.type == 'WHEELDOWNMOUSE':
			# Handle mouse scroll down events
			if event.shift:
				item.size = item.size * 0.975
			else:
				item.size = item.size * 0.9

		elif event.type == 'S':
			item.size = 1

		elif event.type == 'R':
			item.x = 0
			item.y = 0
			
		if event.type == 'LEFTMOUSE':
			return {'FINISHED'}

		if event.type in {'RIGHTMOUSE', 'ESC'}:
			item.x = self.x
			item.y = self.y 
			item.pivot_x = self.pivot_x
			item.pivot_y = self.pivot_y
			item.size = self.size
			return {'CANCELLED'}

		return {'RUNNING_MODAL'}
	
	def invoke(self, context, event):
		if context.area.type == 'VIEW_3D':
			item = context.screen.references_overlays
			self.x = item.x
			self.y = item.y
			self.mouse_region_x = event.mouse_region_x
			self.mouse_region_y = event.mouse_region_y
			self.size = item.size	

			# The arguments we pass the callback.
			context.window_manager.modal_handler_add(self)
			return {'RUNNING_MODAL'}
		else:
			self.report({'WARNING'}, "View3D not found, cannot run operator")
			return {'CANCELLED'}

class Align_References_OT(bpy.types.Operator):
	bl_idname = "screen.align_reference"
	bl_label = "Align References"
	bl_description = "Align References"
	bl_options = {'REGISTER', 'UNDO'}

	align_x : bpy.props.StringProperty(name='Align X', options={'HIDDEN'})
	align_y : bpy.props.StringProperty(name='Align Y', options={'HIDDEN'})

	def execute(self, context):
		references_overlays = context.screen.references_overlays
		item = references_overlays.reference[references_overlays.reference_index]
		image = bpy.data.images[item.name]

		region_width = context.window.width
		region_height = context.window.height

		if self.align_x == 'LEFT':
			item.x = image.size[0]/2 * item.size/2
		elif self.align_x == 'RIGHT':
			item.x = region_width - image.size[0]/2 * item.size/2
		elif self.align_x == 'CENTER':
			item.x = region_width/2

		if self.align_y == 'DOWN':
			item.y = image.size[1]/2 * item.size/2
		elif self.align_y == 'UP':
			item.y = region_height - image.size[1]/2 * item.size/2
		elif self.align_y == 'CENTER':
			item.y = region_height/2
		bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)

		return{'FINISHED'}

class Toggle_References_OT(bpy.types.Operator):
	bl_idname = "screen.toggle_references_overlays"
	bl_label = "Toggle References Overlays"
	bl_description = "Toggle References Overlays"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		context.screen.references_overlays.overlays_toggle = not context.screen.references_overlays.overlays_toggle
		context.area.tag_redraw()
		return {'FINISHED'}

class Toggle_Lock_References_OT(bpy.types.Operator):
	bl_idname = "screen.toggle_lock_references_overlays"
	bl_label = "Toggle Lock References Overlays"
	bl_description = "Toggle Lock References Overlays"
	bl_options = {'REGISTER', 'UNDO'}

	@classmethod
	def poll(cls, context):
		return context.screen.references_overlays.overlays_toggle

	def execute(self, context):
		context.screen.references_overlays.full_lock = not context.screen.references_overlays.full_lock
		if context.screen.references_overlays.full_lock == True:
			self.report({'INFO'}, "References Overlays ignore mouse events.")
		else:
			self.report({'INFO'}, "References Overlays is unlocked.")
		return {'FINISHED'}

class Toggle_Grayscale_References_OT(bpy.types.Operator):
	bl_idname = "screen.toggle_grayscale_references_overlays"
	bl_label = "Toggle References Overlays Grayscale Mode"
	bl_description = "Toggle References Overlays Grayscale Mode"
	bl_options = {'REGISTER', 'UNDO'}

	@classmethod
	def poll(cls, context):
		return context.screen.references_overlays.overlays_toggle

	def execute(self, context):
		context.screen.references_overlays.grayscale = not context.screen.references_overlays.grayscale
		bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
		if context.screen.references_overlays.full_lock == True:
			self.report({'INFO'}, "References Overlays Grayscale Mode is on.")
		else:
			self.report({'INFO'}, "References Overlays Grayscale Mode is off.")
		return {'FINISHED'}

class Paste_References_OT(bpy.types.Operator):
	"""Paste Reference from the clipboard"""
	bl_idname = "screen.paste_reference"
	bl_label = "Paste Reference from the clipboard"
	bl_options = {'REGISTER', 'UNDO'}

	x: bpy.props.FloatProperty(options={'HIDDEN'})
	y: bpy.props.FloatProperty(options={'HIDDEN'})

	def invoke(self, context, event):
		self.x = map_range(event.mouse_region_x, 0, context.region.width, 0,context.window.width)
		self.y = map_range(event.mouse_region_y, 0, context.region.height, 0,context.window.height)
		return self.execute(context)

	def execute(self, context):
		try:
			from PIL import ImageGrab, Image
			image = ImageGrab.grabclipboard()
			if isinstance(image, Image.Image):
				temp_dir = tempfile.gettempdir()
				current_time = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
				temp_path = os.path.join(temp_dir, f"{current_time}_clipboard.png")
				image.save(temp_path)
				
				img = bpy.data.images.load(temp_path)
				img.use_fake_user = True

				references_overlays = context.screen.references_overlays
				item = references_overlays.reference.add()
				item.name = img.name
				item.x = self.x
				item.y = self.y
				if context.screen.references_overlays.overlays_toggle == False:
					context.screen.references_overlays.overlays_toggle = True

				if context.screen.references_overlays.full_lock == True:
					context.screen.references_overlays.full_lock = False
				
				self.report({'INFO'}, f"Image pasted from clipboard {current_time}")

			else:
				self.report({'WARNING'}, "No image in clipboard")
		except ImportError:
			self.report({'ERROR'}, "Pillow is not installed. Please install Pillow from the add-on preferences and restart Blender.")
		except Exception as e:
			self.report({'ERROR'}, str(e))
		
		return {'FINISHED'}

class InstallPillow_OT(bpy.types.Operator):
	"""Install or update Pillow"""
	bl_idname = "preferences.install_pillow"
	bl_label = "Install / Update Pillow"

	def execute(self, context):
		try:
			import ensurepip
			ensurepip.bootstrap()
			python_exe = getattr(bpy.app, 'binary_path_python', None) or sys.executable
			subprocess.check_call([python_exe, "-m", "pip", "install", "--upgrade", "Pillow"])
			if not ensure_pillow():
				self.report({'ERROR'}, "Failed to verify Pillow installation after installation.")
			else:
				self.report({'INFO'}, "Pillow installed or updated successfully. Please restart Blender.")
		except Exception as e:
			self.report({'ERROR'}, f"Failed to install or update Pillow: {e}")
		return {'FINISHED'}

classes = (
	 Load_References_OT,
	 Add_References_OT,
	 Remove_References_OT,
	 Rest_References_OT,
 	 Clear_References_OT,
	 Copy_References_From_OT,
	 Move_References_OT,
	 Global_Move_References_OT,
	 Align_References_OT,
	 Toggle_References_OT,
	 Toggle_Lock_References_OT,
	 Toggle_Grayscale_References_OT,
	 Paste_References_OT,
	 InstallPillow_OT,
)

def register():
	for cls in classes:
		bpy.utils.register_class(cls)

def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)