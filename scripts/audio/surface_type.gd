class_name SurfaceType
## Тип поверхности под ногами (для шагов; позже — для попаданий).
## Порядок: метаданные `surface` на узле или его предках → материалы модуля набора → бетон.
## Техописание — docs/TECHNICAL_DESIGN.md, «Звук v0.1».

const DEFAULT := &"concrete"
const ALL: Array[StringName] = [&"concrete", &"tile", &"asphalt", &"dirt", &"metal", &"wood"]

## Материал библиотеки → поверхность. Если у модуля несколько материалов (пол сверху, потолок
## снизу), побеждает тот, что выше в списке.
const MATERIALS := [
	["floor_tile", &"tile"],
	["ground_dirt", &"dirt"],
	["soil", &"dirt"],
	["asphalt", &"asphalt"],
	["wood", &"wood"],
	["wood_raw", &"wood"],
	["stair_tread", &"concrete"],
	["concrete", &"concrete"],
	["metal_grey", &"metal"],
	["metal_dark", &"metal"],
	["roof_metal", &"metal"],
]
## Сколько предков проверять на метаданные `surface`.
const META_DEPTH := 4

static var _cache := {}


static func of(collider: Object) -> StringName:
	if not collider is Node:
		return DEFAULT
	var id := collider.get_instance_id()
	if not _cache.has(id):
		_cache[id] = _resolve(collider)
	return _cache[id]


static func _resolve(collider: Node) -> StringName:
	var node := collider
	for i in META_DEPTH:
		if node == null:
			break
		if node.has_meta(&"surface"):
			return StringName(node.get_meta(&"surface"))
		node = node.get_parent()

	var names := {}
	_add_materials(collider, names)
	for child in collider.get_children():
		_add_materials(child, names)
	var parent := collider.get_parent()
	if parent is MeshInstance3D:
		_add_materials(parent, names)  # модель «-col»: коллизия — дочерний узел меша
	elif parent != null and not parent.scene_file_path.is_empty():
		for sibling in parent.get_children():  # модель «-colonly»: меши — соседи коллизии
			_add_materials(sibling, names)
	for pair: Array in MATERIALS:
		if names.has(pair[0]):
			return pair[1]
	return DEFAULT


static func _add_materials(node: Node, names: Dictionary) -> void:
	if node is MeshInstance3D and node.mesh != null:
		for i in node.mesh.get_surface_count():
			_add_material(node.get_active_material(i), names)
	elif node is CSGShape3D and node.get(&"material") != null:
		_add_material(node.get(&"material"), names)


static func _add_material(material: Material, names: Dictionary) -> void:
	if material == null:
		return
	var material_name := material.resource_path.get_file().get_basename()
	if material_name.is_empty():
		material_name = material.resource_name
	names[material_name] = true
