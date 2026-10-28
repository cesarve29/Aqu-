#!/usr/bin/env bash
# Renderiza el video completo en segmentos paralelos, sintetiza la banda sonora y lo une todo.
#   ./build.sh            (FPS=24 WORKERS=4 por defecto)
set -euo pipefail
cd "$(dirname "$0")"
FPS=${FPS:-24}
WORKERS=${WORKERS:-4}
SEG=${SEG:-28}
DUR=335
mkdir -p segments
[ -d node_modules/three ] || npm install --no-audit --no-fund
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
ls segments/seg_*.mp4 | sort | sed "s/^/file '/; s/$/'/; s#file 'segments/#file '#" > segments/list.txt
ffmpeg -y -loglevel error -f concat -safe 0 -i segments/list.txt -i soundtrack.wav \
  -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart blockcraft_1080p.mp4
ls -la blockcraft_1080p.mp4
