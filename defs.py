import math

import bpy


def get_reference_prop(context):
    if context.screen.references_overlays_independent:
        props = context.screen.references_overlays
    else:
        props = context.scene.references_overlays
    return props

def transfer_properties(target, source):
    target.x = source.x
    target.y = source.y
    target.size = source.size
    target.rotation = source.rotation
    target.opacity = source.opacity
    target.flip_x = source.flip_x
    target.flip_y = source.flip_y
    target.pivot_x = source.pivot_x
    target.pivot_y = source.pivot_y
    target.zoom = source.zoom
    target.crop_left = source.crop_left
    target.crop_top = source.crop_top
    target.crop_right = source.crop_right
    target.crop_bottom = source.crop_bottom
    target.depth_set = source.depth_set
    target.orthographic = source.orthographic
    target.front = source.front
    target.back = source.back
    target.left = source.left
    target.right = source.right
    target.top = source.top
    target.bottom = source.bottom
    target.hide = source.hide
    target.grayscale = source.grayscale
    target.lock_position = source.lock_position

def resize_image(context, image):
    x = image.size[0]
    y = image.size[1]
    current_size = x * y

    sizes = []
    for item in get_reference_prop(context).reference:
        image = bpy.data.images.get(item.name)
        sizes.append(image.size[0] * image.size[1])

    average = sum(sizes) / len(sizes)

    target_size = int(average**0.5)  # Resize images to a square of average size
    scale_factor = (target_size / current_size) ** 0.5
    new_x = int(x * scale_factor) * 15
    new_y = int(y * scale_factor) * 15

    return new_x, new_y


def map_range(value, in_min, in_max, out_min, out_max):
    if value < 0:
        new_value = value * -1
    else:
        new_value = value

    # First, normalize the input value
    normalized_value = (new_value - in_min) / (in_max - in_min)

    # Apply the mapping to the output range
    mapped_value = normalized_value * (out_max - out_min) + out_min

    if value < 0:
        mapped_value = mapped_value * -1
    else:
        mapped_value = mapped_value

    return mapped_value


def point_in_area(point, area):
    x, y = point
    n = len(area)
    inside = False

    p1x, p1y = area[0]
    for i in range(n + 1):
        p2x, p2y = area[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
        p1x, p1y = p2x, p2y

    return inside


def rotate_vertices(vertices, center_x, center_y, rotation_angle):
    rotated_vertices = []
    for vertex in vertices:
        # Translate the vertex so that the center of rotation is at the origin
        translated_x = vertex[0] - center_x
        translated_y = vertex[1] - center_y

        # Apply rotation
        rotated_x = translated_x * math.cos(rotation_angle) - translated_y * math.sin(
            rotation_angle
        )
        rotated_y = translated_x * math.sin(rotation_angle) + translated_y * math.cos(
            rotation_angle
        )

        # Translate the vertex back to its original position
        rotated_vertices.append((rotated_x + center_x, rotated_y + center_y))
    return rotated_vertices


def scale_vertices(vertices, center_x, center_y, scale):
    scaled_vertices = []
    for vertex in vertices:
        x = vertex[0]
        y = vertex[1]
        # Scale the vertex around the center point
        scaled_x = center_x + (x - center_x) * scale
        scaled_y = center_y + (y - center_y) * scale
        scaled_vertices.append((scaled_x, scaled_y))
    return scaled_vertices


def get_view_orientation_from_matrix(view_matrix):
    r = lambda x: round(x, 2)
    view_rot = view_matrix.to_euler()

    orientation_dict = {
        (0.0, 0.0, 0.0): "TOP",
        (r(math.pi), 0.0, 0.0): "BOTTOM",
        (r(-math.pi / 2), 0.0, 0.0): "FRONT",
        (r(math.pi / 2), 0.0, r(-math.pi)): "BACK",
        (r(-math.pi / 2), r(math.pi / 2), 0.0): "LEFT",
        (r(-math.pi / 2), r(-math.pi / 2), 0.0): "RIGHT",
    }

    return orientation_dict.get(tuple(map(r, view_rot)), "USER")


def get_view_orientations(context):
    r3d = context.area.spaces.active.region_3d  # fine for right-upper quadview view
    view_matrix = r3d.view_matrix
    view_orientation = get_view_orientation_from_matrix(view_matrix).capitalize()
    view_orientation += " " + r3d.view_perspective.capitalize()
    return view_orientation
