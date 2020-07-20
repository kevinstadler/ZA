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
  osm2pgsql --database $DBNAME --prefix "" --slim --drop --latlong --style za.style -G --multi-geometry $APPEND "$FILE"
#  osm2pgsql --database $DBNAME --prefix "" --slim --drop --latlong --tag-transform-script style.lua $APPEND "$FILE"
  APPEND='--append'
done

# SLIM: _nodes, _ways, _rels
# for use/manipulation: _points, _lines, _polygons

SCHEMA=$(psql -qAt -d $DBNAME -c "SELECT 1 FROM information_schema.columns WHERE table_name = '_polygon' AND column_name = 'area'")
if [ ! -n "$SCHEMA" ]; then
  echo "First time populating database, adding custom length/area columns"
  psql -d $DBNAME -c "ALTER TABLE _polygon ADD area INTEGER;
			ALTER TABLE _polygon ADD simplified geometry(Geometry,4326);
			ALTER TABLE _polygon ADD simplified2 geometry(Geometry,4326);
			CREATE INDEX _polygon_simplified_idx ON _polygon USING GIST(simplified);
			CREATE INDEX _polygon_simplified2_idx ON _polygon USING GIST(simplified2);
			ALTER TABLE _line ADD length INTEGER;
			ALTER TABLE _line ADD direction SMALLINT NOT NULL DEFAULT 0;
			ALTER TABLE _line ADD flatcap BOOL NOT NULL DEFAULT false;
			ALTER TABLE _line ADD simplified geometry(Geometry,4326);
			CREATE INDEX _line_simplified_idx ON _line USING GIST(simplified);"
fi

## fix oneways by creating new integer column (and reversing UK ways)
echo "Populating direction column..."
psql -d $DBNAME -c "UPDATE _line SET direction = 1 WHERE oneway = '1' OR oneway = 'yes';
			UPDATE _line SET direction = -1 WHERE oneway = '-1';
			UPDATE _line SET direction = -direction WHERE direction != 0 AND ST_Contains(ST_Envelope(ST_GeomFromText('LINESTRING(-12 61, 2 50)', 4326)), way);"

## compute which ways should have flat caps (because they are a dead end on at least one side)
echo "Populating flatcap column..."
CONNECTEDHIGHWAYS="('motorway', 'motorway_link', 'primary', 'primary_link', 'secondary', 'secondary_link', 'tertiary', 'residential', 'unclassified', 'road', 'pedestrian')"
psql -q $DBNAME -c "UPDATE _line SET flatcap = true WHERE flatcap = false AND _line.osm_id NOT IN (SELECT DISTINCT ON (source.osm_id) source.osm_id FROM _line source JOIN _line end1 ON (end1.highway IN $CONNECTEDHIGHWAYS OR source.highway = end1.highway) AND source.osm_id != end1.osm_id AND end1.tunnel IS NULL AND ST_Covers(end1.way, ST_StartPoint(source.way)) JOIN _line end2 ON (end2.highway IN $CONNECTEDHIGHWAYS OR source.highway = end2.highway) AND source.osm_id != end2.osm_id AND end2.tunnel IS NULL AND ST_Covers(end2.way, ST_EndPoint(source.way)) WHERE source.highway IS NOT NULL);"
# QUERY to test:
# SELECT DISTINCT ON (source.osm_id) source.osm_id, end1.osm_id, end2.osm_id, source.flatcap FROM _line source LEFT JOIN _line end1 ON end1.highway IS NOT NULL AND source.osm_id != end1.osm_id AND ST_Covers(end1.way, ST_StartPoint(source.way)) LEFT JOIN _line end2 ON end2.highway IS NOT NULL AND source.osm_id != end2.osm_id AND ST_Covers(end2.way, ST_EndPoint(source.way)) WHERE source.highway IS NOT NULL;

echo "Removing inner rings from leisure = 'golf_course' polygons..."
psql -d $DBNAME -c "UPDATE _polygon SET way = ST_MakePolygon(ST_ExteriorRing(way)) WHERE leisure = 'golf_course' AND ST_GeometryType(way) = 'ST_Polygon';"

echo "Populating length column..."
psql -d $DBNAME -c 'UPDATE _line SET length = ST_Length(way, false) WHERE length IS NULL'
## faster but fails in Serbia: https://gis.stackexchange.com/questions/312910/postgis-st-area-causing-error-when-used-with-use-spheroid-false-setting-succe
echo "Populating area column..."
psql -d $DBNAME -c 'UPDATE _polygon SET area = ST_Area(Geography(way)) WHERE area IS NULL'

# TODO delete polygons below a minimum size
psql -d $DBNAME -c "DELETE FROM _polygon WHERE area < 16"
# TODO delete highway = 'footpath', 'path' ETC which are short and either (a) only connected to other short paths or (b) contained in small (garden?) polygons

TOLERANCE="4.0"
echo "Simplifying polygons (tolerance=${TOLERANCE}m)..."
PROJ="'+proj=stere +lat_0=' || ST_Y(ST_Centroid(way)) || ' +lon_0=' || ST_X(ST_Centroid(way)) || ' +k=1 +datum=WGS84 +units=m +no_defs'"
#PROJ="'+proj=gnom +lat_0=' || ST_Y(ST_Centroid(way)) || ' +lon_0=' || ST_X(ST_Centroid(way)) || ' +datum=WGS84 +units=m +no_defs'"
psql -d $DBNAME -c "UPDATE _polygon SET simplified = ST_Transform(ST_SimplifyPreserveTopology(ST_Transform(way, $PROJ), $TOLERANCE), $PROJ, 4326) WHERE simplified IS NULL;"
#psql -d $DBNAME -c "UPDATE _polygon SET simplified = ST_Transform(ST_SimplifyPreserveTopology(ST_Transform(way, $PROJ), $TOLERANCE), $PROJ, 4326), simplified2 = ST_Transform(ST_SimplifyVW(ST_Transform(way, $PROJ), $TOLERANCE), $PROJ, 4326) WHERE simplified IS NULL;"
echo "Simplifying ways (tolerance=${TOLERANCE}m)..."
psql -d $DBNAME -c "UPDATE _line SET simplified = ST_Transform(ST_SimplifyPreserveTopology(ST_Transform(way, $PROJ), $TOLERANCE), $PROJ, 4326) WHERE simplified IS NULL;"

echo "Removing layer = 0, tunnel = 'no', oneway = 'no', bridge = 'no' tags..."
psql -d $DBNAME -c "UPDATE _line SET layer = NULL WHERE layer = 0;\
		UPDATE _line SET oneway = NULL WHERE oneway = 'no';
		UPDATE _line SET bridge = NULL WHERE bridge = 'no';
		UPDATE _line SET tunnel = NULL WHERE tunnel = 'no';"

echo "Marking any underspecified buildings on amenity (school, hospital,...) grounds as buildings of that type, and removing names of buildings contained in areas of the same name..."
GENERICBUILDING="('yes', 'public', 'roof', 'service')"

AMENITY="('hospital', 'school', 'college', 'university', 'arts_centre', 'bus_station')"
LANDUSE="('depot', 'industrial', 'railway')"
LEISURE="('sports_centre')"
#CONTAINSSPATIALLY="ST_Covers(grounds.way, bldg.way)"
CONTAINSSPATIALLY="ST_Within(ST_Centroid(bldg.way), grounds.way)"
psql -d $DBNAME -c "UPDATE _polygon SET building = NULL WHERE building = 'no';
		UPDATE _polygon SET building = amenity WHERE building in $GENERICBUILDING AND amenity IS NOT NULL;
		UPDATE _polygon SET building = tourism WHERE building in $GENERICBUILDING AND tourism IS NOT NULL;
		UPDATE _polygon SET building = 'commercial' WHERE building IN $GENERICBUILDING AND shop IS NOT NULL;
		UPDATE _polygon bldg SET building = grounds.amenity FROM _polygon grounds WHERE bldg.building IN $GENERICBUILDING AND bldg.leisure IS NULL AND grounds.building IS NULL AND grounds.amenity IN $AMENITY AND $CONTAINSSPATIALLY;
		UPDATE _polygon bldg SET name = NULL FROM _polygon grounds WHERE bldg.building IS NOT NULL AND bldg.name IS NOT NULL AND grounds.building IS NULL AND bldg.name = grounds.name AND (grounds.amenity IN $AMENITY OR grounds.landuse IS NOT NULL) AND $CONTAINSSPATIALLY;
		UPDATE _polygon bldg SET building = grounds.landuse FROM _polygon grounds WHERE bldg.building IN $GENERICBUILDING AND bldg.leisure IS NULL AND grounds.building IS NULL AND grounds.landuse IN $LANDUSE AND $CONTAINSSPATIALLY;
		UPDATE _polygon bldg SET building = grounds.leisure FROM _polygon grounds WHERE bldg.building IN $GENERICBUILDING AND bldg.leisure IS NULL AND grounds.building IS NULL AND grounds.leisure IN $LEISURE AND $CONTAINSSPATIALLY;"

# TODO set amenity-area name to amenity only if it contains no named buildings...
#psql -d "$DBNAME" -c "UPDATE _polygon grounds SET name = amenity FROM _polygon bldg WHERE grounds.name IS NULL AND grounds.amenity IN $AMENITY AND bldg.building IS NOT NULL AND NOT ST_Covers(grounds.way, bldg.way);"
# TODO add name = 'School' for buildings which are NOT on (named) school grounds
#psql -d "$DBNAME" -c "UPDATE _polygon bldg SET name = amenity FROM _polygon grounds WHERE bldg.name IS NULL AND bldg.building IN $AMENITY AND bldg.building = grounds.amenity AND NOT ST_Covers(grounds.way, bldg.way);"

echo "Capitalising names of large train_stations"
psql -d $DBNAME -c "UPDATE _point station SET name = UPPER(station.name) FROM _polygon bldg WHERE bldg.building = 'train_station' AND (station.public_transport = 'station' OR station.railway = 'station') AND bldg.name = station.name AND ST_Within(station.way, bldg.way) AND bldg.area > 10000;"
echo "Removing names of train station areas if they contain a train_station point (of the same name) inside them"
psql -d $DBNAME -c "UPDATE _polygon bldg SET name = NULL FROM _point station WHERE bldg.building = 'train_station' AND (station.public_transport = 'station' OR station.railway = 'station') AND bldg.name = station.name AND ST_Within(station.way, bldg.way)"

echo "Transfering point 'place' tags to co-located non-place residential areas with the same name"
psql -d $DBNAME -c "UPDATE _polygon a SET place = p.place FROM _point p WHERE a.place IS NULL AND a.landuse = 'residential' AND p.place IS NOT NULL AND p.name = a.name AND ST_Intersects(ST_Buffer(geography(p.way), 100), a.way)"
echo "Dropping point 'place's if they are within a 'place'-area with the same name"
psql -d $DBNAME -c "DELETE FROM _point p USING _polygon a WHERE p.place IS NOT NULL AND p.place = a.place AND p.name = a.name AND ST_Intersects(ST_Buffer(geography(p.way), 100), a.way);"

echo "Creating 'places' view"
# OSM urban places: city > borough   >   suburb > quarter   >   neighbourhood > city_block > plot, square
# OSM rural places:    town   >   village       >       hamlet                >              isolated_dwelling, farm, allotments 
# OSM other places: island > islet, square, locality
psql -d $DBNAME -c "CREATE OR REPLACE VIEW places ( osm_id, place, name, way ) AS (SELECT osm_id, place, name, way FROM _polygon WHERE place IS NOT NULL) UNION (SELECT osm_id, place, name, ST_Buffer(geography(way), ('city=>500, town=>300, borough=>300, village=>200, suburb=>200, quarter=>150, neighbourhood=>100, hamlet=>50, city_block=>30, plot=>20, square=>15'::hstore -> place)::INTEGER) FROM _point WHERE place IS NOT NULL AND name IS NOT NULL);"

echo "Remove ; from names"
psql -d $DBNAME -c "UPDATE _polygon SET name = SUBSTRING(name FOR POSITION(';' IN name) - 1) WHERE name IS NOT NULL AND POSITION(';' IN name) > 0;"
psql -d $DBNAME -c "UPDATE _line SET ref = SUBSTRING(ref FOR POSITION(';' IN ref) - 1) WHERE ref IS NOT NULL AND POSITION(';' IN ref) > 0;"
