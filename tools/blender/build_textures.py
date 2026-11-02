"""Процедурные текстуры набора «Больница» — генератор для Blender (использует встроенный numpy).

Для каждого материала создаёт бесшовные карты: цвет (_albedo), рельеф (_normal, OpenGL / Y+),
шероховатость (_roughness). Ничего не скачивает — текстуры полностью собственные.

Запуск (из корня проекта):
    Blender -b --factory-startup --python tools/blender/build_textures.py -- assets/textures/hospital [--overwrite]

Существующие текстуры не перезаписываются без --overwrite (их мог заменить создатель, D-037).
"""

import os
import sys

import bpy
import numpy as np

SIZE = 1024
rng = np.random.default_rng(1940)  # фиксированное зерно — результат одинаковый при каждом запуске


# --- Шум ------------------------------------------------------------------------------------------

def _upsample(grid, size):
	"""Бесшовная билинейная интерполяция сетки grid (g × g) до size × size."""
	g = grid.shape[0]
	coords = np.arange(size) * g / size
	i0 = np.floor(coords).astype(int)
	t = coords - i0
	i1 = (i0 + 1) % g
	t = t * t * (3 - 2 * t)  # сглаживание
	rows = grid[i0] * (1 - t)[:, None] + grid[i1] * t[:, None]
	return rows[:, i0] * (1 - t)[None, :] + rows[:, i1] * t[None, :]


def noise(cells, octaves=4, persistence=0.5, size=SIZE):
	"""Бесшовный фрактальный шум 0..1. cells — число ячеек базовой октавы на текстуру."""
	result = np.zeros((size, size))
	amplitude, total = 1.0, 0.0
	for octave in range(octaves):
		g = cells * 2 ** octave
		if g > size:
			break
		result += _upsample(rng.random((g, g)), size) * amplitude
		total += amplitude
		amplitude *= persistence
	return result / total


def normal_from_height(height, strength):
	"""Карта нормалей OpenGL (Y+) из карты высот, бесшовно."""
	dx = (np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)) * strength
	dy = (np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)) * strength
	n = np.dstack((-dx, -dy, np.ones_like(height)))
	n /= np.linalg.norm(n, axis=2, keepdims=True)
	return n * 0.5 + 0.5


# --- Сохранение -----------------------------------------------------------------------------------

def save(path, rgb):
	"""rgb — массив (size, size, 3) или (size, size) в 0..1; строка 0 — низ изображения (как в Blender)."""
	if rgb.ndim == 2:
		rgb = np.dstack((rgb, rgb, rgb))
	size = rgb.shape[0]
	rgba = np.dstack((np.clip(rgb, 0, 1), np.ones((size, size))))
	image = bpy.data.images.new(os.path.basename(path), size, size, alpha=False)
	image.pixels.foreach_set(rgba.astype(np.float32).ravel())
	image.filepath_raw = path
	image.file_format = "PNG"
	image.save()
	bpy.data.images.remove(image)
	print(f"[textures] {os.path.basename(path)}")


def write_set(out_dir, name, albedo, height, roughness, normal_strength):
	save(os.path.join(out_dir, f"{name}_albedo.png"), albedo)
	save(os.path.join(out_dir, f"{name}_normal.png"), normal_from_height(height, normal_strength))
	save(os.path.join(out_dir, f"{name}_roughness.png"), roughness)


def tint(base, variation):
	"""Цвет base (sRGB), умноженный на поле яркости variation."""
	return np.asarray(base)[None, None, :] * variation[:, :, None]


# --- Материалы ------------------------------------------------------------------------------------

def floor_tile():
	"""Метлахская плитка 8 × 8 на текстуру (1 м → 12,5 см), коричнево-красная, с затиркой."""
	tiles, grout = 8, 3
	cell = SIZE // tiles
	y, x = np.mgrid[0:SIZE, 0:SIZE]
	in_grout = ((x % cell) < grout) | ((y % cell) < grout)
	tile_id = (y // cell) * tiles + (x // cell)
	per_tile = rng.uniform(0.85, 1.1, tiles * tiles)[tile_id]
	hue = rng.choice([0, 1], tiles * tiles, p=[0.85, 0.15])[tile_id]  # редкие плитки другого оттенка
	fine = noise(64, 3) * 0.25 + 0.85
	wear = noise(4, 3)
	base = np.where(hue[:, :, None] == 1, (0.50, 0.30, 0.22), (0.45, 0.25, 0.19))
	albedo = base * (per_tile * fine * (0.92 + wear * 0.12))[:, :, None]
	albedo[in_grout] = np.array((0.28, 0.27, 0.25)) * fine[in_grout][:, None]
	height = np.where(in_grout, 0.0, 1.0) + noise(64, 2) * 0.05
	roughness = np.where(in_grout, 0.9, 0.45 + wear * 0.25)
	return albedo, height, roughness, 2.0


def whitewash():
	"""Побелка: пятна, неровная штукатурка под ней."""
	blotch = noise(3, 4)
	fine = noise(48, 4)
	albedo = tint((0.86, 0.86, 0.82), 0.9 + blotch * 0.1 - fine * 0.05)
	height = noise(8, 5) * 0.7 + fine * 0.3
	roughness = 0.88 + fine * 0.1
	return albedo, height, roughness, 0.5


def paint(base=(0.30, 0.45, 0.38)):
	"""Масляная краска с полосами от валика и редкими сколами до побелки."""
	streak = _upsample(rng.random((8, 8)), SIZE) * 0.3 + noise(4, 3) * 0.7
	streak = 0.5 * streak + 0.5 * np.repeat(noise(64, 2)[:1, :], SIZE, axis=0)  # вертикальные мазки
	chips = noise(16, 4) > 0.81
	albedo = tint(base, 0.94 + streak * 0.08)
	albedo[chips] = np.array((0.72, 0.72, 0.68))
	height = streak * 0.3 + np.where(chips, -0.6, 0.0)
	roughness = np.where(chips, 0.9, 0.3 + streak * 0.15)
	return albedo, height, roughness, 2.0


def concrete():
	"""Бетон: пятна и мелкие поры."""
	big = noise(4, 4)
	fine = noise(64, 3)
	pores = noise(128, 1) > 0.82
	albedo = tint((0.55, 0.55, 0.53), 0.85 + big * 0.2 + fine * 0.05)
	albedo[pores] *= 0.7
	height = fine * 0.6 + big * 0.4 - pores * 0.5
	roughness = 0.85 + fine * 0.1
	return albedo, height, roughness, 2.5


def terrazzo():
	"""Мозаичный пол лестниц: серый цемент с крошкой."""
	base = noise(6, 3)
	albedo = tint((0.42, 0.41, 0.40), 0.9 + base * 0.15)
	for color, threshold in (((0.15, 0.15, 0.15), 0.86), ((0.75, 0.73, 0.70), 0.86), ((0.45, 0.30, 0.25), 0.9)):
		chips = noise(96, 1) > threshold
		albedo[chips] = color
	height = noise(96, 2) * 0.2
	roughness = 0.4 + base * 0.2
	return albedo, height, roughness, 1.0


def door_paint():
	"""Окрашенное дерево: волокна под слоем краски."""
	grain = np.repeat(noise(96, 2)[:1, :], SIZE, axis=0) * 0.6 + noise(8, 3) * 0.4
	albedo = tint((0.85, 0.86, 0.82), 0.95 + grain * 0.06)
	height = grain * 0.5
	roughness = 0.35 + grain * 0.1
	return albedo, height, roughness, 1.0


def wood():
	"""Лакированное дерево скамеек: волокна вдоль X."""
	grain = np.repeat(noise(128, 3)[:, :1], SIZE, axis=1)
	rings = np.sin((grain + noise(4, 3) * 0.5) * 40) * 0.5 + 0.5
	albedo = tint((0.45, 0.30, 0.18), 0.8 + rings * 0.3)
	height = rings * 0.4
	roughness = 0.5 + rings * 0.15
	return albedo, height, roughness, 1.0


def wall_tile():
	"""Белый кафель шлюза: 8 × 8 плиток на текстуру (1 м → 12,5 см), тонкие светлые швы, блестит."""
	tiles, grout = 8, 2
	cell = SIZE // tiles
	y, x = np.mgrid[0:SIZE, 0:SIZE]
	in_grout = ((x % cell) < grout) | ((y % cell) < grout)
	tile_id = (y // cell) * tiles + (x // cell)
	per_tile = rng.uniform(0.96, 1.02, tiles * tiles)[tile_id]
	stain = noise(4, 3)
	albedo = tint((0.88, 0.89, 0.88), per_tile * (0.97 + stain * 0.05))
	albedo[in_grout] = np.array((0.62, 0.62, 0.60))
	height = np.where(in_grout, 0.0, 1.0)
	roughness = np.where(in_grout, 0.8, 0.12 + stain * 0.1)
	return albedo, height, roughness, 1.5


def brick():
	"""Силикатный кирпич фасада: 4 кирпича × 14 рядов на текстуру (1,04 × 1,05 м), перевязка в полкирпича."""
	cols, rows, joint = 4, 14, 9
	y, x = np.mgrid[0:SIZE, 0:SIZE]
	row = (y * rows) // SIZE
	row_y = (y * rows) % SIZE
	shifted = (x + (row % 2) * (SIZE // cols // 2)) % SIZE
	col = (shifted * cols) // SIZE
	col_x = (shifted * cols) % SIZE
	in_joint = (row_y < joint * rows) | (col_x < joint * cols)
	brick_id = row * cols + col
	per_brick = rng.uniform(0.88, 1.05, rows * cols)[brick_id]
	dirt = noise(3, 4)
	fine = noise(96, 2)
	albedo = tint((0.78, 0.76, 0.70), per_brick * (0.9 + fine * 0.1) * (0.85 + dirt * 0.15))
	albedo[in_joint] = np.array((0.50, 0.49, 0.46)) * (0.9 + fine[in_joint] * 0.1)[:, None]
	height = np.where(in_joint, 0.0, 1.0) + fine * 0.15
	roughness = np.where(in_joint, 0.95, 0.8 + fine * 0.1)
	return albedo, height, roughness, 2.0


def asphalt():
	"""Асфальт двора: тёмный, с крупкой, пятнами и трещинами. Текстура на 4 × 4 м."""
	big = noise(3, 4)
	grit = noise(160, 1)
	ridge = 1 - np.abs(noise(4, 3, persistence=0.35) * 2 - 1)  # «хребты» шума — трещины
	cracks = ridge > 0.992
	albedo = tint((0.24, 0.24, 0.23), 0.85 + big * 0.2 + grit * 0.12)
	albedo[cracks] *= 0.6
	height = grit * 0.5 - cracks * 0.8
	roughness = 0.9 + grit * 0.08
	return albedo, height, roughness, 2.0


TEXTURES = {
	"floor_tile": floor_tile,
	"whitewash": whitewash,
	"paint_green": paint,
	"concrete": concrete,
	"stair_tread": terrazzo,
	"door_paint": door_paint,
	"wood": wood,
	# v0.4 — добавлены в конец, чтобы прежние текстуры не изменились (общее зерно случайностей)
	"wall_tile": wall_tile,
	"brick": brick,
	"asphalt": asphalt,
	"paint_grey": lambda: paint((0.45, 0.47, 0.47)),
}


def main():
	all_args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
	args = [a for a in all_args if not a.startswith("--")]
	overwrite = "--overwrite" in all_args
	out_dir = os.path.abspath(args[0] if args else "assets/textures/hospital")
	os.makedirs(out_dir, exist_ok=True)
	for name, builder in TEXTURES.items():
		# Считаем всегда (общее зерно случайностей — иначе сдвинутся следующие текстуры),
		# а пишем только недостающие: готовые мог заменить или доработать создатель (D-037).
		albedo, height, roughness, strength = builder()
		files = [os.path.join(out_dir, f"{name}_{kind}.png") for kind in ("albedo", "normal", "roughness")]
		if all(os.path.exists(f) for f in files) and not overwrite:
			print(f"[textures] {name}: уже есть, не трогаю (перезаписать — --overwrite)")
			continue
		write_set(out_dir, name, albedo, height, roughness, strength)


main()
