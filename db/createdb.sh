#!/bin/sh
if [ -d "db$1" ]; then
  echo "DB already exists?"
  exit 1
fi
sudo -u postgres pg_createcluster --encoding=utf8 --start --port=5432 12 db$1 -- --auth=trust

DBNAME=za
createdb -U postgres $DBNAME
psql -U postgres -d $DBNAME -c 'CREATE EXTENSION postgis; CREATE EXTENSION hstore;'
sudo -u postgres createuser $DBNAME
# && ./adddata.sh data/*.osm

# psql -d "$DB" -c "DROP VIEW districts; CREATE VIEW districts AS SELECT id, boundary, admin_level, name, ST_MakePolygon(parts) AS geometry FROM _rels WHERE

