#!/bin/bash

SITES=(
	Kunming
	Oxford
	Moulsford
	Nunhead
	Crossmyloof
#	Vienna
)
# W S E N
BBOXES=(
	102.3459,24.7194,103.0085,25.4706
	-89.5951,34.3219,-89.4596,34.4078
	-1.1827,51.5344,-1.1197,51.5753
	-0.0748,51.4533,-0.0265,51.4788
	-4.3070,55.8187,-4.2522,55.8442
#	16.1444,48.1033,16.6127,48.3594
)

cd data
export OSM_CONFIG_FILE="../osmtags.ini"

for ((i = 0; i < ${#SITES[@]}; i++)); do
	if [ ! -f "${SITES[i]}.db" ]; then
		if [ ! -f "${SITES[i]}.osm" ]; then
			# XAPI: http://overpass.openstreetmap.ru/cgi/xapi_meta?*[bbox=11.5,48.1,11.6,48.2]
			echo "Downloading ${SITES[i]} (${BBOXES[i]})..."
			wget --no-verbose --show-progress --progress=dot:mega -O "${SITES[i]}.osm" "http://overpass.openstreetmap.ru/cgi/xapi_meta?*[bbox=${BBOXES[i]}]"
		fi
		# https://gis.stackexchange.com/questions/15135/using-field-to-rgb-mapping-for-symbology-in-qgis
		# better: https://gis.stackexchange.com/questions/155395/how-to-style-a-vector-layer-in-qgis-using-hexadecimal-color-code-stored-in-attri
		# https://wiki.openstreetmap.org/wiki/Osmosis/TagTransform
#		echo "Converting ${SITES[i]}.osm to spatialite..."
#		ogr2ogr -a_srs 'EPSG:4326' -f "SQLite" -dsco SPATIALITE=YES "${SITES[i]}.db" "${SITES[i]}.osm"
	fi
done

cd ..
