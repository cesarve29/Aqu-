#!/usr/bin/env bash
# Ensambla el video final: escenas + banda sonora + subtitulos.
#   1) ./render_all.sh            (cuadros 3D -> renders/scene_XX.mp4)
#   2) python3 soundtrack.py      (audio/soundtrack.wav)
#   3) python3 voiceover.py       (audio/mezcla.wav: voz en off de ElevenLabs + musica)
#   4) python3 subtitles.py       (audio/subtitulos.ass)
#   5) ./make_video.sh            (la_mascara_del_eco_azul_1080p60.mp4)
set -e
cd "$(dirname "$0")"
python3 subtitles.py
[ -f audio/soundtrack.wav ] || python3 soundtrack.py
[ -f audio/mezcla.wav ] || python3 voiceover.py
(cd renders && ls scene_*.mp4 | sort | sed "s/^/file '/; s/$/'/") > renders/list.txt
ffmpeg -y -loglevel error -f concat -safe 0 -i renders/list.txt -c copy renders/all.mp4
OUT=${OUT:-la_mascara_del_eco_azul_1080p60.mp4}
ffmpeg -y -loglevel error -i renders/all.mp4 -i audio/mezcla.wav \
  -vf "ass=audio/subtitulos.ass" \
  -c:v libx264 -preset slow -crf ${CRF:-21} -pix_fmt yuv420p -r 60 -g 120 \
  -c:a aac -b:a 192k -shortest -movflags +faststart "$OUT"
ls -la "$OUT"
