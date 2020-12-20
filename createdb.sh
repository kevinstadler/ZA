#!/bin/sh
if [ -d "db$1" ]; then
	echo "DB already exists?"
	exit 1
fi
initdb "./db$1" -E utf8
pg_ctl -D "db$1" start > /dev/null

DBNAME=za
createdb $DBNAME && psql -d $DBNAME -c 'CREATE EXTENSION postgis; CREATE EXTENSION hstore;'
# && ./adddata.sh data/*.osm

# psql -d "$DB" -c "DROP VIEW districts; CREATE VIEW districts AS SELECT id, boundary, admin_level, name, ST_MakePolygon(parts) AS geometry FROM _rels WHERE

