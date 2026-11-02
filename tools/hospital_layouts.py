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
	for g in groups + ["Lights", "Labels"]:
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
)


if __name__ == "__main__":
	force = "--force" in sys.argv
	for layout, name, root in BLOCKOUT_SCENES:
		write_tscn(layout(), os.path.join(BLOCKOUTS, name), root, force)
