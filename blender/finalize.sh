#!/bin/bash
# Une los tramos, aplica el acabado (viñeta, grano, franjas 2.39:1 -> 1920x1080),
# añade música + voz y subtítulos en español (quemados y como pista aparte).
set -eu
cd "$(dirname "$0")"
mkdir -p final
ls chunks/s*_*.mp4 | sort | sed "s/^/file '..\//; s/$/'/" > final/lista.txt
ffmpeg -y -loglevel error -f concat -safe 0 -i final/lista.txt -c copy final/_video.mp4
SUB="subtitles=audio/subtitulos_es.srt:force_style='FontName=DejaVu Sans,FontSize=13,PrimaryColour=&H00F0F0F0,OutlineColour=&H00000000,Outline=1,Shadow=0,MarginV=10'"
ffmpeg -y -loglevel error -i final/_video.mp4 -i audio/banda_sonora.wav -i audio/subtitulos_es.srt \
  -filter_complex "[0:v]vignette=PI/5,noise=alls=5:allf=t+u,pad=1920:1080:0:138:black,fade=t=in:st=0:d=1.2,fade=t=out:st=58.6:d=1.4,${SUB}[v]" \
  -map "[v]" -map 1:a -map 2:s -c:v libx264 -crf 17 -preset slow -pix_fmt yuv420p \
  -c:a aac -b:a 192k -c:s mov_text -metadata:s:s:0 language=spa -movflags +faststart -shortest \
  final/ORIGEN_1080p.mp4
rm -f final/_video.mp4 final/lista.txt
echo "OK final/ORIGEN_1080p.mp4"
