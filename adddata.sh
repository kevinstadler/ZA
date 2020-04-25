#!/bin/sh
if [ "$1" == "" ]; then
  echo "No file?"
fi
DBNAME=za
# TODO implement diffs properly? https://ircama.github.io/osm-carto-tutorials/updating-data/ 
for FILE in `ls "$1"`; do
  osm2pgsql --database $DBNAME --prefix "" --slim --latlong --style za.style --append "$FILE"
#  osm2pgsql --database $DBNAME --prefix "" --slim --latlong --style za.style "$FILE"
done
