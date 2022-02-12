#!/usr/local/bin/python3

import argparse
import psycopg2
import os

# small cutouts:
#./adddata.py --bbox 102.66 25.033 102.73 25.085 -- data/Kunming.osm.pbf
#./adddata.py --bbox -96.013 36.095 -95.95 36.167 -- data/Tulsa.osm.pbf
#./adddata.py --bbox -3.2315 55.9265 -3.1548 55.9582 -- data/Edinburgh.osm.pbf

parser = argparse.ArgumentParser(description='Add (and post-process) data to an OSM PostGIS database')
parser.add_argument('--user', default='za')
parser.add_argument('--db', default='za')
parser.add_argument('--style', default='za.style')
parser.add_argument('--simplify', type=float, default=4.0)
parser.add_argument('--simplify2', type=float, default=3000.0, help='simplification tolerance for the simplified2 column (VW)') # was already up to 5000, only small changes there
parser.add_argument('--bbox', nargs='*', help='bounding box in "minlon minlat maxlon maxlat" (WSEN) order (provide four bbox arguments for every osmfile)')
parser.add_argument('--minarea', type=int, default=16, help='polygons with an area < this will be dropped')
parser.add_argument('osmfile', nargs='*')

args = parser.parse_args()

try:
  conn = psycopg2.connect(host="localhost", user=args.user, database=args.db)
  cur = conn.cursor()

  def execute(text, cmd):
    print(text)
    cur.execute(cmd)
    print(f"{cur.rowcount} rows affected\n")
    conn.commit()
    return cur.rowcount

  def getcount(query, asstr = True):
    cur.execute(f"SELECT COUNT(*) FROM {query};")
    return str(cur.fetchone()[0]) if asstr else cur.fetchone()[0]

  cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name = '_point'")
  append = '' if cur.fetchone() == None else '--append'

  cmd = f"osm2pgsql -U {args.user} --database {args.db} --prefix '' --slim --latlong --style {args.style} --multi-geometry {append} "
  # --append can only be used with slim mode (so don't --drop!)

  if args.bbox == None:
    if len(args.osmfile) > 0:
      # add all at once
      if os.system(cmd + '"' + '" "'.join(args.osmfile) + '"') != 0:
        print(cmd)
        raise Exception('osm2pgsql failed!')
  else:
    # add each individually
    bboxes = [','.join(map(str, args.bbox[i:i + 4])) for i in range(0, len(args.bbox), 4)]
    for (file, bbox) in zip(args.osmfile, bboxes):
      print(f"Adding {file} ({bbox})")
      if os.system(cmd + f'--bbox "{bbox}" {file}') != 0:
        raise Exception('osm2pgsql failed!')

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
      ALTER TABLE _line ADD direction SMALLINT;
      ALTER TABLE _line ADD flatcap BOOL NOT NULL DEFAULT false;
      ALTER TABLE _line ADD singlynamed BOOL;
      ALTER TABLE _line ADD simplified geometry(Geometry,4326);
      CREATE INDEX _line_simplified_idx ON _line USING GIST(simplified);""")
    conn.commit()

  # OSM urban places: city > borough   >   suburb > quarter   >   neighbourhood > city_block > plot, square
  # OSM rural places:    town   >   village       >       hamlet                >              isolated_dwelling, farm, allotments 
  # OSM other places: island > islet, square, locality
  execute("Creating 'places' view",
    "CREATE OR REPLACE VIEW places ( osm_id, place, name, way ) AS (SELECT osm_id, place, name, way FROM _polygon WHERE place IS NOT NULL) UNION (SELECT osm_id, place, name, ST_Buffer(geography(way), ('city=>500, town=>300, borough=>300, village=>200, suburb=>200, quarter=>150, neighbourhood=>100, hamlet=>50, city_block=>30, plot=>20, square=>15'::hstore -> place)::INTEGER) FROM _point WHERE place IS NOT NULL AND name IS NOT NULL);")

  # POSTPROCESSING
  execute("Removing inner rings from leisure = 'golf_course' polygons...",
    # TODO this won't work on MultiPolygons...
    "UPDATE _polygon SET way = ST_MakePolygon(ST_ExteriorRing(way)) WHERE leisure = 'golf_course' AND ST_GeometryType(way) = 'ST_Polygon' AND ST_NumInteriorRings(way) > 0;")

  execute(f"Populating length column ({getcount('_line WHERE length IS NULL')} rows)...",
    'UPDATE _line SET length = ST_Length(way, false) WHERE length IS NULL')
  ## faster but fails in Serbia: https://gis.stackexchange.com/questions/312910/postgis-st-area-causing-error-when-used-with-use-spheroid-false-setting-succe
  execute(f"Populating area column ({getcount('_polygon WHERE area IS NULL')} rows)...",
    'UPDATE _polygon SET area = ST_Area(Geography(way)) WHERE area IS NULL')

  execute(f"Deleting polygons below a minimum size of {args.minarea}m^2", f"DELETE FROM _polygon WHERE area < {args.minarea}")
  # TODO delete highway = 'footpath', 'path' ETC which are short and either (a) only connected to other short paths or (b) contained in small (garden?) polygons

  proj = "'+proj=stere +lat_0=' || ST_Y(ST_Centroid(way)) || ' +lon_0=' || ST_X(ST_Centroid(way)) || ' +k=1 +datum=WGS84 +units=m +no_defs'"
  #proj = "'+proj=gnom +lat_0=' || ST_Y(ST_Centroid(way)) || ' +lon_0=' || ST_X(ST_Centroid(way)) || ' +datum=WGS84 +units=m +no_defs'"
  execute(f"Simplifying {getcount('_polygon WHERE simplified IS NULL')} polygons (tolerance={args.simplify}m)...",
    f"UPDATE _polygon SET simplified = ST_Transform(ST_SimplifyPreserveTopology(ST_Transform(way, {proj}), {args.simplify}), {proj}, 4326) WHERE simplified IS NULL;")
  execute(f"Simplifying {getcount('_polygon WHERE simplified2 IS NULL')} polygons for overview (tolerance={args.simplify2}m)...",
    f"UPDATE _polygon SET simplified2 = ST_Transform(ST_ChaikinSmoothing(ST_SimplifyVW(ST_Transform(way, {proj}), {args.simplify2})), {proj}, 4326) WHERE (aeroway IS NOT NULL OR landuse IS NOT NULL OR 'natural' IS NOT NULL OR water IS NOT NULL);") # TODO REPLACE CONDITION AND simplified2 IS NULL;")
#  cur.execute("UPDATE _polygon SET simplified = ST_Transform(ST_SimplifyPreserveTopology(ST_Transform(way, $PROJ), $TOLERANCE), $PROJ, 4326), simplified2 = ST_Transform(ST_SimplifyVW(ST_Transform(way, $PROJ), $TOLERANCE), $PROJ, 4326) WHERE simplified IS NULL;")
  execute(f"Simplifying {getcount('_line WHERE simplified IS NULL')} ways (tolerance={args.simplify}m)...",
    f"UPDATE _line SET simplified = ST_Transform(ST_SimplifyPreserveTopology(ST_Transform(way, {proj}), {args.simplify}), {proj}, 4326) WHERE simplified IS NULL;")

  execute("Removing layer = 0, tunnel = 'no', oneway = 'no', bridge = 'no' tags...",
    """UPDATE _line SET layer = NULL WHERE layer = 0;
    UPDATE _line SET oneway = NULL WHERE oneway = 'no';
    UPDATE _line SET bridge = NULL WHERE bridge = 'no';
    UPDATE _line SET tunnel = NULL WHERE tunnel = 'no';""")

  genericbuilding = "('yes', 'public', 'roof', 'service')"
  AMENITY = "('hospital', 'school', 'college', 'university', 'arts_centre', 'bus_station', 'place_of_worship')"
  LANDUSE = "('depot', 'industrial', 'railway', 'retail')" # TODO also do with 'commercial' or 'retail'?
  LEISURE = "('sports_centre')"
  #containsspatially = "ST_Covers(grounds.way, bldg.way)"
  containsspatially = "ST_Within(ST_Centroid(bldg.way), grounds.way)"
  execute("Marking any underspecified buildings on amenity (school, hospital,...) grounds as buildings of that type, and removing names of buildings contained in areas of the same name...",
#    f"""UPDATE _polygon SET building = NULL WHERE building = 'no';
    f"""UPDATE _polygon SET building = amenity WHERE building in {genericbuilding} AND amenity IS NOT NULL;
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

  ncols = getcount("information_schema.columns WHERE table_name = '_polygon'", False)
  # don't select way, area, simplified, simplified2
  cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = '_polygon' LIMIT " + str(ncols - 4))
  cols = ", ".join(map(lambda col: '"' + col[0] + '"', cur.fetchall()))

  execute("Copying roundabouts accidentally added as polygons over to _line table...",
    f"INSERT INTO _line SELECT {cols}, ST_ExteriorRing(way) AS way FROM _polygon WHERE highway IS NOT NULL AND (oneway = 'yes' OR junction = 'roundabout')")

  execute("Populating direction column...",
    "UPDATE _line SET direction = ('1=>1, yes=>1, -1=>-1'::hstore -> oneway)::INTEGER * CASE WHEN ST_Contains(ST_Envelope(ST_GeomFromText('LINESTRING(-12 61, 2 50)', 4326)), way) THEN -1 ELSE 1 END WHERE direction IS NULL;")

  ## compute which ways should have flat caps (because they are a dead end on at least one side)
  connectedhighways = "('motorway', 'motorway_link', 'primary', 'primary_link', 'secondary', 'secondary_link', 'tertiary', 'residential', 'unclassified', 'road', 'pedestrian')"
  execute(f"Populating flatcap column (testing {getcount('_line WHERE flatcap = false')} rows)...",
    f"UPDATE _line SET flatcap = true WHERE flatcap = false AND _line.osm_id NOT IN (SELECT DISTINCT ON (source.osm_id) source.osm_id FROM _line source JOIN _line end1 ON (end1.highway IN {connectedhighways} OR source.highway = end1.highway) AND source.osm_id != end1.osm_id AND end1.tunnel IS NULL AND ST_Covers(end1.way, ST_StartPoint(source.way)) JOIN _line end2 ON (end2.highway IN {connectedhighways} OR source.highway = end2.highway) AND source.osm_id != end2.osm_id AND end2.tunnel IS NULL AND ST_Covers(end2.way, ST_EndPoint(source.way)) WHERE source.highway IS NOT NULL);")
  # QUERY to test:
  # SELECT DISTINCT ON (source.osm_id) source.osm_id, end1.osm_id, end2.osm_id, source.flatcap FROM _line source LEFT JOIN _line end1 ON end1.highway IS NOT NULL AND source.osm_id != end1.osm_id AND ST_Covers(end1.way, ST_StartPoint(source.way)) LEFT JOIN _line end2 ON end2.highway IS NOT NULL AND source.osm_id != end2.osm_id AND ST_Covers(end2.way, ST_EndPoint(source.way)) WHERE source.highway IS NOT NULL;

  # this column can be used to try and fit as small a possible a label onto the segment in QGIS (in particular half font-height line break labels for primary and secondary roads and their bridges!)
  singlynamed = execute(f"Marking highway segments which are singly named (not connected to any same-named highways)",
    # TODO use ST_Intersects instead (faster?)
    """UPDATE _line hw SET singlynamed = true WHERE hw.highway IS NOT NULL AND hw.singlynamed IS NULL AND hw.name IS NOT NULL
        AND NOT EXISTS (SELECT 1 FROM _line adjacent WHERE adjacent.highway IS NOT NULL AND hw.name = adjacent.name AND ST_Touches(hw.way, adjacent.way))""")
  # rough solution: undo suspicious duplicates based on counts with the same name.
  # (better way to do this right in the first place would be with buffers instead of simple ST_Touches....)
  execute(f"Testing {singlynamed} singly-named highways if they might not have been marked singly-named on accident...",
    "UPDATE _line hw SET singlynamed = false WHERE hw.singlynamed AND (SELECT COUNT(*) FROM _line WHERE singlynamed AND name = hw.name) > 1;")

  # TODO actually create an "amenities" view which has a union of points + polygon centroids for railway=station and the relevant amenities to be rendered
  # FIXME this is broken, something about no. of columns?
#  execute("Copying railway=station polygons over to _points table...",
#    f"INSERT INTO _point SELECT {cols}, ST_Centroid(way) AS way FROM _polygon WHERE railway = 'station'")

  execute("Capitalising names of large train_stations",
    "UPDATE _point station SET name = UPPER(station.name) FROM _polygon bldg WHERE bldg.building = 'train_station' AND (station.public_transport = 'station' OR station.railway = 'station') AND bldg.name = station.name AND ST_Within(station.way, bldg.way) AND bldg.area > 10000;")
  execute("Removing names of train station areas if they contain a train_station point (of the same name) inside them",
    "UPDATE _polygon bldg SET name = NULL FROM _point station WHERE bldg.building = 'train_station' AND (station.public_transport = 'station' OR station.railway = 'station') AND bldg.name = station.name AND ST_Within(station.way, bldg.way)")

  execute("Transfering point 'place' tags to co-located non-place residential areas with the same name",
    "UPDATE _polygon a SET place = p.place FROM _point p WHERE a.place IS NULL AND a.landuse = 'residential' AND p.place IS NOT NULL AND p.name = a.name AND ST_Intersects(ST_Buffer(geography(p.way), 100), a.way)")
  execute("Dropping point 'place's if they are within a 'place'-area with the same name",
    "DELETE FROM _point p USING _polygon a WHERE p.place IS NOT NULL AND p.place = a.place AND p.name = a.name AND ST_Intersects(ST_Buffer(geography(p.way), 100), a.way);")

  execute("Removing ; from line and polygon names",
    """UPDATE _polygon SET name = SUBSTRING(name FOR POSITION(';' IN name) - 1) WHERE name IS NOT NULL AND POSITION(';' IN name) > 0;
    UPDATE _line SET ref = SUBSTRING(ref FOR POSITION(';' IN ref) - 1) WHERE ref IS NOT NULL AND POSITION(';' IN ref) > 0;""")


  cur.close()

except (Exception, psycopg2.DatabaseError) as error:
  print(error)
finally:
  if conn is not None:
      conn.close()
