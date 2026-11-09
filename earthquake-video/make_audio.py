"""Synthesise the soundtrack (music + sound design) and mix it with the narration.

Output: audio/soundtrack.wav (48 kHz stereo, 142 s)
"""
import json
import re
import numpy as np
from scipy.signal import butter, sosfilt
from scipy.io import wavfile

SR = 48000
DUR = 142.0
N = int(SR * DUR)
rng = np.random.default_rng(7)

# ---- timeline (mirrors js/timeline.js)
src = open('js/timeline.js', encoding='utf8').read()
T = {k: float(v) for k, v in re.findall(r"(\w+): ([\d.]+),", src.split('export const T = {')[1].split('};')[0])}
NARR = [tuple(map(float, m)) for m in re.findall(r"\[([\d.]+), ([\d.]+), ([\d.]+), '", src)]


def t_axis(n=N):
    return np.arange(n) / SR


def bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], btype='band', fs=SR, output='sos'), x)


def lp(x, f, order=2):
    return sosfilt(butter(order, f, btype='low', fs=SR, output='sos'), x)


def hp(x, f, order=2):
    return sosfilt(butter(order, f, btype='high', fs=SR, output='sos'), x)


def smooth(e0, e1, x):
    k = np.clip((x - e0) / (e1 - e0), 0, 1)
    return k * k * (3 - 2 * k)


def env(t, a, b, fi=0.5, fo=0.5):
    return smooth(a, a + fi, t) * (1 - smooth(b - fo, b, t))


def noise(n):
    return rng.standard_normal(n)


def brown(n):
    x = np.cumsum(rng.standard_normal(n))
    x = hp(x, 8)
    return x / (np.abs(x).max() + 1e-9)


def place(buf, sig, at, gain=1.0, pan=0.0):
    i = int(at * SR)
    if i >= buf.shape[0]:
        return
    j = min(buf.shape[0], i + len(sig))
    s = sig[: j - i] * gain
    l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    buf[i:j, 0] += s * l * 1.414
    buf[i:j, 1] += s * r * 1.414


def shake_env(t):
    p = smooth(T['pStart'], T['pStart'] + 2.5, t) * 0.12 * (1 - smooth(T['sStart'] - 0.3, T['sStart'], t))
    s = smooth(T['sStart'] - 0.2, T['sStart'] + 1.2, t) * (1 - smooth(T['shakeEnd'] - 3.5, T['shakeEnd'], t))
    s = s * (0.78 + 0.22 * np.sin(t * 0.9) * np.sin(t * 0.37 + 1.0))
    s = np.where((t > T['collapse'] - 0.5) & (t < T['collapse'] + 2), np.maximum(s, 1.0), s)
    return np.maximum(p, s)


t = t_axis()
fx = np.zeros((N, 2))
mus = np.zeros((N, 2))
city_scene = (t >= T['introEnd']) & (t < T['beachCut'])

# ---------------------------------------------------------------- ambience
# city bed: traffic rumble + distant hum
bed = lp(brown(N), 300) * 0.5 + bp(noise(N), 200, 1200) * 0.02
bed_env = env(t, 0, T['beachCut'], 1.5, 0.4) * (0.35 + 0.65 * (t > T['introEnd'])) * (1 - 0.6 * smooth(T['pStart'] + 2, T['sStart'] + 3, t))
fx[:, 0] += bed * bed_env * 0.22
fx[:, 1] += np.roll(bed, 2400) * bed_env * 0.22
# sea + wind for the aerial intro
surf = lp(noise(N), 900) * (0.6 + 0.4 * np.sin(2 * np.pi * t / 6.5) ** 2)
fx[:, 0] += surf * env(t, 0, T['introEnd'], 1.5, 0.5) * 0.05
fx[:, 1] += np.roll(surf, 9000) * env(t, 0, T['introEnd'], 1.5, 0.5) * 0.05
# car passes
for k in range(12):
    at = T['introEnd'] + 1 + k * 1.9 + rng.uniform(0, 1.2)
    if at > T['pStart'] + 2:
        break
    d = 3.0
    n = int(d * SR)
    tt = np.arange(n) / SR
    sw = np.exp(-((tt - d / 2) ** 2) / 0.35)
    sig = bp(noise(n), 120, 900) * sw * 0.18
    place(fx, sig, at, 1.0, rng.uniform(-0.8, 0.8))
# birds in the calm walk
for k in range(16):
    at = T['introEnd'] + rng.uniform(0, 22)
    n = int(0.09 * SR)
    tt = np.arange(n) / SR
    f0 = rng.uniform(2800, 4200)
    for rep in range(rng.integers(2, 5)):
        ch = np.sin(2 * np.pi * (f0 * tt + rng.uniform(800, 2000) * tt ** 2 * 6)) * np.sin(np.pi * tt / tt[-1]) ** 2
        place(fx, ch, at + rep * 0.13, 0.025, rng.uniform(-0.9, 0.9))
# crowd murmur (calm -> panic)
mur = bp(noise(N), 250, 1600) * (0.7 + 0.3 * np.sin(2 * np.pi * 3.1 * t) * np.sin(2 * np.pi * 0.7 * t))
mur_env = env(t, T['introEnd'], T['beachCut'], 1, 0.3) * (0.25 + 1.4 * smooth(T['sStart'], T['sStart'] + 2, t) * (1 - 0.6 * smooth(T['crouch'], T['crouch'] + 4, t)))
fx[:, 0] += mur * mur_env * 0.035
fx[:, 1] += np.roll(mur, 5000) * mur_env * 0.035

# footsteps (walking / running)
def steps(a, b, period, gain, heavy=False):
    at = a
    while at < b:
        n = int(0.12 * SR)
        tt = np.arange(n) / SR
        s = lp(noise(n), 900 if not heavy else 500) * np.exp(-tt * 45) + np.sin(2 * np.pi * 70 * tt) * np.exp(-tt * 30) * 0.6
        place(fx, s, at + rng.uniform(-0.01, 0.01), gain, rng.uniform(-0.2, 0.2))
        at += period
steps(T['walkStart'] + 0.2, 43.0, 0.52, 0.10)
steps(59.9, 63.6, 0.3, 0.16, True)
steps(97.4, 101.0, 0.29, 0.18, True)

# ---------------------------------------------------------------- phone alert
a0 = T['alert']
n = int((47.4 - a0) * SR)
tt = np.arange(n) / SR
pattern = ((tt % 0.9) < 0.6).astype(float)
tone = (np.sin(2 * np.pi * 853 * tt) + np.sin(2 * np.pi * 960 * tt)) * 0.5
alert = tone * pattern * np.exp(-np.maximum(0, tt - 4.5) * 0.6)
alert = lp(alert, 5000) * smooth(0, 0.05, tt)
buzz = np.sign(np.sin(2 * np.pi * 160 * tt)) * ((tt % 0.5) < 0.3) * np.exp(-tt * 0.8) * 0.3
place(fx, lp(buzz, 400), a0, 0.25, 0.2)
place(fx, alert, a0 + 0.3, 0.16, 0.25)
# other phones around (city-wide alert)
for k in range(5):
    d = rng.uniform(0.4, 1.8)
    place(fx, hp(alert, 600) * 0.6, a0 + d, 0.05, rng.uniform(-1, 1))

# ---------------------------------------------------------------- earthquake
se = shake_env(t)
rum = lp(brown(N), 70, 4) * 1.6 + lp(noise(N), 160, 2) * 0.25
grind = bp(noise(N), 300, 2500) * (0.5 + 0.5 * np.abs(np.sin(2 * np.pi * 5.3 * t)))
in_city = smooth(T['pStart'] - 1, T['pStart'], t) * (1 - smooth(T['beachCut'] - 0.6, T['beachCut'], t))
quake_g = se * in_city
fx[:, 0] += (rum * 0.55 + grind * 0.05 * (se > 0.3)) * quake_g
fx[:, 1] += (np.roll(rum, 700) * 0.55 + np.roll(grind, 3000) * 0.05 * (se > 0.3)) * quake_g
# rattling objects/windows
rattle = hp(noise(N), 2500) * (np.sin(2 * np.pi * 11 * t) > 0.6)
fx[:, 0] += rattle * quake_g * 0.03
fx[:, 1] += np.roll(rattle, 1111) * quake_g * 0.03


def crash(at, size=1.0, pan=0.0):
    d = 3.5 * size
    n = int(d * SR)
    tt = np.arange(n) / SR
    boom = lp(noise(n), 120, 3) * np.exp(-tt * 1.2 / size) * 3
    debris = bp(noise(n), 400, 4000) * np.exp(-tt * 2.0 / size) * (rng.random(n) < 0.02 * size + 0.002) * 6
    body = bp(noise(n), 90, 700) * np.exp(-tt * 1.6 / size)
    place(fx, (boom + debris + body) * smooth(0, 0.01, tt), at, 0.5 * size, pan)


def glass(at, gain=0.3, pan=0.0):
    n = int(1.2 * SR)
    tt = np.arange(n) / SR
    sig = np.zeros(n)
    for k in range(30):
        f = rng.uniform(2500, 9000)
        st = rng.uniform(0, 0.6)
        m = tt > st
        sig += m * np.sin(2 * np.pi * f * (tt - st)) * np.exp(-(tt - st) * rng.uniform(15, 40)) * rng.uniform(0.2, 1)
    sig += hp(noise(n), 3000) * np.exp(-tt * 9) * 2
    place(fx, sig * 0.15, at, gain, pan)


for k in range(26):
    glass(T['sStart'] + 0.5 + rng.uniform(0, 22), rng.uniform(0.15, 0.4), rng.uniform(-0.9, 0.9))
for k in range(14):
    crash(T['sStart'] + 1 + rng.uniform(0, 28), rng.uniform(0.25, 0.5), rng.uniform(-0.9, 0.9))
crash(T['collapse'], 2.2, -0.5)
crash(T['collapse'] + 0.8, 1.6, -0.6)
crash(T['collapse'] + 1.9, 1.2, -0.4)
crash(67.6, 1.8, -0.3)
crash(68.5, 1.2, -0.3)
# electrical zap of the falling pole
n = int(1.6 * SR)
tt = np.arange(n) / SR
zap = np.sign(np.sin(2 * np.pi * 60 * tt + 3 * np.sin(2 * np.pi * 7 * tt))) * (rng.random(n) < 0.3) * np.exp(-tt * 2)
zap += hp(noise(n), 4000) * (rng.random(n) < 0.05) * np.exp(-tt * 2) * 3
place(fx, bp(zap, 200, 8000), T['poleFall'] + 0.4, 0.22, -0.2)
crash(T['poleFall'] + 0.9, 0.6, -0.2)
# car alarms
for k, (st, f1, f2, pan) in enumerate([(50.2, 700, 1100, 0.6), (51.5, 1250, 900, -0.7), (53.0, 520, 760, 0.2)]):
    d = T['beachCut'] - st
    n = int(d * SR)
    tt = np.arange(n) / SR
    ff = np.where((tt * 2.5 % 1) < 0.5, f1, f2)
    ph = np.cumsum(2 * np.pi * ff / SR)
    sig = np.sign(np.sin(ph)) * 0.5
    sig = bp(sig, 400, 3000) * env(tt, 0, d, 0.05, 0.3)
    place(fx, sig, st, 0.03, pan)
# cracking ground / liquefaction
for k in range(10):
    at = T['cracks'] + k * 0.6 + rng.uniform(0, 0.3)
    n = int(1.2 * SR)
    tt = np.arange(n) / SR
    cr = (lp(noise(n), 200) * 2 + bp(noise(n), 800, 3000) * (rng.random(n) < 0.05) * 4) * np.exp(-tt * 3)
    place(fx, cr, at, 0.25, rng.uniform(-0.6, 0.6))
# aftermath: sirens far away + dust wind
for k, (st, base, pan) in enumerate([(T['shakeEnd'] - 1, 680, -0.5), (T['shakeEnd'] + 0.6, 760, 0.6)]):
    d = T['beachCut'] - st
    n = int(d * SR)
    tt = np.arange(n) / SR
    f = base + 380 * (0.5 + 0.5 * np.sin(2 * np.pi * tt / 3.2))
    sig = np.sin(np.cumsum(2 * np.pi * f / SR)) * env(tt, 0, d, 1.5, 0.3)
    place(fx, lp(sig, 2500), st, 0.035, pan)

# ---------------------------------------------------------------- coast & tsunami
beach = (t >= T['beachCut']) & (t < T['hillCut'])
waves = lp(noise(N), 1500) * (0.4 + 0.6 * np.sin(2 * np.pi * t / 7) ** 4) * (1 - 0.7 * smooth(T['recedeStart'], T['recedeStart'] + 7, t))
wind = bp(noise(N), 150, 900) * (0.6 + 0.4 * np.sin(2 * np.pi * t / 4.3))
fx[:, 0] += (waves * 0.12 + wind * 0.03) * env(t, T['beachCut'], T['hillCut'], 0.4, 0.3)
fx[:, 1] += (np.roll(waves, 4000) * 0.12 + np.roll(wind, 2000) * 0.03) * env(t, T['beachCut'], T['hillCut'], 0.4, 0.3)
# tsunami siren (long wail)
st = T['tsunamiAlarm']
d = T['globeCut'] - st
n = int(d * SR)
tt = np.arange(n) / SR
f = 420 + 380 * smooth(0, 3.5, tt % 7.0) * (1 - smooth(4.5, 7.0, tt % 7.0))
siren = (np.sin(np.cumsum(2 * np.pi * f / SR)) + 0.4 * np.sin(np.cumsum(2 * np.pi * f * 2.01 / SR))) * env(tt, 0, d, 0.6, 0.6)
siren = lp(siren, 3000)
place(fx, siren, st, 0.06, 0.3)
# wind on the hill + approaching roar + impact
hill = env(t, T['hillCut'], T['globeCut'], 0.3, 0.4)
fx[:, 0] += wind * 0.05 * hill
fx[:, 1] += np.roll(wind, 7000) * 0.05 * hill
roar = lp(brown(N), 220, 3) + bp(noise(N), 200, 1800) * 0.3
roar_g = smooth(99, T['waveHitCoast'], t) * (1 - smooth(T['globeCut'] - 0.6, T['globeCut'], t)) * ((t >= T['hillCut'] - 0.5) | (t < T['hillCut']))
roar_g = roar_g * np.where(t < T['hillCut'], 0.25, 1.0)
fx[:, 0] += roar * roar_g * 0.5
fx[:, 1] += np.roll(roar, 900) * roar_g * 0.5
crash(T['waveHitCoast'], 2.4, 0.0)
crash(T['waveHitCoast'] + 1.6, 1.5, 0.3)
crash(T['waveHitCoast'] + 3.0, 1.2, -0.3)

# ---------------------------------------------------------------- the planet rings like a bell
st = T['globeCut'] + 0.4
for k, f0 in enumerate([55.0, 82.5, 110.3]):
    d = 12.0
    n = int(d * SR)
    tt = np.arange(n) / SR
    partials = [1, 2.76, 5.4, 8.93]
    sig = sum(np.sin(2 * np.pi * f0 * p * tt) * np.exp(-tt * (0.25 + 0.15 * i)) / (i + 1) for i, p in enumerate(partials))
    sig *= smooth(0, 0.02, tt)
    place(fx, sig, st + k * 3.2, 0.14, [-0.4, 0.4, 0.0][k])
space = lp(brown(N), 120) * env(t, T['globeCut'], T['endingCut'], 1, 1)
fx[:, 0] += space * 0.15
fx[:, 1] += np.roll(space, 3000) * 0.15
# hill wind for the ending
fx[:, 0] += wind * 0.03 * env(t, T['endingCut'], DUR, 1, 2)
fx[:, 1] += np.roll(wind, 7000) * 0.03 * env(t, T['endingCut'], DUR, 1, 2)

# ---------------------------------------------------------------- music
def note(f, d, amp=1.0, bright=0.3):
    n = int(d * SR)
    tt = np.arange(n) / SR
    det = [0.997, 1.0, 1.003]
    s = sum(np.sin(2 * np.pi * f * dd * tt) + bright * np.sin(2 * np.pi * 2 * f * dd * tt) * 0.5 for dd in det) / 3
    a = smooth(0, min(1.5, d * 0.3), tt) * (1 - smooth(d - min(2.0, d * 0.4), d, tt))
    return s * a * amp


def midi(m):
    return 440 * 2 ** ((m - 69) / 12)


# calm section: Dm9 - Bbmaj7 - F - C (pads), 0 .. 41
prog = [[50, 57, 62, 65, 69], [46, 53, 57, 62, 65], [41, 53, 57, 60, 65], [48, 55, 60, 64, 67]]
bar = 4.4
tt0 = 0.0
i = 0
while tt0 < T['pStart'] + 2:
    ch = prog[i % 4]
    for m in ch:
        sig = note(midi(m), bar + 1.2, 0.05, 0.25)
        place(mus, sig, tt0, 1.0, (m % 7 - 3) / 6)
    # simple piano-ish arpeggio
    for k in range(4):
        m = ch[1 + (k % 4)] + 12
        n = int(1.2 * SR)
        tt = np.arange(n) / SR
        pn = (np.sin(2 * np.pi * midi(m) * tt) + 0.3 * np.sin(4 * np.pi * midi(m) * tt)) * np.exp(-tt * 3.5) * smooth(0, 0.004, tt)
        place(mus, pn, tt0 + k * bar / 4, 0.03, 0.3 - k * 0.2)
    tt0 += bar
    i += 1
calm = 1 - smooth(T['pStart'], T['pStart'] + 2.5, t)
mus *= calm[:, None]

# tension: low drone + heartbeat pulses during the quake and tsunami
dr = (np.sin(2 * np.pi * 36.7 * t) + 0.5 * np.sin(2 * np.pi * 55 * t + 0.3 * np.sin(2 * np.pi * 0.2 * t)) + 0.25 * np.sin(2 * np.pi * 73.4 * t))
tens = env(t, T['pStart'], T['globeCut'], 3, 1.0) * (0.6 + 0.4 * smooth(T['sStart'], T['sStart'] + 2, t))
mus[:, 0] += dr * tens * 0.05
mus[:, 1] += dr * tens * 0.05
beat_t = T['pStart'] + 1.0
while beat_t < T['globeCut'] - 0.5:
    rate = 0.85 if beat_t < T['sStart'] else 0.6 if beat_t < T['shakeEnd'] else 0.8 if beat_t < T['runInland'] else 0.5
    n = int(0.35 * SR)
    tt = np.arange(n) / SR
    hb = np.sin(2 * np.pi * 52 * tt) * np.exp(-tt * 14)
    place(mus, hb, beat_t, 0.18, 0)
    place(mus, hb, beat_t + 0.22, 0.11, 0)
    beat_t += rate
# strings swell for the tsunami (A minor cluster)
for m in [45, 52, 57, 60, 64]:
    sig = note(midi(m), 14, 0.035, 0.5)
    place(mus, sig, T['hillCut'] - 1, 1.0, (m % 5 - 2) / 3)
# hopeful ending: F - C - Dm - Bb - F
prog2 = [[41, 53, 57, 60, 65, 69], [48, 55, 60, 64, 67, 72], [50, 57, 62, 65, 69, 74], [46, 53, 58, 62, 65, 70], [41, 53, 57, 60, 65, 72]]
tt0 = T['endingCut'] - 0.5
for k, ch in enumerate(prog2):
    d = 3.8 if k < 4 else 6.5
    for m in ch:
        place(mus, note(midi(m), d + 1.0, 0.045, 0.3), tt0, 1.0, (m % 7 - 3) / 6)
    for j in range(3):
        m = ch[2 + j] + 12
        n = int(1.6 * SR)
        tt = np.arange(n) / SR
        pn = (np.sin(2 * np.pi * midi(m) * tt) + 0.3 * np.sin(4 * np.pi * midi(m) * tt)) * np.exp(-tt * 2.5) * smooth(0, 0.004, tt)
        place(mus, pn, tt0 + j * d / 3, 0.035, 0.3 - j * 0.3)
    tt0 += d
# title stinger
n = int(5 * SR)
tt = np.arange(n) / SR
sting = lp(brown(n), 90) * np.exp(-tt * 0.8) * smooth(0, 0.02, tt)
place(mus, sting, 1.0, 0.6, 0)
place(mus, sting, T['endCard'], 0.5, 0)

# ---------------------------------------------------------------- narration
sr_n, nar = wavfile.read('audio/narration.wav')
nar = nar.astype(np.float64) / 32768.0
if nar.ndim > 1:
    nar = nar.mean(axis=1)
assert sr_n == SR
voice = np.zeros(N)
for (vt, f0, f1) in NARR:
    a, b = int((f0 - 0.08) * SR), int((f1 + 0.3) * SR)
    seg = nar[max(0, a):b].copy()
    ramp = int(0.03 * SR)
    seg[:ramp] *= np.linspace(0, 1, ramp)
    seg[-ramp:] *= np.linspace(1, 0, ramp)
    i = int((vt - 0.08) * SR)
    voice[i:i + len(seg)] += seg[: N - i]
# ducking envelope from voice activity
act = np.abs(voice)
act = lp(act, 3)
act = np.clip(act / (act.max() * 0.25), 0, 1)
duck = 1 - 0.5 * act

mix = fx * duck[:, None] * 1.0 + mus * (1 - 0.35 * act)[:, None]
# gentle bus compression
peak = np.abs(mix).max()
mix = np.tanh(mix / (peak * 0.6)) * 0.55
vo = voice / np.abs(voice).max() * 0.9
mix[:, 0] += vo
mix[:, 1] += vo
mix /= np.abs(mix).max() / 0.97
# fade in/out
fade = smooth(0, 0.8, t) * (1 - smooth(DUR - 2.2, DUR - 0.1, t))
mix *= fade[:, None]
wavfile.write('audio/soundtrack.wav', SR, (mix * 32767).astype(np.int16))
print('ok', mix.shape, NARR[:2])
