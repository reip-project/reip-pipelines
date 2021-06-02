#!/bin/bash


DURATION=90
SIZES=(2 60 120 240 480 960 1080 1200)
#SIZES=(2 60)

ALL_KINDS=("waggle" "ray" "reip")
KINDS=("${@:-${ALL_KINDS[@]}}")

SLEEP=30

echo 'sizes:' "${SIZES[@]}"
echo 'kinds:' "${KINDS[@]}"

for s in ${SIZES[@]}; do
    for kind in ${KINDS[@]}; do
        name="${kind}-${s}x${s}"
        python benchmarks.py run "$kind" --size "[$s,$s]" --name "$name" --duration "$DURATION"  2>&1 | tee "$name".out

	echo "sleeping for $SLEEP to let things breathe and plasma to gc hopefully !!"
        sleep "$SLEEP"
    done
done

