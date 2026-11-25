import json, sys, subprocess
import numpy as np
from faster_whisper import WhisperModel
m = WhisperModel("large-v3", device="cpu", compute_type="int8", cpu_threads=4)
audio=np.frombuffer(subprocess.run(["ffmpeg","-v","error","-i",sys.argv[1],"-ac","1","-ar","16000","-f","f32le","-"],capture_output=True,check=True).stdout,dtype=np.float32)
segs, info = m.transcribe(audio, word_timestamps=True, vad_filter=False, beam_size=5, condition_on_previous_text=False)
print("lang", info.language, info.language_probability, flush=True)
out=[]
for s in segs:
    print(f"[{s.start:7.2f}-{s.end:7.2f}] {s.text}", flush=True)
    out.append({"start":s.start,"end":s.end,"text":s.text,"words":[{"w":w.word,"s":w.start,"e":w.end,"p":w.probability} for w in s.words]})
json.dump(out, open(sys.argv[2],"w"), indent=1, ensure_ascii=False)
