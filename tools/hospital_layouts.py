"""Наброски уровней набора «Больница» — общий источник для сцен Godot и превью Blender.

Запуск из корня проекта: python3 tools/hospital_layouts.py [--force]
Пишет наброски в scenes/blockouts/. Набросок, который правили вручную, не перезаписывается
(сверка с контрольной суммой из scenes/blockouts/.generated.json) — только с --force.
Свою локацию создатель делает копией наброска в scenes/levels/<миссия>/ (D-037).

Координаты — Godot: X вправо, Y вверх, Z к зрителю; поворот — градусы вокруг Y.
Сетка 3 м; стены — на линиях сетки. У стен и настенных предметов «внутренняя» сторона (+Y модуля
в Blender) при повороте 0 смотрит в −Z, при 180 — в +Z, при 90 — в −X, при −90 — в +X.
"""

import hashlib
import json
import os
import sys

KIT = "res://assets/models/kits/hospital/"
BLOCKOUTS = "scenes/blockouts"
CHECKSUMS = os.path.join(BLOCKOUTS, ".generated.json")

G = 0.0      # пол первого этажа
B = -3.3     # пол подвала
Y = -1.1     # двор (рампа поднята на 1,1 м)
CEIL = 3.1   # потолок этажа (низ перекрытия)


# --- Генератор этажей по плану комнат ----------------------------------------------------------------

# Какой модуль ставить на границе: (вид, отделка стороны +Y модуля, отделка стороны −Y) → модуль.
STYLE_MODULES = {
	("wall", "paint", "paint"): "hosp_wall",
	("wall", "tile", "tile"): "hosp_wall_tile",
	("wall", "basement", "basement"): "hosp_wall_bsmt",
	("wall", "tile", "paint"): "hosp_wall_tile_paint",
	("wall", "basement", "paint"): "hosp_wall_bsmt_paint",
	("wall", "paint", "brick"): "hosp_wall_ext",
	("wall", "tile", "brick"): "hosp_wall_tile_ext",
	("wall", "basement", "brick"): "hosp_wall_bsmt_ext",
	("wall", "basement", "concrete"): "hosp_wall_bsmt_ground",
	("door", "paint", "paint"): "hosp_wall_door",
	("door", "tile", "tile"): "hosp_wall_door_tile",
	("door", "basement", "basement"): "hosp_wall_door_bsmt",
	("door", "tile", "paint"): "hosp_wall_door_tile_paint",
	("door", "tile", "basement"): "hosp_wall_door_tile_bsmt",
	("door", "basement", "paint"): "hosp_wall_door_bsmt_paint",
	("door", "paint", "brick"): "hosp_wall_door_ext",
	("door", "tile", "brick"): "hosp_wall_door_tile_ext",
	("window", "paint", "brick"): "hosp_wall_window_ext",
	("window", "tile", "brick"): "hosp_wall_window_tile_ext",
	("double", "paint", "brick"): "hosp_wall_door_double_ext",
	("gate", "basement", "brick"): "hosp_wall_gate_bsmt_ext",
	("gate", "basement", "concrete"): "hosp_wall_gate_bsmt_ground",
	("glass", "paint", "paint"): "hosp_wall_glass",
	("glass_door", "paint", "paint"): "hosp_wall_glass_door",
}


def plan_floor(add, group, y, rooms, styles, outer, edges=None, corridors=(), basement=False, open_out=()):
	"""Строит стены, углы и открытые двери этажа по плану комнат.

	rooms — {(i, cz): комната} (x = 3i, cz — центр ряда по Z); styles — {комната: отделка};
	outer — отделка снаружи («brick» или «concrete»); edges — особые границы: ключ ("h", i, zb) — стена вдоль X
	в ячейке i на линии z = zb, ("v", xb, cz) — вдоль Z на линии x = xb; значение — door, window, double,
	gate, glass, glass_door. Остальные границы между разными комнатами и с улицей — глухие стены.
	Двери открыты внутрь комнаты (из коридора, с улицы); ворота — наружу; из комнат open_out (лестничные
	клетки — узкие площадки) — наружу, в коридор.
	Возвращает наружные границы (для цоколя и поясов)."""
	edges = edges or {}
	walls, outside = [], []
	seen = set()
	for (i, cz), room in rooms.items():
		for key, other, cell_side in ((("h", i, cz + 1.5), (i, cz + 3), "-"), (("h", i, cz - 1.5), (i, cz - 3), "+"),
				(("v", 3 * i - 1.5, cz), (i - 1, cz), "+"), (("v", 3 * i + 1.5, cz), (i + 1, cz), "-")):
			if key in seen:
				continue
			seen.add(key)
			other_room = rooms.get(other)
			if other_room == room:
				continue
			kind = edges.get(key, "wall")
			a, b = styles[room], styles[other_room] if other_room else outer
			if (kind, a, b) in STYLE_MODULES:
				module, inner_side = STYLE_MODULES[(kind, a, b)], cell_side
			else:
				module, inner_side = STYLE_MODULES[(kind, b, a)], ("+" if cell_side == "-" else "-")
			# inner_side: «−» — внутренняя отделка смотрит в сторону меньших координат, «+» — больших
			if key[0] == "h":
				_, ci, zb = key
				add(group, module, (3 * ci, y, zb), 0 if inner_side == "-" else 180)
			else:
				_, xb, ccz = key
				add(group, module, (xb, y, ccz), 90 if inner_side == "-" else -90)
			walls.append(key)
			if other_room is None:
				outside.append((key, cell_side))
			if kind in ("door", "double", "glass_door", "gate"):
				_door_leaves(add, group, key, kind, y, room, other_room, cell_side, corridors, basement, open_out)
	_corners(add, group, y, walls, outside, basement)
	return outside


def _door_leaves(add, group, key, kind, y, room, other_room, cell_side, corridors, basement, open_out=()):
	"""Открытая створка: из коридора и с улицы — внутрь комнаты; ворота — наружу."""
	# cell_side — с какой стороны границы (по оси) лежит сама ячейка; по умолчанию дверь открыта в неё
	other_side = "-" if cell_side == "+" else "+"
	into = cell_side
	if kind == "gate" or (other_room and room in corridors) or room in open_out:
		into = other_side
	if other_room in open_out:
		into = cell_side
	leaf = "hosp_door_metal" if basement else "hosp_door"
	if key[0] == "h":
		_, ci, zb = key
		rot = 90 if into == "-" else -90  # 90: открыта в −Z
		x = 3 * ci
		if kind == "double":
			add(group, "hosp_door_double_leaf", (x - 0.94, y, zb), rot)
			add(group, "hosp_door_double_leaf", (x + 0.94, y, zb), rot)
		elif kind == "gate":
			add(group, "hosp_gate_leaf", (x - 1.14, y, zb), rot)
			add(group, "hosp_gate_leaf", (x + 1.14, y, zb), rot)
		else:
			add(group, leaf, (x - 0.54, y, zb), rot)
	else:
		_, xb, cz = key
		rot = 0 if into == "+" else 180
		add(group, leaf, (xb, y, cz - 0.54), rot)


def _corners(add, group, y, walls, outside, basement):
	"""Угловые колонны там, где стены сходятся под углом (без продолжения)."""
	outer_keys = {k for k, _ in outside}
	nodes = {}
	for key in walls:
		if key[0] == "h":
			_, i, zb = key
			for x, d in ((3 * i - 1.5, "r"), (3 * i + 1.5, "l")):
				nodes.setdefault((x, zb), {})[d] = key
		else:
			_, xb, cz = key
			for z, d in ((cz - 1.5, "d"), (cz + 1.5, "u")):
				nodes.setdefault((xb, z), {})[d] = key
	for (x, z), inc in nodes.items():
		horizontal, vertical = inc.keys() & {"l", "r"}, inc.keys() & {"u", "d"}
		if horizontal and vertical and len(horizontal) == 1 and len(vertical) == 1:
			exterior = any(k in outer_keys for k in inc.values())
			if basement:
				module = "hosp_wall_corner_bsmt"
			else:
				module = "hosp_wall_corner_brick" if exterior else "hosp_wall_corner"
			add(group, module, (x, y, z))


def asphalt(add, group, y, x0, x1, z0, z1, holes):
	"""Покрывает прямоугольник асфальтом: плиты 6 × 6, у препятствий — 3 × 3. holes — [(x0, x1, z0, z1)]."""
	def clear(ax0, ax1, az0, az1):
		return all(ax1 <= hx0 or ax0 >= hx1 or az1 <= hz0 or az0 >= hz1 for hx0, hx1, hz0, hz1 in holes)
	x = x0
	while x < x1 - 0.01:
		z = z0
		while z < z1 - 0.01:
			if x + 6 <= x1 + 0.01 and z + 6 <= z1 + 0.01 and clear(x, x + 6, z, z + 6):
				add(group, "ext_ground_asphalt", (x + 3, y, z + 3))
			else:
				for dx in (0, 3):
					for dz in (0, 3):
						sx, sz = x + dx, z + dz
						if sx + 3 <= x1 + 0.01 and sz + 3 <= z1 + 0.01 and clear(sx, sx + 3, sz, sz + 3):
							add(group, "ext_ground_asphalt_small", (sx + 1.5, y, sz + 1.5))
			z += 6
		x += 6


def ward_layout():
	"""Палата и коридор: коридор с окнами, палата на 4 койки, лестничная клетка на второй этаж."""
	p = []

	def add(group, name, module, pos, rot=0):
		p.append((group, name, module, pos, rot))

	cells_floor = [(3 * i, 0) for i in range(4)] + [(3, -3), (6, -3)] + [(12, 0), (15, 0)]
	for k, (x, z) in enumerate(cells_floor):
		add("Floors", f"Floor{k}", "hosp_floor", (x, G, z))
	for k, (x, z) in enumerate([(3 * i, 0) for i in range(4)] + [(3, -3), (6, -3)]):
		add("Ceilings", f"Ceiling{k}", "hosp_floor", (x, G + 3.3, z))
	w = []
	w += [("hosp_wall_window", (x, G, 1.5), 0) for x in (0, 3, 6, 9)]  # коридор, юг
	w += [("hosp_wall", (0, G, -1.5), 0), ("hosp_wall_door", (3, G, -1.5), 0),
		("hosp_wall", (6, G, -1.5), 0), ("hosp_wall", (9, G, -1.5), 0)]
	w += [("hosp_wall", (-1.5, G, 0), 90)]  # торец коридора
	w += [("hosp_wall_window", (x, G, -4.5), 180) for x in (3, 6)]  # палата, север
	w += [("hosp_wall", (1.5, G, -3), 90), ("hosp_wall", (7.5, G, -3), 90)]  # палата, бока
	w += [("hosp_wall_window", (x, G, 1.5), 0) for x in (12, 15)]  # лестница, юг
	w += [("hosp_wall", (x, G, -1.5), 0) for x in (12, 15)]  # лестница, север
	w += [("hosp_wall", (16.5, G, 0), 90)]  # лестница, торец
	for k, (m, pos, r) in enumerate(w):
		add("Walls", f"Wall{k}", m, pos, r)
	add("Walls", "WardDoor", "hosp_door", (2.46, G, -1.5), 90)
	for k, (x, z) in enumerate([(-1.5, 1.5), (-1.5, -1.5), (1.5, -1.5), (1.5, -4.5), (7.5, -4.5),
			(7.5, -1.5), (16.5, 1.5), (16.5, -1.5)]):
		add("Walls", f"Corner{k}", "hosp_wall_corner", (x, G, z))
	add("Stairs", "Flight1", "hosp_stairs_flight", (12.0, G, 0.7))
	add("Stairs", "MidLanding", "hosp_stairs_landing", (15.7, 1.65, 0))
	add("Stairs", "Flight2", "hosp_stairs_flight", (15.0, 1.65, -0.7), 180)
	add("Stairs", "UpperLanding", "hosp_stairs_landing", (11.3, 3.3, 0))
	add("Stairs", "Railing1", "hosp_stairs_railing", (12.0, G, 0.7))  # перила — как марши
	add("Stairs", "Railing2", "hosp_stairs_railing", (15.0, 1.65, -0.7), 180)
	add("Stairs", "LandingRailing", "hosp_railing_straight", (12.0, 3.3, 0.75), 90)  # край 2 этажа
	for k, x in enumerate((2.4, 3.9, 5.4, 6.9)):
		add("Props", f"Bed{k}", "prop_bed", (x, G, -3.4))
	add("Props", "Cabinet0", "prop_cabinet", (3.15, G, -4.15))
	add("Props", "Cabinet1", "prop_cabinet", (6.15, G, -4.15))
	for k, pos in enumerate([(1.95, G, -4.2), (4.65, G, -4.2), (8.2, G, -1.2), (8.5, G, -1.15), (8.8, G, -1.2)]):
		add("Props", f"Oxygen{k}", "prop_oxygen_cylinder", pos)
	add("Props", "Gurney", "prop_gurney", (5.0, G, 0.8), 90)
	add("Props", "Bench", "prop_bench", (0.5, G, -1.2))
	for k, (x, z, r) in enumerate([(0, 1.5, 0), (3, 1.5, 0), (6, 1.5, 0), (9, 1.5, 0), (3, -4.5, 180), (6, -4.5, 180)]):
		add("Props", f"Radiator{k}", "prop_radiator", (x, G, z), r)  # привязка как у окон над ними
	for k, pos in enumerate([(0, CEIL, 0), (3, CEIL, 0), (6, CEIL, 0), (9, CEIL, 0), (3, CEIL, -3), (6, CEIL, -3)]):
		add("Props", f"Lamp{k}", "prop_ceiling_lamp", pos)
	add("Props", "StairLamp", "prop_ceiling_lamp", (11.3, CEIL, 0), 90)
	add("Props", "Sink", "prop_sink", (1.5, G, -2.2), -90)
	add("Props", "IVStand", "prop_iv_stand", (3.1, G, -2.9))
	add("Props", "MedCabinet", "prop_med_cabinet", (7.5, G, -1.95), 90)
	add("Props", "WardSign", "prop_sign_plate", (3.95, 1.6, -1.5), 180)

	cool = (0.92, 1.0, 0.95)
	lights = [(f"CorridorLight{i}", (3 * i, 2.9, 0), cool, 1.1, 6.0) for i in range(4)]
	lights += [(name, pos, cool, 1.1, 6.0) for name, pos in (("WardLight0", (3, 2.9, -3)),
		("WardLight1", (6, 2.9, -3)), ("StairLight0", (12, 2.9, 0)), ("StairLight1", (15, 2.9, 0)),
		("StairLight2", (13.5, 5.5, 0)))]
	labels = [("WardSignText", (3.95, 1.6, -1.385), 0, "Палата № 214", 36, (0.12, 0.12, 0.12))]
	return {"placements": p, "lights": lights, "labels": labels, "player": ((0, 0.05, 0), -90)}


def service_layout():
	"""Служебный блок для миссии 3: шлюз, приёмка с воротами, подвал с аптечным складом, двор с рампой."""
	p = []  # (группа, имя, модуль, позиция, поворот)

	def add(group, name, module, pos, rot=0):
		p.append((group, name, module, pos, rot))

	# --- Шлюз: x −7,5…−1,5; запад — вход из «чистой» зоны, восток — дверь в «красную» -------------
	for k, x in enumerate((-6, -3)):
		add("Airlock", f"Floor{k}", "hosp_floor", (x, G, 0))
		add("Airlock", f"Ceiling{k}", "hosp_floor", (x, G + 3.3, 0))
		add("Airlock", f"WallN{k}", "hosp_wall_tile", (x, G, -1.5), 180)
		add("Airlock", f"WallS{k}", "hosp_wall_tile_ext", (x, G, 1.5))
		add("Airlock", f"Lamp{k}", "prop_ceiling_lamp", (x, CEIL, 0))
	add("Airlock", "WallW", "hosp_wall_door_tile", (-7.5, G, 0), -90)
	add("Airlock", "DoorW", "hosp_door", (-7.5, G, -0.54), -90)  # закрыта
	add("Airlock", "WallE", "hosp_wall_door_tile_bsmt", (-1.5, G, 0), 90)
	add("Airlock", "DoorE", "hosp_door", (-1.5, G, -0.54), 0)  # открыта в «красную» зону
	add("Airlock", "CornerNW", "hosp_wall_corner_tile", (-7.5, G, -1.5))
	add("Airlock", "CornerNE", "hosp_wall_corner_tile", (-1.5, G, -1.5))
	add("Airlock", "CornerSW", "hosp_wall_corner_brick", (-7.5, G, 1.5))
	add("Airlock", "CornerSE", "hosp_wall_corner_brick", (-1.5, G, 1.5))
	add("Airlock", "RedLine", "prop_floor_line", (-4.5, G + 0.001, 0), 90)
	add("Airlock", "Suits", "prop_coat_rack_suits", (-6.0, G, -1.5), 180)
	add("Airlock", "PPECabinet", "prop_med_cabinet", (-6.9, G, 1.5))
	add("Airlock", "Bench", "prop_bench", (-5.5, G, 1.15), 180)
	add("Airlock", "Sink", "prop_sink", (-2.4, G, 1.5))
	add("Airlock", "Bin0", "prop_bin_hazard", (-3.6, G, 1.1))
	add("Airlock", "Bin1", "prop_bin_hazard", (-2.0, G, -1.1))
	add("Airlock", "SignRed", "prop_sign_plate_red", (-1.5, G + 2.35, 0), 90)
	add("Airlock", "SignClean", "prop_sign_plate", (-7.5, G + 2.3, 0), -90)

	# --- Приёмка: x −1,5…13,5, пол 0; в южной половине x > 4,5 — проём лестницы в подвал --------
	for k, x in enumerate((0, 3)):
		add("Receiving", f"Floor{k}", "hosp_floor_concrete", (x, G, 0))
	for k, x in enumerate((6, 9, 12)):
		add("Receiving", f"FloorHalf{k}", "hosp_floor_half", (x, G, -0.75))
		add("Receiving", f"Beam{k}", "hosp_beam", (x, G, 1.5))
	add("Receiving", "BeamE", "hosp_beam", (13.5, G, 0), 90)
	for k, x in enumerate((0, 3, 6, 9, 12)):
		add("Receiving", f"Ceiling{k}", "hosp_floor", (x, G + 3.3, 0))
		add("Receiving", f"WallN{k}", "hosp_wall_bsmt", (x, G, -1.5), 180)
		if x:
			add("Receiving", f"WallS{k}", "hosp_wall_bsmt_ext", (x, G, 1.5))
	add("Receiving", "Gate", "hosp_wall_gate_bsmt_ext", (0, G, 1.5))
	add("Receiving", "GateLeafL", "hosp_gate_leaf", (-1.14, G, 1.5), -90)  # створки открыты во двор
	add("Receiving", "GateLeafR", "hosp_gate_leaf", (1.14, G, 1.5), -90)
	add("Receiving", "WallE", "hosp_wall_bsmt", (13.5, G, 0), 90)
	add("Receiving", "CornerNE", "hosp_wall_corner_bsmt", (13.5, G, -1.5))
	add("Receiving", "CornerSE", "hosp_wall_corner_brick", (13.5, G, 1.5))
	for k, x in enumerate((5.15, 6.45, 7.75, 9.05, 10.35, 11.65, 12.95)):
		add("Receiving", f"Railing{k}", "hosp_railing_straight", (x, G, -0.05))
	for k, x in enumerate((0, 6, 12)):
		add("Receiving", f"Lamp{k}", "prop_ceiling_lamp", (x, CEIL, 0))
	add("Receiving", "Pallet0", "prop_pallet_boxes", (2.6, G, -0.7), 90)
	add("Receiving", "Box0", "prop_box", (1.6, G, -1.1))

	# Лестница в подвал: два марша вниз вдоль +X в южной половине
	add("Stairs", "FlightA", "hosp_stairs_flight", (7.5, -1.65, 0.75), 180)
	add("Stairs", "RailingA", "hosp_stairs_railing_l", (7.5, -1.65, 0.75), 180)
	add("Stairs", "Landing", "hosp_stairs_landing_half", (8.2, -1.65, 0.75))
	add("Stairs", "LandingRailing", "hosp_railing_straight", (8.2, -1.65, 0.12))
	add("Stairs", "FlightB", "hosp_stairs_flight", (11.9, B, 0.75), 180)
	add("Stairs", "RailingB", "hosp_stairs_railing_l", (11.9, B, 0.75), 180)

	# --- Подвал: коридор x −1,5…13,5 и аптечный склад x 4,5…10,5, z −4,5…−1,5 ------------------
	for k, x in enumerate((0, 3, 6, 9, 12)):
		add("Basement", f"Floor{k}", "hosp_floor_concrete", (x, B, 0))
		add("Basement", f"WallS{k}", "hosp_wall_bsmt_ground", (x, B, 1.5))
		add("Basement", f"Pipes{k}", "prop_pipe_run", (x, B + 2.55, -1.5), 180)
		module = "hosp_wall_door_bsmt" if x == 9 else "hosp_wall_bsmt"
		add("Basement", f"WallN{k}", module, (x, B, -1.5), 180)
	add("Basement", "StoreDoor", "hosp_door_metal", (8.46, B, -1.5), 90)
	add("Basement", "WallW", "hosp_wall_bsmt_ground", (-1.5, B, 0), -90)
	add("Basement", "WallE", "hosp_wall_bsmt_ground", (13.5, B, 0), 90)
	for k, (x, z) in enumerate(((-1.5, -1.5), (-1.5, 1.5), (13.5, -1.5), (13.5, 1.5),
			(4.5, -1.5), (4.5, -4.5), (10.5, -4.5), (10.5, -1.5))):
		add("Basement", f"Corner{k}", "hosp_wall_corner_bsmt", (x, B, z))
	for k, x in enumerate((6, 9)):
		add("Basement", f"StoreFloor{k}", "hosp_floor_concrete", (x, B, -3))
		add("Basement", f"StoreCeiling{k}", "hosp_floor_concrete", (x, G, -3))
		add("Basement", f"StoreWallN{k}", "hosp_wall_bsmt_ground", (x, B, -4.5), 180)
	add("Basement", "StoreWallW", "hosp_wall_bsmt", (4.5, B, -3), -90)
	add("Basement", "StoreWallE", "hosp_wall_bsmt", (10.5, B, -3), 90)
	for k, (x, z, r) in enumerate(((6.0, -4.1, 0), (8.2, -4.1, 0), (4.85, -2.9, 90))):
		add("Basement", f"Rack{k}", "prop_shelf_rack", (x, B, z), r)
	add("Basement", "StorePallet", "prop_pallet_boxes", (9.7, B, -2.6), 90)
	add("Basement", "StoreBox0", "prop_box", (7.2, B, -2.3))
	add("Basement", "StoreBox1", "prop_box", (7.25, B + 0.3, -2.3), 15)
	for k, x in enumerate((0.6, 0.9, 1.2, 1.5, 1.8)):
		add("Basement", f"Oxygen{k}", "prop_oxygen_cylinder", (x, B, 1.2))
	for k, (x, z) in enumerate(((0, -0.75), (6, -0.75), (12, -0.75), (7.5, -3))):
		add("Basement", f"Lamp{k}", "prop_bulkhead_lamp", (x, -0.2, z))
	add("Basement", "StoreSign", "prop_sign_plate", (9.9, B + 1.6, -1.5), 180)

	# --- Двор и рампа ---------------------------------------------------------------------------
	for i, x in enumerate((-7.5, -1.5, 4.5, 10.5, 16.5)):
		for j, z in enumerate((4.5, 10.5)):
			add("Yard", f"Asphalt{i}_{j}", "ext_ground_asphalt", (x, Y, z))
	for k, x in enumerate((0, 3, 6)):
		add("Yard", f"Dock{k}", "hosp_dock_platform", (x, G, 3.1))
	add("Yard", "DockSteps", "hosp_dock_steps", (9.0, Y, 3.1), 180)
	for k, x in enumerate((-1.5, 1.5, 4.5)):
		add("Yard", f"Canopy{k}", "hosp_dock_canopy", (x, G, 1.5))
	add("Yard", "DockLamp", "prop_bulkhead_lamp", (0, G + 2.88, 2.2))
	add("Yard", "DockPallet0", "prop_pallet_boxes", (4.0, G, 3.4), 10)
	add("Yard", "DockPallet1", "prop_pallet_boxes", (5.5, G, 2.7), -5)
	add("Yard", "DockPallet2", "prop_pallet", (6.6, G, 3.9), 30)
	add("Yard", "DockBox0", "prop_box", (2.0, G, 4.1), 20)
	add("Yard", "DockBox1", "prop_box", (2.1, G + 0.3, 4.05), -10)
	add("Yard", "GateSign", "prop_sign_plate", (0, G + 2.62, 1.5), 180)

	cool, warm = (0.92, 1.0, 0.95), (1.0, 0.85, 0.6)
	lights = [  # (имя, позиция, цвет, энергия, радиус)
		("AirlockLight0", (-6, 2.9, 0), cool, 1.1, 6.0),
		("AirlockLight1", (-3, 2.9, 0), cool, 1.1, 6.0),
		("ReceivingLight0", (0, 2.9, 0), cool, 1.0, 6.0),
		("ReceivingLight1", (6, 2.9, 0), cool, 1.0, 7.0),
		("ReceivingLight2", (12, 2.9, 0), cool, 1.0, 7.0),
		("BasementLight0", (0, -0.5, -0.75), warm, 0.9, 6.0),
		("BasementLight1", (6, -0.5, -0.75), warm, 0.9, 6.0),
		("BasementLight2", (12, -0.5, -0.75), warm, 0.9, 6.0),
		("StoreLight", (7.5, -0.5, -3), warm, 0.9, 6.0),
		("StairLight", (9.5, -1.0, 0.75), warm, 0.6, 5.0),
		("DockLight", (0, 2.6, 2.2), warm, 1.5, 6.0),
	]
	labels = [  # (имя, позиция, поворот, текст, размер, цвет)
		("SignRedText", (-1.5 - 0.113, 2.35, 0), -90, "КРАСНАЯ ЗОНА", 44, (1, 1, 1)),
		("SignCleanText", (-7.5 + 0.113, 2.3, 0), 90, "ЧИСТАЯ ЗОНА", 36, (0.12, 0.12, 0.12)),
		("StoreSignText", (9.9, B + 1.6, -1.5 + 0.113), 0, "АПТЕЧНЫЙ СКЛАД", 28, (0.12, 0.12, 0.12)),
		("GateSignText", (0, 2.62, 1.5 + 0.113), 0, "ПРИЁМ ГРУЗОВ", 32, (0.12, 0.12, 0.12)),
	]
	return {
		"placements": p,
		"lights": lights,
		"labels": labels,
		"player": ((-6.5, 0.05, 0.3), -90),
	}


def m03_layout():
	"""Набросок уровня миссии 3 «Красная зона», версия 2 (D-038).

	Корпус № 4: подвал, 1 этаж, 2 этаж (x ≥ 10,5). Ячейки по X: i = 0…10 (x = 3i); ряды: юг S (z = 0),
	коридор C (z = −3), север N (z = −6). Фасады: юг z = 1,5, север z = −7,5, запад x = −1,5, восток x = 31,5.
	Подвал — свой вход с заднего двора: грузовой спуск → приёмка → аптечный склад (петли). Территория —
	больничный городок: площадь с палатками МЧС, задний двор, котельная, морг, соседние корпуса."""
	p = []
	count = {}

	def add(group, module, pos, rot=0, name=None):
		if name is None:
			count[(group, module)] = count.get((group, module), 0) + 1
			name = f"{module}_{count[(group, module)]}"
		p.append((group, name, module, pos, rot))

	S, C, N = 0, -3, -6
	H2, ROOF = G + 3.3, G + 6.6
	L1, L2 = G + 3.1, H2 + 3.1  # потолки этажей

	# ---------------- 1 этаж ----------------
	rooms1 = {}
	for i, room in enumerate(["airlock", "airlock", "vestibule", "vestibule", "stair", "stair", "ordinator",
			"procedure", "ward1", "ward1", "wc"]):
		rooms1[(i, S)] = room
	for i in range(11):
		rooms1[(i, C)] = "corridor"
	for i, room in enumerate(["w101", "w101", "w102", "w102", "w103", "w103", "w104", "w104", "store",
			"laundry", "laundry"]):
		rooms1[(i, N)] = room
	styles1 = {r: "paint" for r in rooms1.values()}
	styles1.update(airlock="tile", wc="tile", laundry="tile")
	edges1 = {("h", 2, 1.5): "double", ("h", 3, 1.5): "window", ("v", -1.5, S): "door",
		("v", -1.5, C): "window", ("v", -1.5, N): "window", ("v", 31.5, S): "window", ("v", 31.5, C): "door",
		("v", 31.5, N): "door", ("h", 9, -7.5): "door", ("h", 1, -1.5): "door", ("h", 2, -1.5): "glass_door",
		("h", 3, -1.5): "glass"}
	for i in (6, 7, 8, 9, 10):
		edges1[("h", i, 1.5)] = "window"
	for i in (0, 1, 2, 3, 4, 5, 6, 7, 10):
		edges1[("h", i, -7.5)] = "window"
	for i in (4, 6, 7, 8, 10):
		edges1[("h", i, -1.5)] = "door"
	for i in (0, 2, 4, 6, 8, 9):
		edges1[("h", i, -4.5)] = "door"
	outside1 = plan_floor(add, "Floor1", G, rooms1, styles1, "brick", edges1, corridors=("corridor",), open_out=("stair",))
	for (i, cz), room in rooms1.items():
		if room != "stair":
			add("Floor1", "hosp_floor", (3 * i, G, cz))
		if i < 4:
			add("Roof", "hosp_roof", (3 * i, H2, cz))
	add("Floor1", "hosp_floor_half", (11.25, G, 0), 90)  # площадка у лестницы
	for key, _ in outside1:  # цоколь и межэтажный пояс по всему периметру 1 этажа
		x, z, rot = (3 * key[1], key[2], 0) if key[0] == "h" else (key[1], key[2], 90)
		add("Exterior", "hosp_plinth", (x, G, z), rot)
		add("Exterior", "hosp_band", (x, H2, z), rot)

	# ---------------- 2 этаж ----------------
	rooms2 = {}
	for i, room in zip(range(4, 11), ["stair2", "stair2", "ordinator2", "w214", "w214", "w214", "w214"]):
		rooms2[(i, S)] = room
	for i in range(4, 11):
		rooms2[(i, C)] = "corridor2"
	for i, room in zip(range(4, 11), ["w211", "w211", "w212", "w212", "w213", "w213", "nurse"]):
		rooms2[(i, N)] = room
	styles2 = {r: "paint" for r in rooms2.values()}
	edges2 = {("v", 10.5, C): "window", ("v", 31.5, S): "window", ("v", 31.5, C): "window",
		("v", 31.5, N): "window"}
	for i in range(4, 11):
		edges2[("h", i, 1.5)] = "window"
		edges2[("h", i, -7.5)] = "window"
	for i in (4, 6, 10):
		edges2[("h", i, -1.5)] = "door"
	for i in (4, 6, 8, 10):
		edges2[("h", i, -4.5)] = "door"
	outside2 = plan_floor(add, "Floor2", H2, rooms2, styles2, "brick", edges2, corridors=("corridor2",), open_out=("stair2",))
	for (i, cz), room in rooms2.items():
		if room != "stair2":
			add("Floor2", "hosp_floor", (3 * i, H2, cz))
		add("Roof", "hosp_roof", (3 * i, ROOF, cz))
	for key, _ in outside2:
		x, z, rot = (3 * key[1], key[2], 0) if key[0] == "h" else (key[1], key[2], 90)
		add("Exterior", "hosp_band", (x, ROOF, z), rot)

	# ---------------- лестница (ножничная): вверх — юг, вниз в подвал — север ----------------
	for module, pos, rot in (
			("hosp_stairs_flight", (12, G, 0.7), 0), ("hosp_stairs_railing", (12, G, 0.7), 0),
			("hosp_stairs_landing", (15.7, 1.65, 0), 0),
			("hosp_stairs_flight", (15, 1.65, -0.7), 180), ("hosp_stairs_railing", (15, 1.65, -0.7), 180),
			("hosp_stairs_landing", (11.3, H2, 0), 0), ("hosp_railing_straight", (12.05, H2, 0.75), 90),
			("hosp_stairs_flight", (15, -1.65, -0.7), 180), ("hosp_stairs_railing", (15, -1.65, -0.7), 180),
			("hosp_stairs_landing", (15.7, -1.65, 0), 0),
			("hosp_stairs_flight", (12, B, 0.7), 0), ("hosp_stairs_railing", (12, B, 0.7), 0)):
		add("Stairs", module, pos, rot)

	# ---------------- подвал ----------------
	roomsb = {}
	for i in range(2, 9):
		roomsb[(i, C)] = "corridor_b"
	for i, room in zip(range(2, 9), ["receiving", "receiving", "pharmacy", "pharmacy", "pharmacy", "heat", "heat"]):
		roomsb[(i, N)] = room
	for i, room in zip(range(4, 8), ["stair_b", "stair_b", "oxygen", "oxygen"]):
		roomsb[(i, S)] = room
	stylesb = {r: "basement" for r in roomsb.values()}
	edgesb = {("h", 2, -7.5): "gate", ("h", 3, -4.5): "door", ("v", 10.5, N): "door", ("h", 4, -4.5): "door",
		("h", 6, -4.5): "door", ("h", 7, -4.5): "door", ("h", 8, -4.5): "door", ("h", 4, -1.5): "door",
		("h", 6, -1.5): "door"}
	plan_floor(add, "Basement", B, roomsb, stylesb, "concrete", edgesb, corridors=("corridor_b",), basement=True,
		open_out=("stair_b",))
	for (i, cz) in roomsb:
		add("Basement", "hosp_floor_concrete", (3 * i, B, cz))
	for i in range(2, 9):
		add("PropsB", "prop_pipe_run", (3 * i, B + 2.55, -4.5), 180)
	for x, z in ((6, C), (12, C), (18, C), (24, C), (7.5, N), (15, N), (22.5, N), (19.5, S)):
		add("PropsB", "prop_bulkhead_lamp", (x, -0.2, z))
	for k in range(12):                                   # кислород
		add("PropsB", "prop_oxygen_cylinder", (17.0 + k * 0.45, B, 1.2))
	for k in range(6):
		add("PropsB", "prop_oxygen_cylinder", (19.6 + k * 0.45, B, 0.7))
	for x in (11.6, 13.6, 15.6, 17.6):                    # аптечный склад
		add("PropsB", "prop_shelf_rack", (x, B, -7.1))
	add("PropsB", "prop_pallet_boxes", (13.0, B, -6.3))
	add("PropsB", "prop_pallet_boxes", (17.2, B, -6.3))
	add("PropsB", "prop_box", (15.2, B, -6.2), 15)
	add("PropsB", "prop_pallet_boxes", (8.6, B, -6.6))   # приёмка
	add("PropsB", "prop_pallet", (6.2, B, -5.4), 20)
	add("PropsB", "prop_box", (9.4, B, -5.3))
	add("PropsB", "prop_heat_unit", (22.5, B, -6.4))     # тепловой узел — петля вокруг
	add("PropsB", "prop_barrel", (20.2, B, -7.0))
	add("PropsB", "prop_sign_plate", (12.95, B + 1.6, -4.5), 180)
	add("PropsB", "prop_sign_plate", (18.95, B + 1.6, -1.5))

	# ---------------- грузовой спуск в подвал (задний двор) ----------------
	for x in (6, 9):
		for z in (-9, -12):
			add("Ramp", "hosp_floor_concrete", (x, B, z))
		for k in range(4):
			add("Ramp", "ext_ramp_down", (x, B + RAMP_HALF + 0.55 * k, -15 - 3 * k), 90)
	for x in (4.6, 10.4):
		for k in range(6):
			add("Ramp", "ext_retaining_wall", (x, B, -9 - 3 * k), 90)
	add("Ramp", "blk_vehicle_uaz", (7.5, B, -11.6), 90)      # «буханка» задом к воротам
	add("Ramp", "prop_pallet_boxes", (5.0, B, -12.5), 90)
	add("Ramp", "prop_barrel", (9.8, B, -8.3))
	add("Ramp", "prop_barrel", (9.75, B, -9.0))
	add("Ramp", "prop_barrel", (9.2, B, -8.6))
	add("Ramp", "prop_container", (9.6, B, -12.8), 90)
	add("Ramp", "prop_sign_plate", (6, B + 2.62, -7.5))

	# ---------------- реквизит 1 этажа ----------------
	add("Props1", "prop_coat_rack_suits", (0, G, 1.5))            # шлюз
	add("Props1", "prop_med_cabinet", (-0.6, G, -1.5), 180)
	add("Props1", "prop_bench", (0.8, G, -1.2))
	add("Props1", "prop_floor_line", (1.5, G + 0.001, 0), 90)
	add("Props1", "prop_sink", (3.8, G, 1.5))
	add("Props1", "prop_bin_hazard", (2.1, G, 1.1))
	add("Props1", "prop_bin_hazard", (4.1, G, -1.05))
	add("Props1", "prop_sign_plate_red", (3, G + 2.35, -1.5), 180)
	add("Props1", "prop_sign_plate", (-1.5, G + 2.3, 0), -90)
	add("Props1", "prop_bench", (8.9, G, 1.15), 180)              # вестибюль — родственники
	add("Props1", "prop_bench", (9.2, G, -1.15))
	add("Props1", "prop_bag", (8.0, G, 0.4), 30)
	add("Props1", "prop_bag", (9.9, G, 0.9), -10)
	add("Props1", "prop_desk", (18.0, G, 0.9))                    # ординаторская
	add("Props1", "prop_chair", (18.0, G, 0.3))
	add("Props1", "prop_med_cabinet", (16.5, G, -0.4), -90)
	add("Props1", "prop_sink", (19.5, G, 0.5), -90)               # процедурная
	add("Props1", "prop_med_cabinet", (22.5, G, 0.2), 90)
	add("Props1", "prop_gurney", (21.1, G, 0.3), 90)
	for x in (25.3, 26.6, 27.9):                                  # палата 1 этажа
		add("Props1", "prop_bed", (x, G, -0.4))
	add("Props1", "prop_screen", (24.0, G, 0.4), 90)
	add("Props1", "prop_bag", (26.0, G, 0.9))
	add("Props1", "prop_sink", (28.5, G, 0.4), -90)               # санузел
	for xs in ((1.3, 2.6, 3.9), (7.3, 8.6, 9.9), (13.3, 14.55, 15.8), (19.3, 20.6, 21.9)):
		for x in xs:
			add("Props1", "prop_bed", (x, G, -5.6), 180)
	add("Props1", "prop_screen", (5.2, G, -6.4), 90)
	add("Props1", "prop_chair", (14.0, G, -6.9))
	add("Props1", "prop_bag", (20.0, G, -6.9), 15)
	add("Props1", "prop_shelf_rack", (24, G, -7.1))               # кладовая
	add("Props1", "prop_washer", (28.3, G, -6.9))                 # прачечная
	add("Props1", "prop_washer", (29.2, G, -6.9))
	add("Props1", "prop_shelf_rack", (25.85, G, -6.0), 90)
	for i in (0, 1, 2, 3, 4, 5, 6, 7):
		add("Props1", "prop_radiator", (3 * i, G, -7.5), 180)
	for i in (3, 6, 7, 8, 9):
		add("Props1", "prop_radiator", (3 * i, G, 1.5))
	add("Props1", "prop_gurney", (15.0, G, -2.0), 90)             # коридор
	add("Props1", "prop_gurney", (21.0, G, -4.0), 90)
	add("Props1", "prop_mattress_floor", (9.0, G, -2.1), 90)
	add("Props1", "prop_mattress_floor", (9.0, G, -3.95), 90)
	add("Props1", "prop_bench", (2.2, G, -4.15))
	add("Props1", "prop_iv_stand", (16.2, G, -1.9))
	for i in range(11):
		add("Props1", "prop_ceiling_lamp", (3 * i, L1, C))
	for (i, cz), room in rooms1.items():
		if cz != C and room != "stair":
			add("Props1", "prop_ceiling_lamp", (3 * i, L1, cz))
	add("Props1", "prop_ceiling_lamp", (11.3, L1, 0), 90)

	# ---------------- реквизит 2 этажа: маршрут с баллоном идёт через весь коридор ----------------
	add("Props2", "prop_desk", (18.0, H2, 0.9))                   # ординаторская — детские рисунки
	add("Props2", "prop_chair", (18.0, H2, 0.3))
	add("Props2", "prop_med_cabinet", (19.5, H2, -0.4), 90)
	for x in (21.0, 22.6, 24.2, 25.8, 27.4, 28.95):               # палата 214 — шесть коек
		add("Props2", "prop_bed", (x, H2, -0.4))
	for x in (21.8, 25.0, 28.2):
		add("Props2", "prop_iv_stand", (x, H2, 0.9))
		add("Props2", "prop_oxygen_cylinder", (x, H2, -1.2))
	add("Props2", "prop_screen", (23.4, H2, 0.4), 90)
	add("Props2", "prop_bag", (26.6, H2, 0.95), 20)
	add("Props2", "prop_chair", (29.9, H2, 0.9))
	for i in range(4, 11):
		if i not in (4, 5):  # над лестничным пролётом батарей нет
			add("Props2", "prop_radiator", (3 * i, H2, 1.5))
		add("Props2", "prop_radiator", (3 * i, H2, -7.5), 180)
	for xs in ((13.3, 14.55, 15.8), (19.3, 20.6, 21.9), (25.3, 26.6, 27.9)):
		for x in xs:
			add("Props2", "prop_bed", (x, H2, -5.6), 180)
	add("Props2", "prop_shelf_rack", (28.85, H2, -6.0), 90)       # сестринская
	add("Props2", "prop_oxygen_cylinder", (30.5, H2, -5.0))
	add("Props2", "prop_oxygen_cylinder", (30.8, H2, -5.0))
	add("Props2", "prop_desk", (21, H2, -4.1), 180)               # пост: список умерших на стене
	add("Props2", "prop_chair", (21, H2, -3.7), 180)
	add("Props2", "prop_oxygen_cylinder", (22.2, H2, -4.15))
	add("Props2", "prop_sign_plate", (21, H2 + 1.7, -4.5), 180)
	for x, z in ((15.0, -2.0), (15.0, -4.0), (21.0, -2.0), (25.5, -2.0)):
		add("Props2", "prop_gurney", (x, H2, z), 90)
	add("Props2", "prop_iv_stand", (16.2, H2, -1.9))
	add("Props2", "prop_iv_stand", (26.7, H2, -1.9))
	add("Props2", "prop_mattress_floor", (27.0, H2, -3.95), 90)
	add("Props2", "prop_sign_plate", (30.95, H2 + 1.6, -1.5))
	for i in range(4, 11):
		add("Props2", "prop_ceiling_lamp", (3 * i, L2, C))
	for (i, cz), room in rooms2.items():
		if cz != C and room != "stair2":
			add("Props2", "prop_ceiling_lamp", (3 * i, L2, cz))
	add("Props2", "prop_ceiling_lamp", (13.5, L2, 0), 90)

	# ---------------- улица: крыльца ----------------
	add("Exterior", "hosp_porch", (4.5, G, 3.1))                  # главное крыльцо 6 м
	add("Exterior", "hosp_porch", (7.5, G, 3.1))
	add("Exterior", "hosp_dock_steps", (6, Y, 6.1), 90)
	add("Exterior", "hosp_dock_canopy", (4.5, G, 1.5))
	add("Exterior", "hosp_dock_canopy", (7.5, G, 1.5))
	add("Exterior", "prop_bulkhead_lamp", (6, G + 2.88, 2.2))
	add("Exterior", "prop_sign_plate_red", (6, G + 2.62, 1.5), 180)
	add("Exterior", "hosp_porch", (-3.1, G, 0), 90)               # крыльцо шлюза
	add("Exterior", "hosp_dock_steps", (-6.1, Y, 0))
	add("Exterior", "hosp_porch", (27, G, -9.1))                  # крыльцо прачечной
	add("Exterior", "hosp_dock_steps", (27, Y, -12.1), -90)
	add("Exterior", "hosp_porch", (33.1, G, -6))                  # боковое крыльцо
	add("Exterior", "hosp_porch", (33.1, G, -3))
	add("Exterior", "hosp_dock_steps", (36.1, Y, -4.5), 180)

	# ---------------- улица: площадь (сц. 1, 7–9) — укрытия ----------------
	for k, (x, z) in enumerate(((17, 9.5), (24, 9.5), (17, 17.0))):
		add("Square", "ext_tent", (x, Y, z), 180)                 # полевой госпиталь МЧС
	add("Square", "blk_vehicle_truck", (1.5, Y, 17.0), 90)         # «Урал» (сц. 1)
	add("Square", "blk_vehicle_van", (11.5, Y, 7.0))               # сварщики (сц. 7)
	add("Square", "blk_vehicle_ambulance", (29.0, Y, 15.0))
	add("Square", "blk_vehicle_ambulance", (29.0, Y, 18.5))
	add("Square", "blk_vehicle_car", (-5.0, Y, 17.5))              # полиция у ворот
	add("Square", "ext_booth", (-3.5, Y, 21.0))                    # проходная
	for x, z in ((3, 9.5), (9, 10.5)):
		add("Square", "ext_flowerbed", (x, Y, z))
		add("Square", "prop_bench", (x, Y, z + 1.6), 180)
	for x, z, r in ((0.5, 12.5, 5), (3.6, 13.0, -4), (7.6, 13.2, 3), (10.8, 12.6, -6)):
		add("Square", "ext_block_fdb", (x, Y, z), r)                # оцепление
	add("Square", "prop_bag", (4.0, Y, 17.5), 30)                  # вещи родственников у ворот
	add("Square", "prop_bag", (6.0, Y, 20.5), -20)

	# ---------------- задний двор (сц. 5, 6, 10) ----------------
	add("BackYard", "prop_container", (13.5, Y, -14.0), 90)
	add("BackYard", "prop_container", (13.5, Y, -16.2), 90)
	add("BackYard", "blk_vehicle_ambulance", (30.0, Y, -28.0))     # скорая у задних ворот (сц. 10)
	add("BackYard", "blk_boiler_house", (-5.0, Y, -26.0))          # котельная и труба — ориентир
	add("BackYard", "ext_chimney", (1.0, Y, -28.0))
	add("BackYard", "blk_building_small", (-5.0, Y, -15.0))        # морг
	add("BackYard", "prop_bench", (24.5, Y, -11.0), 90)            # перекур у прачечной (сц. 5)

	# ---------------- городок: фонари, деревья, забор, соседние корпуса ----------------
	for x, z, r in ((-1.5, 6.5, 0), (13.5, 4.0, 0), (-1.5, 15.0, 0), (13.5, 15.0, 0), (34.5, 1.0, 180),
			(14.0, -11.0, 0), (20.0, -20.0, 0), (31.0, -18.0, 180), (-1.0, -12.0, 0)):
		add("Town", "ext_lamp_post", (x, Y, z), r)
	for x, z in ((-8.5, 20.0), (8.0, 20.5), (14.0, 20.5), (21.0, 20.5), (34.5, 20.0), (-8.5, 6.0),
			(-8.5, 12.0), (35.5, 11.0), (16.0, -28.5), (22.0, -29.0), (-8.5, -8.0), (35.5, -14.0), (20.0, -12.0)):
		add("Town", "blk_tree", (x, Y, z))
	for k in range(16):
		x = -9 + 3 * k
		if x not in (0, 3):
			add("Town", "ext_fence", (x, Y, 22.5))
		if x not in (27, 30):
			add("Town", "ext_fence", (x, Y, -31.5))
	for k in range(18):
		z = -30 + 3 * k
		add("Town", "ext_fence", (-10.5, Y, z), 90)
		add("Town", "ext_fence", (37.5, Y, z), 90)
	add("Town", "blk_building_corps", (-26.0, Y, -5.0), 90)        # соседние корпуса за забором
	add("Town", "blk_building_corps", (54.0, Y, -5.0), 90)
	add("Town", "blk_building_corps", (14.0, Y, 38.0))
	add("Town", "blk_building_corps", (14.0, Y, -46.0))
	asphalt(add, "Ground", Y, -10.5, 37.5, -31.5, 22.5,
		[(-1.5, 31.5, -7.5, 1.5), (4.5, 10.5, -25.5, -7.5)])
	k = 0
	for x in (-25.5, 4.5, 34.5, 52.5):                               # земля за забором (плиты 30 × 30)
		for z in (-46.5, -16.5, 13.5, 37.5):
			if x + 15 > -1.5 and x - 15 < 31.5 and z + 15 > -25.5 and z - 15 < 1.5:
				continue  # не под корпусом и подвалом
			k += 1
			add("Ground", "ext_ground_dirt", (x, Y - 0.02 - 0.003 * k, z))  # разная высота — без мерцания

	# ---------------- свет ----------------
	cool, warm = (0.92, 1.0, 0.95), (1.0, 0.85, 0.6)
	lights = []
	for i in range(0, 11, 2):
		lights.append((f"Corridor1_{i}", (3 * i, 2.9, C), cool, 1.0, 7.0))
	for k, (x, z) in enumerate(((1.5, S), (7.5, S), (18, S), (21, S), (25.5, S), (30, S), (1.5, N), (7.5, N),
			(13.5, N), (19.5, N), (24, N), (28.5, N))):
		lights.append((f"Room1_{k}", (x, 2.9, z), cool, 1.0, 6.0))
	for k, y in enumerate((2.4, 5.6, -1.0, -2.6)):
		lights.append((f"Stair_{k}", (13.5, y, 0), cool, 0.9, 6.0))
	for i in range(4, 11, 2):
		lights.append((f"Corridor2_{i}", (3 * i, 6.2, C), cool, 1.0, 7.0))
	for k, (x, z) in enumerate(((18, S), (22.5, S), (28.5, S), (13.5, N), (19.5, N), (25.5, N), (30, N))):
		lights.append((f"Room2_{k}", (x, 6.2, z), cool, 1.0, 6.0))
	for k, (x, z) in enumerate(((6, C), (12, C), (18, C), (24, C), (7.5, N), (15, N), (22.5, N), (19.5, S))):
		lights.append((f"Basement_{k}", (x, -0.5, z), warm, 0.9, 6.0))
	for k, pos in enumerate(((6, 2.6, 2.2), (7.5, -1.2, -10.0), (27, 2.2, -8.6), (-2.5, 2.2, 0), (30, 3.0, -27),
			(33.1, 2.2, -4.5), (-1.5, 4.4, 6.5), (13.5, 4.4, 6.5), (14, 4.4, -11))):
		lights.append((f"Outdoor_{k}", pos, warm, 1.5, 8.0))

	dark, white = (0.12, 0.12, 0.12), (1, 1, 1)
	labels = [
		("SignAirlockRed", (3, 2.35, -1.387), 0, "КРАСНАЯ ЗОНА", 44, white),
		("SignAirlockClean", (-1.387, 2.3, 0), 90, "ЧИСТАЯ ЗОНА", 36, dark),
		("SignMain", (6, 2.62, 1.613), 0, "ИНФЕКЦИОННЫЙ КОРПУС № 4", 22, white),
		("Sign214", (30.95, H2 + 1.6, -1.613), 180, "Палата № 214", 36, dark),
		("SignDeadList", (21, H2 + 1.7, -4.387), 0, "СПИСОК", 40, dark),
		("SignPharmacy", (12.95, B + 1.6, -4.387), 0, "АПТЕЧНЫЙ СКЛАД", 28, dark),
		("SignOxygen", (18.95, B + 1.6, -1.613), 180, "КИСЛОРОД", 36, dark),
		("SignDock", (6, B + 2.62, -7.613), 180, "АПТЕКА", 36, dark),
	]
	markers = [
		("S01_Gate", (1.5, 1.6, 19.0), "Сц.1: «Урал» у ворот, родственники"),
		("S01_Airlock", (1.5, 2.2, 0), "Сц.1: шлюз — надеть СИЗ"),
		("S02_Olga", (4.5, 2.2, -3), "Сц.2: Ольга — «мне нужны руки»"),
		("S02_Oxygen", (19.5, -1.2, 0), "Сц.2: кислород в подвале"),
		("S02_Route", (13.5, 5.4, -3), "Сц.2: с баллоном — через весь коридор к 214"),
		("S02_Drawings", (18, 5.4, 0), "Сц.2: детские рисунки"),
		("S02_DeadList", (21, 5.6, -4.0), "Сц.2: список умерших у поста"),
		("S02_Grandma", (24, 5.4, -3), "Сц.2: бабушка ищет Валю"),
		("S03_Gena", (7.5, 2.2, -0.6), "Сц.3: Гена у стекла"),
		("S03_Lida", (28.95, 4.8, 0.4), "Сц.3: палата 214, Лида у окна"),
		("S04_Syringe", (27.4, 3.6, 0.9), "Сц.4: шприц на полу → В-2"),
		("S05_Break", (25.5, 0.6, -11.0), "Сц.5: ночь, перерыв с Ольгой"),
		("S06_Ramp", (7.5, -0.5, -12.5), "Сц.6: мародёры грузят «буханку» в приямке"),
		("S06_Store", (15, -1.2, -5.5), "Сц.6: бой на складе; петли через приёмку и узел"),
		("S06_Escape", (13.5, 1.2, 0), "Сц.6: бегство — лестница → коридор → прачечная"),
		("S07_Order", (6, 1.2, 8.5), "Сц.7: приказ Ершова, сварщики"),
		("S08_Doors", (6, 2.0, 3.0), "Сц.8: двери — заварили одну створку"),
		("S09_Fight", (8, 1.2, 14), "Сц.9: бой — палатки, блоки, машины"),
		("S10_Ershov", (33.5, 1.2, 3.0), "Сц.10: Ершов за углом"),
		("S10_Exit", (30.0, 2.0, -25.5), "Сц.10: прачечная → задний двор → скорая"),
	]
	return {"placements": p, "lights": lights, "labels": labels, "markers": markers,
		"player": ((4.2, -1.05, 19.5), 0)}


RAMP_HALF = 0.275  # половина подъёма секции грузового спуска ext_ramp_down (0,55 м на 3 м)


def write_tscn(layout, path, root_name, force=False):
	"""Пишет сцену Godot из расстановки: модули — экземпляры .glb, свет — OmniLight3D, надписи — Label3D.
	Не перезаписывает файл, если его правили после генерации (если не force). Возвращает True, если записал."""
	modules = sorted({m for _, _, m, _, _ in layout["placements"]})
	ids = {m: f"{i + 3}_{m}" for i, m in enumerate(modules)}
	groups = list(dict.fromkeys(g for g, _, _, _, _ in layout["placements"]))

	def fmt(v):
		return ", ".join("%g" % c for c in v)

	out = ["[gd_scene format=3]", "",
		'[ext_resource type="PackedScene" path="res://scenes/player/player.tscn" id="1_player"]',
		'[ext_resource type="Script" path="res://scripts/debug/debug_overlay.gd" id="2_overlay"]']
	out += [f'[ext_resource type="PackedScene" path="{KIT}{m}.glb" id="{ids[m]}"]' for m in modules]
	out += ["",
		'[sub_resource type="ProceduralSkyMaterial" id="SkyMat_overcast"]',
		"sky_top_color = Color(0.42, 0.46, 0.5, 1)", "sky_horizon_color = Color(0.62, 0.64, 0.66, 1)",
		"ground_bottom_color = Color(0.18, 0.19, 0.2, 1)", "ground_horizon_color = Color(0.62, 0.64, 0.66, 1)", "",
		'[sub_resource type="Sky" id="Sky_overcast"]', 'sky_material = SubResource("SkyMat_overcast")', "",
		'[sub_resource type="Environment" id="Env"]', "background_mode = 2", 'sky = SubResource("Sky_overcast")',
		"ambient_light_source = 3", "ambient_light_energy = 0.35", "tonemap_mode = 2", "",
		f'[node name="{root_name}" type="Node3D"]', "",
		'[node name="WorldEnvironment" type="WorldEnvironment" parent="."]', 'environment = SubResource("Env")', "",
		'[node name="Sun" type="DirectionalLight3D" parent="."]', "rotation_degrees = Vector3(-35, -150, 0)",
		"light_color = Color(0.92, 0.94, 1, 1)", "light_energy = 0.7", "shadow_enabled = true", ""]
	extra = ["Lights", "Labels"] + (["Markers"] if layout.get("markers") else [])
	for g in groups + extra:
		out += [f'[node name="{g}" type="Node3D" parent="."]', ""]
	for g, name, m, pos, rot in layout["placements"]:
		out.append(f'[node name="{name}" parent="{g}" instance=ExtResource("{ids[m]}")]')
		out.append(f"position = Vector3({fmt(pos)})")
		if rot:
			out.append(f"rotation_degrees = Vector3(0, {rot}, 0)")
		out.append("")
	for name, pos, color, energy, radius in layout["lights"]:
		out += [f'[node name="{name}" type="OmniLight3D" parent="Lights"]', f"position = Vector3({fmt(pos)})",
			f"light_color = Color({fmt(color)}, 1)", f"light_energy = {energy}", f"omni_range = {radius}", ""]
	for name, pos, rot, text, size, color in layout["labels"]:
		out += [f'[node name="{name}" type="Label3D" parent="Labels"]', f"position = Vector3({fmt(pos)})"]
		if rot:
			out.append(f"rotation_degrees = Vector3(0, {rot}, 0)")
		out += ["pixel_size = 0.001", f"modulate = Color({fmt(color)}, 1)", "outline_size = 0",
			f'text = "{text}"', f"font_size = {size}", ""]
	for name, pos, text in layout.get("markers", []):
		# Подписи сцен сценария — для создателя; в финальной локации их удаляют.
		out += [f'[node name="{name}" type="Marker3D" parent="Markers"]', f"position = Vector3({fmt(pos)})", "",
			f'[node name="Text" type="Label3D" parent="Markers/{name}"]', "pixel_size = 0.004", "billboard = 1",
			"modulate = Color(1, 0.55, 0.1, 1)", "outline_size = 8", f'text = "{text}"', "font_size = 48", ""]
	(px, py, pz), prot = layout["player"]
	out += ['[node name="Player" parent="." instance=ExtResource("1_player")]',
		f"position = Vector3({px}, {py}, {pz})", f"rotation_degrees = Vector3(0, {prot}, 0)", "",
		'[node name="HUD" type="CanvasLayer" parent="."]', "",
		'[node name="DebugOverlay" type="Label" parent="HUD" node_paths=PackedStringArray("player")]',
		"offset_left = 16.0", "offset_top = 16.0", "offset_right = 520.0", "offset_bottom = 200.0",
		'script = ExtResource("2_overlay")', 'player = NodePath("../../Player")', ""]
	text = "\n".join(out)
	checksums = json.load(open(CHECKSUMS)) if os.path.exists(CHECKSUMS) else {}
	if os.path.exists(path) and not force:
		current = hashlib.sha256(open(path, "rb").read()).hexdigest()
		if checksums.get(path) != current:
			print(f"[blockouts] ПРОПУЩЕН {path}: его правили вручную (или он не из генератора). "
				"Перезаписать — с флагом --force.")
			return False
	os.makedirs(os.path.dirname(path), exist_ok=True)
	with open(path, "w") as f:
		f.write(text)
	checksums[path] = hashlib.sha256(text.encode()).hexdigest()
	with open(CHECKSUMS, "w") as f:
		json.dump(checksums, f, indent=1, ensure_ascii=False, sort_keys=True)
	print(f"[blockouts] {path}: {len(layout['placements'])} модулей")
	return True


BLOCKOUT_SCENES = (
	(ward_layout, "hospital_ward_blockout.tscn", "HospitalWardBlockout"),
	(service_layout, "hospital_service_blockout.tscn", "HospitalServiceBlockout"),
	(m03_layout, "m03_red_zone_blockout.tscn", "M03RedZoneBlockout"),
)


if __name__ == "__main__":
	force = "--force" in sys.argv
	for layout, name, root in BLOCKOUT_SCENES:
		write_tscn(layout(), os.path.join(BLOCKOUTS, name), root, force)
