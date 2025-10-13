#!/bin/bash

sed -i -e 's/${DB_USER}/'"$(cat /run/secrets/postgres_user)"'/g' ./init.sql
sed -i -e 's/${DB_PASSWD}/'"$(cat /run/secrets/postgres_password)"'/g' ./init.sql
sed -i -e 's/${BACKEND_DB_NAME}/'"$BACKEND_DB"'/g' ./init.sql
sed -i -e 's/${AUTH_DB_NAME}/'"$AUTH_DB"'/g' ./init.sql

cp ./init.sql /docker-entrypoint-initdb.d/

exec /usr/local/bin/docker-entrypoint.sh "$@"