## database setup

### pgsql/PostGIS setup

```
sudo apt install postgis

echo "listen_addresses = '*'" > /etc/postgresql/12/main/postgresql.conf

echo "local   all             all                                     trust
host    all             all             127.0.0.1/32            trust
host    all             all             ::1/128                 trust
hostnossl    all          all            0.0.0.0/0  trust" > /etc/postgresql/12/main/pg_hba.conf

# WSL sucks so here we go
sudo service postgresql start

sudo -u postgres createuser -s za
```

### populate the database

```
# install dependencies
sudo apt install osm2pgsql
pip install psycopg2-binary
```

```
cd db
./createdb.sh dbnamejustforthatfile
./adddata.py SOMEFILE.osm.pbf
```

WSL sucks pt.2: run `db/wsl.sh` on every boot to fix its IP to 10.10.10.1 (for connecting from QGIS run in Windows)

## Fonts

* Avenir Next Condensed Regular (https://gitlab.com/jeichert/fonts/-/blob/master/Avenir%20Next%20Condensed/AvenirNextCondensed-Regular.ttf)
* DIN Condensed
* .SF NS Text
* Assistant (Place+Station labels) (https://www.1001fonts.com/assistant-font.html)

```

<!--
Setting up postgresql-12 (12.9-0ubuntu0.20.04.1) ...                                                                    Creating new PostgreSQL cluster 12/main ...                                                                             /usr/lib/postgresql/12/bin/initdb -D /var/lib/postgresql/12/main --auth-local peer --auth-host md5                      The files belonging to this database system will be owned by user "postgres".                                           This user must also own the server process.                                                                                                                                                                                                     The database cluster will be initialized with locale "C.UTF-8".                                                         The default database encoding has accordingly been set to "UTF8".                                                       The default text search configuration will be set to "english".         


syncing data to disk ... ok                                                                                                                                                                                                                     Success. You can now start the database server using:                                                                                                                                                                                               pg_ctlcluster 12 main start                                                                                                                                                                                                                 Ver Cluster Port Status Owner    Data directory              Log file                                                   12  main    5432 down   postgres /var/lib/postgresql/12/main /var/log/postgresql/postgresql-12-main.log                 update-alternatives: using /usr/share/postgresql/12/man/man1/postmaster.1.gz to provide /usr/share/man/man1/postmaster.1.gz (postmaster.1.gz) in auto mode                                                                                      invoke-rc.d: could not determine current runlevel 
-->
