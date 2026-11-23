#!/bin/bash
# Final render: 12 blocks of 120 frames. Each block -> PNG frames -> H.264 segment -> git push.
# Resumable: existing frames and segments are skipped.
cd "$(dirname "$0")"
B=/opt/blender-dl/blender-5.3.0-linux-x64/blender
mkdir -p frames render_segments
for blk in $(seq 0 11); do
  s=$((blk*120+1)); e=$((s+119)); seg=$(printf "render_segments/seg_%02d.mp4" $blk)
  [ -f "$seg" ] && continue
  for attempt in 1 2 3; do
    $B -b duelo.blend -P scene/render_frames.py -- --range $s $e --out frames --skip-existing >> render.log 2>&1
    n=$(ls frames/f*.png 2>/dev/null | awk -F'f' '{print $NF}' | sed 's/.png//' | awk -v s=$s -v e=$e '$1+0>=s && $1+0<=e' | wc -l)
    [ "$n" -eq 120 ] && break
    echo "block $blk incomplete ($n/120), retry $attempt" >> render.log
  done
  ffmpeg -y -hide_banner -loglevel error -framerate 24 -start_number $s -i frames/f%04d.png -frames:v 120 \
    -c:v libx264 -preset slow -crf 16 -tune film -pix_fmt yuv420p -profile:v high -g 48 -keyint_min 24 \
    -sc_threshold 0 -x264-params open-gop=0 -an "$seg"
  echo "SEGMENT $blk done $(date -u +%H:%M)" >> render.log
  ( cd .. && git add "duelo-arcano/$seg" && git commit -q -m "Render segment $blk of 12 (frames $s-$e)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01J5NsSawYeHXi3rWXbkpacm" && \
    for i in 1 2 3 4; do git push -q origin ccr-79829758-gerdp9 && break || sleep $((2**i*5)); done ) >> render.log 2>&1
done
echo "ALL DONE $(date -u +%H:%M)" >> render.log
