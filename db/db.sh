#!/bin/bash
if [ $# -ne 2 ]; then
  echo "Usage: ./db.sh <create|start|stop|delete> dbname"
fi

case "$1" in
  create)
    ./createdb.sh "$2"
    ;;
  start)
    sudo pg_ctlcluster 12 db$2 $1
    ;;
  stop)
    sudo pg_ctlcluster 12 db$2 $1
    ;;
  drop)
    sudo pg_dropcluster --stop 12 db$2
    ;;
esac
