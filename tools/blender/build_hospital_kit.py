"""Модульный набор «Больница» v0.3 — генератор для Blender.

Строит модули (стены, углы, перекрытия, двери, лестницы, реквизит) и выгружает каждый в отдельный
.glb. Пишет библиотеку материалов Godot (assets/materials/hospital/*.tres), которые ссылаются на
текстуры из tools/blender/build_textures.py. Превью рендерится с текстурами.
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
	"handrail": ((0.28, 0.16, 0.10), 0.4, 0.0, 1.0),
	"ceramic": ((0.92, 0.92, 0.90), 0.15, 0.0, 1.0),
	"mirror": ((0.80, 0.82, 0.82), 0.05, 1.0, 1.0),
	"lamp_diffuser": ((0.95, 0.97, 0.95), 0.3, 0.0, 1.0),
	"iv_bag": ((0.85, 0.90, 0.90), 0.2, 0.0, 0.4),
	"sign_plate": ((0.90, 0.90, 0.88), 0.3, 0.0, 1.0),
}

# Светящиеся материалы: сила свечения.
EMISSION = {"lamp_diffuser": 3.0}

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
	if name in EMISSION:
		bsdf.inputs["Emission Color"].default_value = (*[srgb_to_linear(c) for c in rgb], 1.0)
		bsdf.inputs["Emission Strength"].default_value = EMISSION[name]
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


def build_wall_corner():
	"""Угловая колонна 0,2 × 0,2 м: ставится в узел сетки, где сходятся стены, и закрывает щель."""
	mb = MeshBuilder()
	t = WALL_THICKNESS / 2
	for z0, z1, mat in ((0, PAINT_HEIGHT, "paint_green"), (PAINT_HEIGHT, WALL_HEIGHT, "whitewash")):
		mb.box((-t, -t, z0), (t, t, z1), mat)
	return [mb.build("hosp_wall_corner-col")]


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


def build_stairs_railing():
	"""Перила марша: стойки на каждой ступени и поручень. Та же точка привязки, что у марша;
	стоят у края +Y (внутренняя сторона между маршами)."""
	mb = MeshBuilder()
	y, height = FLIGHT_WIDTH / 2 - 0.04, 0.9
	run, rise = STEP_COUNT * STEP_RUN, STEP_COUNT * STEP_RISE
	slope = rise / run

	def rail_z(x):
		return slope * x + STEP_RISE / 2 + height

	for i in range(STEP_COUNT):
		x = (i + 0.5) * STEP_RUN
		mb.box((x - 0.01, y - 0.01, (i + 1) * STEP_RISE), (x + 0.01, y + 0.01, rail_z(x)), "metal_dark")
	angle, length = math.atan2(rise, run), math.hypot(run, rise)
	rail = (Matrix.Translation((run / 2, y, rail_z(run / 2))) @ Matrix.Rotation(-angle, 4, "Y"))
	mb.box((-length / 2 - 0.1, -0.03, -0.02), (length / 2 + 0.1, 0.03, 0.03), "handrail", matrix=rail)
	visual = mb.build("hosp_stairs_railing")
	col = MeshBuilder()
	wall = Matrix.Translation((run / 2, y, rise / 2 + 0.5)) @ Matrix.Rotation(-angle, 4, "Y")
	col.box((-length / 2, -0.03, -0.5), (length / 2, 0.03, 0.5), "concrete", matrix=wall)
	return [visual, col.build("hosp_stairs_railing_col-colonly")]


def build_railing_straight():
	"""Прямое ограждение 1,3 м (край площадки). Центр нижней грани, вдоль X."""
	mb = MeshBuilder()
	half, height = 0.65, 0.95
	for i in range(11):
		x = -half + 0.05 + i * (2 * half - 0.1) / 10
		mb.box((x - 0.01, -0.01, 0), (x + 0.01, 0.01, height), "metal_dark")
	mb.box((-half, -0.01, 0.1), (half, 0.01, 0.12), "metal_dark")
	mb.box((-half, -0.03, height), (half, 0.03, height + 0.05), "handrail")
	col = MeshBuilder()
	col.box((-half, -0.03, 0), (half, 0.03, height + 0.05), "concrete")
	return [mb.build("hosp_railing_straight"), col.build("hosp_railing_straight_col-colonly")]


def build_ceiling_lamp():
	"""Люминесцентный светильник. Точка привязки — потолок (верх корпуса), вдоль X."""
	mb = MeshBuilder()
	mb.box((-0.62, -0.08, -0.07), (0.62, 0.08, 0), "metal_white")
	mb.box((-0.6, -0.065, -0.085), (0.6, 0.065, -0.07), "lamp_diffuser")
	return [mb.build("prop_ceiling_lamp")]


def build_radiator():
	"""Чугунная батарея под окном. Точка привязки — как у стены (линия стены), батарея на стороне +Y."""
	mb = MeshBuilder()
	y0 = WALL_THICKNESS / 2 + 0.05
	for i in range(10):
		x = -0.45 + i * 0.1
		mb.box((x, y0, 0.18), (x + 0.07, y0 + 0.1, 0.72), "metal_white")
	mb.box((-0.46, y0 + 0.02, 0.24), (0.46, y0 + 0.08, 0.28), "metal_white")
	mb.box((-0.46, y0 + 0.02, 0.62), (0.46, y0 + 0.08, 0.66), "metal_white")
	# стояк сбоку от окна и подводки к батарее
	mb.box((-0.84, y0 + 0.03, 0), (-0.81, y0 + 0.06, WALL_HEIGHT), "metal_white")
	for z in (0.25, 0.63):
		mb.box((-0.84, y0 + 0.035, z), (-0.46, y0 + 0.055, z + 0.02), "metal_white")
	col = MeshBuilder()
	col.box((-0.5, y0, 0.15), (0.5, y0 + 0.1, 0.75), "concrete")
	return [mb.build("prop_radiator"), col.build("prop_radiator_col-colonly")]


def build_sink():
	"""Раковина с краном и зеркалом. Точка привязки — линия стены, всё на стороне +Y."""
	mb = MeshBuilder()
	y0 = WALL_THICKNESS / 2
	mb.box((-0.25, y0, 0.66), (0.25, y0 + 0.42, 0.7), "ceramic")  # дно
	for (x0, x1, ya, yb) in ((-0.25, -0.22, 0, 0.42), (0.22, 0.25, 0, 0.42), (-0.25, 0.25, 0, 0.03), (-0.25, 0.25, 0.39, 0.42)):
		mb.box((x0, y0 + ya, 0.7), (x1, y0 + yb, 0.84), "ceramic")
	mb.box((-0.04, y0 + 0.05, 0.4), (0.04, y0 + 0.13, 0.66), "ceramic")  # кронштейн
	mb.box((-0.015, y0, 0.95), (0.015, y0 + 0.15, 0.98), "metal_white")  # кран
	mb.box((-0.015, y0 + 0.13, 0.9), (0.015, y0 + 0.16, 0.98), "metal_white")
	mb.box((-0.06, y0, 0.98), (0.06, y0 + 0.03, 1.02), "metal_white")
	mb.box((-0.22, y0, 1.15), (0.22, y0 + 0.01, 1.6), "mirror")
	col = MeshBuilder()
	col.box((-0.25, y0, 0.4), (0.25, y0 + 0.42, 0.84), "concrete")
	return [mb.build("prop_sink"), col.build("prop_sink_col-colonly")]


def build_iv_stand():
	"""Стойка для капельницы с флаконом."""
	mb = MeshBuilder()
	mb.box((-0.3, -0.02, 0.03), (0.3, 0.02, 0.06), "metal_white")
	mb.box((-0.02, -0.3, 0.03), (0.02, 0.3, 0.06), "metal_white")
	for x, y in ((-0.3, 0), (0.3, 0), (0, -0.3), (0, 0.3)):
		mb.box((x - 0.02, y - 0.02, 0), (x + 0.02, y + 0.02, 0.03), "metal_dark")
	mb.cylinder((0, 0, 0.06), 0.012, 1.84, "metal_white", segments=8)
	mb.box((-0.15, -0.006, 1.86), (0.15, 0.006, 1.88), "metal_white")
	mb.box((0.07, -0.025, 1.6), (0.15, 0.025, 1.83), "iv_bag")
	col = MeshBuilder()
	col.box((-0.15, -0.15, 0), (0.15, 0.15, 1.9), "concrete")
	return [mb.build("prop_iv_stand"), col.build("prop_iv_stand_col-colonly")]


def build_med_cabinet():
	"""Медицинский шкаф со стеклянной дверцей. Точка привязки — линия стены, шкаф на стороне +Y."""
	mb = MeshBuilder()
	y0, w, d, h = WALL_THICKNESS / 2, 0.4, 0.4, 1.75
	mb.box((-w, y0, 0.1), (w, y0 + 0.02, h), "metal_white")  # задняя стенка
	mb.box((-w, y0, 0.1), (-w + 0.02, y0 + d, h), "metal_white")
	mb.box((w - 0.02, y0, 0.1), (w, y0 + d, h), "metal_white")
	mb.box((-w, y0, h - 0.02), (w, y0 + d, h), "metal_white")
	for z in (0.1, 0.55, 0.95, 1.35):
		mb.box((-w + 0.02, y0 + 0.02, z), (w - 0.02, y0 + d - 0.02, z + 0.02), "metal_white")
	mb.box((-w + 0.03, y0 + d - 0.015, 0.13), (w - 0.03, y0 + d - 0.005, h - 0.03), "glass")
	for x in (-w + 0.01, w - 0.05):
		mb.box((x, y0 + 0.01, 0), (x + 0.04, y0 + d - 0.01, 0.1), "metal_white")  # ножки-цоколь
	col = MeshBuilder()
	col.box((-w, y0, 0), (w, y0 + d, h), "concrete")
	return [mb.build("prop_med_cabinet"), col.build("prop_med_cabinet_col-colonly")]


def build_sign_plate():
	"""Табличка на стену 30 × 12 см (текст — Label3D в сцене). Точка привязки — центр, линия стены."""
	mb = MeshBuilder()
	y0 = WALL_THICKNESS / 2
	mb.box((-0.15, y0, -0.06), (0.15, y0 + 0.012, 0.06), "sign_plate")
	return [mb.build("prop_sign_plate")]


MODULES = {
	"hosp_floor": build_floor,
	"hosp_wall": build_wall,
	"hosp_wall_corner": build_wall_corner,
	"hosp_wall_door": build_wall_door,
	"hosp_wall_window": build_wall_window,
	"hosp_door": build_door,
	"hosp_stairs_flight": build_stairs_flight,
	"hosp_stairs_landing": build_stairs_landing,
	"hosp_stairs_railing": build_stairs_railing,
	"hosp_railing_straight": build_railing_straight,
	"prop_bed": build_bed,
	"prop_cabinet": build_cabinet,
	"prop_oxygen_cylinder": build_oxygen_cylinder,
	"prop_gurney": build_gurney,
	"prop_bench": build_bench,
	"prop_ceiling_lamp": build_ceiling_lamp,
	"prop_radiator": build_radiator,
	"prop_sink": build_sink,
	"prop_iv_stand": build_iv_stand,
	"prop_med_cabinet": build_med_cabinet,
	"prop_sign_plate": build_sign_plate,
}


# --- Экспорт и превью ----------------------------------------------------------------------------

def export(objects, path):
	bpy.ops.object.select_all(action="DESELECT")
	for obj in objects:
		obj.select_set(True)
	bpy.context.view_layer.objects.active = objects[0]
	bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True,
		export_yup=True, export_apply=True)


# Материалы с текстурами: набор текстур и число повторов текстуры на метр (UV 1 = 1 м).
TEXTURED = {
	"paint_green": ("paint_green", 0.5),
	"whitewash": ("whitewash", 0.5),
	"ceiling": ("whitewash", 0.5),
	"floor_tile": ("floor_tile", 1.0),
	"concrete": ("concrete", 0.5),
	"stair_tread": ("stair_tread", 1.0),
	"door_paint": ("door_paint", 1.0),
	"frame_paint": ("door_paint", 1.0),
	"wood": ("wood", 1.0),
}
TEXTURE_DIR = "assets/textures/hospital"
MATERIAL_DIR = "assets/materials/hospital"


def write_godot_materials():
	"""Пишет библиотеку StandardMaterial3D (.tres) для Godot — по одному файлу на материал палитры.
	Скрипт импорта scripts/editor/kit_material_import.gd подставляет их в модели по имени материала."""
	os.makedirs(MATERIAL_DIR, exist_ok=True)
	for name, (rgb, roughness, metallic, alpha) in PALETTE.items():
		lines, resources = [], []
		color = (*rgb, alpha)
		if name in TEXTURED:
			texture, scale = TEXTURED[name]
			base = PALETTE[texture][0]
			color = (*[min(1.0, c / b) for c, b in zip(rgb, base)], alpha)  # оттенок поверх текстуры
			for i, (kind, prop) in enumerate((("albedo", "albedo_texture"), ("normal", "normal_texture"),
					("roughness", "roughness_texture"))):
				resources.append(f'[ext_resource type="Texture2D" path="res://{TEXTURE_DIR}/{texture}_{kind}.png" id="{i + 1}_{kind}"]')
				lines.append(f'{prop} = ExtResource("{i + 1}_{kind}")')
			lines += ["normal_enabled = true", "roughness = 1.0", f"uv1_scale = Vector3({scale}, {scale}, {scale})"]
		else:
			lines.append(f"roughness = {roughness}")
		lines.insert(0, f'albedo_color = Color({color[0]:.3f}, {color[1]:.3f}, {color[2]:.3f}, {color[3]})')
		if metallic:
			lines.append(f"metallic = {metallic}")
		if alpha < 1.0:
			lines.append("transparency = 1")
		if name in EMISSION:
			lines += ["emission_enabled = true", f"emission = Color({rgb[0]}, {rgb[1]}, {rgb[2]}, 1)",
				f"emission_energy_multiplier = {EMISSION[name]}"]
		text = "[gd_resource type=\"StandardMaterial3D\" format=3]\n\n"
		if resources:
			text += "\n".join(resources) + "\n\n"
		text += f'[resource]\nresource_name = "{name}"\n' + "\n".join(lines) + "\n"
		with open(os.path.join(MATERIAL_DIR, name + ".tres"), "w") as f:
			f.write(text)
	print(f"[hospital_kit] материалы Godot: {MATERIAL_DIR}")


def apply_preview_textures():
	"""Подключает текстуры к материалам Blender — только для превью, после экспорта."""
	for name, (texture, scale) in TEXTURED.items():
		mat = material(name)
		nodes, links = mat.node_tree.nodes, mat.node_tree.links
		bsdf = nodes["Principled BSDF"]
		coords = nodes.new("ShaderNodeTexCoord")
		mapping = nodes.new("ShaderNodeMapping")
		mapping.inputs["Scale"].default_value = (scale, scale, scale)
		links.new(coords.outputs["UV"], mapping.inputs["Vector"])
		for kind, socket in (("albedo", "Base Color"), ("roughness", "Roughness"), ("normal", None)):
			node = nodes.new("ShaderNodeTexImage")
			node.image = bpy.data.images.load(os.path.abspath(f"{TEXTURE_DIR}/{texture}_{kind}.png"))
			if kind != "albedo":
				node.image.colorspace_settings.name = "Non-Color"
			links.new(mapping.outputs["Vector"], node.inputs["Vector"])
			if socket:
				links.new(node.outputs["Color"], bsdf.inputs[socket])
			else:
				normal_map = nodes.new("ShaderNodeNormalMap")
				links.new(node.outputs["Color"], normal_map.inputs["Color"])
				links.new(normal_map.outputs["Normal"], bsdf.inputs["Normal"])


def place(objects, location, rotation_z=0.0):
	"""Ставит копию модуля (меши общие) в сцену превью. Координаты — Blender (Z вверх)."""
	for obj in objects:
		if obj.name.endswith("-colonly"):
			continue
		copy = obj.copy()
		copy.hide_render = False
		copy.location = location
		copy.rotation_euler = (0, 0, math.radians(rotation_z))
		bpy.context.scene.collection.objects.link(copy)


def render_preview(modules, path):
	"""Уголок палаты 6 × 6 м с текстурами — рендер EEVEE (запасной вариант — Workbench)."""
	for objects in modules.values():
		for obj in objects:
			obj.hide_render = True
	for x in (0, 3):
		for y in (0, 3):
			place(modules["hosp_floor"], (x, y, 0))
			place(modules["hosp_floor"], (x, y, FLOOR_HEIGHT))
	place(modules["hosp_wall_window"], (0, 4.5, 0), 180)
	place(modules["hosp_wall_window"], (3, 4.5, 0), 180)
	place(modules["hosp_wall_door"], (-1.5, 0, 0), 90)
	place(modules["hosp_wall"], (-1.5, 3, 0), 90)
	place(modules["hosp_wall_corner"], (-1.5, 4.5, 0))
	place(modules["prop_bed"], (0.6, 3.4, 0))
	place(modules["prop_bed"], (2.1, 3.4, 0))
	place(modules["prop_cabinet"], (1.35, 4.15, 0))
	place(modules["prop_oxygen_cylinder"], (-0.9, 4.1, 0))
	place(modules["prop_oxygen_cylinder"], (-0.6, 4.2, 0))
	place(modules["prop_bench"], (-1.15, 1.6, 0), 90)
	place(modules["prop_gurney"], (2.6, 0.2, 0), 90)
	place(modules["prop_radiator"], (0, 4.5, 0), 180)
	place(modules["prop_radiator"], (3, 4.5, 0), 180)
	place(modules["prop_sink"], (-1.5, 3.4, 0), -90)
	place(modules["prop_iv_stand"], (1.35, 2.7, 0))
	place(modules["prop_ceiling_lamp"], (0.5, 1.5, WALL_HEIGHT), 90)
	place(modules["prop_ceiling_lamp"], (2.5, 3.0, WALL_HEIGHT), 90)

	scene = bpy.context.scene
	world = bpy.data.worlds.new("PreviewWorld")
	world.color = (0.35, 0.37, 0.4)
	scene.world = world
	sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
	sun.data.energy = 3.0
	sun.rotation_euler = (math.radians(55), 0, math.radians(200))
	scene.collection.objects.link(sun)
	for i, loc in enumerate(((0.5, 1.5, 2.85), (2.5, 3.0, 2.85))):
		lamp = bpy.data.objects.new(f"Lamp{i}", bpy.data.lights.new(f"Lamp{i}", "POINT"))
		lamp.data.energy = 250
		lamp.data.color = (0.95, 1.0, 0.96)
		lamp.location = loc
		scene.collection.objects.link(lamp)
	cam = bpy.data.objects.new("PreviewCam", bpy.data.cameras.new("PreviewCam"))
	cam.data.lens = 18
	cam.location = (4.0, -1.0, 1.65)
	cam.rotation_euler = (Vector((-0.6, 3.6, 1.1)) - cam.location).to_track_quat("-Z", "Y").to_euler()
	scene.collection.objects.link(cam)
	scene.camera = cam
	scene.render.resolution_x, scene.render.resolution_y = 1600, 900
	scene.render.filepath = path
	for engine in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "BLENDER_WORKBENCH"):
		try:
			scene.render.engine = engine
			break
		except TypeError:
			continue
	if scene.render.engine == "BLENDER_WORKBENCH":
		scene.display.shading.color_type = "TEXTURE"
	bpy.ops.render.render(write_still=True)


def main():
	args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
	out_dir = os.path.abspath(args[0] if args else "assets/models/kits/hospital")
	preview = os.path.abspath(args[1]) if len(args) > 1 else None
	os.makedirs(out_dir, exist_ok=True)

	bpy.ops.wm.read_factory_settings(use_empty=True)
	modules = {}
	for name, builder in MODULES.items():
		objects = builder()
		export(objects, os.path.join(out_dir, name + ".glb"))
		modules[name] = objects
		print(f"[hospital_kit] {name}.glb")
	write_godot_materials()

	if preview:
		apply_preview_textures()
		render_preview(modules, preview)
		print(f"[hospital_kit] превью: {preview}")


main()
