#!/bin/sh
pg_ctl -D "db$1" stop
rm -rf "db$1"
