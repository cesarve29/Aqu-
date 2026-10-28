#!/usr/bin/env bash
# Timelapse completo: render paralelo por segmentos a 60 fps + banda sonora + montaje.
set -euo pipefail
cd "$(dirname "$0")"
FPS=${FPS:-60}
WORKERS=${WORKERS:-4}
SEG=${SEG:-15}
DUR=180
mkdir -p segments
[ -d ../voxel-video/node_modules/three ] || (cd ../voxel-video && npm install --no-audit --no-fund)
node render.cjs --events
python3 audio.py &
AUDIO=$!
jobs=()
for ((s = 0; s < DUR; s += SEG)); do
  e=$((s + SEG > DUR ? DUR : s + SEG))
  f=$(printf "segments/seg_%03d.mp4" "$s")
  [ -s "$f.ok" ] || jobs+=("$s $e $f")
done
printf '%s\n' "${jobs[@]}" | xargs -P "$WORKERS" -L 1 bash -c 'node render.cjs --fps '"$FPS"' --from $0 --to $1 --out $2 > $2.log 2>&1 && echo ok > $2.ok'
wait $AUDIO
ls segments/seg_*.mp4 | sort | sed "s#^segments/#file '#; s/$/'/" > segments/list.txt
ffmpeg -y -loglevel error -f concat -safe 0 -i segments/list.txt -i soundtrack.wav \
  -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart timelapse_ciudad_1080p60.mp4
ls -la timelapse_ciudad_1080p60.mp4
