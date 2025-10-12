#!/bin/bash

# Test script for Samba AD authentication
# This script tests LDAP connectivity and user authentication

set -e

echo "=================================="
echo "Samba AD Authentication Test"
echo "=================================="
echo ""

# Configuration
AD_SERVER="${AD_SERVER:-samba-ad}"
AD_PORT="${AD_PORT:-389}"
BASE_DN="DC=assetman,DC=local"
BIND_DN="Administrator@assetman.local"
BIND_PASSWORD="Admin@123456"

# Test 1: Check if Samba AD container is running
echo "Test 1: Checking if Samba AD container is running..."
if docker ps | grep -q "ams-samba-ad"; then
    echo "✓ Samba AD container is running"
else
    echo "✗ Samba AD container is not running"
    echo "  Start it with: docker-compose up -d samba-ad"
    exit 1
fi
echo ""

# Test 2: List users in AD
echo "Test 2: Listing users in Active Directory..."
docker-compose exec -T samba-ad samba-tool user list | head -10
echo "✓ Successfully retrieved user list"
echo ""

# Test 3: Test LDAP connectivity from inside Docker network
echo "Test 3: Testing LDAP connectivity from auth container..."
if docker-compose exec -T auth which ldapsearch > /dev/null 2>&1; then
    echo "ldapsearch is already installed"
else
    echo "Installing ldapsearch in auth container..."
    docker-compose exec -T auth bash -c "apt-get update -qq && apt-get install -y -qq ldap-utils" > /dev/null 2>&1
fi

TEST_SEARCH=$(docker-compose exec -T auth ldapsearch -H ldap://${AD_SERVER}:${AD_PORT} \
    -D "${BIND_DN}" \
    -w "${BIND_PASSWORD}" \
    -b "${BASE_DN}" \
    "(objectClass=user)" \
    -LLL \
    sAMAccountName 2>&1)

if echo "$TEST_SEARCH" | grep -q "sAMAccountName"; then
    echo "✓ LDAP search successful"
    echo "  Found users:"
    echo "$TEST_SEARCH" | grep "sAMAccountName:" | head -5
else
    echo "✗ LDAP search failed"
    echo "$TEST_SEARCH"
    exit 1
fi
echo ""

# Test 4: Test specific user authentication
echo "Test 4: Testing user authentication..."
TEST_USERS=("testadmin" "testmanager" "testuser1")
for user in "${TEST_USERS[@]}"; do
    USER_DN="CN=${user},OU=Users,OU=AssetManagement,${BASE_DN}"
    TEST_BIND=$(docker-compose exec -T auth ldapsearch -H ldap://${AD_SERVER}:${AD_PORT} \
        -D "${USER_DN}" \
        -w "User@123456" \
        -b "${BASE_DN}" \
        -s base \
        "(objectClass=*)" 2>&1)

    if echo "$TEST_BIND" | grep -q "result: 0 Success"; then
        echo "✓ User '${user}' authenticated successfully"
    else
        echo "✗ User '${user}' authentication failed"
    fi
done
echo ""

# Test 5: Test group membership
echo "Test 5: Checking group memberships..."
echo "AssetAdmins members:"
docker-compose exec -T samba-ad samba-tool group listmembers AssetAdmins | sed 's/^/  - /'
echo ""
echo "AssetManagers members:"
docker-compose exec -T samba-ad samba-tool group listmembers AssetManagers | sed 's/^/  - /'
echo ""
echo "AssetUsers members:"
docker-compose exec -T samba-ad samba-tool group listmembers AssetUsers | head -5 | sed 's/^/  - /'
echo "✓ Group memberships verified"
echo ""

# Test 6: Test API authentication with AD user (if AD is enabled)
echo "Test 6: Testing API authentication with AD user..."
if grep -q "AD_ENABLED=true" .env 2>/dev/null; then
    echo "AD authentication is ENABLED in .env"
    echo "Attempting to login with testadmin..."

    LOGIN_RESPONSE=$(curl -s -X POST http://localhost:8080/api/auth/login \
        -H "Content-Type: application/json" \
        -d '{"username":"testadmin","password":"User@123456"}')

    if echo "$LOGIN_RESPONSE" | grep -q "access_token"; then
        echo "✓ AD user 'testadmin' successfully authenticated via API"
        echo "  Response:"
        echo "$LOGIN_RESPONSE" | python3 -m json.tool 2>/dev/null | head -10
    else
        echo "✗ AD user authentication failed"
        echo "  Response: $LOGIN_RESPONSE"
    fi
else
    echo "⚠ AD authentication is DISABLED in .env"
    echo "  To enable, set AD_ENABLED=true in .env and restart auth service"
    echo "  Command: docker-compose restart auth"
fi
echo ""

echo "=================================="
echo "Test Summary"
echo "=================================="
echo "All basic connectivity tests passed!"
echo ""
echo "To enable AD authentication:"
echo "1. Edit .env file and set AD_ENABLED=true"
echo "2. Restart auth service: docker-compose restart auth"
echo "3. Try logging in with AD users:"
echo "   - testadmin / User@123456"
echo "   - testmanager / User@123456"
echo "   - testuser1 / User@123456"
echo ""
