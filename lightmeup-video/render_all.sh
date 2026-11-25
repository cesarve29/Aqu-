#!/bin/bash
# Renders the full video in parallel segments, then muxes the soundtrack.
set -e
cd "$(dirname "$0")"
WORKERS=${WORKERS:-4}
TOTAL=$(python3 -c "import json;print(json.load(open('audio_features.json'))['nframes'])")
CHUNK=$(( (TOTAL + WORKERS - 1) / WORKERS ))
mkdir -p segs
pids=()
for ((w=0; w<WORKERS; w++)); do
  s=$((w*CHUNK)); e=$(( (w+1)*CHUNK ))
  node render.js --start $s --end $e --out segs/seg$w.mp4 > segs/log$w.txt 2>&1 &
  pids+=($!)
done
for p in "${pids[@]}"; do wait $p; done
: > segs/list.txt
for ((w=0; w<WORKERS; w++)); do echo "file 'seg$w.mp4'" >> segs/list.txt; done
ffmpeg -y -v error -f concat -safe 0 -i segs/list.txt -i soundtrack.wav -map 0:v -map 1:a -c:v copy \
  -c:a aac -b:a 320k -movflags +faststart -shortest LightMeUp_EchoBot_1080p.mp4
ffprobe -v error -show_entries format=duration,size -of default=nw=1 LightMeUp_EchoBot_1080p.mp4
