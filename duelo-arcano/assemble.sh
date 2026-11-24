#!/bin/bash
# Join the 12 rendered segments (stream copy) and mux the ElevenLabs mix.
set -e
cd "$(dirname "$0")"
python3 audio/mix.py
(cd render_segments && ls seg_*.mp4 | sort | sed "s/^/file '/; s/$/'/") > render_segments/list.txt
ffmpeg -y -hide_banner -loglevel error -f concat -safe 0 -i render_segments/list.txt -i audio/duelo_mix.wav \
  -map 0:v -map 1:a -c:v copy -c:a aac -b:a 320k -ar 48000 -shortest -movflags +faststart duelo_arcano_1080p.mp4
ffprobe -v error -show_entries format=duration,size -of default=nw=1 duelo_arcano_1080p.mp4
