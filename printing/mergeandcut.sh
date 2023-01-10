#!/bin/sh
echo "Merging preface and atlas map pages into one file..."
mutool merge -o "$1-merged.pdf" "$1 overview.pdf" "$1.pdf"
# should only be called with files in the PARENT directory, because booklet.sh will overwrite stuff
./booklet.sh "$1-merged.pdf"
