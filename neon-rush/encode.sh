#!/usr/bin/env bash
# Final edit: upscale the 2.39:1 frames, letterbox into 16:9 1080p, film grain,
# vignette, fades, opening caption, end title card and soundtrack.
#
#   ./encode.sh FRAMES_DIR SOUNDTRACK.wav OUT.mp4 [crf]
set -euo pipefail
FRAMES=${1:-frames}
AUDIO=${2:-soundtrack.wav}
OUT=${3:-neon_rush_1080p.mp4}
CRF=${4:-16}
FONT_B=/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf
FONT_L=/usr/share/fonts/opentype/inter/Inter-ExtraLight.otf
FONT_M=/usr/share/fonts/opentype/inter/InterDisplay-Medium.otf
[ -f "$FONT_L" ] || FONT_L=$FONT_M

MAIN_DUR=62.0   # 1488 frames @ 24 fps
CARD_DUR=3.5
TMP=$(mktemp -d)

# 1) main picture
ffmpeg -y -loglevel error -stats -framerate 24 -start_number 0 -i "$FRAMES/nr_%04d.png" \
  -vf "scale=1920:804:flags=lanczos,
       eq=contrast=1.04:saturation=1.08:gamma=0.98,
       colorbalance=rs=-0.03:bs=0.04:rh=0.03:bh=-0.02,
       vignette=angle=PI/5,
       noise=alls=7:allf=t,
       pad=1920:1080:0:138:black,
       drawtext=fontfile=$FONT_L:text='DISTRITO KAIRO':fontsize=34:fontcolor=white:x=(w-tw)/2:y=870:alpha='if(lt(t,2.2),0,if(lt(t,3.2),t-2.2,if(lt(t,6.2),1,if(lt(t,7.2),7.2-t,0))))',
       drawtext=fontfile=$FONT_L:text='2 0 8 7':fontsize=22:fontcolor=0xff2d8a:x=(w-tw)/2:y=918:alpha='if(lt(t,2.6),0,if(lt(t,3.6),t-2.6,if(lt(t,6.2),1,if(lt(t,7.2),7.2-t,0))))',
       fade=t=in:st=0:d=1.5,
       fade=t=out:st=$(echo "$MAIN_DUR-1.0" | bc):d=1.0,
       format=yuv420p" \
  -c:v libx264 -preset slow -crf "$CRF" -tune film "$TMP/main.mp4"

# 2) end title card
ffmpeg -y -loglevel error -f lavfi -i "color=c=black:s=1920x1080:r=24:d=$CARD_DUR" \
  -vf "drawtext=fontfile=$FONT_B:text='AISTUDIO3D':fontsize=150:fontcolor=0xff1f7a:x=(w-tw)/2:y=(h-th)/2-30:alpha='min(1,t/0.6)',
       drawtext=fontfile=$FONT_L:text='NEON RUSH  ·  ANIMACIÓN PROCEDURAL EN BLENDER 5.3':fontsize=26:fontcolor=0x5fe6ff:x=(w-tw)/2:y=(h/2)+90:alpha='min(1,max(0,(t-0.7)/0.8))',
       gblur=sigma=0:steps=1,
       noise=alls=6:allf=t,
       fade=t=out:st=$(echo "$CARD_DUR-0.8" | bc):d=0.8,format=yuv420p" \
  -c:v libx264 -preset slow -crf "$CRF" -tune film "$TMP/card.mp4"

# 3) concat + audio
printf "file '%s'\nfile '%s'\n" "$TMP/main.mp4" "$TMP/card.mp4" > "$TMP/list.txt"
ffmpeg -y -loglevel error -f concat -safe 0 -i "$TMP/list.txt" -i "$AUDIO" \
  -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k -shortest -movflags +faststart "$OUT"
rm -rf "$TMP"
echo "wrote $OUT"
