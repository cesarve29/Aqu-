#!/usr/bin/env bash
# Final edit: upscale the 2.39:1 frames, letterbox into 16:9 1080p, light grain and vignette,
# fade in from black and a plain fade out at the end (no titles, no end card), plus the sound mix.
#
#   ./encode.sh FRAMES_DIR SOUNDTRACK.wav OUT.mp4 [video_kbps]     (2-pass, default 11000 kbps -> < 100 MB)
set -euo pipefail
FRAMES=${1:-frames}
AUDIO=${2:-soundtrack.wav}
OUT=${3:-bogota_lluvia_1080p.mp4}
KBPS=${4:-11000}
DUR=60.0
TMP=$(mktemp -d)
VF="scale=1920:804:flags=lanczos,
    eq=contrast=1.03:saturation=1.04,
    vignette=angle=PI/5,
    noise=alls=5:allf=t,
    pad=1920:1080:0:138:black,
    fade=t=in:st=0:d=1.5,
    fade=t=out:st=$(echo "$DUR-2.5" | bc):d=2.5,
    format=yuv420p"
for pass in 1 2; do
  if [ $pass = 1 ]; then OUTP=(-an -f null /dev/null); else OUTP=(-map 0:v -map 1:a -c:a aac -b:a 192k -shortest -movflags +faststart "$OUT"); fi
  ffmpeg -y -loglevel error -stats -framerate 24 -start_number 0 -i "$FRAMES/bg_%04d.png" -i "$AUDIO" \
    -vf "$VF" -c:v libx264 -preset slow -tune film -b:v ${KBPS}k -pass $pass -passlogfile "$TMP/2p" "${OUTP[@]}"
done
rm -rf "$TMP"
echo "wrote $OUT"
