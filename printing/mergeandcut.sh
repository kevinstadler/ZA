#!/bin/sh
echo "Merging preface and atlas map pages into one file..."
mutool merge -o "$1-merged.pdf" "$1 overview.pdf" "$1.pdf"
./booklet.sh "$1-merged.pdf"
