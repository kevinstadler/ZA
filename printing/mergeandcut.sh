#!/bin/sh
mutool merge -o "$1-merged.pdf" "$1 overview.pdf" "$1.pdf"
./booklet.sh "$1-merged.pdf"
