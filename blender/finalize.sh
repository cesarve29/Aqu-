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
  -filter_complex "[0:v]scale=1920:804:flags=lanczos,vignette=PI/5,noise=alls=5:allf=t+u,pad=1920:1080:0:138:black,fade=t=in:st=0:d=1.2,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='O R I G E N':fontcolor=white:fontsize=96:x=(w-text_w)/2:y=(h-text_h)/2+40:alpha='if(lt(t,56.6),0,min(1,(t-56.6)/1.2))':shadowcolor=0x66CCFF@0.6:shadowx=0:shadowy=0,fade=t=out:st=58.6:d=1.4,${SUB}[v]" \
  -map "[v]" -map 1:a -map 2:s -c:v libx264 -crf 17 -preset slow -pix_fmt yuv420p \
  -c:a aac -b:a 192k -c:s mov_text -metadata:s:s:0 language=spa -movflags +faststart -t 60 \
  final/ORIGEN_1080p.mp4
rm -f final/_video.mp4 final/lista.txt
echo "OK final/ORIGEN_1080p.mp4"
