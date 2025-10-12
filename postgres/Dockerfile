FROM postgres:15-alpine

WORKDIR /scripts

ADD ./init.sql .

COPY ./entry.sh /usr/local/bin/entry.sh
RUN chmod +x /usr/local/bin/entry.sh

EXPOSE 5432

ENTRYPOINT ["/usr/local/bin/entry.sh"]

CMD ["postgres"]