FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install Samba AD DC and required packages
RUN apt-get update && apt-get install -y \
    samba \
    winbind \
    krb5-user \
    krb5-config \
    libpam-krb5 \
    libpam-winbind \
    libnss-winbind \
    ldb-tools \
    ldap-utils \
    dnsutils \
    net-tools \
    iputils-ping \
    nano \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Create directories
RUN mkdir -p /var/log/samba \
    && mkdir -p /var/lib/samba \
    && mkdir -p /etc/samba \
    && mkdir -p /run/samba

# Copy initialization scripts
COPY scripts/init-samba-ad.sh /usr/local/bin/init-samba-ad.sh
COPY scripts/create-test-users.sh /usr/local/bin/create-test-users.sh
COPY scripts/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

RUN chmod +x /usr/local/bin/init-samba-ad.sh \
    && chmod +x /usr/local/bin/create-test-users.sh

EXPOSE 53 88 135 139 389 445 464 636 3268 3269

VOLUME ["/var/lib/samba", "/etc/samba"]

ENTRYPOINT ["/usr/local/bin/init-samba-ad.sh"]
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
