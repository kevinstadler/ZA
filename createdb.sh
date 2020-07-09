#!/bin/sh
if [ -d db ]; then
	echo "DB already exists?"
	exit 1
fi
initdb ./db -E utf8
pg_ctl -D db start

DBNAME=za
createdb $DBNAME && psql -d $DBNAME -c 'CREATE EXTENSION postgis; CREATE EXTENSION hstore;'
# && ./adddata.sh data/*.osm

# psql -d "$DB" -c "DROP VIEW districts; CREATE VIEW districts AS SELECT id, boundary, admin_level, name, ST_MakePolygon(parts) AS geometry FROM _rels WHERE

