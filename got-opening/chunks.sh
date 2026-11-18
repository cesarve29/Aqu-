#!/bin/bash
# chunks.sh PREFIX FROM TO STEP FPS W H [CRF] : renderiza por tramos reanudables
cd "$(dirname "$0")"
P=$1; A=$2; B=$3; S=$4; FPS=$5; W=$6; H=$7; CRF=${8:-17}
t=$A
while (( $(echo "$t < $B" | bc -l) )); do
  e=$(echo "if ($t + $S > $B) $B else $t + $S" | bc -l)
  f=out/${P}_$(printf "%07.2f" $t).mp4
  if [ ! -s "$f" ]; then
    node render.mjs --from $t --to $e --fps $FPS --w $W --h $H --crf $CRF --out $f 2>&1 | grep -v "GPU stall" | grep -E "wrote|error|Error" 
  fi
  t=$e
done
echo DONE $P
