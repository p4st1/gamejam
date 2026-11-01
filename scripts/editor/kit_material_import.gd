@tool
extends EditorScenePostImport
## Скрипт импорта модульных наборов: заменяет материалы модели на общие из библиотеки по имени.
## Так текстура хранится один раз, а не копируется в каждый .glb.
## Подключается в настройках импорта модели (import_script/path). Библиотеку пишет
## tools/blender/build_hospital_kit.py.

const LIBRARIES: Array[String] = ["res://assets/materials/hospital/"]


func _post_import(scene: Node) -> Object:
	_replace_materials(scene)
	return scene


func _replace_materials(node: Node) -> void:
	var mesh_instance := node as MeshInstance3D
	if mesh_instance and mesh_instance.mesh:
		var mesh := mesh_instance.mesh
		for i in mesh.get_surface_count():
			var material := mesh.surface_get_material(i)
			if material == null:
				continue
			var shared := _find_shared(material.resource_name)
			if shared:
				mesh.surface_set_material(i, shared)
	for child in node.get_children():
		_replace_materials(child)


func _find_shared(material_name: String) -> Material:
	for library in LIBRARIES:
		var path := library + material_name + ".tres"
		if ResourceLoader.exists(path):
			return load(path)
	return null
