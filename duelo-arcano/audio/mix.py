"""Mix the ElevenLabs SFX layers into the 60 s soundtrack, locked to timeline.py.

python3 audio/mix.py            -> audio/duelo_mix.wav
Each cue: (clip, start_seconds, gain_dB, fade_in, fade_out, max_len, pan(-1..1))
"""
import os
import sys
import json
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'scene'))
import timeline as T  # noqa: E402

E = T.E
SR = 48000
DUR = T.F_END / T.FPS          # 60.0 s


def s(frame, offset=0.0):
    return (frame - 1) / T.FPS + offset


CUES = [
    # ambience
    ('wind_bed', 0.0, -17, 2.5, 1.5, 31.0, 0.0),
    ('wind_bed_b', 29.5, -17, 1.5, 3.0, 31.0, 0.0),
    ('thunder_far', s(E['lightning1'], 0.6), -9, 0.05, 2.0, 8, -0.3),
    ('thunder_far_b', s(E['lightning2'], 0.5), -11, 0.05, 2.0, 8, 0.4),
    ('thunder_far', s(E['lightning3'], 0.35), -8, 0.05, 2.5, 8, 0.2),
    ('drone_dark', 5.0, -16, 4.0, 1.2, s(E['release']) - 5.0 + 0.6, 0.0),
    # awakening
    ('eyes_ignite', s(E['eyes_on'], -0.08), -5, 0.0, 0.4, 3, 0.0),
    ('runes_burn', s(E['runes_start']), -9, 0.1, 1.0, 5, 0.0),
    ('energy_suction', s(E['gather_start']), -15, 1.5, 1.5, 12, 0.0),
    ('energy_suction_b', s(E['gather_start']) + 11.0, -14, 1.5, 0.3, s(E['windup_end']) - s(E['gather_start']) - 11.0, 0.0),
    ('orb_birth', s(E['orb_birth'], -0.05), -5, 0.0, 0.5, 3, 0.0),
    ('orb_charge', s(E['orb_birth'], 0.4), -12, 2.0, 0.12, s(E['release']) - s(E['orb_birth'], 0.4), 0.0),
    ('rocks_levitate', s(E['rocks_rise_start']), -13, 0.6, 1.5, 6, 0.15),
    ('electric_arcs', s(E['arcs_start']), -17, 0.8, 0.8, 10, -0.15),
    ('electric_arcs_b', s(E['arcs_start']) + 9.0, -14, 0.5, 0.12, s(E['release']) - s(E['arcs_start']) - 9.0, 0.15),
    ('whispers', s(600), -15, 2.5, 1.5, 9.0, 0.0),
    # wind-up / release / flight
    ('windup_swell', s(E['release']) - 2.95, -5, 0.3, 0.05, 3, 0.0),
    ('launch_blast', s(E['release'], -0.04), 2, 0.0, 1.2, 3, 0.0),
    ('rocks_fall', s(E['rocks_fall'], 0.45), -12, 0.0, 0.8, 3, -0.2),
    ('flyby', s(E['release'], 0.25), -5, 0.05, 0.4, 3.5, 0.0),
    ('shield_form', s(E['shield_start'], -0.1), -6, 0.0, 0.6, 2.5, -0.1),
    # impact / struggle / burst
    ('impact', s(E['impact'], -0.04), 3, 0.0, 1.5, 4, 0.0),
    ('struggle', s(E['impact'], 0.25), -9, 0.3, 0.15, s(E['burst']) - s(E['impact'], 0.25), 0.0),
    ('burst', s(E['burst'], -0.04), 3, 0.0, 2.0, 4, 0.0),
    ('frag_hits', s(E['burst'], 0.5), -8, 0.0, 1.0, 3, 0.3),
    ('debris_settle', s(E['burst'], 1.0), -12, 0.2, 2.5, 6, 0.0),
    # aftermath
    ('shield_dissolve', s(E['shield_fade_start']), -8, 0.1, 1.5, 4, -0.2),
    ('palm_flame', s(1320), -9, 0.2, 1.0, 4, 0.25),
    ('growl', s(E['eyes_flare'], -0.1), -7, 0.05, 0.6, 2.5, 0.25),
    ('final_hit', s(E['eyes_flare'], 0.05), 0, 0.0, 2.5, 6, 0.0),
]


def clip_path(name):
    sel = json.load(open(os.path.join(HERE, 'selection.json')))
    return os.path.join(HERE, 'sfx', sel[name])


def active_level_db(path):
    """RMS of the non-silent part (50 ms windows above -50 dBFS)."""
    import numpy as np
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-ac', '1', '-ar', '24000', '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(raw, dtype=np.float32)
    win = 1200
    n = len(x) // win
    rms = np.sqrt(np.mean(x[:n * win].reshape(n, win) ** 2, axis=1) + 1e-12)
    db = 20 * np.log10(rms)
    act = db[db > -50]
    return float(20 * np.log10(np.sqrt(np.mean((10 ** (act / 20)) ** 2)))) if len(act) else -40.0


REF_DB = -20.0


def main(out=os.path.join(HERE, 'duelo_mix.wav')):
    inputs, filters, labels = [], [], []
    for i, (name, start, gain, fin, fout, maxlen, pan) in enumerate(CUES):
        path = clip_path(name)
        inputs += ['-i', path]
        norm = max(-18.0, min(18.0, REF_DB - active_level_db(path)))
        gain = gain + norm
        start = max(0.0, start)
        dur = min(maxlen, DUR - start)
        lg = 0.5 * (1 - pan)
        rg = 0.5 * (1 + pan)
        f = (f"[{i}:a]aresample={SR},aformat=channel_layouts=stereo,"
             f"atrim=0:{dur:.3f},asetpts=PTS-STARTPTS,"
             f"afade=t=in:st=0:d={max(fin, 0.005):.3f},"
             f"afade=t=out:st={max(dur - fout, 0):.3f}:d={max(fout, 0.005):.3f},"
             f"volume={gain}dB,"
             f"pan=stereo|c0={2 * lg:.3f}*c0|c1={2 * rg:.3f}*c1,"
             f"adelay={int(start * 1000)}|{int(start * 1000)}[a{i}]")
        filters.append(f)
        labels.append(f'[a{i}]')
    filters.append(''.join(labels) + f'amix=inputs={len(labels)}:normalize=0:duration=longest,'
                   f'atrim=0:{DUR},'
                   f'afade=t=in:st=0:d=0.8,afade=t=out:st={DUR - 1.6}:d=1.6[out]')
    tmp = out.replace('.wav', '_pre.wav')
    cmd = ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error'] + inputs + [
        '-filter_complex', ';'.join(filters), '-map', '[out]', '-ac', '2', '-ar', str(SR),
        '-c:a', 'pcm_f32le', tmp]
    subprocess.run(cmd, check=True)
    # linear loudness normalisation to -16 LUFS, then a brick-wall limiter (keeps dynamics)
    meas = subprocess.run(['ffmpeg', '-hide_banner', '-i', tmp, '-af', 'ebur128', '-f', 'null', '-'],
                          capture_output=True, text=True).stderr
    integ = float([l for l in meas.splitlines() if l.strip().startswith('I:')][-1].split()[1])
    gain = -16.0 - integ
    subprocess.run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-i', tmp, '-af',
                    f'volume={gain:.2f}dB,alimiter=limit=0.84:attack=2:release=60:level=false',
                    '-c:a', 'pcm_s24le', out], check=True)
    os.remove(tmp)
    print('wrote', out)


if __name__ == '__main__':
    main()
