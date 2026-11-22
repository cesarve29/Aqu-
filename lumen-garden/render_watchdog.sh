#!/usr/bin/env bash
# Keeps the final render going until every frame exists; resumes after crashes.
#   nohup ./render_watchdog.sh > render.log 2>&1 &
cd "$(dirname "$0")"
TOTAL=1440
mkdir -p frames
while true; do
  done_frames=$(find frames -name 'lg_*.png' -size +0 | wc -l)
  if [ "$done_frames" -ge "$TOTAL" ]; then
    echo "ALL FRAMES DONE $(date)"
    exit 0
  fi
  # remove zero-byte placeholders left by an interrupted run
  find frames -name 'lg_*.png' -size 0 -delete
  echo "starting blender at $(date), $done_frames/$TOTAL done"
  blender -b lumen_garden.blend -P render_final.py -a
  echo "blender exited with $? at $(date)"
  sleep 5
done
