import math
import os
import tempfile
from datetime import datetime

import bpy
import mathutils
from bpy_extras.io_utils import ImportHelper

from .defs import *


class Load_References_OT(bpy.types.Operator, ImportHelper):
    bl_idname = "screen.load_references"
    bl_label = "Load References"
    bl_description = "Load References"
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ".bmp, .tiff, .png, .jpg, .jpeg, .gif, .mp4, .webm"

    filter_glob: bpy.props.StringProperty(
        default="*.bmp;*.tiff;*.png;*.jpg;*.jpeg;*.gif;*.mp4;*.webm", options={"HIDDEN"}
    )

    directory: bpy.props.StringProperty(subtype="DIR_PATH")
    files: bpy.props.CollectionProperty(type=bpy.types.OperatorFileListElement)

    def execute(self, context):
        from . import references_overlays

        references_overlays_props = context.scene.references_overlays

        directory = self.directory

        for file_elem in self.files:
            image_path = os.path.join(directory, file_elem.name)
            blend_dir = os.path.dirname(bpy.data.filepath)
            if os.path.exists(blend_dir):
                folders = os.listdir(blend_dir)
                folders.extend(["..", "../.."])
                for relative_dir in folders:
                    test_path = os.path.join(blend_dir, relative_dir, file_elem.name)
                    if os.path.exists(test_path):
                        image_path = os.path.join("//" + relative_dir, file_elem.name)
                        break

            if bpy.data.images.get(file_elem.name):
                image = bpy.data.images[file_elem.name]
            else:
                image = bpy.data.images.load(image_path)

            image.use_fake_user = True
            item = references_overlays_props.reference.add()
            item.name = image.name

            new_index = len(references_overlays_props.reference) - 1
            init_x = image.size[0] / 4
            init_y = image.size[1] / 4

            references_overlays.initialize_transform_for_all_viewports(
                context, new_index, init_x, init_y
            )

            item.fps = context.scene.render.fps
            if image.source in {"SEQUENCE", "MOVIE"}:
                item.use_cyclic = True

        references_overlays_props.reference_index = (
            len(references_overlays_props.reference) - 1
        )

        vp_key = references_overlays.get_vp_key(context)
        if vp_key:
            references_overlays._viewport_toggle_states[vp_key] = True
            vp_state = references_overlays.get_current_viewport_state(context)
            if vp_state:
                vp_state.is_enabled = True

        self.report({"INFO"}, f"Loaded {file_elem.name} Image.")

        return {"FINISHED"}


class Add_References_OT(bpy.types.Operator):
    bl_idname = "screen.add_references_slot"
    bl_label = "Add References Slots"
    bl_description = "Add References Slots"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        from . import references_overlays

        references_overlays_props = context.scene.references_overlays
        item = references_overlays_props.reference.add()
        item.fps = context.scene.render.fps

        new_index = len(references_overlays_props.reference) - 1
        references_overlays_props.reference_index = new_index

        references_overlays.initialize_transform_for_all_viewports(context, new_index)

        vp_key = references_overlays.get_vp_key(context)
        if vp_key:
            references_overlays._viewport_toggle_states[vp_key] = True
            vp_state = references_overlays.get_current_viewport_state(context)
            if vp_state:
                vp_state.is_enabled = True

        return {"FINISHED"}


class Rest_References_OT(bpy.types.Operator):
    bl_idname = "screen.rest_reference"
    bl_label = "Rest References"
    bl_description = "Rest References"
    bl_options = {"REGISTER", "UNDO"}

    index: bpy.props.IntProperty(options={"HIDDEN"})

    def execute(self, context):
        from . import references_overlays

        references_overlays_props = context.scene.references_overlays
        item = references_overlays_props.reference[self.index]
        transform = references_overlays.get_image_transform_state(context, self.index)
        if not transform:
            return {"CANCELLED"}

        image = bpy.data.images[item.name]

        transform.size = 1
        transform.rotation = 0
        transform.x = image.size[0] / 4
        transform.y = image.size[1] / 4
        transform.flip_x = False
        transform.flip_y = False
        transform.opacity = 1
        transform.depth_set = "Default"
        transform.pivot_x = 0
        transform.pivot_y = 0
        transform.zoom = 0
        transform.crop_left = 0
        transform.crop_right = 0
        transform.crop_top = 0
        transform.crop_bottom = 0
        transform.hide = False
        transform.grayscale = False
        transform.orthographic = False
        transform.front = True
        transform.back = False
        transform.left = False
        transform.right = False
        transform.top = False
        transform.bottom = False
        transform.lock_position = False

        item.fps = context.scene.render.fps

        return {"FINISHED"}


class Remove_References_OT(bpy.types.Operator):
    bl_idname = "screen.remove_references_slot"
    bl_label = "Remove References Slots"
    bl_description = "Remove References Slots"
    bl_options = {"REGISTER", "UNDO"}

    index: bpy.props.IntProperty(options={"HIDDEN"})

    def execute(self, context):
        from . import references_overlays

        references_overlays_props = context.scene.references_overlays
        idx = self.index

        references_overlays_props.reference.remove(idx)

        # Remove the corresponding transform from ALL viewports
        for vp_state in references_overlays_props.viewport_states:
            if idx < len(vp_state.transforms):
                vp_state.transforms.remove(idx)

        if references_overlays_props.reference_index >= len(
            references_overlays_props.reference
        ):
            references_overlays_props.reference_index = max(
                0, len(references_overlays_props.reference) - 1
            )

        return {"FINISHED"}


class Clear_References_OT(bpy.types.Operator):
    bl_idname = "screen.clear_references_slot"
    bl_label = "Clear References Slots"
    bl_description = "Clear References Slots"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        references_overlays = context.scene.references_overlays
        references_overlays.reference.clear()
        references_overlays.reference_index = 0
        return {"FINISHED"}


class Move_References_OT(bpy.types.Operator):
    bl_idname = "screen.move_reference"
    bl_label = "Move References"
    bl_description = "Move References"
    bl_options = {"REGISTER", "UNDO"}

    index: bpy.props.IntProperty(options={"HIDDEN"})

    lock = None
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
    opacity = None
    depth_set = None
    init_crop_left = 0
    init_crop_right = 0
    init_crop_top = 0
    init_crop_bottom = 0

    mode = "MOVE"
    init_mouse_x = 0
    init_val = 0.0
    last_mouse_x = None
    last_mouse_y = None
    closest_corner = None
    image_screen_width = 0
    image_screen_height = 0

    center_x = 0.0
    center_y = 0.0
    init_angle = 0.0

    def modal(self, context, event):
        context.area.tag_redraw()
        from . import references_overlays

        references_overlays_props = context.scene.references_overlays
        item = references_overlays_props.reference[self.index]
        transform = references_overlays.get_image_transform_state(context, self.index)
        if not transform:
            context.area.header_text_set(None)
            return {"CANCELLED"}

        if event.type == "R" and not event.alt:
            if event.value == "PRESS":
                references_overlays._locked_move_attempt_index = -1
                self.mode = "ROTATE"
                self.init_val = transform.rotation
                self.init_angle = math.atan2(
                    event.mouse_region_y - self.center_y,
                    event.mouse_region_x - self.center_x,
                )
            elif event.value == "RELEASE":
                self.mode = "MOVE"

        if event.type == "S" and not event.alt:
            if event.value == "PRESS":
                references_overlays._locked_move_attempt_index = -1
                self.init_mouse_x = event.mouse_x
                if event.shift:
                    self.mode = "ZOOM"
                    self.init_val = transform.zoom
                else:
                    self.mode = "SCALE"
                    self.init_val = transform.size
            elif event.value == "RELEASE":
                self.mode = "MOVE"

        if event.type == "Z" and not event.alt:
            if event.value == "PRESS":
                references_overlays._locked_move_attempt_index = -1
                self.mode = "ZOOM"
                self.init_mouse_x = event.mouse_x
                self.init_val = transform.zoom
            elif event.value == "RELEASE":
                self.mode = "MOVE"

        if event.type == "A" and not event.alt:
            if event.value == "PRESS":
                references_overlays._locked_move_attempt_index = -1
                self.mode = "ALPHA"
                self.init_mouse_x = event.mouse_x
                self.init_val = transform.opacity
            elif event.value == "RELEASE":
                self.mode = "MOVE"

        # Reverted Crop back to C
        if event.type == "C" and not event.alt:
            if event.value == "PRESS":
                references_overlays._locked_move_attempt_index = -1
                self.mode = "CROP"
            elif event.value == "RELEASE":
                self.mode = "MOVE"

        # Pan is G
        if event.type == "G" and not event.alt:
            if event.value == "PRESS":
                references_overlays._locked_move_attempt_index = -1
                self.mode = "PAN"
            elif event.value == "RELEASE":
                self.mode = "MOVE"

        if event.value == "PRESS":
            if event.type == "R" and event.alt:
                transform.rotation = 0
            elif event.type == "S" and event.alt:
                transform.size = 1.0
            # Reverted Crop Reset back to Alt+C
            elif event.type == "C" and event.alt:
                transform.crop_left = 0.0
                transform.crop_right = 0.0
                transform.crop_top = 0.0
                transform.crop_bottom = 0.0
            elif event.type == "A" and event.alt:
                transform.opacity = 1.0
            elif event.type == "Z" and event.alt:
                transform.zoom = 0.0
            # New: Reset Pan (Pivot) with Alt+G
            elif event.type == "G" and event.alt:
                transform.pivot_x = 0.0
                transform.pivot_y = 0.0
            elif event.type == "F":
                transform.flip_x = not transform.flip_x
            elif event.type == "V":
                transform.flip_y = not transform.flip_y
            # Changed Grayscale from C to B
            elif event.type == "B":
                transform.grayscale = not transform.grayscale
            elif event.type == "L" and event.value == "PRESS":
                transform.lock_position = not transform.lock_position
                if transform.lock_position:
                    self.report({"INFO"}, "Position Locked")
                else:
                    self.report({"INFO"}, "Position Unlocked")
            elif event.type == "O" and event.value == "PRESS":
                if transform.orthographic:
                    transform.orthographic = False
                else:
                    rv3d = context.space_data.region_3d
                    view_dir = rv3d.view_rotation.to_matrix() @ mathutils.Vector(
                        (0.0, 0.0, -1.0)
                    )
                    axes = {
                        "front": mathutils.Vector((0.0, 1.0, 0.0)),
                        "back": mathutils.Vector((0.0, -1.0, 0.0)),
                        "left": mathutils.Vector((1.0, 0.0, 0.0)),
                        "right": mathutils.Vector((-1.0, 0.0, 0.0)),
                        "top": mathutils.Vector((0.0, 0.0, 1.0)),
                        "bottom": mathutils.Vector((0.0, 0.0, -1.0)),
                    }
                    best_axis = "front"
                    max_dot = -1.0
                    for name, axis in axes.items():
                        dot = view_dir.dot(axis)
                        if dot > max_dot:
                            max_dot = dot
                            best_axis = name
                    transform.orthographic = True
                    transform.front = transform.back = transform.left = (
                        transform.right
                    ) = transform.top = transform.bottom = False
                    setattr(transform, best_axis, True)
                context.area.tag_redraw()
            elif event.type == "H":
                if event.alt:
                    for i in range(len(references_overlays_props.reference)):
                        t = references_overlays.get_image_transform_state(context, i)
                        if t:
                            t.hide = False
                elif event.shift:
                    for i in range(len(references_overlays_props.reference)):
                        if i != self.index:
                            t = references_overlays.get_image_transform_state(
                                context, i
                            )
                            if t:
                                t.hide = True
                else:
                    transform.hide = True
            elif event.type == "ONE":
                transform.depth_set = "Default"
            elif event.type == "TWO":
                transform.depth_set = "Back"
            elif event.type in {"X", "DEL"}:
                bpy.ops.screen.remove_references_slot(index=self.index)
                context.area.header_text_set(None)
                return {"FINISHED"}

        if self.mode == "PAN":
            if event.type == "MOUSEMOVE":
                value = 0.2 if event.shift else 1.0
                transform.pivot_x = (
                    self.pivot_x
                    + (event.mouse_region_x - self.mouse_region_x)
                    / (context.window.width / 2)
                    * -1
                    * value
                )
                transform.pivot_y = (
                    self.pivot_y
                    + (event.mouse_region_y - self.mouse_region_y)
                    / (context.window.width / 2)
                    * -1
                    * value
                )

        elif self.mode == "CROP":
            if event.type == "MOUSEMOVE":
                if self.last_mouse_x is None:
                    self.last_mouse_x = event.mouse_region_x
                    self.last_mouse_y = event.mouse_region_y

                step_delta_x = event.mouse_region_x - self.last_mouse_x
                step_delta_y = event.mouse_region_y - self.last_mouse_y
                self.last_mouse_x = event.mouse_region_x
                self.last_mouse_y = event.mouse_region_y

                step_crop_x = (
                    step_delta_x / self.image_screen_width
                    if self.image_screen_width != 0
                    else 0
                )
                step_crop_y = (
                    step_delta_y / self.image_screen_height
                    if self.image_screen_height != 0
                    else 0
                )

                if self.closest_corner == "BL":
                    if transform.flip_x:
                        transform.crop_right = max(
                            0.0, min(1.0, transform.crop_right - step_crop_x)
                        )
                    else:
                        transform.crop_left = max(
                            0.0, min(1.0, transform.crop_left + step_crop_x)
                        )
                    if transform.flip_y:
                        transform.crop_top = max(
                            0.0, min(1.0, transform.crop_top - step_crop_y)
                        )
                    else:
                        transform.crop_bottom = max(
                            0.0, min(1.0, transform.crop_bottom + step_crop_y)
                        )
                elif self.closest_corner == "BR":
                    if transform.flip_x:
                        transform.crop_left = max(
                            0.0, min(1.0, transform.crop_left + step_crop_x)
                        )
                    else:
                        transform.crop_right = max(
                            0.0, min(1.0, transform.crop_right - step_crop_x)
                        )
                    if transform.flip_y:
                        transform.crop_top = max(
                            0.0, min(1.0, transform.crop_top - step_crop_y)
                        )
                    else:
                        transform.crop_bottom = max(
                            0.0, min(1.0, transform.crop_bottom + step_crop_y)
                        )
                elif self.closest_corner == "TL":
                    if transform.flip_x:
                        transform.crop_right = max(
                            0.0, min(1.0, transform.crop_right - step_crop_x)
                        )
                    else:
                        transform.crop_left = max(
                            0.0, min(1.0, transform.crop_left + step_crop_x)
                        )
                    if transform.flip_y:
                        transform.crop_bottom = max(
                            0.0, min(1.0, transform.crop_bottom + step_crop_y)
                        )
                    else:
                        transform.crop_top = max(
                            0.0, min(1.0, transform.crop_top - step_crop_y)
                        )
                elif self.closest_corner == "TR":
                    if transform.flip_x:
                        transform.crop_left = max(
                            0.0, min(1.0, transform.crop_left + step_crop_x)
                        )
                    else:
                        transform.crop_right = max(
                            0.0, min(1.0, transform.crop_right - step_crop_x)
                        )
                    if transform.flip_y:
                        transform.crop_bottom = max(
                            0.0, min(1.0, transform.crop_bottom + step_crop_y)
                        )
                    else:
                        transform.crop_top = max(
                            0.0, min(1.0, transform.crop_top - step_crop_y)
                        )

        else:
            if event.type == "MOUSEMOVE":
                if self.mode == "ROTATE":
                    current_angle = math.atan2(
                        event.mouse_region_y - self.center_y,
                        event.mouse_region_x - self.center_x,
                    )
                    delta_angle = current_angle - self.init_angle

                    if delta_angle > math.pi:
                        delta_angle -= 2 * math.pi
                    elif delta_angle < -math.pi:
                        delta_angle += 2 * math.pi

                    new_rot = self.init_val - delta_angle

                    if event.shift:
                        snap = math.radians(5)
                        new_rot = round(new_rot / snap) * snap

                    transform.rotation = new_rot

                elif self.mode == "SCALE":
                    delta = event.mouse_x - self.init_mouse_x
                    factor = 0.01 if event.shift else 0.02
                    transform.size = max(0.01, self.init_val * (1.0 + delta * factor))

                elif self.mode == "ZOOM":
                    delta = event.mouse_x - self.init_mouse_x
                    factor = 0.002 if event.shift else 0.005
                    transform.zoom = max(0.0, min(1.0, self.init_val + delta * factor))

                elif self.mode == "ALPHA":
                    delta = event.mouse_x - self.init_mouse_x
                    factor = 0.002 if event.shift else 0.005
                    transform.opacity = max(
                        0.0, min(1.0, self.init_val + delta * factor)
                    )

                else:
                    if not transform.lock_position:
                        references_overlays._locked_move_attempt_index = -1
                        if references_overlays_props.fit_view_distance:
                            view_distance = (
                                context.area.spaces.active.region_3d.view_distance / 15
                            )
                        else:
                            view_distance = 1

                        map_range_x = map_range(
                            self.mouse_region_x,
                            0,
                            context.region.width,
                            0,
                            context.window.width * view_distance,
                        )
                        map_range_y = map_range(
                            self.mouse_region_y,
                            0,
                            context.region.height,
                            0,
                            context.window.height * view_distance,
                        )

                        region_x = (
                            map_range(
                                event.mouse_region_x,
                                0,
                                context.region.width,
                                0,
                                context.window.width * view_distance,
                            )
                            + (map_range_x - self.x) * -1
                        )
                        region_y = (
                            map_range(
                                event.mouse_region_y,
                                0,
                                context.region.height,
                                0,
                                context.window.height * view_distance,
                            )
                            + (map_range_y - self.y) * -1
                        )

                        if event.ctrl:
                            snap_value = 25 if event.shift else 50
                            transform.x = round(region_x / snap_value) * snap_value
                            transform.y = round(region_y / snap_value) * snap_value
                        else:
                            transform.x = region_x
                            transform.y = region_y
                    else:
                        references_overlays._locked_move_attempt_index = self.index
                        context.area.tag_redraw()

        if event.type == "LEFTMOUSE":
            references_overlays._locked_move_attempt_index = -1
            context.area.header_text_set(None)
            return {"FINISHED"}

        if event.type in {"RIGHTMOUSE", "ESC"}:
            references_overlays._locked_move_attempt_index = -1
            transform.x = self.x
            transform.y = self.y
            transform.pivot_x = self.pivot_x
            transform.pivot_y = self.pivot_y
            transform.zoom = self.zoom
            transform.size = self.size
            transform.rotation = self.rotation
            transform.opacity = self.opacity
            transform.depth_set = self.depth_set
            transform.flip_x = self.flip_x
            transform.flip_y = self.flip_y

            transform.crop_left = self.init_crop_left
            transform.crop_right = self.init_crop_right
            transform.crop_top = self.init_crop_top
            transform.crop_bottom = self.init_crop_bottom

            item.lock = self.lock
            context.area.header_text_set(None)
            return {"CANCELLED"}

        return {"RUNNING_MODAL"}

    def invoke(self, context, event):
        from . import references_overlays

        references_overlays._locked_move_attempt_index = -1

        if context.area.type == "VIEW_3D":
            references_overlays_props = context.scene.references_overlays
            references_overlays_props.reference_index = self.index
            item = references_overlays_props.reference[self.index]
            transform = references_overlays.get_image_transform_state(
                context, self.index
            )
            if not transform:
                return {"CANCELLED"}

            self.lock = item.lock
            self.x = transform.x
            self.y = transform.y
            self.size = transform.size
            self.rotation = transform.rotation
            self.opacity = transform.opacity
            self.depth_set = transform.depth_set
            self.flip_x = transform.flip_x
            self.flip_y = transform.flip_y
            self.pivot_x = transform.pivot_x
            self.pivot_y = transform.pivot_y
            self.zoom = transform.zoom

            self.init_crop_left = transform.crop_left
            self.init_crop_right = transform.crop_right
            self.init_crop_top = transform.crop_top
            self.init_crop_bottom = transform.crop_bottom

            self.mouse_region_x = event.mouse_region_x
            self.mouse_region_y = event.mouse_region_y

            self.last_mouse_x = event.mouse_region_x
            self.last_mouse_y = event.mouse_region_y

            image = bpy.data.images.get(item.name)
            if image:
                if references_overlays_props.resize_image:
                    img_x, img_y = resize_image(context, image)
                else:
                    img_x = image.size[0]
                    img_y = image.size[1]

                if references_overlays_props.tweak_size:
                    size = transform.size / (
                        (context.window.width + context.region.width)
                        / (context.window.height + context.region.height)
                    )
                    region_size = map_range(
                        size, 0, context.window.width / 2, 0, context.region.width
                    ) * map_range(
                        size, 0, context.window.height / 2, 0, context.region.height
                    )
                else:
                    region_size = transform.size

                region_x = map_range(
                    transform.x, 0, context.window.width, 0, context.region.width
                )
                region_y = map_range(
                    transform.y, 0, context.window.height, 0, context.region.height
                )

                self.center_x = region_x
                self.center_y = region_y

                if transform.flip_x:
                    edge1_x = region_x + img_x / 2 * region_size / 2 * (
                        1 - transform.crop_right
                    )
                    edge2_x = region_x - img_x / 2 * region_size / 2 * (
                        1 - transform.crop_left
                    )
                else:
                    edge1_x = region_x - img_x / 2 * region_size / 2 * (
                        1 - transform.crop_left
                    )
                    edge2_x = region_x + img_x / 2 * region_size / 2 * (
                        1 - transform.crop_right
                    )

                actual_min_x = min(edge1_x, edge2_x)
                actual_max_x = max(edge1_x, edge2_x)

                if transform.flip_y:
                    edge1_y = region_y + img_y / 2 * region_size / 2 * (
                        1 - transform.crop_bottom
                    )
                    edge2_y = region_y - img_y / 2 * region_size / 2 * (
                        1 - transform.crop_top
                    )
                else:
                    edge1_y = region_y - img_y / 2 * region_size / 2 * (
                        1 - transform.crop_bottom
                    )
                    edge2_y = region_y + img_y / 2 * region_size / 2 * (
                        1 - transform.crop_top
                    )

                actual_min_y = min(edge1_y, edge2_y)
                actual_max_y = max(edge1_y, edge2_y)

                self.image_screen_width = actual_max_x - actual_min_x
                self.image_screen_height = actual_max_y - actual_min_y

                center_x = (actual_min_x + actual_max_x) / 2
                center_y = (actual_min_y + actual_max_y) / 2
                rotation_angle = transform.rotation * -1

                def rotate_point(px, py, cx, cy, angle):
                    sin_a = math.sin(angle)
                    cos_a = math.cos(angle)
                    dx = px - cx
                    dy = py - cy
                    return (cx + dx * cos_a - dy * sin_a, cy + dx * sin_a + dy * cos_a)

                rotated_corners = {
                    "BL": rotate_point(
                        actual_min_x, actual_min_y, center_x, center_y, rotation_angle
                    ),
                    "BR": rotate_point(
                        actual_max_x, actual_min_y, center_x, center_y, rotation_angle
                    ),
                    "TL": rotate_point(
                        actual_min_x, actual_max_y, center_x, center_y, rotation_angle
                    ),
                    "TR": rotate_point(
                        actual_max_x, actual_max_y, center_x, center_y, rotation_angle
                    ),
                }

                self.closest_corner = min(
                    rotated_corners,
                    key=lambda c: math.dist(
                        rotated_corners[c], (event.mouse_region_x, event.mouse_region_y)
                    ),
                )
            else:
                self.closest_corner = "TL"
                self.center_x = map_range(
                    transform.x, 0, context.window.width, 0, context.region.width
                )
                self.center_y = map_range(
                    transform.y, 0, context.window.height, 0, context.region.height
                )

            context.area.header_text_set(
                "LMB:Confirm | RMB:Cancel | Drag: R=Rotate, S=Scale, Z=Zoom, A=Alpha, C=Crop, G=Pan | "
                "B:Grayscale | L:Lock Pos | O:Ortho | Alt+R/S/Z/A/C/G:Reset | F/V:Flip | H:Hide | Shift+H:Isolate | Alt+H:Unhide | 1/2:Depth | X:Remove"
            )

            context.window_manager.modal_handler_add(self)
            return {"RUNNING_MODAL"}
        else:
            self.report({"WARNING"}, "View3D not found, cannot run operator")
            return {"CANCELLED"}


class Global_Move_References_OT(bpy.types.Operator):
    bl_idname = "screen.gobal_move_reference"
    bl_label = "Global Move References"
    bl_description = "Move References"
    bl_options = {"REGISTER", "UNDO"}

    mouse_region_x = None
    mouse_region_y = None
    x = None
    y = None
    size = None
    pivot_x = None
    pivot_y = None

    def modal(self, context, event):
        context.area.tag_redraw()
        item = context.scene.references_overlays

        if event.type == "MOUSEMOVE":
            region_x = self.x + event.mouse_region_x - self.mouse_region_x
            region_y = self.y + event.mouse_region_y - self.mouse_region_y

            if event.shift:
                snap_value = 25
            else:
                snap_value = 50
            item.x = round(region_x / snap_value) * snap_value
            item.y = round(region_y / snap_value) * snap_value

        elif event.type == "WHEELUPMOUSE":
            if event.shift:
                item.size = item.size * 1.025
            else:
                item.size = item.size * 1.1
        elif event.type == "WHEELDOWNMOUSE":
            if event.shift:
                item.size = item.size * 0.975
            else:
                item.size = item.size * 0.9
        elif event.type == "S":
            item.size = 1
        elif event.type == "R":
            item.x = 0
            item.y = 0

        if event.type == "LEFTMOUSE":
            context.area.header_text_set(None)
            return {"FINISHED"}

        if event.type in {"RIGHTMOUSE", "ESC"}:
            item.x = self.x
            item.y = self.y
            item.pivot_x = self.pivot_x
            item.pivot_y = self.pivot_y
            item.size = self.size
            context.area.header_text_set(None)
            return {"CANCELLED"}

        return {"RUNNING_MODAL"}

    def invoke(self, context, event):
        if context.area.type == "VIEW_3D":
            item = context.scene.references_overlays
            self.x = item.x
            self.y = item.y
            self.mouse_region_x = event.mouse_region_x
            self.mouse_region_y = event.mouse_region_y
            self.size = item.size

            context.area.header_text_set(
                "LMB: Confirm | RMB/ESC: Cancel | Scroll: Global Scale | "
                "S: Reset Size | R: Reset Position | Shift: Snap"
            )

            context.window_manager.modal_handler_add(self)
            return {"RUNNING_MODAL"}
        else:
            self.report({"WARNING"}, "View3D not found, cannot run operator")
            return {"CANCELLED"}


class Align_References_OT(bpy.types.Operator):
    bl_idname = "screen.align_reference"
    bl_label = "Align References"
    bl_description = "Align References"
    bl_options = {"REGISTER", "UNDO"}

    align_x: bpy.props.StringProperty(name="Align X", options={"HIDDEN"})
    align_y: bpy.props.StringProperty(name="Align Y", options={"HIDDEN"})

    def execute(self, context):
        from . import references_overlays

        references_overlays_props = context.scene.references_overlays
        item = references_overlays_props.reference[
            references_overlays_props.reference_index
        ]
        transform = references_overlays.get_image_transform_state(
            context, references_overlays_props.reference_index
        )
        if not transform:
            return {"CANCELLED"}

        image = bpy.data.images[item.name]

        region_width = context.window.width
        region_height = context.window.height

        if self.align_x == "LEFT":
            transform.x = image.size[0] / 2 * transform.size / 2
        elif self.align_x == "RIGHT":
            transform.x = region_width - image.size[0] / 2 * transform.size / 2
        elif self.align_x == "CENTER":
            transform.x = region_width / 2

        if self.align_y == "DOWN":
            transform.y = image.size[1] / 2 * transform.size / 2
        elif self.align_y == "UP":
            transform.y = region_height - image.size[1] / 2 * transform.size / 2
        elif self.align_y == "CENTER":
            transform.y = region_height / 2
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

        return {"FINISHED"}


class Toggle_References_OT(bpy.types.Operator):
    bl_idname = "screen.toggle_references_overlays"
    bl_label = "Toggle References Overlays"
    bl_description = "Toggle References Overlays"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        from . import references_overlays

        vp_key = references_overlays.get_vp_key(context)
        if not vp_key:
            return {"CANCELLED"}

        vp_state = references_overlays.get_current_viewport_state(context)
        if not vp_state:
            return {"CANCELLED"}

        # Simple toggle
        current_state = references_overlays._viewport_toggle_states.get(vp_key, False)
        new_state = not current_state

        references_overlays._viewport_toggle_states[vp_key] = new_state
        vp_state.is_enabled = new_state

        if new_state:
            props = context.scene.references_overlays
            for i in range(len(props.reference)):
                references_overlays.get_image_transform_state(context, i)

        context.area.tag_redraw()
        return {"FINISHED"}


class Toggle_Lock_References_OT(bpy.types.Operator):
    bl_idname = "screen.toggle_lock_references_overlays"
    bl_label = "Toggle Lock References Overlays"
    bl_description = "Toggle Lock References Overlays"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        from . import references_overlays

        vp_key = references_overlays.get_vp_key(context)
        if not vp_key:
            return False
        return references_overlays._viewport_toggle_states.get(vp_key, False)

    def execute(self, context):
        context.scene.references_overlays.full_lock = (
            not context.scene.references_overlays.full_lock
        )
        if context.scene.references_overlays.full_lock == True:
            self.report({"INFO"}, "References Overlays ignore mouse events.")
        else:
            self.report({"INFO"}, "References Overlays is unlocked.")
        return {"FINISHED"}


class Paste_References_OT(bpy.types.Operator):
    bl_idname = "screen.paste_reference"
    bl_label = "Paste Reference from the clipboard"
    bl_options = {"REGISTER", "UNDO"}

    x: bpy.props.FloatProperty(options={"HIDDEN"})
    y: bpy.props.FloatProperty(options={"HIDDEN"})

    def invoke(self, context, event):
        self.x = map_range(
            event.mouse_region_x, 0, context.region.width, 0, context.window.width
        )
        self.y = map_range(
            event.mouse_region_y, 0, context.region.height, 0, context.window.height
        )
        return self.execute(context)

    def execute(self, context):
        from PIL import Image, ImageGrab

        from . import references_overlays

        image = ImageGrab.grabclipboard()
        if isinstance(image, Image.Image):
            temp_dir = tempfile.gettempdir()
            current_time = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
            temp_path = os.path.join(temp_dir, f"{current_time}_clipboard.png")
            image.save(temp_path)

            img = bpy.data.images.load(temp_path)
            img.use_fake_user = True

            references_overlays_props = context.scene.references_overlays
            item = references_overlays_props.reference.add()
            item.name = img.name

            new_index = len(references_overlays_props.reference) - 1

            references_overlays.initialize_transform_for_all_viewports(
                context, new_index, self.x, self.y
            )

            vp_key = references_overlays.get_vp_key(context)
            if vp_key:
                references_overlays._viewport_toggle_states[vp_key] = True
                vp_state = references_overlays.get_current_viewport_state(context)
                if vp_state:
                    vp_state.is_enabled = True

            if references_overlays_props.full_lock == True:
                references_overlays_props.full_lock = False

            self.report({"INFO"}, f"Image pasted from clipboard {current_time}")

        else:
            self.report({"WARNING"}, "No image in clipboard")

        return {"FINISHED"}


class Propagate_Transforms_OT(bpy.types.Operator):
    bl_idname = "screen.propagate_reference_transforms"
    bl_label = "Propagate Transforms to All Viewports"
    bl_description = (
        "Copy the transform settings of the current viewport to all other viewports"
    )
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        from . import references_overlays

        props = context.scene.references_overlays
        source_vp_state = references_overlays.get_current_viewport_state(context)
        if not source_vp_state:
            return {"CANCELLED"}

        for vp_state in props.viewport_states:
            if vp_state == source_vp_state:
                continue

            while len(vp_state.transforms) < len(source_vp_state.transforms):
                vp_state.transforms.add()

            for i, src_transform in enumerate(source_vp_state.transforms):
                if i < len(vp_state.transforms):
                    tgt_transform = vp_state.transforms[i]
                    tgt_transform.x = src_transform.x
                    tgt_transform.y = src_transform.y
                    tgt_transform.size = src_transform.size
                    tgt_transform.rotation = src_transform.rotation
                    tgt_transform.opacity = src_transform.opacity
                    tgt_transform.flip_x = src_transform.flip_x
                    tgt_transform.flip_y = src_transform.flip_y
                    tgt_transform.pivot_x = src_transform.pivot_x
                    tgt_transform.pivot_y = src_transform.pivot_y
                    tgt_transform.zoom = src_transform.zoom
                    tgt_transform.crop_left = src_transform.crop_left
                    tgt_transform.crop_top = src_transform.crop_top
                    tgt_transform.crop_right = src_transform.crop_right
                    tgt_transform.crop_bottom = src_transform.crop_bottom
                    tgt_transform.depth_set = src_transform.depth_set
                    tgt_transform.orthographic = src_transform.orthographic
                    tgt_transform.front = src_transform.front
                    tgt_transform.back = src_transform.back
                    tgt_transform.left = src_transform.left
                    tgt_transform.right = src_transform.right
                    tgt_transform.top = src_transform.top
                    tgt_transform.bottom = src_transform.bottom
                    tgt_transform.hide = src_transform.hide
                    tgt_transform.grayscale = src_transform.grayscale
                    tgt_transform.lock_position = src_transform.lock_position

        context.area.tag_redraw()
        self.report({"INFO"}, "Transforms propagated to all viewports")
        return {"FINISHED"}


classes = (
    Load_References_OT,
    Add_References_OT,
    Remove_References_OT,
    Rest_References_OT,
    Clear_References_OT,
    Move_References_OT,
    Global_Move_References_OT,
    Align_References_OT,
    Toggle_References_OT,
    Toggle_Lock_References_OT,
    Paste_References_OT,
    Propagate_Transforms_OT,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
