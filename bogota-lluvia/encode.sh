#!/usr/bin/env bash
# Final edit: upscale the 2.39:1 frames, letterbox into 16:9 1080p, light grain and vignette,
# opening title (COLOMBIA in the flag colours), fade in from black, plain fade out (no end card), sound mix.
#
#   ./encode.sh FRAMES_DIR SOUNDTRACK.wav OUT.mp4 [video_kbps]     (2-pass, default 11000 kbps -> < 100 MB)
set -euo pipefail
FRAMES=${1:-frames}
AUDIO=${2:-soundtrack.wav}
OUT=${3:-bogota_lluvia_1080p.mp4}
KBPS=${4:-11000}
TITLE=$(dirname "$0")/title.png
[ -f "$TITLE" ] || python3 "$(dirname "$0")/make_title.py" "$TITLE"
DUR=60.0
TMP=$(mktemp -d)
VF="scale=1920:804:flags=lanczos,
    eq=contrast=1.03:saturation=1.04,
    vignette=angle=PI/5,
    noise=alls=5:allf=t,
    pad=1920:1080:0:138:black[bg];
    [2:v]format=rgba,fade=t=in:st=1.2:d=1.3:alpha=1,fade=t=out:st=6.4:d=1.4:alpha=1[tt];
    [bg][tt]overlay=0:0:shortest=0:eof_action=pass,
    fade=t=in:st=0:d=1.5,
    fade=t=out:st=$(echo "$DUR-2.5" | bc):d=2.5,
    format=yuv420p"
for pass in 1 2; do
  if [ $pass = 1 ]; then OUTP=(-map "[v]" -an -f null /dev/null); else OUTP=(-map "[v]" -map 1:a -c:a aac -b:a 192k -shortest -movflags +faststart "$OUT"); fi
  ffmpeg -y -loglevel error -stats -framerate 24 -start_number 0 -i "$FRAMES/bg_%04d.png" -i "$AUDIO" -loop 1 -t 8 -framerate 24 -i "$TITLE" \
    -filter_complex "[0:v]$VF[v]" -c:v libx264 -preset slow -tune film -b:v ${KBPS}k -pass $pass -passlogfile "$TMP/2p" "${OUTP[@]}"
done
rm -rf "$TMP"
echo "wrote $OUT"
