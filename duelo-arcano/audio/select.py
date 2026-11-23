"""Pick the best ElevenLabs variant per layer with simple objective audio metrics."""
import os, glob, json, subprocess
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
SR = 24000

def load(path):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)

def metrics(x):
    win = SR // 20
    n = len(x) // win
    rms = np.sqrt(np.mean(x[:n * win].reshape(n, win) ** 2, axis=1) + 1e-12)
    db = 20 * np.log10(rms)
    pk = int(np.argmax(np.abs(x)))
    return dict(dur=len(x) / SR, peak_t=pk / SR, peak_db=float(20 * np.log10(np.abs(x).max() + 1e-9)),
                loud=float(db.mean()), silence=float((db < -45).mean()), stab=float(db[db > -60].std() if (db > -60).any() else 99),
                onset=float(np.argmax(db > db.max() - 20) * win / SR))

ROLE = {  # how to rank: 'hit' early strong peak, 'swell' late peak, 'bed' steady, 'event' strong & low silence
    'wind_bed': 'bed', 'drone_dark': 'bed', 'orb_charge': 'bed', 'energy_suction': 'event', 'electric_arcs': 'event',
    'whispers': 'event', 'struggle': 'bed', 'debris_settle': 'event', 'thunder_far': 'event', 'runes_burn': 'event',
    'rocks_levitate': 'event', 'eyes_ignite': 'hit', 'orb_birth': 'hit', 'launch_blast': 'hit', 'impact': 'hit',
    'burst': 'hit', 'final_hit': 'hit', 'growl': 'hit', 'frag_hits': 'event', 'shield_form': 'hit',
    'rocks_fall': 'event', 'flyby': 'event', 'shield_dissolve': 'event', 'palm_flame': 'event', 'windup_swell': 'swell',
}

def score(role, m):
    if role == 'hit':
        return m['peak_db'] - 8 * max(0, m['onset'] - 0.15) - 3 * m['silence']
    if role == 'swell':
        return 10 * (m['peak_t'] / m['dur']) + 0.2 * m['loud']
    if role == 'bed':
        return -m['stab'] - 20 * m['silence'] + 0.1 * m['loud']
    return 0.3 * m['loud'] - 40 * m['silence'] - 2 * m['onset']

files = sorted(glob.glob(os.path.join(HERE, 'sfx', '*.mp3')))
groups = {}
for f in files:
    base = os.path.basename(f)[:-4]
    name, idx = base.rsplit('_', 1)
    groups.setdefault(name, []).append((base, metrics(load(f))))
sel, report = {}, {}
for name, items in groups.items():
    role = ROLE.get(name, 'event')
    ranked = sorted(items, key=lambda it: -score(role, it[1]))
    sel[name] = ranked[0][0] + '.mp3'
    if len(ranked) > 1:
        sel[name + '_b'] = ranked[1][0] + '.mp3'      # second-best for doubled cues
    report[name] = [(b, {k: round(v, 2) for k, v in m.items()}) for b, m in ranked]
json.dump(sel, open(os.path.join(HERE, 'selection.json'), 'w'), indent=1)
for k, v in report.items():
    print(k, '->', v[0][0], '|', v[0][1])
