"""Модульный набор «Больница» v0.5 — генератор для Blender.

Строит модули (стены, углы, перекрытия, двери, лестницы, реквизит) и выгружает каждый в отдельный
.glb. Пишет библиотеку материалов Godot (assets/materials/hospital/*.tres), которые ссылаются на
текстуры из tools/blender/build_textures.py. Превью рендерится с текстурами.
Техописание — docs/TECHNICAL_DESIGN.md, «Модульный набор „Больница“ v0.1».

Запуск (из корня проекта):
    Blender -b --factory-startup --python tools/blender/build_hospital_kit.py -- <папка> [превью.png] [--overwrite-materials]

Модели .glb пересобираются всегда; материалы .tres — только недостающие (D-037).

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
	# v0.4 — шлюз, подвал, рампа
	"wall_tile": ((0.88, 0.89, 0.88), 0.2, 0.0, 1.0),
	"brick": ((0.78, 0.76, 0.70), 0.9, 0.0, 1.0),
	"asphalt": ((0.24, 0.24, 0.23), 0.95, 0.0, 1.0),
	"paint_grey": ((0.45, 0.47, 0.47), 0.5, 0.0, 1.0),
	"metal_grey": ((0.42, 0.44, 0.44), 0.45, 0.5, 1.0),
	"tyvek": ((0.93, 0.94, 0.95), 0.8, 0.0, 1.0),
	"cardboard": ((0.55, 0.42, 0.28), 0.9, 0.0, 1.0),
	"wood_raw": ((0.70, 0.58, 0.40), 0.85, 0.0, 1.0),
	"rubber_black": ((0.08, 0.08, 0.08), 0.8, 0.0, 1.0),
	"hazard_yellow": ((0.85, 0.70, 0.10), 0.5, 0.0, 1.0),
	"warning_red": ((0.70, 0.10, 0.08), 0.5, 0.0, 1.0),
	"pipe_insulation": ((0.75, 0.74, 0.70), 0.9, 0.0, 1.0),
	"pipe_rust": ((0.30, 0.20, 0.15), 0.7, 0.6, 1.0),
	"roof_metal": ((0.55, 0.57, 0.58), 0.4, 0.8, 1.0),
	"lamp_warm": ((1.00, 0.85, 0.60), 0.3, 0.0, 1.0),
	# v0.5 — болванки наброска (заменить готовыми моделями)
	"blockout_orange": ((0.95, 0.50, 0.10), 0.6, 0.0, 1.0),
	"blockout_white": ((0.92, 0.92, 0.90), 0.6, 0.0, 1.0),
}

# Светящиеся материалы: сила свечения.
EMISSION = {"lamp_diffuser": 3.0, "lamp_warm": 2.5}

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

	def box(self, mn, mx, mat, top=None, bottom=None, matrix=None, faces=None):
		"""Коробка от угла mn до угла mx. top/bottom — отдельные материалы верхней/нижней грани;
		faces — материалы граней по направлению нормали: {"+y": ..., "-y": ...}."""
		size = Vector(mx) - Vector(mn)
		center = (Vector(mx) + Vector(mn)) / 2
		verts = bmesh.ops.create_cube(self.bm, size=1.0)["verts"]
		transform = Matrix.Translation(center) @ Matrix.Diagonal((*size, 1.0))
		if matrix is not None:
			transform = matrix @ transform
		bmesh.ops.transform(self.bm, matrix=transform, verts=verts)
		faces = dict(faces or {})
		if top:
			faces["+z"] = top
		if bottom:
			faces["-z"] = bottom
		self._assign(verts, mat, faces)

	def cylinder(self, center, radius, height, mat, segments=16, matrix=None):
		"""Цилиндр вдоль Z; center — центр нижнего основания. matrix — дополнительный поворот/сдвиг."""
		transform = Matrix.Translation(Vector(center) + Vector((0, 0, height / 2)))
		if matrix is not None:
			transform = matrix @ transform
		verts = bmesh.ops.create_cone(
			self.bm, cap_ends=True, segments=segments,
			radius1=radius, radius2=radius, depth=height, matrix=transform,
		)["verts"]
		self._assign(verts, mat)
		axis = (transform.to_3x3() @ Vector((0, 0, 1))).normalized()
		for face in {f for v in verts for f in v.link_faces}:
			face.smooth = abs(face.normal.dot(axis)) < 0.5

	def _assign(self, verts, mat, faces=None):
		self.bm.normal_update()
		for face in {f for v in verts for f in v.link_faces}:
			name = mat
			if faces:
				n = face.normal
				axis = max(range(3), key=lambda i: abs(n[i]))
				key = ("+" if n[axis] > 0 else "-") + "xyz"[axis]
				name = faces.get(key, mat)
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


# Отделка стен: полосы (верхняя граница полосы, материал) снизу вверх; None — до верха.
STYLES = {
	"paint": ((PAINT_HEIGHT, "paint_green"), (None, "whitewash")),  # палаты, коридоры
	"tile": ((1.8, "wall_tile"), (None, "whitewash")),               # шлюз, процедурные
	"basement": ((1.2, "paint_grey"), (None, "whitewash")),          # подвал, склад
	"brick": ((None, "brick"),),                                     # фасад
	"concrete": ((None, "concrete"),),                               # стены в грунте
}


def style_material(style, z):
	for limit, mat in STYLES[style]:
		if limit is None or z < limit:
			return mat


def wall_piece(mb, x0, x1, z0, z1, inner="paint", outer=None, t=WALL_THICKNESS / 2):
	"""Участок стены. inner — отделка стороны +Y (внутренняя), outer — стороны −Y (по умолчанию та же)."""
	outer = outer or inner
	cuts = sorted({z0, z1} | {lim for st in (inner, outer) for lim, _ in STYLES[st]
		if lim is not None and z0 < lim < z1})
	for a, b in zip(cuts, cuts[1:]):
		mid = (a + b) / 2
		mat = style_material(inner, mid)
		mb.box((x0, -t, a), (x1, t, b), mat, faces={"+y": mat, "-y": style_material(outer, mid)})


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


def make_wall_window(name, inner="paint", outer=None):
	return lambda: _wall_window(name, inner, outer)


def _wall_window(name, inner, outer):
	mb = MeshBuilder()
	h, w = CELL / 2, WINDOW_WIDTH / 2
	wall_piece(mb, -h, -w, 0, WALL_HEIGHT, inner, outer)
	wall_piece(mb, w, h, 0, WALL_HEIGHT, inner, outer)
	wall_piece(mb, -w, w, 0, WINDOW_SILL, inner, outer)
	wall_piece(mb, -w, w, WINDOW_TOP, WALL_HEIGHT, inner, outer)
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
	return [mb.build(name + "-col")]


def build_door():
	"""Дверное полотно. Ось — на петлях (x = 0), полотно идёт вдоль +X."""
	mb = MeshBuilder()
	width = DOOR_WIDTH - 2 * FRAME - 0.02
	mb.box((0, -0.025, 0.01), (width, 0.025, DOOR_HEIGHT - FRAME - 0.01), "door_paint")
	mb.box((width - 0.12, -0.06, 0.95), (width - 0.08, 0.06, 1.05), "metal_dark")
	return [mb.build("hosp_door-col")]


def make_wall(name, inner="paint", outer=None):
	def build():
		mb = MeshBuilder()
		wall_piece(mb, -CELL / 2, CELL / 2, 0, WALL_HEIGHT, inner, outer)
		return [mb.build(name + "-col")]
	return build


def make_wall_opening(name, width, height, inner="paint", outer=None, frame="frame_paint"):
	"""Стена с проёмом (дверь, ворота) по центру."""
	def build():
		mb = MeshBuilder()
		h, d = CELL / 2, width / 2
		wall_piece(mb, -h, -d, 0, WALL_HEIGHT, inner, outer)
		wall_piece(mb, d, h, 0, WALL_HEIGHT, inner, outer)
		wall_piece(mb, -d, d, height, WALL_HEIGHT, inner, outer)
		t = WALL_THICKNESS / 2 + 0.02
		mb.box((-d, -t, 0), (-d + FRAME, t, height), frame)
		mb.box((d - FRAME, -t, 0), (d, t, height), frame)
		mb.box((-d, -t, height - FRAME), (d, t, height), frame)
		return [mb.build(name + "-col")]
	return build


def make_corner(name, style):
	def build():
		mb = MeshBuilder()
		t = WALL_THICKNESS / 2
		wall_piece(mb, -t, t, 0, WALL_HEIGHT, style, style, t)
		return [mb.build(name + "-col")]
	return build


def make_door_leaf(name, mat, opening=DOOR_WIDTH, height=DOOR_HEIGHT):
	"""Полотно двери/створка ворот. Ось — на петлях (x = 0), полотно вдоль +X."""
	def build():
		mb = MeshBuilder()
		width = opening - 2 * FRAME - 0.02
		mb.box((0, -0.025, 0.01), (width, 0.025, height - FRAME - 0.01), mat)
		mb.box((width - 0.12, -0.06, 0.95), (width - 0.08, 0.06, 1.05), "metal_dark")
		return [mb.build(name + "-col")]
	return build


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


def make_stairs_railing(name, side=1):
	"""Перила марша: стойки на каждой ступени и поручень. Та же точка привязки, что у марша;
	side=1 — у края +Y (внутренняя сторона между маршами), side=−1 — у края −Y."""
	return lambda: _stairs_railing(name, side)


def _stairs_railing(name, side):
	mb = MeshBuilder()
	y, height = side * (FLIGHT_WIDTH / 2 - 0.04), 0.9
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
	visual = mb.build(name)
	col = MeshBuilder()
	wall = Matrix.Translation((run / 2, y, rise / 2 + 0.5)) @ Matrix.Rotation(-angle, 4, "Y")
	col.box((-length / 2, -0.03, -0.5), (length / 2, 0.03, 0.5), "concrete", matrix=wall)
	return [visual, col.build(name + "_col-colonly")]


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


# --- v0.4: шлюз, подвал, рампа -------------------------------------------------------------------

def build_floor_concrete():
	"""Перекрытие с бетонным полом (подвал, склад)."""
	mb = MeshBuilder()
	h = CELL / 2
	mb.box((-h, -h, -SLAB), (h, h, 0), "concrete", bottom="ceiling")
	return [mb.build("hosp_floor_concrete-col")]


def build_floor_half():
	"""Половина перекрытия 3 × 1,5 м (край над лестничным проёмом). Центр половины, верх на нуле."""
	mb = MeshBuilder()
	mb.box((-CELL / 2, -CELL / 4, -SLAB), (CELL / 2, CELL / 4, 0), "concrete", top="concrete", bottom="ceiling")
	return [mb.build("hosp_floor_half-col")]


def build_beam():
	"""Ригель 3 × 0,2 × 0,2 м — закрывает торец перекрытия там, где пола нет. Верх на нуле."""
	mb = MeshBuilder()
	mb.box((-CELL / 2, -WALL_THICKNESS / 2, -SLAB), (CELL / 2, WALL_THICKNESS / 2, 0), "concrete")
	return [mb.build("hosp_beam-col")]


def build_stairs_landing_half():
	"""Узкая площадка 1,4 × 1,3 м — только под шириной марша."""
	mb = MeshBuilder()
	mb.box((-0.7, -0.65, -SLAB), (0.7, 0.65, 0), "concrete", top="stair_tread", bottom="ceiling")
	return [mb.build("hosp_stairs_landing_half-col")]


DOCK_HEIGHT = 1.1


def build_dock_platform():
	"""Погрузочная рампа 3 × 3 м высотой 1,1 м. Центр, верх на нуле; отбойники — на стороне −Y (к двору)."""
	mb = MeshBuilder()
	h = CELL / 2
	mb.box((-h, -h, -DOCK_HEIGHT), (h, h, 0), "concrete")
	mb.box((-h, -h - 0.01, -0.06), (h, -h + 0.05, 0), "metal_grey")  # уголок по кромке
	for x in (-0.9, 0.9):
		mb.box((x - 0.15, -h - 0.12, -0.75), (x + 0.15, -h, -0.25), "rubber_black")
	return [mb.build("hosp_dock_platform-col")]


def build_dock_steps():
	"""Лестница на рампу: 5 ступеней по 0,22 м, ширина 1,2 м, подъём вдоль +X; пандус-коллизия."""
	mb = MeshBuilder()
	w, rise, run, n = 0.6, DOCK_HEIGHT / 5, 0.3, 5
	for i in range(n):
		mb.box((i * run, -w, 0), ((i + 1) * run, w, (i + 1) * rise), "concrete", top="concrete")
	angle, length = math.atan2(DOCK_HEIGHT, n * run), math.hypot(DOCK_HEIGHT, n * run)
	ramp = MeshBuilder()
	m = (Matrix.Translation((n * run / 2, 0, DOCK_HEIGHT / 2)) @ Matrix.Rotation(-angle, 4, "Y")
		@ Matrix.Translation((0, 0, -0.05)))
	ramp.box((-length / 2, -w, -0.05), (length / 2, w, 0.05), "concrete", matrix=m)
	return [mb.build("hosp_dock_steps"), ramp.build("hosp_dock_steps_ramp-colonly")]


def build_dock_canopy():
	"""Навес над рампой, секция 3 м. Привязка — линия стены на уровне рампы; навес на стороне −Y (к двору)."""
	mb = MeshBuilder()
	h, depth, z_wall, z_front = CELL / 2, 3.0, 3.0, 2.7
	angle = math.atan2(z_wall - z_front, depth)
	roof = Matrix.Translation((0, -depth / 2 - WALL_THICKNESS / 2, (z_wall + z_front) / 2)) @ Matrix.Rotation(angle, 4, "X")
	mb.box((-h, -depth / 2, -0.02), (h, depth / 2, 0.02), "roof_metal", matrix=roof)
	y_front = -depth - WALL_THICKNESS / 2 + 0.1
	mb.box((-h, y_front - 0.05, z_front - 0.15), (h, y_front + 0.05, z_front - 0.03), "metal_grey")  # прогон
	mb.box((-0.05, y_front - 0.05, 0), (0.05, y_front + 0.05, z_front - 0.03), "metal_grey")  # стойка
	col = MeshBuilder()
	col.box((-0.06, y_front - 0.06, 0), (0.06, y_front + 0.06, z_front), "concrete")
	return [mb.build("hosp_dock_canopy"), col.build("hosp_dock_canopy_col-colonly")]


def build_ground_asphalt():
	"""Асфальт двора, плита 6 × 6 м. Центр, верх на нуле."""
	mb = MeshBuilder()
	mb.box((-3, -3, -0.2), (3, 3, 0), "concrete", top="asphalt")
	return [mb.build("ext_ground_asphalt-col")]


def _boxes_on(mb, x0, x1, y0, y1, z, seed):
	"""Ставит коробки в ряд на полку/поддон; размеры чуть разные, но всегда одинаковые при пересборке."""
	x = x0
	k = seed
	while True:
		w = 0.3 + (k * 37 % 5) * 0.03
		hgt = 0.2 + (k * 53 % 4) * 0.04
		if x + w > x1:
			break
		d = min(y1 - y0, 0.3 + (k * 29 % 3) * 0.05)
		mb.box((x, y0, z), (x + w - 0.02, y0 + d, z + hgt), "cardboard")
		mb.box((x + (w - 0.02) / 2 - 0.02, y0, z + hgt), (x + (w - 0.02) / 2 + 0.02, y0 + d, z + hgt + 0.002), "tyvek")
		x += w
		k += 1


def build_shelf_rack():
	"""Металлический стеллаж 1,8 × 0,5 × 2 м с коробками. Центр низа; глубина вдоль Y."""
	mb = MeshBuilder()
	w, d, h = 0.9, 0.25, 2.0
	for x in (-w, w - 0.04):
		for y in (-d, d - 0.04):
			mb.box((x, y, 0), (x + 0.04, y + 0.04, h), "metal_grey")
	for i, z in enumerate((0.1, 0.6, 1.1, 1.6, 1.98)):
		mb.box((-w, -d, z), (w, d, z + 0.02), "metal_grey")
		if z < 1.9:
			_boxes_on(mb, -w + 0.05, w - 0.05, -d + 0.03, d - 0.03, z + 0.02, i * 3 + 1)
	col = MeshBuilder()
	col.box((-w, -d, 0), (w, d, h), "concrete")
	return [mb.build("prop_shelf_rack"), col.build("prop_shelf_rack_col-colonly")]


def build_box():
	"""Картонная коробка 0,4 × 0,3 × 0,3 м с лентой."""
	mb = MeshBuilder()
	mb.box((-0.2, -0.15, 0), (0.2, 0.15, 0.3), "cardboard")
	mb.box((-0.2, -0.02, 0.3), (0.2, 0.02, 0.302), "tyvek")
	return [mb.build("prop_box-col")]


def _pallet(mb):
	for y in (-0.38, -0.02, 0.32):
		mb.box((-0.6, y, 0), (0.6, y + 0.06, 0.1), "wood_raw")
	for i in range(7):
		x = -0.6 + i * 0.19
		mb.box((x, -0.4, 0.1), (x + 0.12, 0.4, 0.13), "wood_raw")


def build_pallet():
	"""Деревянный поддон 1,2 × 0,8 м."""
	mb = MeshBuilder()
	_pallet(mb)
	return [mb.build("prop_pallet-col")]


def build_pallet_boxes():
	"""Поддон с коробками в два яруса — укрытие высотой ~1 м."""
	mb = MeshBuilder()
	_pallet(mb)
	for layer in range(2):
		z = 0.13 + layer * 0.42
		for row, (y0, y1) in enumerate(((-0.4, -0.01), (0.01, 0.4))):
			_boxes_on(mb, -0.6, 0.6, y0, y1, z, layer * 5 + row * 2 + 7)
	col = MeshBuilder()
	col.box((-0.6, -0.4, 0), (0.6, 0.4, 0.95), "concrete")
	return [mb.build("prop_pallet_boxes"), col.build("prop_pallet_boxes_col-colonly")]


def build_coat_rack_suits():
	"""Настенная вешалка с защитными комбинезонами. Привязка — линия стены, всё на стороне +Y."""
	mb = MeshBuilder()
	y0 = WALL_THICKNESS / 2
	mb.box((-0.9, y0, 1.9), (0.9, y0 + 0.03, 1.98), "wood")
	for i in range(4):
		x = -0.6 + i * 0.4
		mb.box((x - 0.01, y0, 1.88), (x + 0.01, y0 + 0.08, 1.92), "metal_dark")  # крючок
		yy = y0 + 0.05
		mb.box((x - 0.12, yy, 1.65), (x + 0.12, yy + 0.12, 1.88), "tyvek")  # капюшон
		mb.box((x - 0.2, yy, 0.95), (x + 0.2, yy + 0.14, 1.67), "tyvek")  # туловище
		mb.box((x - 0.19, yy + 0.01, 0.25), (x - 0.02, yy + 0.13, 0.97), "tyvek")  # штанины
		mb.box((x + 0.02, yy + 0.01, 0.25), (x + 0.19, yy + 0.13, 0.97), "tyvek")
	col = MeshBuilder()
	col.box((-0.9, y0, 0.25), (0.9, y0 + 0.2, 1.98), "concrete")
	return [mb.build("prop_coat_rack_suits"), col.build("prop_coat_rack_suits_col-colonly")]


def build_pipe_run():
	"""Трубы под потолком, секция 3 м вдоль X: две голые и одна в изоляции, кронштейны.
	Привязка — линия стены на высоте оси труб; трубы на стороне +Y."""
	mb = MeshBuilder()
	y0 = WALL_THICKNESS / 2
	along_x = Matrix.Rotation(math.radians(90), 4, "Y")
	for y, z, r, mat in ((y0 + 0.12, 0.0, 0.05, "pipe_rust"), (y0 + 0.28, 0.0, 0.05, "pipe_rust"),
			(y0 + 0.2, 0.22, 0.1, "pipe_insulation")):
		mb.cylinder((-z, y, -CELL / 2), r, CELL, mat, segments=12, matrix=along_x)
	for x in (-0.75, 0.75):
		mb.box((x - 0.02, y0, -0.07), (x + 0.02, y0 + 0.36, -0.05), "metal_dark")
		mb.box((x - 0.02, y0, 0.08), (x + 0.02, y0 + 0.32, 0.1), "metal_dark")
	return [mb.build("prop_pipe_run")]


def build_bulkhead_lamp():
	"""Плафон в решётке (подвал, рампа). Привязка — потолок, висит вниз."""
	mb = MeshBuilder()
	mb.cylinder((0, 0, -0.04), 0.12, 0.04, "metal_dark", segments=12)
	mb.cylinder((0, 0, -0.15), 0.09, 0.11, "lamp_warm", segments=12)
	for a in range(4):
		m = Matrix.Rotation(math.radians(45 + 90 * a), 4, "Z")
		mb.box((0.088, -0.006, -0.16), (0.1, 0.006, -0.04), "metal_dark", matrix=m)
	mb.box((-0.1, -0.006, -0.165), (0.1, 0.006, -0.155), "metal_dark")
	mb.box((-0.006, -0.1, -0.165), (0.006, 0.1, -0.155), "metal_dark")
	return [mb.build("prop_bulkhead_lamp")]


def build_bin_hazard():
	"""Жёлтый бак для медицинских отходов класса Б."""
	mb = MeshBuilder()
	mb.cylinder((0, 0, 0), 0.2, 0.55, "hazard_yellow", segments=16)
	mb.cylinder((0, 0, 0.55), 0.21, 0.04, "hazard_yellow", segments=16)
	mb.box((-0.06, -0.26, 0), (0.06, -0.18, 0.03), "metal_dark")  # педаль
	col = MeshBuilder()
	col.box((-0.21, -0.21, 0), (0.21, 0.21, 0.59), "concrete")
	return [mb.build("prop_bin_hazard"), col.build("prop_bin_hazard_col-colonly")]


def build_floor_line():
	"""Красная линия на полу 3 м — граница «чистой» и «грязной» зоны."""
	mb = MeshBuilder()
	mb.box((-CELL / 2, -0.04, 0), (CELL / 2, 0.04, 0.003), "warning_red")
	return [mb.build("prop_floor_line")]


def build_sign_plate_red():
	"""Красная табличка 40 × 15 см (текст — Label3D). Привязка — центр, линия стены, сторона +Y."""
	mb = MeshBuilder()
	y0 = WALL_THICKNESS / 2
	mb.box((-0.2, y0, -0.075), (0.2, y0 + 0.012, 0.075), "warning_red")
	return [mb.build("prop_sign_plate_red")]


# --- v0.5: модули для наброска уровня миссии 3 --------------------------------------------------

def make_wall_glass(name, door=False):
	"""Стеклянная перегородка (вестибюль): глухой низ 0,9 м, стекло до 2,4 м, побелка выше.
	С door=True — посередине дверной проём."""
	def build():
		mb = MeshBuilder()
		h, t, sill, top = CELL / 2, WALL_THICKNESS / 2, 0.9, 2.4
		spans = [(-h, -DOOR_WIDTH / 2), (DOOR_WIDTH / 2, h)] if door else [(-h, h)]
		for x0, x1 in spans:
			wall_piece(mb, x0, x1, 0, sill)
			mb.box((x0, -0.05, sill), (x1, 0.05, sill + FRAME), "frame_paint")
			mb.box((x0 + 0.02, -0.005, sill + FRAME), (x1 - 0.02, 0.005, top - FRAME), "glass")
			n = max(1, round((x1 - x0) / 1.0))
			for k in range(n + 1):  # стойки рамы
				x = x0 + (x1 - x0) * k / n
				mb.box((x - FRAME / 2, -0.05, sill), (x + FRAME / 2, 0.05, top), "frame_paint")
		wall_piece(mb, -h, h, top, WALL_HEIGHT)
		mb.box((-h, -0.05, top - FRAME), (h, 0.05, top), "frame_paint")
		if door:
			d = DOOR_WIDTH / 2
			mb.box((-d, -t - 0.02, 0), (-d + FRAME, t + 0.02, DOOR_HEIGHT), "frame_paint")
			mb.box((d - FRAME, -t - 0.02, 0), (d, t + 0.02, DOOR_HEIGHT), "frame_paint")
			mb.box((-d, -0.05, DOOR_HEIGHT), (d, 0.05, top), "glass")
		return [mb.build(name + "-col")]
	return build


def build_porch():
	"""Крыльцо 3 × 3 × 1,1 м (без отбойников). Центр, верх на нуле."""
	mb = MeshBuilder()
	h = CELL / 2
	mb.box((-h, -h, -DOCK_HEIGHT), (h, h, 0), "concrete")
	return [mb.build("hosp_porch-col")]


def build_roof():
	"""Кровля 3 × 3 м: сверху рубероид (текстура асфальта), снизу побелка. Центр, верх на нуле."""
	mb = MeshBuilder()
	h = CELL / 2
	mb.box((-h, -h, -SLAB), (h, h, 0), "concrete", top="asphalt", bottom="ceiling")
	return [mb.build("hosp_roof-col")]


def build_band():
	"""Межэтажный пояс фасада 3,2 × 0,24 × 0,2 м (перекрывает углы): закрывает торец перекрытия
	на линии стены. Ставится на отметке пола верхнего этажа (верх на нуле)."""
	mb = MeshBuilder()
	mb.box((-1.6, -0.12, -SLAB), (1.6, 0.12, 0), "concrete")
	return [mb.build("hosp_band-col")]


def build_plinth():
	"""Цоколь под стеной: 3,2 м (перекрывает углы), от −1,3 до −0,2 м. Ставится на уровне пола этажа."""
	mb = MeshBuilder()
	mb.box((-1.6, -0.12, -1.3), (1.6, 0.12, -SLAB), "concrete")
	return [mb.build("hosp_plinth-col")]


def build_asphalt_small():
	"""Асфальт 3 × 3 м — для узких полос у стен."""
	mb = MeshBuilder()
	mb.box((-1.5, -1.5, -0.2), (1.5, 1.5, 0), "concrete", top="asphalt")
	return [mb.build("ext_ground_asphalt_small-col")]


def build_fence():
	"""Забор территории, секция 3 м вдоль X: бетонный столб на −X, металлические прутья."""
	mb = MeshBuilder()
	mb.box((-1.58, -0.08, 0), (-1.42, 0.08, 2.2), "concrete")
	for z in (0.15, 1.9):
		mb.box((-1.42, -0.015, z), (1.5, 0.015, z + 0.04), "metal_dark")
	for i in range(19):
		x = -1.35 + i * 0.15
		mb.box((x - 0.01, -0.01, 0.05), (x + 0.01, 0.01, 2.05), "metal_dark")
	col = MeshBuilder()
	col.box((-1.58, -0.08, 0), (1.5, 0.08, 2.2), "concrete")
	return [mb.build("ext_fence"), col.build("ext_fence_col-colonly")]


def make_vehicle(name, parts, wheels):
	"""Болванка машины для наброска (оранжевая — «заменить готовой моделью»). Длина вдоль X, нос на +X.
	parts — коробки (mn, mx, материал); wheels — x-координаты осей."""
	def build():
		mb = MeshBuilder()
		for mn, mx, mat in parts:
			mb.box(mn, mx, mat)
		width = max(mx[1] for mn, mx, _ in parts)
		for x in wheels:
			for y in (-width + 0.05, width - 0.25):
				mb.box((x - 0.45, y, 0), (x + 0.45, y + 0.2, 0.9), "rubber_black")
		return [mb.build(name + "-col")]
	return build


def build_desk():
	"""Стол (пост медсестры, ординаторская) 1,2 × 0,6 м. Центр низа, глубина вдоль Y."""
	mb = MeshBuilder()
	mb.box((-0.6, -0.3, 0.72), (0.6, 0.3, 0.76), "wood")
	mb.box((0.15, -0.28, 0.1), (0.58, 0.28, 0.72), "wood")  # тумба
	for x in (-0.58, ):
		for y in (-0.28, 0.24):
			mb.box((x, y, 0), (x + 0.04, y + 0.04, 0.72), "metal_dark")
	mb.box((-0.5, -0.1, 0.76), (-0.2, 0.15, 0.78), "tyvek")  # журнал
	return [mb.build("prop_desk-col")]


def build_chair():
	"""Стул."""
	mb = MeshBuilder()
	mb.box((-0.22, -0.22, 0.44), (0.22, 0.22, 0.48), "wood")
	mb.box((-0.22, 0.18, 0.48), (0.22, 0.22, 0.9), "wood")
	for x in (-0.21, 0.18):
		for y in (-0.21, 0.18):
			mb.box((x, y, 0), (x + 0.03, y + 0.03, 0.44), "metal_dark")
	return [mb.build("prop_chair-col")]


def build_washer():
	"""Промышленная стиральная машина 0,8 × 1,0 × 1,4 м с круглым люком на стороне −Y."""
	mb = MeshBuilder()
	mb.box((-0.4, -0.5, 0), (0.4, 0.5, 1.4), "metal_white")
	along_y = Matrix.Rotation(math.radians(90), 4, "X")
	mb.cylinder((0, -0.8, 0.51), 0.28, 0.02, "glass", segments=20, matrix=along_y)
	mb.cylinder((0, -0.8, 0.505), 0.32, 0.01, "metal_dark", segments=20, matrix=along_y)
	mb.box((-0.35, -0.51, 1.15), (0.35, -0.5, 1.35), "metal_dark")  # панель
	return [mb.build("prop_washer-col")]


MODULES = {
	"hosp_floor": build_floor,
	"hosp_wall": build_wall,
	"hosp_wall_corner": build_wall_corner,
	"hosp_wall_door": build_wall_door,
	"hosp_wall_window": make_wall_window("hosp_wall_window"),
	"hosp_door": build_door,
	"hosp_stairs_flight": build_stairs_flight,
	"hosp_stairs_landing": build_stairs_landing,
	"hosp_stairs_railing": make_stairs_railing("hosp_stairs_railing", 1),
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
	# v0.4 — отделка стен: _tile (кафель), _bsmt (подвал); _ext — снаружи кирпич/бетон
	"hosp_wall_tile": make_wall("hosp_wall_tile", "tile"),
	"hosp_wall_tile_ext": make_wall("hosp_wall_tile_ext", "tile", "brick"),
	"hosp_wall_door_tile": make_wall_opening("hosp_wall_door_tile", DOOR_WIDTH, DOOR_HEIGHT, "tile"),
	"hosp_wall_door_tile_bsmt": make_wall_opening("hosp_wall_door_tile_bsmt", DOOR_WIDTH, DOOR_HEIGHT, "tile",
		"basement"),
	"hosp_wall_corner_tile": make_corner("hosp_wall_corner_tile", "tile"),
	"hosp_wall_bsmt": make_wall("hosp_wall_bsmt", "basement"),
	"hosp_wall_bsmt_ext": make_wall("hosp_wall_bsmt_ext", "basement", "brick"),
	"hosp_wall_bsmt_ground": make_wall("hosp_wall_bsmt_ground", "basement", "concrete"),
	"hosp_wall_door_bsmt": make_wall_opening("hosp_wall_door_bsmt", DOOR_WIDTH, DOOR_HEIGHT, "basement",
		frame="metal_grey"),
	"hosp_wall_gate_bsmt_ext": make_wall_opening("hosp_wall_gate_bsmt_ext", 2.4, 2.4, "basement", "brick",
		frame="metal_grey"),
	"hosp_wall_corner_bsmt": make_corner("hosp_wall_corner_bsmt", "basement"),
	"hosp_wall_corner_brick": make_corner("hosp_wall_corner_brick", "brick"),
	"hosp_door_metal": make_door_leaf("hosp_door_metal", "metal_grey"),
	"hosp_gate_leaf": make_door_leaf("hosp_gate_leaf", "metal_grey", 1.2 + 2 * FRAME, 2.4),
	"hosp_floor_concrete": build_floor_concrete,
	"hosp_floor_half": build_floor_half,
	"hosp_beam": build_beam,
	"hosp_stairs_landing_half": build_stairs_landing_half,
	"hosp_stairs_railing_l": make_stairs_railing("hosp_stairs_railing_l", -1),
	"hosp_dock_platform": build_dock_platform,
	"hosp_dock_steps": build_dock_steps,
	"hosp_dock_canopy": build_dock_canopy,
	"ext_ground_asphalt": build_ground_asphalt,
	"prop_shelf_rack": build_shelf_rack,
	"prop_box": build_box,
	"prop_pallet": build_pallet,
	"prop_pallet_boxes": build_pallet_boxes,
	"prop_coat_rack_suits": build_coat_rack_suits,
	"prop_pipe_run": build_pipe_run,
	"prop_bulkhead_lamp": build_bulkhead_lamp,
	"prop_bin_hazard": build_bin_hazard,
	"prop_floor_line": build_floor_line,
	"prop_sign_plate_red": build_sign_plate_red,
	# v0.5 — для наброска уровня миссии 3
	"hosp_wall_ext": make_wall("hosp_wall_ext", "paint", "brick"),
	"hosp_wall_window_ext": make_wall_window("hosp_wall_window_ext", "paint", "brick"),
	"hosp_wall_window_tile_ext": make_wall_window("hosp_wall_window_tile_ext", "tile", "brick"),
	"hosp_wall_door_ext": make_wall_opening("hosp_wall_door_ext", DOOR_WIDTH, DOOR_HEIGHT, "paint", "brick"),
	"hosp_wall_door_tile_ext": make_wall_opening("hosp_wall_door_tile_ext", DOOR_WIDTH, DOOR_HEIGHT, "tile", "brick"),
	"hosp_wall_tile_paint": make_wall("hosp_wall_tile_paint", "tile", "paint"),
	"hosp_wall_door_tile_paint": make_wall_opening("hosp_wall_door_tile_paint", DOOR_WIDTH, DOOR_HEIGHT, "tile", "paint"),
	"hosp_wall_bsmt_paint": make_wall("hosp_wall_bsmt_paint", "basement", "paint"),
	"hosp_wall_door_bsmt_paint": make_wall_opening("hosp_wall_door_bsmt_paint", DOOR_WIDTH, DOOR_HEIGHT,
		"basement", "paint", frame="metal_grey"),
	"hosp_wall_glass": make_wall_glass("hosp_wall_glass"),
	"hosp_wall_glass_door": make_wall_glass("hosp_wall_glass_door", door=True),
	"hosp_porch": build_porch,
	"hosp_plinth": build_plinth,
	"hosp_roof": build_roof,
	"hosp_band": build_band,
	"ext_ground_asphalt_small": build_asphalt_small,
	"ext_fence": build_fence,
	"blk_vehicle_truck": make_vehicle("blk_vehicle_truck", [
		((-3.7, -1.25, 0.5), (-1.3, 1.25, 3.1), "blockout_orange"),   # кузов под тентом
		((-1.2, -1.2, 0.5), (1.2, 1.2, 1.1), "blockout_orange"),      # рама
		((1.3, -1.2, 0.6), (3.7, 1.2, 2.9), "blockout_orange")], (-2.8, -1.4, 2.6)),  # кабина
	"blk_vehicle_van": make_vehicle("blk_vehicle_van", [
		((-2.75, -1.05, 0.4), (1.5, 1.05, 2.4), "blockout_orange"),
		((1.5, -1.0, 0.4), (2.75, 1.0, 1.9), "blockout_orange")], (-1.8, 1.9)),
	"blk_vehicle_uaz": make_vehicle("blk_vehicle_uaz", [
		((-2.2, -1.0, 0.45), (2.2, 1.0, 2.1), "blockout_orange")], (-1.3, 1.3)),
	"blk_vehicle_ambulance": make_vehicle("blk_vehicle_ambulance", [
		((-2.75, -1.05, 0.4), (1.5, 1.05, 2.5), "blockout_white"),
		((-2.76, -1.06, 1.2), (1.51, 1.06, 1.45), "warning_red"),
		((1.5, -1.0, 0.4), (2.75, 1.0, 1.9), "blockout_white")], (-1.8, 1.9)),
	"prop_desk": build_desk,
	"prop_chair": build_chair,
	"prop_washer": build_washer,
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
	"wall_tile": ("wall_tile", 1.0),
	"brick": ("brick", (1 / 1.04, 1 / 1.05)),
	"asphalt": ("asphalt", 0.25),
	"paint_grey": ("paint_grey", 0.5),
}
TEXTURE_DIR = "assets/textures/hospital"
MATERIAL_DIR = "assets/materials/hospital"


def write_godot_materials(overwrite=False):
	"""Пишет библиотеку StandardMaterial3D (.tres) для Godot — по одному файлу на материал палитры.
	Скрипт импорта scripts/editor/kit_material_import.gd подставляет их в модели по имени материала.
	Существующие файлы не трогает (их мог доработать создатель, D-037) — только при overwrite."""
	os.makedirs(MATERIAL_DIR, exist_ok=True)
	created = 0
	for name, (rgb, roughness, metallic, alpha) in PALETTE.items():
		target = os.path.join(MATERIAL_DIR, name + ".tres")
		if os.path.exists(target) and not overwrite:
			continue
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
			sx, sy = scale if isinstance(scale, tuple) else (scale, scale)
			lines += ["normal_enabled = true", "roughness = 1.0", f"uv1_scale = Vector3({sx:g}, {sy:g}, 1)"]
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
		with open(target, "w") as f:
			f.write(text)
		created += 1
	print(f"[hospital_kit] материалы Godot: записано {created} в {MATERIAL_DIR}"
		+ ("" if overwrite else " (существующие не тронуты; перезаписать — --overwrite-materials)"))


def apply_preview_textures():
	"""Подключает текстуры к материалам Blender — только для превью, после экспорта."""
	for name, (texture, scale) in TEXTURED.items():
		mat = material(name)
		nodes, links = mat.node_tree.nodes, mat.node_tree.links
		bsdf = nodes["Principled BSDF"]
		coords = nodes.new("ShaderNodeTexCoord")
		mapping = nodes.new("ShaderNodeMapping")
		sx, sy = scale if isinstance(scale, tuple) else (scale, scale)
		mapping.inputs["Scale"].default_value = (sx, sy, 1)
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


def place(objects, location, rotation_z=0.0, scene=None):
	"""Ставит копию модуля (меши общие) в сцену превью. Координаты — Blender (Z вверх)."""
	scene = scene or bpy.context.scene
	for obj in objects:
		if obj.name.endswith("-colonly"):
			continue
		copy = obj.copy()
		copy.hide_render = False
		copy.location = location
		copy.rotation_euler = (0, 0, math.radians(rotation_z))
		scene.collection.objects.link(copy)


def godot_to_blender(pos):
	"""Godot (X, Y вверх, Z) → Blender (X, Y, Z вверх). Поворот вокруг Y Godot = поворот вокруг Z Blender."""
	x, y, z = pos
	return (x, -z, y)


def _set_engine(scene):
	for engine in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "BLENDER_WORKBENCH"):
		try:
			scene.render.engine = engine
			return
		except TypeError:
			continue


# Превью набросков: (функция расстановки, имя файла, ракурсы). Ракурс: (суффикс, камера, точка взгляда —
# в координатах Godot, наружный?).
PREVIEWS = (
	("service_layout", "hospital_kit_v04", (
		("airlock", (-7.0, 1.65, 0.3), (-2.0, 1.2, -0.6), False),
		("dock", (10.5, 0.9, 9.5), (1.5, 0.6, 2.0), True),
		("basement", (-1.0, -1.65, -0.3), (10.0, -2.3, -0.9), False))),
	("m03_layout", "m03_blockout", (
		("front", (26.0, 9.0, 24.0), (10.0, 0.5, 0.0), True),
		("back", (-2.0, 8.0, -26.0), (14.0, 0.5, -8.0), True),
		("corridor2", (11.4, 4.95, -3.0), (31.0, 4.6, -3.2), False),
		("ward214", (21.2, 4.95, -1.1), (30.5, 4.2, 0.9), False))),
)


def render_layout_previews(modules, art_dir, only=None):
	"""Превью набросков по общим расстановкам tools/hospital_layouts.py."""
	sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
	import hospital_layouts
	for layout_name, base, shots in PREVIEWS:
		if only and base not in only:
			continue
		layout = getattr(hospital_layouts, layout_name)()
		_render_shots(modules, layout, os.path.join(art_dir, base), shots)


def _render_shots(modules, layout, base_path, shots):
	for suffix, cam_pos, target, outdoor in shots:
		scene = bpy.data.scenes.new(f"Preview_{suffix}")
		for _, _, module, pos, rot in layout["placements"]:
			place(modules[module], godot_to_blender(pos), rot, scene)
		for name, pos, color, energy, _ in layout["lights"]:
			lamp = bpy.data.objects.new(name, bpy.data.lights.new(name, "POINT"))
			lamp.data.energy = 220 * energy
			lamp.data.color = color
			lamp.data.use_shadow = False  # десятки ламп переполняют буфер теней EEVEE; тень даёт солнце
			lamp.location = godot_to_blender(pos)
			scene.collection.objects.link(lamp)
		world = bpy.data.worlds.new(f"World_{suffix}")
		world.color = (0.45, 0.48, 0.52) if outdoor else (0.04, 0.04, 0.045)
		scene.world = world
		sun = bpy.data.objects.new(f"Sun_{suffix}", bpy.data.lights.new(f"Sun_{suffix}", "SUN"))
		sun.data.energy = 3.0 if outdoor else 0.5
		sun.rotation_euler = (math.radians(50), 0, math.radians(30))
		scene.collection.objects.link(sun)
		cam = bpy.data.objects.new(f"Cam_{suffix}", bpy.data.cameras.new(f"Cam_{suffix}"))
		cam.data.lens = 18
		cam.location = godot_to_blender(cam_pos)
		cam.rotation_euler = (Vector(godot_to_blender(target)) - cam.location).to_track_quat("-Z", "Y").to_euler()
		scene.collection.objects.link(cam)
		scene.camera = cam
		scene.render.resolution_x, scene.render.resolution_y = 1600, 900
		scene.render.filepath = f"{base_path}_{suffix}.png"
		_set_engine(scene)
		bpy.ops.render.render(write_still=True, scene=scene.name)
		print(f"[hospital_kit] превью: {scene.render.filepath}")


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
	all_args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
	args = [a for a in all_args if not a.startswith("--")]
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
	write_godot_materials("--overwrite-materials" in all_args)

	if preview:
		apply_preview_textures()
		if not any(a.startswith("--only=") for a in all_args):
			render_preview(modules, preview)
			print(f"[hospital_kit] превью: {preview}")
		only = [a.split("=", 1)[1] for a in all_args if a.startswith("--only=")]
		render_layout_previews(modules, os.path.dirname(preview), only)


main()
