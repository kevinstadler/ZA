#!/bin/sh
# https://gis.stackexchange.com/questions/15135/using-field-to-rgb-mapping-for-symbology-in-qgis
# better: https://gis.stackexchange.com/questions/155395/how-to-style-a-vector-layer-in-qgis-using-hexadecimal-color-code-stored-in-attri
# https://wiki.openstreetmap.org/wiki/Osmosis/TagTransform
if [ ! -f "$1" ]; then
	exit 1
fi
#osmosis --read-xml file="$1" --tag-transform file=transform.xml --write-xml file=data.osm
export OSM_CONFIG_FILE=othertags.ini  
ogr2ogr -f "SQLite" -dsco SPATIALITE=YES data.db "$1"
