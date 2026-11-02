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
	"""Набросок уровня миссии 3 «Красная зона»: корпус № 4 (подвал, 2 этажа), площадь перед ним, задний
	двор с рампой и прачечной. Ячейки по X: i = 0…10 (x = 3i), ряды: S (z = 0), C — коридор (z = −3),
	N (z = −6). Фасады: юг z = 1,5, север z = −7,5, запад x = −1,5, восток x = 31,5."""
	p = []
	count = {}

	def add(group, module, pos, rot=0, name=None):
		if name is None:
			count[(group, module)] = count.get((group, module), 0) + 1
			name = f"{module}_{count[(group, module)]}"
		p.append((group, name, module, pos, rot))

	def hw(group, i, zb, y, module, inner="-z"):
		"""Стена вдоль X на линии z = zb; inner — куда смотрит её внутренняя отделка."""
		add(group, module, (3 * i, y, zb), 180 if inner == "+z" else 0)

	def vw(group, xb, cz, y, module, inner="-x"):
		"""Стена вдоль Z на линии x = xb."""
		add(group, module, (xb, y, cz), -90 if inner == "+x" else 90)

	def leaf_h(group, i, zb, y, into, module="hosp_door"):
		"""Открытая дверь в стене вдоль X: петли у западного края проёма; into — куда открыта."""
		add(group, module, (3 * i - 0.54, y, zb), 90 if into == "-z" else -90)

	def leaf_v(group, xb, cz, y, into, module="hosp_door"):
		add(group, module, (xb, y, cz - 0.54), 0 if into == "+x" else 180)

	S, C, N = 0, -3, -6
	H2 = G + 3.3          # пол 2 этажа
	ROOF = G + 6.6
	stair = {(5, S), (6, S)}

	# ---------- 1 этаж ----------
	for i in range(11):
		for cz in (S, C, N):
			if (i, cz) in stair:
				continue
			add("Floor1", "hosp_floor_concrete" if (i in (2, 3) and cz == N) else "hosp_floor", (3 * i, G, cz))
			if i < 4:
				add("Roof", "hosp_roof", (3 * i, H2, cz))  # крыша одноэтажного крыла
	add("Floor1", "hosp_floor_half", (14.25, G, 0), 90)  # площадка у лестницы
	south = ["hosp_wall_tile_ext"] * 2 + ["hosp_wall_door_ext", "hosp_wall_window_ext", "hosp_wall_window_ext",
		"hosp_wall_ext", "hosp_wall_ext", "hosp_wall_window_ext", "hosp_wall_window_ext", "hosp_wall_window_ext",
		"hosp_wall_ext"]
	north = ["hosp_wall_window_ext"] * 2 + ["hosp_wall_gate_bsmt_ext", "hosp_wall_bsmt_ext"] + \
		["hosp_wall_window_ext"] * 4 + ["hosp_wall_ext", "hosp_wall_door_tile_ext", "hosp_wall_window_tile_ext"]
	for i in range(11):
		hw("Walls1", i, 1.5, G, south[i], "-z")
		hw("Walls1", i, -7.5, G, north[i], "+z")
		add("Exterior", "hosp_plinth", (3 * i, G, 1.5))
		add("Exterior", "hosp_plinth", (3 * i, G, -7.5))
	for cz, west, east in ((S, "hosp_wall_door_tile_ext", "hosp_wall_ext"),
			(C, "hosp_wall_window_ext", "hosp_wall_door_ext"),
			(N, "hosp_wall_ext", "hosp_wall_door_tile_ext")):
		vw("Walls1", -1.5, cz, G, west, "+x")
		vw("Walls1", 31.5, cz, G, east, "-x")
		add("Exterior", "hosp_plinth", (-1.5, G, cz), 90)
		add("Exterior", "hosp_plinth", (31.5, G, cz), 90)
	corridor_s = [("hosp_wall_tile_paint", "+z"), ("hosp_wall_door_tile_paint", "+z"), ("hosp_wall_glass_door", "-z"),
		("hosp_wall_glass", "-z")] + [(m, "-z") for m in ("hosp_wall_door", "hosp_wall_door", "hosp_wall",
		"hosp_wall_door", "hosp_wall_door", "hosp_wall", "hosp_wall_door")]
	corridor_n = [("hosp_wall_door", "-z"), ("hosp_wall", "-z"), ("hosp_wall_door_bsmt_paint", "-z"),
		("hosp_wall_bsmt_paint", "-z")] + [(m, "-z") for m in ("hosp_wall_door", "hosp_wall", "hosp_wall_door",
		"hosp_wall", "hosp_wall_door")] + [("hosp_wall_door_tile_paint", "-z"), ("hosp_wall_tile_paint", "-z")]
	for i in range(11):
		hw("Walls1", i, -1.5, G, *corridor_s[i])
		hw("Walls1", i, -4.5, G, *corridor_n[i])
	for xb, module, inner in ((4.5, "hosp_wall_tile_paint", "-x"), (10.5, "hosp_wall", "-x"), (13.5, "hosp_wall", "-x"),
			(19.5, "hosp_wall", "-x"), (22.5, "hosp_wall", "-x"), (28.5, "hosp_wall", "-x")):
		vw("Walls1", xb, S, G, module, inner)
	for xb, module, inner in ((4.5, "hosp_wall_bsmt_paint", "+x"), (10.5, "hosp_wall_bsmt_paint", "-x"),
			(16.5, "hosp_wall", "-x"), (22.5, "hosp_wall", "-x"), (25.5, "hosp_wall_tile_paint", "+x")):
		vw("Walls1", xb, N, G, module, inner)
	for x, z in ((-1.5, 1.5), (31.5, 1.5), (-1.5, -7.5), (31.5, -7.5)):
		add("Walls1", "hosp_wall_corner_brick", (x, G, z))
	# межэтажные пояса по фасадам: над 1 этажом — по всему периметру, над 2 этажом — по его периметру
	for i in range(11):
		add("Exterior", "hosp_band", (3 * i, H2, 1.5))
		add("Exterior", "hosp_band", (3 * i, H2, -7.5))
		if i >= 4:
			add("Exterior", "hosp_band", (3 * i, ROOF, 1.5))
			add("Exterior", "hosp_band", (3 * i, ROOF, -7.5))
	for cz in (S, C, N):
		add("Exterior", "hosp_band", (-1.5, H2, cz), 90)
		add("Exterior", "hosp_band", (31.5, H2, cz), 90)
		add("Exterior", "hosp_band", (10.5, ROOF, cz), 90)
		add("Exterior", "hosp_band", (31.5, ROOF, cz), 90)
	# двери 1 этажа (открыты)
	leaf_v("Doors1", -1.5, S, G, "+x")             # вход в шлюз
	leaf_h("Doors1", 1, -1.5, G, "-z")             # шлюз → коридор
	leaf_h("Doors1", 2, 1.5, G, "-z")              # главный вход
	leaf_h("Doors1", 2, -1.5, G, "-z")             # дверь в стеклянной перегородке
	for i in (4, 7, 8, 10):
		leaf_h("Doors1", i, -1.5, G, "+z")         # комнаты южного ряда
	for i in (0, 2, 4, 6, 8, 9):
		leaf_h("Doors1", i, -4.5, G, "-z")         # комнаты северного ряда
	add("Doors1", "hosp_gate_leaf", (4.86, G, -7.5), 90)   # ворота приёмки — во двор
	add("Doors1", "hosp_gate_leaf", (7.14, G, -7.5), 90)
	leaf_h("Doors1", 9, -7.5, G, "+z")             # прачечная → задний двор
	leaf_v("Doors1", 31.5, N, G, "-x")             # прачечная → боковой проезд
	leaf_v("Doors1", 31.5, C, G, "-x")             # коридор → боковой проезд

	# ---------- лестничная клетка (ножничная: вверх в южной половине, вниз — в северной) ----------
	add("Stairs", "hosp_stairs_flight", (15, G, 0.7))
	add("Stairs", "hosp_stairs_railing", (15, G, 0.7))
	add("Stairs", "hosp_stairs_landing", (18.7, 1.65, 0))
	add("Stairs", "hosp_stairs_flight", (18, 1.65, -0.7), 180)
	add("Stairs", "hosp_stairs_railing", (18, 1.65, -0.7), 180)
	add("Stairs", "hosp_stairs_landing", (14.3, H2, 0))
	add("Stairs", "hosp_railing_straight", (15.05, H2, 0.75), 90)
	add("Stairs", "hosp_stairs_flight", (18, -1.65, -0.7), 180)   # вниз, в подвал
	add("Stairs", "hosp_stairs_railing", (18, -1.65, -0.7), 180)
	add("Stairs", "hosp_stairs_landing", (18.7, -1.65, 0))
	add("Stairs", "hosp_stairs_flight", (15, B, 0.7))
	add("Stairs", "hosp_stairs_railing", (15, B, 0.7))

	# ---------- 2 этаж (x ≥ 10,5) ----------
	for i in range(4, 11):
		for cz in (S, C, N):
			if (i, cz) not in stair:
				add("Floor2", "hosp_floor", (3 * i, H2, cz))
			add("Roof", "hosp_roof", (3 * i, ROOF, cz))
		hw("Walls2", i, 1.5, H2, "hosp_wall_window_ext", "-z")
		hw("Walls2", i, -7.5, H2, "hosp_wall_window_ext", "+z")
	for cz, west, east in ((S, "hosp_wall_ext", "hosp_wall_ext"), (C, "hosp_wall_window_ext", "hosp_wall_window_ext"),
			(N, "hosp_wall_ext", "hosp_wall_window_ext")):
		vw("Walls2", 10.5, cz, H2, west, "+x")
		vw("Walls2", 31.5, cz, H2, east, "-x")
	for i, module in zip(range(4, 11), ("hosp_wall_door", "hosp_wall_door", "hosp_wall", "hosp_wall_door",
			"hosp_wall", "hosp_wall", "hosp_wall")):
		hw("Walls2", i, -1.5, H2, module)
	for i, module in zip(range(4, 11), ("hosp_wall_door", "hosp_wall", "hosp_wall_door", "hosp_wall",
			"hosp_wall_door", "hosp_wall", "hosp_wall_door")):
		hw("Walls2", i, -4.5, H2, module)
	for xb in (13.5, 19.5):
		vw("Walls2", xb, S, H2, "hosp_wall")
	for xb in (16.5, 22.5, 28.5):
		vw("Walls2", xb, N, H2, "hosp_wall")
	for x, z in ((10.5, 1.5), (31.5, 1.5), (10.5, -7.5), (31.5, -7.5)):
		add("Walls2", "hosp_wall_corner_brick", (x, H2, z))
	for i in (4, 7):
		leaf_h("Doors2", i, -1.5, H2, "+z")
	for i in (4, 6, 8, 10):
		leaf_h("Doors2", i, -4.5, H2, "-z")

	# ---------- подвал ----------
	basement_cells = [(i, C) for i in range(3, 9)] + [(5, S), (6, S), (7, S), (8, S)] + [(4, N), (5, N), (6, N)]
	for i, cz in basement_cells:
		add("Basement", "hosp_floor_concrete", (3 * i, B, cz))
	for i, module, inner in ((3, "hosp_wall_bsmt_ground", "-z"), (4, "hosp_wall_bsmt_ground", "-z"),
			(5, "hosp_wall_door_bsmt", "-z"), (6, "hosp_wall_bsmt", "-z"), (7, "hosp_wall_door_bsmt", "-z"),
			(8, "hosp_wall_bsmt", "-z")):
		hw("Basement", i, -1.5, B, module, inner)
	for i, module, inner in ((3, "hosp_wall_bsmt_ground", "+z"), (4, "hosp_wall_bsmt", "+z"),
			(5, "hosp_wall_door_bsmt", "+z"), (6, "hosp_wall_bsmt", "+z"), (7, "hosp_wall_bsmt_ground", "+z"),
			(8, "hosp_wall_bsmt_ground", "+z")):
		hw("Basement", i, -4.5, B, module, inner)
	for i in (5, 6, 7, 8):
		hw("Basement", i, 1.5, B, "hosp_wall_bsmt_ground", "-z")
	for i in (4, 5, 6):
		hw("Basement", i, -7.5, B, "hosp_wall_bsmt_ground", "+z")
	vw("Basement", 7.5, C, B, "hosp_wall_bsmt_ground", "+x")
	vw("Basement", 25.5, C, B, "hosp_wall_bsmt_ground", "-x")
	vw("Basement", 13.5, S, B, "hosp_wall_bsmt_ground", "+x")
	vw("Basement", 19.5, S, B, "hosp_wall_bsmt")
	vw("Basement", 25.5, S, B, "hosp_wall_bsmt_ground", "-x")
	vw("Basement", 10.5, N, B, "hosp_wall_bsmt_ground", "+x")
	vw("Basement", 19.5, N, B, "hosp_wall_bsmt_ground", "-x")
	for x, z in ((7.5, -1.5), (7.5, -4.5), (10.5, -4.5), (10.5, -7.5), (19.5, -7.5), (19.5, -4.5),
			(25.5, -4.5), (25.5, 1.5), (13.5, 1.5), (13.5, -1.5)):
		add("Basement", "hosp_wall_corner_bsmt", (x, B, z))
	leaf_h("Basement", 5, -1.5, B, "+z", "hosp_door_metal")   # коридор → лестница
	leaf_h("Basement", 7, -1.5, B, "+z", "hosp_door_metal")   # коридор → кислород
	leaf_h("Basement", 5, -4.5, B, "-z", "hosp_door_metal")   # коридор → аптечный склад
	for i in range(3, 9):
		add("PropsB", "prop_pipe_run", (3 * i, B + 2.55, -4.5), 180)
	for x, z in ((9, -3), (15, -3), (21, -3), (22.5, 0), (15, -6)):
		add("PropsB", "prop_bulkhead_lamp", (x, -0.2, z))
	for k in range(11):
		add("PropsB", "prop_oxygen_cylinder", (20.0 + k * 0.45, B, 1.2))
	for k in range(5):
		add("PropsB", "prop_oxygen_cylinder", (23.0 + k * 0.45, B, 0.7))
	for x in (11.6, 13.6, 15.6, 17.6):
		add("PropsB", "prop_shelf_rack", (x, B, -7.1))
	add("PropsB", "prop_shelf_rack", (19.1, B, -5.9), 90)
	add("PropsB", "prop_pallet_boxes", (12.5, B, -5.4))
	add("PropsB", "prop_pallet_boxes", (17.0, B, -5.3), 90)
	add("PropsB", "prop_box", (14.0, B, -5.6), 15)

	# ---------- реквизит 1 этажа ----------
	L1 = G + 3.1  # потолок 1 этажа
	# шлюз
	add("Props1", "prop_coat_rack_suits", (0, G, 1.5))
	add("Props1", "prop_med_cabinet", (-0.6, G, -1.5), 180)
	add("Props1", "prop_bench", (0.8, G, -1.2))
	add("Props1", "prop_floor_line", (1.5, G + 0.001, 0), 90)
	add("Props1", "prop_sink", (3.8, G, 1.5))
	add("Props1", "prop_bin_hazard", (2.1, G, 1.1))
	add("Props1", "prop_bin_hazard", (4.1, G, -1.05))
	add("Props1", "prop_sign_plate_red", (3, G + 2.35, -1.5), 180)
	add("Props1", "prop_sign_plate", (-1.5, G + 2.3, 0), -90)
	# вестибюль
	add("Props1", "prop_bench", (8.5, G, 1.15), 180)
	add("Props1", "prop_bench", (9.0, G, -1.15))
	# ординаторская 1 этажа
	add("Props1", "prop_desk", (12.6, G, 0.9))
	add("Props1", "prop_chair", (12.6, G, 0.3))
	add("Props1", "prop_med_cabinet", (13.5, G, -0.4), 90)
	# процедурная
	add("Props1", "prop_sink", (19.5, G, 0.5), -90)
	add("Props1", "prop_med_cabinet", (22.5, G, 0.2), 90)
	add("Props1", "prop_gurney", (21.1, G, 0.3), 90)
	# палата 1 этажа (юг)
	for x in (25.3, 26.6, 27.9):
		add("Props1", "prop_bed", (x, G, -0.4))
	add("Props1", "prop_iv_stand", (25.95, G, 0.8))
	add("Props1", "prop_sink", (31.5, G, 0.5), 90)  # санузел
	# палаты северного ряда
	for x in (1.3, 2.6, 3.9, 13.1, 14.4, 15.7, 19.2, 20.5, 21.8):
		add("Props1", "prop_bed", (x, G, -5.6), 180)
	for i in (0, 1, 4, 5, 6, 7):
		add("Props1", "prop_radiator", (3 * i, G, -7.5), 180)
	for i in (3, 4, 7, 8, 9):
		add("Props1", "prop_radiator", (3 * i, G, 1.5))
	# приёмка, кладовая, прачечная
	add("Props1", "prop_pallet_boxes", (9.0, G, -6.2), 90)
	add("Props1", "prop_box", (8.0, G, -5.2))
	add("Props1", "prop_shelf_rack", (24, G, -7.1))
	add("Props1", "prop_washer", (28.3, G, -6.9))
	add("Props1", "prop_washer", (29.2, G, -6.9))
	add("Props1", "prop_shelf_rack", (25.85, G, -6.0), 90)
	# коридор
	add("Props1", "prop_gurney", (17.2, G, -2.0), 90)
	add("Props1", "prop_gurney", (20.5, G, -4.0), 90)
	add("Props1", "prop_iv_stand", (17.2, G, -2.7))
	add("Props1", "prop_bench", (2.2, G, -4.15))
	add("Props1", "prop_oxygen_cylinder", (9.6, G, -4.2))
	add("Props1", "prop_oxygen_cylinder", (9.9, G, -4.2))
	for i in range(11):
		add("Props1", "prop_ceiling_lamp", (3 * i, L1, C))
	for x, z in ((0, S), (3, S), (6, S), (9, S), (12, S), (21, S), (24, S), (27, S), (30, S), (0, N), (3, N),
			(6, N), (9, N), (12, N), (15, N), (18, N), (21, N), (24, N), (27, N), (30, N)):
		add("Props1", "prop_ceiling_lamp", (x, L1, z))
	add("Props1", "prop_ceiling_lamp", (14.3, L1, 0), 90)  # под верхней площадкой лестницы

	# ---------- реквизит 2 этажа ----------
	L2 = H2 + 3.1
	add("Props2", "prop_desk", (12.6, H2, 0.9))
	add("Props2", "prop_chair", (12.6, H2, 0.3))
	add("Props2", "prop_med_cabinet", (13.5, H2, -0.4), 90)
	for x in (22.4, 24.0, 25.6, 27.2, 28.8, 30.4):   # палата 214 — шесть коек
		add("Props2", "prop_bed", (x, H2, -0.4))
	for x in (23.2, 26.4, 29.6):
		add("Props2", "prop_iv_stand", (x, H2, 0.9))
		add("Props2", "prop_oxygen_cylinder", (x, H2, -1.2))
	for i in (4, 5, 6, 7, 8, 9, 10):
		add("Props2", "prop_radiator", (3 * i, H2, 1.5))
	for i in (4, 5, 6, 7, 8, 9, 10):
		add("Props2", "prop_radiator", (3 * i, H2, -7.5), 180)
	for x in (13.1, 14.4, 15.7, 19.2, 20.5, 21.8, 25.2, 26.5, 27.8):
		add("Props2", "prop_bed", (x, H2, -5.6), 180)
	add("Props2", "prop_shelf_rack", (28.85, H2, -6.0), 90)   # сестринская
	add("Props2", "prop_oxygen_cylinder", (30.5, H2, -5.0))
	add("Props2", "prop_oxygen_cylinder", (30.8, H2, -5.0))
	add("Props2", "prop_desk", (21, H2, -4.1), 180)           # сестринский пост
	add("Props2", "prop_chair", (21, H2, -3.5), 180)
	add("Props2", "prop_oxygen_cylinder", (22.0, H2, -4.15))
	add("Props2", "prop_oxygen_cylinder", (22.3, H2, -4.15))
	for x, z in ((17.6, -2.0), (25.5, -2.0), (27.8, -4.0), (15.2, -4.0)):
		add("Props2", "prop_gurney", (x, H2, z), 90)
	add("Props2", "prop_iv_stand", (17.6, H2, -2.6))
	add("Props2", "prop_iv_stand", (25.5, H2, -2.6))
	add("Props2", "prop_sign_plate", (21.95, H2 + 1.6, -1.5))
	for i in range(4, 11):
		for cz in (C, N) + ((S,) if i not in (5, 6) else ()):
			add("Props2", "prop_ceiling_lamp", (3 * i, L2, cz))
	add("Props2", "prop_ceiling_lamp", (16.5, L2, 0), 90)

	# ---------- улица ----------
	for x in (-7.5, -1.5, 4.5, 10.5, 16.5, 22.5, 28.5, 34.5):
		for z in (4.5, 10.5, 16.5, -10.5, -16.5, -22.5):
			add("Exterior", "ext_ground_asphalt", (x, Y, z))
	for x in (-9, -6, -3, 33, 36):
		for z in (-6, -3, 0):
			add("Exterior", "ext_ground_asphalt_small", (x, Y, z))
	add("Exterior", "hosp_porch", (6, G, 3.1))                      # главное крыльцо
	add("Exterior", "hosp_dock_steps", (6, Y, 6.1), 90)
	add("Exterior", "hosp_dock_canopy", (4.5, G, 1.5))
	add("Exterior", "hosp_dock_canopy", (7.5, G, 1.5))
	add("Exterior", "prop_bulkhead_lamp", (6, G + 2.88, 2.2))
	add("Exterior", "prop_sign_plate_red", (6, G + 2.62, 1.5), 180)
	add("Exterior", "hosp_porch", (-3.1, G, 0), 90)                 # крыльцо шлюза
	add("Exterior", "hosp_dock_steps", (-6.1, Y, 0))
	add("Exterior", "hosp_porch", (27, G, -9.1))                    # крыльцо прачечной
	add("Exterior", "hosp_dock_steps", (27, Y, -12.1), -90)
	add("Exterior", "hosp_porch", (33.1, G, -6))                    # боковое крыльцо
	add("Exterior", "hosp_porch", (33.1, G, -3))
	add("Exterior", "hosp_dock_steps", (36.1, Y, -4.5), 180)
	for x in (6, 9):                                                # рампа аптеки
		add("Exterior", "hosp_dock_platform", (x, G, -9.1), 180)
	add("Exterior", "hosp_dock_steps", (12.0, Y, -9.1), 180)
	for x in (4.5, 7.5, 10.5):
		add("Exterior", "hosp_dock_canopy", (x, G, -7.5), 180)
	add("Exterior", "prop_bulkhead_lamp", (6, G + 2.88, -8.2))
	add("Exterior", "prop_sign_plate", (6, G + 2.62, -7.5))
	for k in range(16):                                             # забор
		x = -9 + 3 * k
		if x not in (0, 3):
			add("Exterior", "ext_fence", (x, Y, 16.5))
		if x not in (27, 30):
			add("Exterior", "ext_fence", (x, Y, -22.5))
	for k in range(13):
		z = -21 + 3 * k
		add("Exterior", "ext_fence", (-10.5, Y, z), 90)
		add("Exterior", "ext_fence", (37.5, Y, z), 90)
	add("Vehicles", "blk_vehicle_truck", (1.5, Y, 12.5), 90)        # «Урал» (сц. 1)
	add("Vehicles", "blk_vehicle_van", (11.5, Y, 7.0))              # фургон сварщиков (сц. 7)
	add("Vehicles", "blk_vehicle_uaz", (7.5, Y, -12.8), 90)         # «буханка» у рампы (сц. 6)
	add("Vehicles", "blk_vehicle_ambulance", (28.5, Y, -19.0))      # скорая (сц. 10)

	cool, warm = (0.92, 1.0, 0.95), (1.0, 0.85, 0.6)
	lights = []
	for i in range(0, 11, 2):
		lights.append((f"Corridor1_{i}", (3 * i, 2.9, C), cool, 1.0, 7.0))
	for k, (x, z) in enumerate(((1.5, S), (7.5, S), (12, S), (21, S), (25.5, S), (30, S), (1.5, N), (7.5, N),
			(13.5, N), (19.5, N), (24, N), (28.5, N))):
		lights.append((f"Room1_{k}", (x, 2.9, z), cool, 1.0, 6.0))
	for k, y in enumerate((2.4, 5.6, -1.0, -2.6)):
		lights.append((f"Stair_{k}", (16.5, y, 0), cool, 0.9, 6.0))
	for i in range(4, 11, 2):
		lights.append((f"Corridor2_{i}", (3 * i, 6.2, C), cool, 1.0, 7.0))
	for k, (x, z) in enumerate(((12, S), (22.5, S), (28.5, S), (13.5, N), (19.5, N), (25.5, N), (30, N))):
		lights.append((f"Room2_{k}", (x, 6.2, z), cool, 1.0, 6.0))
	for k, (x, z) in enumerate(((9, C), (15, C), (21, C), (22.5, S), (15, N))):
		lights.append((f"Basement_{k}", (x, -0.5, z), warm, 0.9, 6.0))
	for k, pos in enumerate(((6, 2.6, 2.2), (6, 2.6, -8.2), (27, 2.2, -8.6), (-2.5, 2.2, 0), (28.5, 3.0, -20),
			(33.1, 2.2, -4.5))):
		lights.append((f"Outdoor_{k}", pos, warm, 1.5, 7.0))

	dark, white = (0.12, 0.12, 0.12), (1, 1, 1)
	labels = [
		("SignAirlockRed", (3, 2.35, -1.387), 0, "КРАСНАЯ ЗОНА", 44, white),
		("SignAirlockClean", (-1.387, 2.3, 0), 90, "ЧИСТАЯ ЗОНА", 36, dark),
		("SignMain", (6, 2.62, 1.613), 0, "ИНФЕКЦИОННЫЙ КОРПУС № 4", 22, white),
		("Sign214", (21.95, H2 + 1.6, -1.613), 180, "Палата № 214", 36, dark),
		("SignPharmacy", (15.95, B + 1.6, -4.387), 0, "АПТЕЧНЫЙ СКЛАД", 28, dark),
		("SignOxygen", (21.95, B + 1.6, -1.613), 180, "КИСЛОРОД", 36, dark),
		("SignDock", (6, 2.62, -7.613), 180, "АПТЕКА", 36, dark),
	]
	p += [("PropsB", "SignPharmacyPlate", "prop_sign_plate", (15.95, B + 1.6, -4.5), 180),
		("PropsB", "SignOxygenPlate", "prop_sign_plate", (21.95, B + 1.6, -1.5), 0)]
	markers = [
		("S01_Gate", (1.5, 1.6, 15.0), "Сц.1: «Урал» у ворот, родственники"),
		("S01_Airlock", (1.5, 2.2, 0), "Сц.1: шлюз — надеть СИЗ"),
		("S02_Olga", (4.5, 2.2, -3), "Сц.2: Ольга — «мне нужны руки»"),
		("S02_Oxygen", (22.5, -1.2, 0), "Сц.2: кислород — 2 ходки на 2 этаж"),
		("S02_Grandma", (16.5, 5.4, -3), "Сц.2: бабушка ищет Валю"),
		("S02_DeadList", (21, 5.4, -4.2), "Сц.2: список умерших у поста"),
		("S02_Drawings", (12, 5.4, 0), "Сц.2: детские рисунки"),
		("S03_Gena", (7.5, 2.2, -0.6), "Сц.3: Гена у стекла"),
		("S03_Lida", (30.4, 5.2, 0.4), "Сц.3: палата 214, Лида у окна"),
		("S04_Syringe", (27.9, 3.6, 0.8), "Сц.4: шприц на полу → В-2"),
		("S05_Break", (27, 1.4, -9.6), "Сц.5: ночь, перерыв с Ольгой"),
		("S06_Dock", (7.5, 1.4, -11.0), "Сц.6: мародёры, «буханка» у рампы"),
		("S06_Store", (15, -1.2, -6), "Сц.6: бой в подвале, аптечный склад"),
		("S06_Escape", (28.5, 2.2, -6), "Сц.6: бегство через прачечную"),
		("S07_Order", (6, 1.2, 7.5), "Сц.7: приказ Ершова, сварщики"),
		("S08_Doors", (6, 2.0, 3.0), "Сц.8: двери открываются"),
		("S09_Fight", (12, 1.2, 10), "Сц.9: бой со своими"),
		("S10_Ershov", (33.5, 1.2, 3.0), "Сц.10: Ершов за углом"),
		("S10_Exit", (28.5, 1.8, -17), "Сц.10: отход — скорая, задние ворота"),
	]
	return {"placements": p, "lights": lights, "labels": labels, "markers": markers,
		"player": ((3, -1.05, 15.5), 0)}


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
