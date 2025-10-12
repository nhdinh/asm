#!/bin/bash
set -e

# Environment variables with defaults
DOMAIN="${DOMAIN:-ASSETMAN}"
REALM="${REALM:-ASSETMAN.LOCAL}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-Admin@123456}"
DNS_FORWARDER="${DNS_FORWARDER:-8.8.8.8}"
HOST_IP="${HOST_IP:-172.18.0.100}"

# Check if Samba AD is already provisioned
if [ ! -f /var/lib/samba/private/sam.ldb ]; then
    echo "==================================="
    echo "Provisioning Samba AD Domain Controller"
    echo "Domain: ${DOMAIN}"
    echo "Realm: ${REALM}"
    echo "DNS Forwarder: ${DNS_FORWARDER}"
    echo "==================================="

    # Remove any existing Samba configuration
    rm -rf /etc/samba/smb.conf
    rm -rf /var/lib/samba/*
    rm -rf /var/cache/samba/*

    # Provision Samba AD DC
    samba-tool domain provision \
        --realm="${REALM}" \
        --domain="${DOMAIN}" \
        --adminpass="${ADMIN_PASSWORD}" \
        --server-role=dc \
        --dns-backend=SAMBA_INTERNAL \
        --use-rfc2307 \
        --option="dns forwarder = ${DNS_FORWARDER}"

    # Copy Kerberos configuration
    cp /var/lib/samba/private/krb5.conf /etc/krb5.conf

    echo "==================================="
    echo "Samba AD DC provisioned successfully"
    echo "Administrator password: ${ADMIN_PASSWORD}"
    echo "==================================="

    # Wait for Samba to start
    sleep 5

    # Create test users
    /usr/local/bin/create-test-users.sh
else
    echo "==================================="
    echo "Samba AD DC already provisioned"
    echo "Domain: ${DOMAIN}"
    echo "Realm: ${REALM}"
    echo "==================================="
fi

# Set permissions
chmod -R 0700 /var/lib/samba/private

# Execute CMD
exec "$@"
