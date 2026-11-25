"""Turn the Whisper word timings into curated, timed lyric lines (lyrics.json).

Times are song time in seconds; the renderer adds the intro offset.
"""
import json

segs = json.load(open("whisper_words.json"))
FIX = {"face": "bass"}          # Whisper misheard "Turn the bass up"
CHORUS_KEYS = ("light me up", "oh,")

lines = []
for s in segs:
    words = [{"w": FIX.get(w["w"].strip().lower().strip(",."), None) or w["w"].strip(), "s": w["s"], "e": w["e"]}
             for w in s["words"]]
    # keep punctuation when a fix was applied
    for w, o in zip(words, s["words"]):
        if o["w"].strip().lower().startswith("face"):
            w["w"] = "bass" + o["w"].strip()[4:]
    text = " ".join(w["w"] for w in words)
    if text.lower().startswith("with a light"):
        continue                                    # low-confidence ad-lib
    lines.append({"words": words})

def mk(ws):
    return {"words": [{"w": w, "s": s, "e": e} for w, s, e in ws]}

# Re-timed drop vocals from the second, focused Whisper pass
out = []
for ln in lines:
    first = ln["words"][0]
    t = first["s"]
    txt = " ".join(w["w"] for w in ln["words"]).lower()
    if abs(t - 64.46) < 0.1:
        ln = mk([("Light", 64.28, 65.40), ("me", 65.40, 65.78), ("up", 65.78, 66.12), ("tonight", 66.12, 66.68)])
    elif abs(t - 66.68) < 0.1:
        ln = mk([("Light", 67.0, 68.72), ("me", 68.72, 72.80), ("up", 72.80, 73.86), ("tonight", 73.86, 77.90)])
    elif abs(t - 127.28) < 0.1:
        ln = mk([("Oh,", 127.30, 128.0), ("light", 128.0, 128.28), ("me", 128.28, 128.45), ("up", 128.45, 128.62), ("tonight", 128.62, 129.2)])
    elif abs(t - 146.94) < 0.1:
        ln = mk([("Oh,", 148.24, 149.02), ("light", 149.02, 149.80), ("me", 149.80, 150.04), ("up", 150.04, 150.32), ("tonight", 150.32, 151.0)])
    out.append(ln)

# Whisper glues the silence before a line onto its first word: trim it.
for ln in out:
    w = ln["words"][0]
    if w["e"] - w["s"] > 0.6 and w["w"].lower() not in ("light",):
        w["s"] = round(w["e"] - 0.5, 2)
    ln["start"] = ln["words"][0]["s"]
    ln["end"] = ln["words"][-1]["e"]
    txt = " ".join(x["w"] for x in ln["words"]).lower()
    ln["chorus"] = any(txt.startswith(k) for k in CHORUS_KEYS)

json.dump(out, open("lyrics.json", "w"), indent=1)
for ln in out:
    print(f"{ln['start']:7.2f}-{ln['end']:7.2f} {'*' if ln['chorus'] else ' '} " + " ".join(w["w"] for w in ln["words"]))
