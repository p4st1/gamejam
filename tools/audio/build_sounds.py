"""Синтез звуков прототипа: шаги, прыжок/приземление, фоновые петли, звуки меню.

Запуск из корня проекта: python3 tools/audio/build_sounds.py [--overwrite]
Только стандартная библиотека Python. Пишет .wav и .tres (AudioStreamRandomizer) в assets/audio/.
Звук, заменённый вручную, не перезаписывается (сверка с контрольной суммой из
assets/audio/.generated.json) — только с --overwrite.
Техописание — docs/TECHNICAL_DESIGN.md, «Звук v0.1».
"""

import hashlib
import json
import math
import os
import random
import struct
import sys

SR = 44100
ROOT = "assets/audio"
CHECKSUMS = os.path.join(ROOT, ".generated.json")
VARIANTS = 5


# --- Обработка сигнала ---------------------------------------------------------------------------

def silence(seconds):
	return [0.0] * int(seconds * SR)


def noise(n, rng):
	return [rng.uniform(-1.0, 1.0) for _ in range(n)]


def biquad(samples, kind, freq, q=0.707):
	"""Фильтр RBJ: lowpass, highpass, bandpass."""
	w = 2 * math.pi * freq / SR
	cos_w, alpha = math.cos(w), math.sin(w) / (2 * q)
	if kind == "lowpass":
		b0, b1, b2 = (1 - cos_w) / 2, 1 - cos_w, (1 - cos_w) / 2
	elif kind == "highpass":
		b0, b1, b2 = (1 + cos_w) / 2, -(1 + cos_w), (1 + cos_w) / 2
	else:
		b0, b1, b2 = alpha, 0.0, -alpha
	a0, a1, a2 = 1 + alpha, -2 * cos_w, 1 - alpha
	b0, b1, b2, a1, a2 = b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0
	out, x1, x2, y1, y2 = [], 0.0, 0.0, 0.0, 0.0
	for x in samples:
		y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
		x2, x1, y2, y1 = x1, x, y1, y
		out.append(y)
	return out


def decay(n, tau, attack=0.002):
	"""Огибающая: быстрая атака и экспоненциальный спад с постоянной tau (с)."""
	a = max(1, int(attack * SR))
	return [(i / a if i < a else 1.0) * math.exp(-i / (tau * SR)) for i in range(n)]


def mul(a, b):
	return [x * y for x, y in zip(a, b)]


def mix_into(dst, src, at=0, gain=1.0):
	start = int(at * SR)
	for i, x in enumerate(src):
		if 0 <= start + i < len(dst):
			dst[start + i] += x * gain


def tone(n, freq, tau, phase=0.0, drop=0.0):
	"""Затухающая синусоида; drop — доля, на которую падает частота (удар корпусом)."""
	out, ph = [], phase
	for i in range(n):
		f = freq * (1 - drop * (1 - math.exp(-i / (0.03 * SR))))
		ph += 2 * math.pi * f / SR
		out.append(math.sin(ph) * math.exp(-i / (tau * SR)))
	return out


def grains(n, rng, density, tau=0.0015):
	"""Россыпь коротких щелчков (песок, мелкие камни)."""
	out = [0.0] * n
	click = int(tau * SR * 5)
	for i in range(n):
		if rng.random() < density / SR:
			amp = rng.uniform(0.3, 1.0) * rng.choice((-1, 1))
			for k in range(min(click, n - i)):
				out[i + k] += amp * math.exp(-k / (tau * SR)) * rng.uniform(-1, 1)
	return out


def normalize(samples, peak_db):
	peak = max(1e-9, max(abs(x) for x in samples))
	gain = 10 ** (peak_db / 20) / peak
	return [x * gain for x in samples]


def fade_tail(samples, seconds=0.01):
	n = int(seconds * SR)
	for i in range(min(n, len(samples))):
		samples[-1 - i] *= i / n
	return samples


def make_loop(samples, crossfade):
	"""Бесшовная петля: хвост равномощно вливается в начало. Длина = len - crossfade."""
	x = int(crossfade * SR)
	n = len(samples) - x
	out = samples[:n]
	for i in range(x):
		t = i / x
		out[i] = samples[i] * math.sin(t * math.pi / 2) + samples[n + i] * math.cos(t * math.pi / 2)
	return out


# --- Шаги ----------------------------------------------------------------------------------------

def impact(surface, rng, strength):
	"""Один удар подошвы (пятка или носок)."""
	n = int(0.4 * SR)
	out = [0.0] * n
	if surface == "concrete":
		mix_into(out, mul(biquad(noise(n, rng), "lowpass", rng.uniform(2800, 3600)), decay(n, 0.016)), 0, 0.9)
		mix_into(out, tone(n, rng.uniform(85, 105), 0.03, drop=0.3), 0, 0.5)
		mix_into(out, biquad(mul(grains(n, rng, 900), decay(n, 0.05)), "highpass", 2500), 0, 0.25)
	elif surface == "tile":
		mix_into(out, mul(biquad(noise(n, rng), "bandpass", rng.uniform(2200, 2900), 1.5), decay(n, 0.009)), 0, 1.4)
		mix_into(out, tone(n, rng.uniform(3000, 3600), 0.007), 0, 0.35)
		mix_into(out, tone(n, rng.uniform(110, 130), 0.025, drop=0.3), 0, 0.4)
	elif surface == "asphalt":
		mix_into(out, mul(biquad(noise(n, rng), "lowpass", rng.uniform(2000, 2600)), decay(n, 0.02)), 0, 0.8)
		mix_into(out, tone(n, rng.uniform(80, 95), 0.03, drop=0.3), 0, 0.5)
		mix_into(out, biquad(mul(grains(n, rng, 2500), decay(n, 0.07)), "highpass", 1800), 0, 0.45)
	elif surface == "dirt":
		mix_into(out, mul(biquad(noise(n, rng), "lowpass", rng.uniform(700, 1000)), decay(n, 0.045, 0.006)), 0, 1.0)
		mix_into(out, tone(n, rng.uniform(60, 75), 0.05, drop=0.4), 0, 0.6)
		mix_into(out, biquad(mul(grains(n, rng, 3000, 0.002), decay(n, 0.09, 0.01)), "lowpass", 2200), 0, 0.5)
	elif surface == "metal":
		mix_into(out, mul(biquad(noise(n, rng), "highpass", 1500), decay(n, 0.006)), 0, 0.6)
		mix_into(out, tone(n, rng.uniform(85, 100), 0.04, drop=0.3), 0, 0.6)
		k = rng.uniform(0.94, 1.06)
		for freq, tau, amp in ((310, 0.22, 0.35), (742, 0.16, 0.25), (1183, 0.12, 0.2), (1731, 0.09, 0.15), (2459, 0.06, 0.1)):
			mix_into(out, tone(n, freq * k, tau, rng.uniform(0, 6.28)), 0, amp)
	elif surface == "wood":
		mix_into(out, mul(biquad(noise(n, rng), "lowpass", 1800), decay(n, 0.012)), 0, 0.6)
		k = rng.uniform(0.92, 1.08)
		for freq, tau, amp in ((175, 0.06, 0.6), (410, 0.04, 0.35), (690, 0.025, 0.2)):
			mix_into(out, tone(n, freq * k, tau, rng.uniform(0, 6.28)), 0, amp)
	return [x * strength for x in out]


SURFACES = {  # поверхность: пиковый уровень, дБ
	"concrete": -6.0, "tile": -6.0, "asphalt": -6.0, "dirt": -8.0, "metal": -7.0, "wood": -7.0,
}


def footstep(surface, rng):
	n = int(0.45 * SR)
	out = [0.0] * n
	mix_into(out, impact(surface, rng, 1.0), 0)                                   # пятка
	mix_into(out, impact(surface, rng, rng.uniform(0.45, 0.65)), rng.uniform(0.04, 0.07))  # носок
	return fade_tail(normalize(out, SURFACES[surface] + rng.uniform(-1.0, 0.0)))


# --- Тело: прыжок и приземление ------------------------------------------------------------------

def gear_rustle(n, rng, length):
	"""Шорох ткани и снаряжения с парой металлических звяков."""
	m = int(length * SR)
	env = [math.sin(math.pi * min(1.0, i / m)) ** 2 if i < m else 0.0 for i in range(n)]
	out = mul(biquad(biquad(noise(n, rng), "bandpass", rng.uniform(1800, 2600), 0.8), "highpass", 900), env)
	for _ in range(rng.randint(1, 3)):
		at = rng.uniform(0.02, length * 0.8)
		mix_into(out, tone(int(0.15 * SR), rng.uniform(2800, 4800), 0.018, rng.uniform(0, 6.28)), at, 0.25)
	return out


def jump(rng):
	n = int(0.45 * SR)
	out = gear_rustle(n, rng, rng.uniform(0.22, 0.3))
	mix_into(out, mul(biquad(noise(n, rng), "lowpass", 400), decay(n, 0.03, 0.01)), 0, 0.5)  # толчок
	return fade_tail(normalize(out, -12.0))


def land(rng):
	n = int(0.6 * SR)
	out = [0.0] * n
	mix_into(out, tone(n, rng.uniform(55, 65), 0.09, drop=0.4), 0, 1.0)
	mix_into(out, mul(biquad(noise(n, rng), "lowpass", 600), decay(n, 0.04)), 0, 0.6)
	mix_into(out, gear_rustle(n, rng, rng.uniform(0.15, 0.2)), 0.01, 0.35)
	return fade_tail(normalize(out, -7.0))


# --- Фон -----------------------------------------------------------------------------------------

LOOP_SECONDS, CROSSFADE = 16.0, 1.0


def lfo(i, periods):
	"""Сумма медленных синусов с периодами, кратными длине петли, — 0…1."""
	t = i / SR
	return 0.5 + 0.5 * sum(math.sin(2 * math.pi * t / p + k) for k, p in enumerate(periods)) / len(periods)


def outdoor_wind(rng):
	n = int((LOOP_SECONDS + CROSSFADE) * SR)
	src = noise(n, rng)
	out, y, y2 = [], 0.0, 0.0
	for i, x in enumerate(src):
		gust = lfo(i, (17.0, 8.5, 5.67))
		cutoff = 250 + 900 * gust ** 2
		a = 1 - math.exp(-2 * math.pi * cutoff / SR)
		y += a * (x - y)
		y2 += a * (y - y2)             # второй порядок — мягче
		out.append(y2 * (0.35 + 0.65 * gust))
	whistle = mul(biquad(noise(n, rng), "bandpass", 900, 6.0), [lfo(i, (8.5, 4.25)) ** 3 for i in range(n)])
	mix_into(out, whistle, 0, 0.15)
	mix_into(out, biquad(noise(n, rng), "lowpass", 60), 0, 0.6)  # далёкий гул
	return normalize(make_loop(out, CROSSFADE), -14.0)


def indoor_hum(rng):
	n = int((LOOP_SECONDS + CROSSFADE) * SR)
	out = [0.0] * n
	for freq, amp in ((50, 0.5), (100, 0.35), (150, 0.12), (200, 0.08), (300, 0.04)):  # сеть 50 Гц
		ph = rng.uniform(0, 6.28)
		for i in range(n):
			out[i] += amp * math.sin(2 * math.pi * freq * i / SR + ph)
	vent = biquad(biquad(noise(n, rng), "lowpass", 380), "highpass", 60)
	mix_into(out, vent, 0, 2.2)
	leak = biquad(noise(n, rng), "lowpass", 180)                 # ветер за окнами
	mix_into(out, mul(leak, [lfo(i, (17.0, 5.67)) for i in range(n)]), 0, 1.5)
	return normalize(make_loop(out, CROSSFADE), -18.0)


def basement(rng):
	n = int((LOOP_SECONDS + CROSSFADE) * SR)
	out = biquad(noise(n, rng), "lowpass", 120)
	out = [x * 3.0 for x in out]
	ph = rng.uniform(0, 6.28)
	for i in range(n):                                          # насос / теплоузел
		out[i] += 0.18 * math.sin(2 * math.pi * 50 * i / SR + ph) * (0.8 + 0.2 * math.sin(2 * math.pi * i / SR / 4.25))
	for at in (1.7, 5.3, 6.1, 10.4, 13.2):                      # капли с эхом подвала
		drop = tone(int(0.3 * SR), rng.uniform(1300, 1900), 0.03, drop=-0.4)
		for echo, gain in ((0.0, 0.5), (0.09, 0.2), (0.21, 0.1), (0.37, 0.05)):
			mix_into(out, drop, at + echo, gain)
	return normalize(make_loop(out, CROSSFADE), -16.0)


# --- Интерфейс -----------------------------------------------------------------------------------

def ui_hover(rng):
	n = int(0.06 * SR)
	out = mul(biquad(noise(n, rng), "bandpass", 3200, 2.0), decay(n, 0.004, 0.0005))
	return fade_tail(normalize(out, -20.0), 0.005)


def ui_click(rng):
	n = int(0.12 * SR)
	out = mul(biquad(noise(n, rng), "bandpass", 2400, 1.5), decay(n, 0.006, 0.0005))
	mix_into(out, tone(n, 180, 0.02, drop=0.3), 0, 0.6)
	return fade_tail(normalize(out, -12.0), 0.01)


# --- Запись --------------------------------------------------------------------------------------

def wav_bytes(samples, loop=False):
	"""16 бит, моно. Для петли — чанк smpl: Godot зацикливает такой файл сам (Loop Mode: Detect)."""
	data = struct.pack(f"<{len(samples)}h", *(max(-32767, min(32767, int(x * 32767))) for x in samples))
	fmt = struct.pack("<HHIIHH", 1, 1, SR, SR * 2, 2, 16)
	chunks = b"fmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack("<I", len(data)) + data
	if loop:
		smpl = struct.pack("<9I", 0, 0, 1_000_000_000 // SR, 60, 0, 0, 0, 1, 0)
		smpl += struct.pack("<6I", 0, 0, 0, len(samples) - 1, 0, 0)
		chunks += b"smpl" + struct.pack("<I", len(smpl)) + smpl
	return b"RIFF" + struct.pack("<I", 4 + len(chunks)) + b"WAVE" + chunks


def randomizer_tres(paths):
	lines = ['[gd_resource type="AudioStreamRandomizer" format=3]', ""]
	lines += [f'[ext_resource type="AudioStream" path="res://{p}" id="{i + 1}"]' for i, p in enumerate(paths)]
	lines += ["", "[resource]", "random_pitch = 1.06", "random_volume_offset_db = 1.5", f"streams_count = {len(paths)}"]
	for i in range(len(paths)):
		lines += [f'stream_{i}/stream = ExtResource("{i + 1}")', f"stream_{i}/weight = 1.0"]
	return ("\n".join(lines) + "\n").encode()


class Writer:
	def __init__(self, overwrite):
		self.overwrite = overwrite
		self.checksums = json.load(open(CHECKSUMS)) if os.path.exists(CHECKSUMS) else {}
		self.written = self.skipped = 0

	def write(self, path, content):
		if os.path.exists(path) and not self.overwrite:
			current = hashlib.sha256(open(path, "rb").read()).hexdigest()
			if self.checksums.get(path) != current:
				print(f"[audio] ПРОПУЩЕН {path}: заменён вручную. Перезаписать — с флагом --overwrite.")
				self.skipped += 1
				return
		os.makedirs(os.path.dirname(path), exist_ok=True)
		with open(path, "wb") as f:
			f.write(content)
		self.checksums[path] = hashlib.sha256(content).hexdigest()
		self.written += 1

	def save(self):
		with open(CHECKSUMS, "w") as f:
			json.dump(self.checksums, f, indent=1, sort_keys=True)


def build_set(writer, folder, name, make, seed):
	rng = random.Random(seed)
	paths = []
	for k in range(1, VARIANTS + 1):
		path = f"{ROOT}/{folder}/{name}_{k}.wav"
		writer.write(path, wav_bytes(make(rng)))
		paths.append(path)
	writer.write(f"{ROOT}/{folder}/{name}.tres", randomizer_tres(paths))


def main():
	writer = Writer("--overwrite" in sys.argv)
	for k, surface in enumerate(SURFACES):
		build_set(writer, "sfx/footsteps", surface, lambda rng, s=surface: footstep(s, rng), 100 + k)
	build_set(writer, "sfx/body", "jump", jump, 200)
	build_set(writer, "sfx/body", "land", land, 201)
	for k, (name, make) in enumerate((("outdoor_wind", outdoor_wind), ("indoor_hum", indoor_hum), ("basement", basement))):
		writer.write(f"{ROOT}/ambience/{name}.wav", wav_bytes(make(random.Random(300 + k)), loop=True))
	writer.write(f"{ROOT}/ui/hover.wav", wav_bytes(ui_hover(random.Random(400))))
	writer.write(f"{ROOT}/ui/click.wav", wav_bytes(ui_click(random.Random(401))))
	writer.save()
	print(f"[audio] записано {writer.written}, пропущено {writer.skipped}")


if __name__ == "__main__":
	main()
