"""Модульный набор «Больница» v0.1 — генератор для Blender.

Строит модули (стены, перекрытия, двери, лестницы, реквизит) и выгружает каждый в отдельный .glb.
Техописание — docs/TECHNICAL_DESIGN.md, «Модульный набор „Больница“ v0.1».

Запуск (из корня проекта):
    Blender -b --factory-startup --python tools/blender/build_hospital_kit.py -- <папка> [превью.png]

Оси Blender: X — вдоль стены/марша, Y — толщина, Z — вверх. При экспорте glTF Z становится Y.
Суффиксы имён для импорта в Godot: «-col» — модель с коллизией, «-colonly» — только коллизия.
"""

import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

# --- Размеры (метры) -----------------------------------------------------------------------------
CELL = 3.0
FLOOR_HEIGHT = 3.3
SLAB = 0.2
WALL_HEIGHT = FLOOR_HEIGHT - SLAB
WALL_THICKNESS = 0.2
PAINT_HEIGHT = 1.5  # до этой высоты стена покрашена масляной краской, выше — побелка

DOOR_WIDTH = 1.2
DOOR_HEIGHT = 2.1
FRAME = 0.06

WINDOW_WIDTH = 1.4
WINDOW_SILL = 0.9
WINDOW_TOP = 2.4

STEP_COUNT = 10
STEP_RISE = FLOOR_HEIGHT / 2 / STEP_COUNT  # 0.165
STEP_RUN = 0.3
FLIGHT_WIDTH = 1.2

# --- Палитра: (цвет sRGB, шероховатость, металл, прозрачность) ----------------------------------
PALETTE = {
	"paint_green": ((0.30, 0.45, 0.38), 0.5, 0.0, 1.0),
	"whitewash": ((0.86, 0.86, 0.82), 0.95, 0.0, 1.0),
	"floor_tile": ((0.42, 0.24, 0.18), 0.6, 0.0, 1.0),
	"ceiling": ((0.88, 0.88, 0.85), 0.95, 0.0, 1.0),
	"concrete": ((0.55, 0.55, 0.53), 0.9, 0.0, 1.0),
	"stair_tread": ((0.40, 0.38, 0.36), 0.7, 0.0, 1.0),
	"door_paint": ((0.85, 0.86, 0.82), 0.4, 0.0, 1.0),
	"frame_paint": ((0.78, 0.79, 0.76), 0.4, 0.0, 1.0),
	"glass": ((0.60, 0.70, 0.72), 0.05, 0.0, 0.25),
	"metal_white": ((0.82, 0.83, 0.82), 0.45, 0.3, 1.0),
	"metal_dark": ((0.20, 0.20, 0.20), 0.4, 0.8, 1.0),
	"linen": ((0.80, 0.80, 0.76), 0.9, 0.0, 1.0),
	"mattress": ((0.55, 0.50, 0.42), 0.9, 0.0, 1.0),
	"oxygen_blue": ((0.12, 0.25, 0.55), 0.4, 0.2, 1.0),
	"brass": ((0.70, 0.55, 0.25), 0.35, 1.0, 1.0),
	"oilcloth": ((0.35, 0.12, 0.10), 0.5, 0.0, 1.0),
	"wood": ((0.45, 0.30, 0.18), 0.7, 0.0, 1.0),
}

_materials = {}


def srgb_to_linear(c):
	return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def material(name):
	if name in _materials:
		return _materials[name]
	rgb, roughness, metallic, alpha = PALETTE[name]
	mat = bpy.data.materials.new(name)
	if mat.node_tree is None:
		mat.use_nodes = True
	bsdf = mat.node_tree.nodes["Principled BSDF"]
	bsdf.inputs["Base Color"].default_value = (*[srgb_to_linear(c) for c in rgb], 1.0)
	bsdf.inputs["Roughness"].default_value = roughness
	bsdf.inputs["Metallic"].default_value = metallic
	bsdf.inputs["Alpha"].default_value = alpha
	if alpha < 1.0:
		if hasattr(mat, "surface_render_method"):
			mat.surface_render_method = "BLENDED"
		if hasattr(mat, "blend_method"):
			mat.blend_method = "BLEND"
	mat.diffuse_color = (*[srgb_to_linear(c) for c in rgb], alpha)
	_materials[name] = mat
	return mat


# --- Построение геометрии ------------------------------------------------------------------------

class MeshBuilder:
	"""Собирает один меш из коробок и цилиндров с несколькими материалами."""

	def __init__(self):
		self.bm = bmesh.new()
		self.material_names = []

	def _index(self, name):
		if name not in self.material_names:
			self.material_names.append(name)
		return self.material_names.index(name)

	def box(self, mn, mx, mat, top=None, bottom=None, matrix=None):
		"""Коробка от угла mn до угла mx. top/bottom — отдельные материалы верхней/нижней грани."""
		size = Vector(mx) - Vector(mn)
		center = (Vector(mx) + Vector(mn)) / 2
		verts = bmesh.ops.create_cube(self.bm, size=1.0)["verts"]
		transform = Matrix.Translation(center) @ Matrix.Diagonal((*size, 1.0))
		if matrix is not None:
			transform = matrix @ transform
		bmesh.ops.transform(self.bm, matrix=transform, verts=verts)
		self._assign(verts, mat, top, bottom)

	def cylinder(self, center, radius, height, mat, segments=16):
		"""Вертикальный цилиндр; center — центр нижнего основания."""
		verts = bmesh.ops.create_cone(
			self.bm, cap_ends=True, segments=segments,
			radius1=radius, radius2=radius, depth=height,
			matrix=Matrix.Translation(Vector(center) + Vector((0, 0, height / 2))),
		)["verts"]
		self._assign(verts, mat)
		for face in {f for v in verts for f in v.link_faces}:
			face.smooth = abs(face.normal.z) < 0.5

	def _assign(self, verts, mat, top=None, bottom=None):
		self.bm.normal_update()
		for face in {f for v in verts for f in v.link_faces}:
			name = mat
			if top and face.normal.z > 0.5:
				name = top
			elif bottom and face.normal.z < -0.5:
				name = bottom
			face.material_index = self._index(name)

	def build(self, name):
		self.bm.normal_update()
		_project_uvs(self.bm)
		mesh = bpy.data.meshes.new(name)
		self.bm.to_mesh(mesh)
		self.bm.free()
		for mat_name in self.material_names:
			mesh.materials.append(material(mat_name))
		obj = bpy.data.objects.new(name, mesh)
		bpy.context.scene.collection.objects.link(obj)
		return obj


def _project_uvs(bm):
	"""Проекция UV по доминирующей оси нормали, 1 UV = 1 м."""
	uv = bm.loops.layers.uv.verify()
	for face in bm.faces:
		n = face.normal
		axis = max(range(3), key=lambda i: abs(n[i]))
		for loop in face.loops:
			co = loop.vert.co
			if axis == 0:
				loop[uv].uv = (co.y, co.z)
			elif axis == 1:
				loop[uv].uv = (co.x, co.z)
			else:
				loop[uv].uv = (co.x, co.y)


def wall_piece(mb, x0, x1, z0, z1):
	"""Участок стены: краска до PAINT_HEIGHT, побелка выше."""
	t = WALL_THICKNESS / 2
	if z0 < PAINT_HEIGHT:
		mb.box((x0, -t, z0), (x1, t, min(z1, PAINT_HEIGHT)), "paint_green")
	if z1 > PAINT_HEIGHT:
		mb.box((x0, -t, max(z0, PAINT_HEIGHT)), (x1, t, z1), "whitewash")


# --- Модули: каждая функция возвращает список объектов одного .glb --------------------------------

def build_floor():
	mb = MeshBuilder()
	h = CELL / 2
	mb.box((-h, -h, -SLAB), (h, h, 0), "concrete", top="floor_tile", bottom="ceiling")
	return [mb.build("hosp_floor-col")]


def build_wall():
	mb = MeshBuilder()
	wall_piece(mb, -CELL / 2, CELL / 2, 0, WALL_HEIGHT)
	return [mb.build("hosp_wall-col")]


def build_wall_door():
	mb = MeshBuilder()
	h, d = CELL / 2, DOOR_WIDTH / 2
	wall_piece(mb, -h, -d, 0, WALL_HEIGHT)
	wall_piece(mb, d, h, 0, WALL_HEIGHT)
	wall_piece(mb, -d, d, DOOR_HEIGHT, WALL_HEIGHT)
	t = WALL_THICKNESS / 2 + 0.02
	mb.box((-d, -t, 0), (-d + FRAME, t, DOOR_HEIGHT), "frame_paint")
	mb.box((d - FRAME, -t, 0), (d, t, DOOR_HEIGHT), "frame_paint")
	mb.box((-d, -t, DOOR_HEIGHT - FRAME), (d, t, DOOR_HEIGHT), "frame_paint")
	return [mb.build("hosp_wall_door-col")]


def build_wall_window():
	mb = MeshBuilder()
	h, w = CELL / 2, WINDOW_WIDTH / 2
	wall_piece(mb, -h, -w, 0, WALL_HEIGHT)
	wall_piece(mb, w, h, 0, WALL_HEIGHT)
	wall_piece(mb, -w, w, 0, WINDOW_SILL)
	wall_piece(mb, -w, w, WINDOW_TOP, WALL_HEIGHT)
	f, fd = FRAME, 0.05
	mb.box((-w, -fd, WINDOW_SILL), (-w + f, fd, WINDOW_TOP), "frame_paint")
	mb.box((w - f, -fd, WINDOW_SILL), (w, fd, WINDOW_TOP), "frame_paint")
	mb.box((-w, -fd, WINDOW_SILL), (w, fd, WINDOW_SILL + f), "frame_paint")
	mb.box((-w, -fd, WINDOW_TOP - f), (w, fd, WINDOW_TOP), "frame_paint")
	mb.box((-f / 2, -fd, WINDOW_SILL), (f / 2, fd, WINDOW_TOP), "frame_paint")  # импост
	mb.box((-w + f, -0.005, WINDOW_SILL + f), (w - f, 0.005, WINDOW_TOP - f), "glass")
	# подоконник — с внутренней стороны (+Y в Blender = −Z в Godot)
	mb.box((-w - 0.05, WALL_THICKNESS / 2 - 0.02, WINDOW_SILL - 0.04),
		(w + 0.05, WALL_THICKNESS / 2 + 0.2, WINDOW_SILL), "whitewash")
	return [mb.build("hosp_wall_window-col")]


def build_door():
	"""Дверное полотно. Ось — на петлях (x = 0), полотно идёт вдоль +X."""
	mb = MeshBuilder()
	width = DOOR_WIDTH - 2 * FRAME - 0.02
	mb.box((0, -0.025, 0.01), (width, 0.025, DOOR_HEIGHT - FRAME - 0.01), "door_paint")
	mb.box((width - 0.12, -0.06, 0.95), (width - 0.08, 0.06, 1.05), "metal_dark")
	return [mb.build("hosp_door-col")]


def build_stairs_flight():
	"""Марш на полэтажа. Начало нижней ступени — в начале координат, подъём вдоль +X."""
	mb = MeshBuilder()
	w = FLIGHT_WIDTH / 2
	for i in range(STEP_COUNT):
		mb.box((i * STEP_RUN, -w, i * STEP_RISE - 0.15), ((i + 1) * STEP_RUN, w, (i + 1) * STEP_RISE),
			"concrete", top="stair_tread")
	run, rise = STEP_COUNT * STEP_RUN, STEP_COUNT * STEP_RISE
	angle = math.atan2(rise, run)
	length = math.hypot(run, rise)
	# наклонная плита под ступенями
	slab = (Matrix.Translation((run / 2, 0, rise / 2 - 0.12)) @ Matrix.Rotation(-angle, 4, "Y")
		@ Matrix.Translation((0, 0, -0.075)))
	mb.box((-length / 2, -w, -0.075), (length / 2, w, 0.075), "concrete", matrix=slab)
	visual = mb.build("hosp_stairs_flight")

	# невидимый пандус для персонажа (P-035): верх проходит от (0, 0) до (run, rise)
	ramp = MeshBuilder()
	ramp_matrix = (Matrix.Translation((run / 2, 0, rise / 2)) @ Matrix.Rotation(-angle, 4, "Y")
		@ Matrix.Translation((0, 0, -0.05)))
	ramp.box((-length / 2, -w, -0.05), (length / 2, w, 0.05), "concrete", matrix=ramp_matrix)
	return [visual, ramp.build("hosp_stairs_flight_ramp-colonly")]


def build_stairs_landing():
	"""Лестничная площадка 1,4 × 2,8 м. Центр, верх — на нуле."""
	mb = MeshBuilder()
	mb.box((-0.7, -1.4, -SLAB), (0.7, 1.4, 0), "concrete", top="stair_tread", bottom="ceiling")
	return [mb.build("hosp_stairs_landing-col")]


def build_bed():
	"""Больничная койка. Длина вдоль Y, изголовье на +Y."""
	mb = MeshBuilder()
	for x in (-0.43, 0.39):
		for y in (-0.98, 0.94):
			mb.box((x, y, 0), (x + 0.04, y + 0.04, 0.5), "metal_white")
	for x in (-0.43, 0.39):
		mb.box((x, -0.98, 0.44), (x + 0.04, 0.98, 0.5), "metal_white")
	mb.box((-0.43, 0.94, 0.5), (0.43, 0.98, 1.0), "metal_white")  # изголовье
	mb.box((-0.43, -0.98, 0.5), (0.43, -0.94, 0.8), "metal_white")  # изножье
	mb.box((-0.42, -0.94, 0.5), (0.42, 0.94, 0.64), "mattress", top="linen")
	mb.box((-0.3, 0.6, 0.64), (0.3, 0.9, 0.74), "linen")  # подушка
	col = MeshBuilder()
	col.box((-0.45, -1.0, 0), (0.45, 1.0, 0.7), "concrete")
	return [mb.build("prop_bed"), col.build("prop_bed_col-colonly")]


def build_cabinet():
	"""Прикроватная тумбочка."""
	mb = MeshBuilder()
	mb.box((-0.2, -0.2, 0.05), (0.2, 0.2, 0.75), "door_paint")
	mb.box((-0.18, -0.21, 0.55), (0.18, -0.2, 0.7), "frame_paint")  # ящик
	mb.box((-0.04, -0.23, 0.61), (0.04, -0.21, 0.64), "metal_dark")
	for x in (-0.19, 0.15):
		for y in (-0.19, 0.15):
			mb.box((x, y, 0), (x + 0.04, y + 0.04, 0.05), "metal_dark")
	return [mb.build("prop_cabinet-col")]


def build_oxygen_cylinder():
	"""Кислородный баллон 40 л — синий, как настоящие."""
	mb = MeshBuilder()
	mb.cylinder((0, 0, 0), 0.115, 1.3, "oxygen_blue")
	mb.cylinder((0, 0, 1.3), 0.08, 0.06, "oxygen_blue")
	mb.cylinder((0, 0, 1.36), 0.025, 0.08, "brass")
	mb.box((-0.06, -0.015, 1.4), (0.06, 0.015, 1.43), "brass")  # вентиль
	col = MeshBuilder()
	col.box((-0.115, -0.115, 0), (0.115, 0.115, 1.44), "concrete")
	return [mb.build("prop_oxygen_cylinder"), col.build("prop_oxygen_cylinder_col-colonly")]


def build_gurney():
	"""Каталка. Длина вдоль Y."""
	mb = MeshBuilder()
	mb.box((-0.3, -0.95, 0.78), (0.3, 0.95, 0.82), "metal_white")
	mb.box((-0.29, -0.93, 0.82), (0.29, 0.93, 0.87), "oilcloth")
	mb.box((-0.3, -0.9, 0.25), (0.3, 0.9, 0.27), "metal_white")  # нижняя полка
	for x in (-0.28, 0.25):
		for y in (-0.9, 0.87):
			mb.box((x, y, 0.08), (x + 0.03, y + 0.03, 0.78), "metal_white")
			mb.box((x - 0.01, y - 0.03, 0), (x + 0.04, y + 0.06, 0.08), "metal_dark")  # колесо
	col = MeshBuilder()
	col.box((-0.3, -0.95, 0), (0.3, 0.95, 0.87), "concrete")
	return [mb.build("prop_gurney"), col.build("prop_gurney_col-colonly")]


def build_bench():
	"""Деревянная скамья в коридоре. Длина вдоль X, спинка на +Y."""
	mb = MeshBuilder()
	mb.box((-0.9, -0.2, 0.42), (0.9, 0.2, 0.46), "wood")
	mb.box((-0.9, 0.16, 0.5), (0.9, 0.2, 0.85), "wood")
	for x in (-0.8, 0.77):
		mb.box((x, -0.18, 0), (x + 0.03, -0.15, 0.42), "metal_dark")
		mb.box((x, 0.15, 0), (x + 0.03, 0.18, 0.85), "metal_dark")
	col = MeshBuilder()
	col.box((-0.9, -0.2, 0), (0.9, 0.2, 0.85), "concrete")
	return [mb.build("prop_bench"), col.build("prop_bench_col-colonly")]


MODULES = {
	"hosp_floor": build_floor,
	"hosp_wall": build_wall,
	"hosp_wall_door": build_wall_door,
	"hosp_wall_window": build_wall_window,
	"hosp_door": build_door,
	"hosp_stairs_flight": build_stairs_flight,
	"hosp_stairs_landing": build_stairs_landing,
	"prop_bed": build_bed,
	"prop_cabinet": build_cabinet,
	"prop_oxygen_cylinder": build_oxygen_cylinder,
	"prop_gurney": build_gurney,
	"prop_bench": build_bench,
}


# --- Экспорт и превью ----------------------------------------------------------------------------

def export(objects, path):
	bpy.ops.object.select_all(action="DESELECT")
	for obj in objects:
		obj.select_set(True)
	bpy.context.view_layer.objects.active = objects[0]
	bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True,
		export_yup=True, export_apply=True)


def render_preview(groups, path):
	"""Раскладывает модули в ряд и рендерит превью движком Workbench."""
	x = 0.0
	for objects in groups:
		width = max(max(abs(v[0]) for v in o.bound_box) for o in objects) * 2
		for obj in objects:
			obj.location.x = x + width / 2
			obj.hide_render = obj.name.endswith("-colonly")
		x += width + 0.8
	scene = bpy.context.scene
	cam_data = bpy.data.cameras.new("PreviewCam")
	cam_data.lens = 22
	cam = bpy.data.objects.new("PreviewCam", cam_data)
	scene.collection.objects.link(cam)
	target = Vector((x / 2, 0, 1.2))
	cam.location = target + Vector((0, -x * 0.55, x * 0.22))
	cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
	scene.camera = cam
	scene.render.engine = "BLENDER_WORKBENCH"
	scene.display.shading.light = "STUDIO"
	scene.display.shading.color_type = "MATERIAL"
	scene.display.shading.show_shadows = True
	scene.render.resolution_x, scene.render.resolution_y = 1800, 700
	scene.render.filepath = path
	bpy.ops.render.render(write_still=True)


def main():
	args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
	out_dir = os.path.abspath(args[0] if args else "assets/models/kits/hospital")
	preview = os.path.abspath(args[1]) if len(args) > 1 else None
	os.makedirs(out_dir, exist_ok=True)

	bpy.ops.wm.read_factory_settings(use_empty=True)
	groups = []
	for name, builder in MODULES.items():
		objects = builder()
		export(objects, os.path.join(out_dir, name + ".glb"))
		groups.append(objects)
		print(f"[hospital_kit] {name}.glb")

	if preview:
		render_preview(groups, preview)
		print(f"[hospital_kit] превью: {preview}")


main()
