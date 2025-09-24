FROM postgres:15-alpine

WORKDIR /scripts

ADD ./init.sql /docker-entrypoint-initdb.d/
ENTRYPOINT ["docker-entrypoint.sh"]

EXPOSE 5432

CMD ["postgres"]