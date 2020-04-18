#!/bin/sh

# up to 0.5x0.5 degrees on the overpass api according to https://wiki.openstreetmap.org/wiki/Downloading_data, but really 50.000 node limit...
#wget -O kunming.osm "https://api.openstreetmap.org/api/0.6/map?bbox=102.5814,24.9406,102.8808,25.1434"
# XAPI: http://overpass.openstreetmap.ru/cgi/xapi_meta?*[bbox=11.5,48.1,11.6,48.2]

wget -O kunming.osm "http://overpass.openstreetmap.ru/cgi/xapi_meta?*[bbox=102.5814,24.9406,102.8808,25.1434]"

