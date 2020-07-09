#!/bin/sh
if [ -z "$1" ]; then
  echo "No file? Adding default data sources..."
  ./adddata.sh data/Oxford.osm data/Kunming.osm data/Moulsford.osm data/Glasgow.osm data/Nunhead.osm data/Edinburgh.osm
  exit 0
fi
DBNAME=za

## if there is really just one file argument, assume we just append
#if [ ! "$2" ]; then
DATA=$(psql -qAt -d $DBNAME -c "SELECT 1 FROM information_schema.tables WHERE table_name = '_nodes'")
if [ -n "$DATA" ]; then
  APPEND='--append'
fi

# TODO implement diffs properly? https://ircama.github.io/osm-carto-tutorials/updating-data/ 
for FILE in "$@"; do
  if [ $APPEND ]; then
    echo "Appending $FILE"
  else
    echo "Creating new database from file $FILE"
  fi
  osm2pgsql --database $DBNAME --prefix "" --slim --latlong --style za.style -G --multi-geometry $APPEND "$FILE"
#  osm2pgsql --database $DBNAME --prefix "" --slim --latlong --tag-transform-script style.lua $APPEND "$FILE"
  APPEND='--append'
done

# SLIM: _nodes, _ways, _rels
# for use/manipulation: _points, _lines, _polygons

SCHEMA=$(psql -qAt -d $DBNAME -c "SELECT 1 FROM information_schema.columns WHERE table_name = '_polygon' AND column_name = 'area'")
if [ ! -n "$SCHEMA" ]; then
  echo "First time populating database, adding custom length/area columns"
  psql -d $DBNAME -c "ALTER TABLE _polygon ADD area INTEGER;
			ALTER TABLE _line ADD length INTEGER;
			ALTER TABLE _line ADD direction SMALLINT NOT NULL DEFAULT 0;
			ALTER TABLE _line ADD flatcap BOOL NOT NULL DEFAULT false;
			ALTER TABLE _polygon ADD simplified geometry(Geometry,4326);"
# CREATE INDEX _polygon_simplified_idx ON _polygon USING GIST(simplified)
fi

## fix oneways by creating new integer column (and reversing UK ways)
#UPDATE _line SET oneway = NULL WHERE oneway = 'no';\
#		UPDATE _line SET oneway = '1' WHERE oneway = 'yes';\
echo "Populating direction column..."
psql -d $DBNAME -c "UPDATE _line SET direction = 1 WHERE oneway = '1' OR oneway = 'yes';
			UPDATE _line SET direction = -1 WHERE oneway = '-1';
			UPDATE _line SET direction = -direction WHERE direction != 0 AND ST_Contains(ST_Envelope(ST_GeomFromText('LINESTRING(-12 61, 2 50)', 4326)), way);"
# FIXME direction is unnecessarily reversed on every later data addition, gotta prevent this somehow...

## compute which ways should have flat caps (because they are a dead end on at least one side)
echo "Populating flatcap column..."
CONNECTEDHIGHWAYS="('motorway', 'motorway_link', 'primary', 'primary_link', 'secondary', 'secondary_link', 'tertiary', 'residential', 'unclassified', 'road')"
psql -q $DBNAME -c "UPDATE _line SET flatcap = true WHERE flatcap = false AND _line.osm_id NOT IN (SELECT DISTINCT ON (source.osm_id) source.osm_id FROM _line source JOIN _line end1 ON (end1.highway IN $CONNECTEDHIGHWAYS OR source.highway = end1.highway) AND source.osm_id != end1.osm_id AND end1.tunnel IS NULL AND ST_Covers(end1.way, ST_StartPoint(source.way)) JOIN _line end2 ON (end2.highway IN $CONNECTEDHIGHWAYS OR source.highway = end2.highway) AND source.osm_id != end2.osm_id AND end2.tunnel IS NULL AND ST_Covers(end2.way, ST_EndPoint(source.way)) WHERE source.highway IS NOT NULL);"
# QUERY to test:
# SELECT DISTINCT ON (source.osm_id) source.osm_id, end1.osm_id, end2.osm_id, source.flatcap FROM _line source LEFT JOIN _line end1 ON end1.highway IS NOT NULL AND source.osm_id != end1.osm_id AND ST_Covers(end1.way, ST_StartPoint(source.way)) LEFT JOIN _line end2 ON end2.highway IS NOT NULL AND source.osm_id != end2.osm_id AND ST_Covers(end2.way, ST_EndPoint(source.way)) WHERE source.highway IS NOT NULL;

# TODO simplify polygons and ways using ST_Simplify
echo "Simplifying polygons..."
#psql -d $DBNAME -c 'UPDATE _polygon SET simplified = ST_Simplify(way, .000003, true) WHERE simplified IS NULL;'
TOLERANCE="4.0"
PROJ="'+proj=stere +lat_0=' || ST_Y(ST_Centroid(way)) || ' +lon_0=' || ST_X(ST_Centroid(way)) || ' +k=1 +datum=WGS84 +units=m +no_defs'"
#PROJ="'+proj=gnom +lat_0=' || ST_Y(ST_Centroid(way)) || ' +lon_0=' || ST_X(ST_Centroid(way)) || ' +datum=WGS84 +units=m +no_defs'"
psql -d $DBNAME -c "UPDATE _polygon SET simplified = ST_Transform(ST_SimplifyPreserveTopology(ST_Transform(way, $PROJ), $TOLERANCE), $PROJ, 4326);"
psql -d $DBNAME -c "UPDATE _line SET simplified = ST_Transform(ST_SimplifyPreserveTopology(ST_Transform(way, $PROJ), $TOLERANCE), $PROJ, 4326);"


echo "Populating length column..."
psql -d $DBNAME -c 'UPDATE _line SET length = ST_Length(way, false) WHERE length IS NULL'
## faster but fails in Serbia: https://gis.stackexchange.com/questions/312910/postgis-st-area-causing-error-when-used-with-use-spheroid-false-setting-succe
echo "Populating area column..."
psql -d $DBNAME -c 'UPDATE _polygon SET area = ST_Area(Geography(way)) WHERE area IS NULL'

# TODO delete polygons below a minimum size

echo "Removing layer = 0 and tunnel = 'no' tags..."
psql -d $DBNAME -c "UPDATE _line SET layer = NULL WHERE layer = 0;\
		UPDATE _line SET tunnel = NULL WHERE tunnel = 'no';"

echo "Marking any underspecified buildings on amenity (school, hospital,...) grounds as buildings of that type..."
GENERICBUILDING="('yes', 'public')"
AMENITY="('hospital', 'school', 'college', 'university', 'arts_centre')"
psql -d $DBNAME -c "UPDATE _polygon SET building = NULL WHERE building = 'no';
		UPDATE _polygon bldg SET building = grounds.amenity FROM _polygon grounds WHERE bldg.building IN $GENERICBUILDING AND bldg.leisure IS NULL AND grounds.building IS NULL AND grounds.amenity IN $AMENITY AND ST_Covers(grounds.way, bldg.way);"

echo "Dropping point 'place's if they are within a 'place'-area with the same name"
psql -d $DBNAME -c "DELETE FROM _point p USING _polygon a WHERE p.place IS NOT NULL AND p.place = a.place AND p.name = a.name AND ST_Covers(a.way, p.way)"

# OSM urban places: city > borough > suburb > quarter > neighbourhood > city_block > plot
# OSM rural places:    town > village > hamlet > isolated_dwelling, farm, allotments 
# OSM other places: island > islet, square, locality
psql -d $DBNAME -c "CREATE OR REPLACE VIEW places ( osm_id, place, name, way ) AS (SELECT osm_id, place, name, way FROM _polygon WHERE place IS NOT NULL) UNION (SELECT osm_id, place, name, ST_Buffer(geography(way), ('city=>500, town=>300, borough=>300, suburb=>300, village=>100, quarter=>150, neighbourhood=>100, hamlet=>50, city_block=>30, plot=>20, square=>15'::hstore -> place)::INTEGER) FROM _point WHERE place IS NOT NULL AND name IS NOT NULL);"
