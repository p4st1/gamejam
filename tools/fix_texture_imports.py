"""Настройки импорта 3D-текстур Godot: VRAM-сжатие, мипмапы, карты нормалей (*_normal).

Фоновый импорт (--headless) не распознаёт «3D-использование» сам, поэтому настройки прописываются
явно в .png.import. Запуск из корня проекта после первого импорта новых текстур:
    python3 tools/fix_texture_imports.py && "<Godot>" --headless --path . --import
"""
import glob
import os
import re

CHANGED = 0
for path in glob.glob("assets/textures/**/*.png.import", recursive=True):
	text = open(path).read()
	new = re.sub(r"^compress/mode=\d+", "compress/mode=2", text, flags=re.M)
	new = re.sub(r"^mipmaps/generate=\w+", "mipmaps/generate=true", new, flags=re.M)
	new = re.sub(r"^detect_3d/compress_to=\d+", "detect_3d/compress_to=0", new, flags=re.M)
	if path.endswith("_normal.png.import"):
		new = re.sub(r"^compress/normal_map=\d+", "compress/normal_map=1", new, flags=re.M)
	if new != text:
		open(path, "w").write(new)
		# удалить импортированную копию, чтобы Godot переимпортировал текстуру с новыми настройками
		name = os.path.basename(path)[:-len(".import")]
		for cached in glob.glob(f".godot/imported/{name}-*"):
			os.remove(cached)
		CHANGED += 1
print(f"[textures] настроено файлов: {CHANGED}")
