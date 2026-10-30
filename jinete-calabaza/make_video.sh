#!/usr/bin/env bash
# Ensambla el video final: escenas + mezcla de audio + subtitulos.
#   1) ./render_all.sh            (cuadros 3D -> renders/scene_XX.mp4)
#   2) python3 mix.py             (audio/mezcla.wav: musica, efectos y voz de ElevenLabs)
#   3) python3 subtitles.py       (audio/subtitulos.ass)
#   4) ./make_video.sh            (el_jinete_de_la_calabaza_llameante_1080p60.mp4)
# Uso parcial (adelanto): ./make_video.sh 6   -> solo las primeras 6 escenas
set -e
cd "$(dirname "$0")"
[ -f audio/mezcla.wav ] || python3 mix.py
python3 subtitles.py
N=${1:-26}
(cd renders && ls scene_*.mp4 | grep -v tmp | sort | head -n $N | sed "s/^/file '/; s/$/'/") > renders/list.txt
ffmpeg -y -loglevel error -f concat -safe 0 -i renders/list.txt -c copy renders/all.mp4
OUT=${OUT:-el_jinete_de_la_calabaza_llameante_1080p60.mp4}
ffmpeg -y -loglevel error -i renders/all.mp4 -i audio/mezcla.wav \
  -vf "ass=audio/subtitulos.ass" \
  -c:v libx264 -preset ${PRESET:-slow} -crf ${CRF:-21} -pix_fmt yuv420p -r 60 -g 120 \
  -c:a aac -b:a 192k -shortest -movflags +faststart "$OUT"
ls -la "$OUT"
