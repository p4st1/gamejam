"""Генератор демо-сцены набора «Больница»: scenes/levels/prototype/hospital_kit_demo.tscn.

Запуск из корня проекта: python3 tools/gen_hospital_demo.py
Координаты — Godot (Y вверх). Сетка 3 м; стены стоят на линиях сетки.
"""
KIT = "res://assets/models/kits/hospital/"
modules = ["hosp_floor","hosp_wall","hosp_wall_corner","hosp_wall_door","hosp_wall_window","hosp_door",
           "hosp_stairs_flight","hosp_stairs_landing","prop_bed","prop_cabinet",
           "prop_oxygen_cylinder","prop_gurney","prop_bench",
           "hosp_stairs_railing","hosp_railing_straight","prop_ceiling_lamp","prop_radiator",
           "prop_sink","prop_iv_stand","prop_med_cabinet","prop_sign_plate"]
ids = {m: f"{i+3}_{m}" for i, m in enumerate(modules)}
nodes = []  # (parent, name, module, pos, rot_y)
def add(group, name, module, pos, rot=0):
    nodes.append((group, name, module, pos, rot))

# Полы (y=0) и перекрытия (y=3.3)
cells_floor = [(3*i, 0) for i in range(4)] + [(3,-3),(6,-3)] + [(12,0),(15,0)]
for k,(x,z) in enumerate(cells_floor):
    add("Floors", f"Floor{k}", "hosp_floor", (x,0,z))
for k,(x,z) in enumerate([(3*i,0) for i in range(4)] + [(3,-3),(6,-3)]):
    add("Ceilings", f"Ceiling{k}", "hosp_floor", (x,3.3,z))
# Стены
w = []
w += [("hosp_wall_window",(x,0,1.5),0) for x in (0,3,6,9)]          # коридор, юг
w += [("hosp_wall",(0,0,-1.5),0),("hosp_wall_door",(3,0,-1.5),0),("hosp_wall",(6,0,-1.5),0),("hosp_wall",(9,0,-1.5),0)]
w += [("hosp_wall",(-1.5,0,0),90)]                                    # торец коридора
w += [("hosp_wall_window",(x,0,-4.5),180) for x in (3,6)]            # палата, север
w += [("hosp_wall",(1.5,0,-3),90),("hosp_wall",(7.5,0,-3),90)]       # палата, бока
w += [("hosp_wall_window",(x,0,1.5),0) for x in (12,15)]             # лестница, юг
w += [("hosp_wall",(x,0,-1.5),0) for x in (12,15)]                   # лестница, север
w += [("hosp_wall",(16.5,0,0),90)]                                    # лестница, торец
for k,(m,p,r) in enumerate(w):
    add("Walls", f"Wall{k}", m, p, r)
add("Walls", "WardDoor", "hosp_door", (2.46,0,-1.5), 90)
# Угловые колонны — в узлах, где стены сходятся под углом
for k,(x,z) in enumerate([(-1.5,1.5),(-1.5,-1.5),(1.5,-1.5),(1.5,-4.5),(7.5,-4.5),(7.5,-1.5),(16.5,1.5),(16.5,-1.5)]):
    add("Walls", f"Corner{k}", "hosp_wall_corner", (x,0,z))
# Лестница
add("Stairs", "Flight1", "hosp_stairs_flight", (12.0,0,0.7), 0)
add("Stairs", "MidLanding", "hosp_stairs_landing", (15.7,1.65,0), 0)
add("Stairs", "Flight2", "hosp_stairs_flight", (15.0,1.65,-0.7), 180)
add("Stairs", "UpperLanding", "hosp_stairs_landing", (11.3,3.3,0), 0)
add("Stairs", "Railing1", "hosp_stairs_railing", (12.0,0,0.7), 0)            # перила — как марши
add("Stairs", "Railing2", "hosp_stairs_railing", (15.0,1.65,-0.7), 180)
add("Stairs", "LandingRailing", "hosp_railing_straight", (12.0,3.3,0.75), 90)  # край площадки 2 этажа
# Реквизит
for k,x in enumerate((2.4,3.9,5.4,6.9)):
    add("Props", f"Bed{k}", "prop_bed", (x,0,-3.4))
add("Props","Cabinet0","prop_cabinet",(3.15,0,-4.15)); add("Props","Cabinet1","prop_cabinet",(6.15,0,-4.15))
for k,p in enumerate([(1.95,0,-4.2),(4.65,0,-4.2),(8.2,0,-1.2),(8.5,0,-1.15),(8.8,0,-1.2)]):
    add("Props", f"Oxygen{k}", "prop_oxygen_cylinder", p)
add("Props","Gurney","prop_gurney",(5.0,0,0.8),90)
add("Props","Bench","prop_bench",(0.5,0,-1.2),0)
# Батареи — с той же привязкой, что и окна над ними
for k,(x,z,r) in enumerate([(0,1.5,0),(3,1.5,0),(6,1.5,0),(9,1.5,0),(3,-4.5,180),(6,-4.5,180)]):
    add("Props", f"Radiator{k}", "prop_radiator", (x,0,z), r)
# Светильники на потолке (их свет — OmniLight в группе Lights)
for k,p in enumerate([(0,3.1,0),(3,3.1,0),(6,3.1,0),(9,3.1,0),(3,3.1,-3),(6,3.1,-3)]):
    add("Props", f"Lamp{k}", "prop_ceiling_lamp", p)
add("Props","StairLamp","prop_ceiling_lamp",(11.3,3.1,0),90)
add("Props","Sink","prop_sink",(1.5,0,-2.2),-90)
add("Props","IVStand","prop_iv_stand",(3.1,0,-2.9))
add("Props","MedCabinet","prop_med_cabinet",(7.5,0,-1.95),90)
add("Props","WardSign","prop_sign_plate",(3.95,1.6,-1.5),180)

lights = [("CorridorLight%d"%i,(3*i,2.9,0)) for i in range(4)] + [("WardLight0",(3,2.9,-3)),("WardLight1",(6,2.9,-3)),("StairLight0",(12,2.9,0)),("StairLight1",(15,2.9,0)),("StairLight2",(13.5,5.5,0))]

def fmt(v): return ", ".join(("%g" % c) for c in v)
out = ['[gd_scene format=3]', '',
 '[ext_resource type="PackedScene" path="res://scenes/player/player.tscn" id="1_player"]',
 '[ext_resource type="Script" path="res://scripts/debug/debug_overlay.gd" id="2_overlay"]']
for m in modules:
    out.append(f'[ext_resource type="PackedScene" path="{KIT}{m}.glb" id="{ids[m]}"]')
out += ['',
'[sub_resource type="ProceduralSkyMaterial" id="SkyMat_overcast"]',
'sky_top_color = Color(0.42, 0.46, 0.5, 1)','sky_horizon_color = Color(0.62, 0.64, 0.66, 1)',
'ground_bottom_color = Color(0.18, 0.19, 0.2, 1)','ground_horizon_color = Color(0.62, 0.64, 0.66, 1)','',
'[sub_resource type="Sky" id="Sky_overcast"]','sky_material = SubResource("SkyMat_overcast")','',
'[sub_resource type="Environment" id="Env_hospital"]','background_mode = 2','sky = SubResource("Sky_overcast")',
'ambient_light_source = 3','ambient_light_energy = 0.35','tonemap_mode = 2','',
'[node name="HospitalKitDemo" type="Node3D"]','',
'[node name="WorldEnvironment" type="WorldEnvironment" parent="."]','environment = SubResource("Env_hospital")','',
'[node name="Sun" type="DirectionalLight3D" parent="."]','rotation_degrees = Vector3(-35, -150, 0)',
'light_color = Color(0.92, 0.94, 1, 1)','light_energy = 0.7','shadow_enabled = true','']
for g in ["Floors","Ceilings","Walls","Stairs","Props","Lights"]:
    out += [f'[node name="{g}" type="Node3D" parent="."]','']
for (g,name,m,p,r) in nodes:
    out.append(f'[node name="{name}" parent="{g}" instance=ExtResource("{ids[m]}")]')
    out.append(f'position = Vector3({fmt(p)})')
    if r: out.append(f'rotation_degrees = Vector3(0, {r}, 0)')
    out.append('')
for name,p in lights:
    out += [f'[node name="{name}" type="OmniLight3D" parent="Lights"]', f'position = Vector3({fmt(p)})',
            'light_color = Color(0.92, 1, 0.95, 1)', 'light_energy = 1.1', 'omni_range = 6.0', '']
out += ['[node name="WardSignText" type="Label3D" parent="Props"]', 'position = Vector3(3.95, 1.6, -1.385)',
        'pixel_size = 0.001', 'modulate = Color(0.12, 0.12, 0.12, 1)', 'outline_size = 0',
        'text = "Палата № 214"', 'font_size = 36', '']
out += ['[node name="Player" parent="." instance=ExtResource("1_player")]',
 'position = Vector3(0, 0.05, 0)','rotation_degrees = Vector3(0, -90, 0)','',
 '[node name="HUD" type="CanvasLayer" parent="."]','',
 '[node name="DebugOverlay" type="Label" parent="HUD" node_paths=PackedStringArray("player")]',
 'offset_left = 16.0','offset_top = 16.0','offset_right = 520.0','offset_bottom = 200.0',
 'script = ExtResource("2_overlay")','player = NodePath("../../Player")','']
open("scenes/levels/prototype/hospital_kit_demo.tscn","w").write("\n".join(out))
print(len(nodes), "nodes")
