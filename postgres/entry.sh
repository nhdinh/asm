#!/usr/bin/env bash

sed -i -e 's/${DB_USER}/'"$(cat /run/secrets/postgres_user)"'/g' ./init.sql
sed -i -e 's/${DB_PASSWD}/'"$(cat /run/secrets/postgres_password)"'/g' ./init.sql
sed -i -e 's/${DB_NAME}/'"$POSTGRES_DB"'/g' ./init.sql

cp ./init.sql /docker-entrypoint-initdb.d/

exec /usr/local/bin/docker-entrypoint.sh "$@"