#!/usr/local/bin/python3

import argparse
import psycopg2
import os

# small cutouts:
#./adddata.py --bbox 102.66 25.033 102.73 25.085 -- data/Kunming.osm
#./adddata.py --bbox -96.013 36.095 -95.95 36.167 -- data/Tulsa.osm
#./adddata.py --bbox -3.2315 55.9268 -3.1548 55.9582 -- data/Edinburgh.osm

parser = argparse.ArgumentParser(description='Add (and post-process) data to an OSM PostGIS database')
parser.add_argument('--db', default='za')
parser.add_argument('--style', default='za.style')
parser.add_argument('--simplify', type=float, default=4.0)
parser.add_argument('--bbox', nargs='*', help='bounding box in "minlon minlat maxlon maxlat" (WSEN) order (provide four bbox arguments for every osmfile)')
parser.add_argument('osmfile', nargs='*', default=['data/Kunming.osm'])

args = parser.parse_args()

try:
  conn = psycopg2.connect(host="localhost", database=args.db)
  cur = conn.cursor()

  def execute(text, cmd):
    print(text)
    cur.execute(cmd)
    print(f"Affected rows: {cur.rowcount}")
    conn.commit()

  cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name = '_point'")
  append = '' if cur.fetchone() == None else '--append'

  cmd = f"osm2pgsql --database {args.db} --prefix '' --slim --latlong --style {args.style} --multi-geometry {append} "
  # --append can only be used with slim mode (so don't --drop!)

  if args.bbox == None:
    # add all at once
    os.system(cmd + ' '.join(args.osmfile))
  else:
    # add each individually
    bboxes = [','.join(map(str, args.bbox[i:i + 4])) for i in range(0, len(args.bbox), 4)]
    for (file, bbox) in zip(args.osmfile, bboxes):
      print(f"Adding {file} ({bbox})")
      print(os.system(cmd + f'--bbox "{bbox}" {file}'))

  cur.execute("SELECT 1 FROM information_schema.columns WHERE table_name = '_polygon' AND column_name = 'area'")
  schema = cur.fetchone()
  if schema == None:
    print("First time populating database, adding custom length/area columns")
    cur.execute("""ALTER TABLE _polygon ADD area INTEGER;
      ALTER TABLE _polygon ADD simplified geometry(Geometry,4326);
      ALTER TABLE _polygon ADD simplified2 geometry(Geometry,4326);
      CREATE INDEX _polygon_simplified_idx ON _polygon USING GIST(simplified);
      CREATE INDEX _polygon_simplified2_idx ON _polygon USING GIST(simplified2);
      ALTER TABLE _line ADD length INTEGER;
      ALTER TABLE _line ADD direction SMALLINT NOT NULL DEFAULT 0;
      ALTER TABLE _line ADD flatcap BOOL NOT NULL DEFAULT false;
      ALTER TABLE _line ADD simplified geometry(Geometry,4326);
      CREATE INDEX _line_simplified_idx ON _line USING GIST(simplified);""")
    conn.commit()

  # OSM urban places: city > borough   >   suburb > quarter   >   neighbourhood > city_block > plot, square
  # OSM rural places:    town   >   village       >       hamlet                >              isolated_dwelling, farm, allotments 
  # OSM other places: island > islet, square, locality
  execute("Creating 'places' view",
    "CREATE OR REPLACE VIEW places ( osm_id, place, name, way ) AS (SELECT osm_id, place, name, way FROM _polygon WHERE place IS NOT NULL) UNION (SELECT osm_id, place, name, ST_Buffer(geography(way), ('city=>500, town=>300, borough=>300, village=>200, suburb=>200, quarter=>150, neighbourhood=>100, hamlet=>50, city_block=>30, plot=>20, square=>15'::hstore -> place)::INTEGER) FROM _point WHERE place IS NOT NULL AND name IS NOT NULL);")

  # POSTPROCESSING

  execute("Populating direction column...",
    """UPDATE _line SET direction = 1 WHERE oneway = '1' OR oneway = 'yes';
       UPDATE _line SET direction = -1 WHERE oneway = '-1';
       UPDATE _line SET direction = -direction WHERE direction != 0 AND ST_Contains(ST_Envelope(ST_GeomFromText('LINESTRING(-12 61, 2 50)', 4326)), way);""")

  ## compute which ways should have flat caps (because they are a dead end on at least one side)
  connectedhighways = "('motorway', 'motorway_link', 'primary', 'primary_link', 'secondary', 'secondary_link', 'tertiary', 'residential', 'unclassified', 'road', 'pedestrian')"
  execute("Populating flatcap column...",
    f"UPDATE _line SET flatcap = true WHERE flatcap = false AND _line.osm_id NOT IN (SELECT DISTINCT ON (source.osm_id) source.osm_id FROM _line source JOIN _line end1 ON (end1.highway IN {connectedhighways} OR source.highway = end1.highway) AND source.osm_id != end1.osm_id AND end1.tunnel IS NULL AND ST_Covers(end1.way, ST_StartPoint(source.way)) JOIN _line end2 ON (end2.highway IN {connectedhighways} OR source.highway = end2.highway) AND source.osm_id != end2.osm_id AND end2.tunnel IS NULL AND ST_Covers(end2.way, ST_EndPoint(source.way)) WHERE source.highway IS NOT NULL);")
  # QUERY to test:
  # SELECT DISTINCT ON (source.osm_id) source.osm_id, end1.osm_id, end2.osm_id, source.flatcap FROM _line source LEFT JOIN _line end1 ON end1.highway IS NOT NULL AND source.osm_id != end1.osm_id AND ST_Covers(end1.way, ST_StartPoint(source.way)) LEFT JOIN _line end2 ON end2.highway IS NOT NULL AND source.osm_id != end2.osm_id AND ST_Covers(end2.way, ST_EndPoint(source.way)) WHERE source.highway IS NOT NULL;

  execute("Removing inner rings from leisure = 'golf_course' polygons...",
    "UPDATE _polygon SET way = ST_MakePolygon(ST_ExteriorRing(way)) WHERE leisure = 'golf_course' AND ST_GeometryType(way) = 'ST_Polygon';")

  execute("Populating length column...",
    'UPDATE _line SET length = ST_Length(way, false) WHERE length IS NULL')
  ## faster but fails in Serbia: https://gis.stackexchange.com/questions/312910/postgis-st-area-causing-error-when-used-with-use-spheroid-false-setting-succe
  execute("Populating area column...",
    'UPDATE _polygon SET area = ST_Area(Geography(way)) WHERE area IS NULL')

  execute("Delete polygons below a minimum size", "DELETE FROM _polygon WHERE area < 16")
  # TODO delete highway = 'footpath', 'path' ETC which are short and either (a) only connected to other short paths or (b) contained in small (garden?) polygons

  proj = "'+proj=stere +lat_0=' || ST_Y(ST_Centroid(way)) || ' +lon_0=' || ST_X(ST_Centroid(way)) || ' +k=1 +datum=WGS84 +units=m +no_defs'"
  #proj = "'+proj=gnom +lat_0=' || ST_Y(ST_Centroid(way)) || ' +lon_0=' || ST_X(ST_Centroid(way)) || ' +datum=WGS84 +units=m +no_defs'"
  execute(f"Simplifying polygons (tolerance={args.simplify}m)...",
    f"UPDATE _polygon SET simplified = ST_Transform(ST_SimplifyPreserveTopology(ST_Transform(way, {proj}), {args.simplify}), {proj}, 4326) WHERE simplified IS NULL;")
#  cur.execute("UPDATE _polygon SET simplified = ST_Transform(ST_SimplifyPreserveTopology(ST_Transform(way, $PROJ), $TOLERANCE), $PROJ, 4326), simplified2 = ST_Transform(ST_SimplifyVW(ST_Transform(way, $PROJ), $TOLERANCE), $PROJ, 4326) WHERE simplified IS NULL;")
  execute(f"Simplifying ways (tolerance={args.simplify}m)...",
    f"UPDATE _line SET simplified = ST_Transform(ST_SimplifyPreserveTopology(ST_Transform(way, {proj}), {args.simplify}), {proj}, 4326) WHERE simplified IS NULL;")

  execute("Removing layer = 0, tunnel = 'no', oneway = 'no', bridge = 'no' tags...",
    """UPDATE _line SET layer = NULL WHERE layer = 0;
    UPDATE _line SET oneway = NULL WHERE oneway = 'no';
    UPDATE _line SET bridge = NULL WHERE bridge = 'no';
    UPDATE _line SET tunnel = NULL WHERE tunnel = 'no';""")

  genericbuilding = "('yes', 'public', 'roof', 'service')"
  AMENITY = "('hospital', 'school', 'college', 'university', 'arts_centre', 'bus_station')"
  LANDUSE = "('depot', 'industrial', 'railway')"
  LEISURE = "('sports_centre')"
  #containsspatially = "ST_Covers(grounds.way, bldg.way)"
  containsspatially = "ST_Within(ST_Centroid(bldg.way), grounds.way)"
  execute("Marking any underspecified buildings on amenity (school, hospital,...) grounds as buildings of that type, and removing names of buildings contained in areas of the same name...",
    f"""UPDATE _polygon SET building = NULL WHERE building = 'no';
    UPDATE _polygon SET building = amenity WHERE building in {genericbuilding} AND amenity IS NOT NULL;
    UPDATE _polygon SET building = tourism WHERE building in {genericbuilding} AND tourism IS NOT NULL;
    UPDATE _polygon SET building = 'commercial' WHERE building IN {genericbuilding} AND shop IS NOT NULL;
    UPDATE _polygon bldg SET building = grounds.amenity FROM _polygon grounds WHERE bldg.building IN {genericbuilding} AND bldg.leisure IS NULL AND grounds.building IS NULL AND grounds.amenity IN {AMENITY} AND {containsspatially};
    UPDATE _polygon bldg SET name = NULL FROM _polygon grounds WHERE bldg.building IS NOT NULL AND bldg.name IS NOT NULL AND grounds.building IS NULL AND bldg.name = grounds.name AND (grounds.amenity IN {AMENITY} OR grounds.landuse IS NOT NULL) AND {containsspatially};
    UPDATE _polygon bldg SET building = grounds.landuse FROM _polygon grounds WHERE bldg.building IN {genericbuilding} AND bldg.leisure IS NULL AND grounds.building IS NULL AND grounds.landuse IN {LANDUSE} AND {containsspatially};
    UPDATE _polygon bldg SET building = grounds.leisure FROM _polygon grounds WHERE bldg.building IN {genericbuilding} AND bldg.leisure IS NULL AND grounds.building IS NULL AND grounds.leisure IN {LEISURE} AND {containsspatially};""")

  # TODO set amenity-area name to amenity only if it contains no named buildings...
  #psql -d "$DBNAME" -c "UPDATE _polygon grounds SET name = amenity FROM _polygon bldg WHERE grounds.name IS NULL AND grounds.amenity IN $AMENITY AND bldg.building IS NOT NULL AND NOT ST_Covers(grounds.way, bldg.way);"
  # TODO add name = 'School' for buildings which are NOT on (named) school grounds
  #psql -d "$DBNAME" -c "UPDATE _polygon bldg SET name = amenity FROM _polygon grounds WHERE bldg.name IS NULL AND bldg.building IN $AMENITY AND bldg.building = grounds.amenity AND NOT ST_Covers(grounds.way, bldg.way);"

  execute("Capitalising names of large train_stations",
    "UPDATE _point station SET name = UPPER(station.name) FROM _polygon bldg WHERE bldg.building = 'train_station' AND (station.public_transport = 'station' OR station.railway = 'station') AND bldg.name = station.name AND ST_Within(station.way, bldg.way) AND bldg.area > 10000;")
  execute("Removing names of train station areas if they contain a train_station point (of the same name) inside them",
    "UPDATE _polygon bldg SET name = NULL FROM _point station WHERE bldg.building = 'train_station' AND (station.public_transport = 'station' OR station.railway = 'station') AND bldg.name = station.name AND ST_Within(station.way, bldg.way)")

  execute("Transfering point 'place' tags to co-located non-place residential areas with the same name",
    "UPDATE _polygon a SET place = p.place FROM _point p WHERE a.place IS NULL AND a.landuse = 'residential' AND p.place IS NOT NULL AND p.name = a.name AND ST_Intersects(ST_Buffer(geography(p.way), 100), a.way)")
  execute("Dropping point 'place's if they are within a 'place'-area with the same name",
    "DELETE FROM _point p USING _polygon a WHERE p.place IS NOT NULL AND p.place = a.place AND p.name = a.name AND ST_Intersects(ST_Buffer(geography(p.way), 100), a.way);")

  execute("Remove ; from names",
    """UPDATE _polygon SET name = SUBSTRING(name FOR POSITION(';' IN name) - 1) WHERE name IS NOT NULL AND POSITION(';' IN name) > 0;
    UPDATE _line SET ref = SUBSTRING(ref FOR POSITION(';' IN ref) - 1) WHERE ref IS NOT NULL AND POSITION(';' IN ref) > 0;""")

  # TODO add 'onlysegment' column testing whether a named way has any adjacent ways with the same name. if not, then the onlysegment column can be used to try and fit as small a possible a label onto the segment in QGIS (in particular half font-height line break labels for primary and secondary roads and their bridges!)

  cur.close()

except (Exception, psycopg2.DatabaseError) as error:
  print(error)
finally:
  if conn is not None:
      conn.close()
