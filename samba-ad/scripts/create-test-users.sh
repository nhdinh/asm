#!/bin/bash
set -e

ADMIN_PASSWORD="${ADMIN_PASSWORD:-Admin@123456}"
DEFAULT_PASSWORD="${DEFAULT_PASSWORD:-User@123456}"

echo "==================================="
echo "Creating test users and groups"
echo "==================================="

# Wait for Samba to be fully started
sleep 3

# Create Organizational Units
echo "Creating Organizational Units..."
samba-tool ou create "OU=AssetManagement,DC=assetman,DC=local" 2>/dev/null || echo "OU AssetManagement already exists"
samba-tool ou create "OU=Users,OU=AssetManagement,DC=assetman,DC=local" 2>/dev/null || echo "OU Users already exists"
samba-tool ou create "OU=Groups,OU=AssetManagement,DC=assetman,DC=local" 2>/dev/null || echo "OU Groups already exists"

# Create Groups
echo "Creating groups..."
samba-tool group add "AssetManagers" --groupou="OU=Groups,OU=AssetManagement" 2>/dev/null || echo "Group AssetManagers already exists"
samba-tool group add "AssetUsers" --groupou="OU=Groups,OU=AssetManagement" 2>/dev/null || echo "Group AssetUsers already exists"
samba-tool group add "AssetAdmins" --groupou="OU=Groups,OU=AssetManagement" 2>/dev/null || echo "Group AssetAdmins already exists"

# Create test users
echo "Creating test users..."

# Admin user
samba-tool user create testadmin "${DEFAULT_PASSWORD}" \
    --userou="OU=Users,OU=AssetManagement" \
    --surname="Admin" \
    --given-name="Test" \
    --mail-address="testadmin@assetman.local" 2>/dev/null || echo "User testadmin already exists"

# Manager users
samba-tool user create testmanager "${DEFAULT_PASSWORD}" \
    --userou="OU=Users,OU=AssetManagement" \
    --surname="Manager" \
    --given-name="Test" \
    --mail-address="testmanager@assetman.local" 2>/dev/null || echo "User testmanager already exists"

samba-tool user create manager1 "${DEFAULT_PASSWORD}" \
    --userou="OU=Users,OU=AssetManagement" \
    --surname="One" \
    --given-name="Manager" \
    --mail-address="manager1@assetman.local" 2>/dev/null || echo "User manager1 already exists"

# Regular users
declare -a users=("testuser1" "testuser2" "testuser3" "testuser4" "testuser5")
for i in "${!users[@]}"; do
    user="${users[$i]}"
    num=$((i+1))
    samba-tool user create "${user}" "${DEFAULT_PASSWORD}" \
        --userou="OU=Users,OU=AssetManagement" \
        --surname="User${num}" \
        --given-name="Test" \
        --mail-address="${user}@assetman.local" 2>/dev/null || echo "User ${user} already exists"
done

# Add users to groups
echo "Adding users to groups..."
samba-tool group addmembers "AssetAdmins" testadmin 2>/dev/null || echo "testadmin already in AssetAdmins"
samba-tool group addmembers "AssetManagers" testmanager,manager1 2>/dev/null || echo "Managers already in group"
samba-tool group addmembers "AssetUsers" testuser1,testuser2,testuser3,testuser4,testuser5 2>/dev/null || echo "Users already in group"

# Also add to Domain Admins for testadmin
samba-tool group addmembers "Domain Admins" testadmin 2>/dev/null || echo "testadmin already in Domain Admins"

echo "==================================="
echo "Test users created successfully"
echo ""
echo "Admin Users:"
echo "  - Administrator / ${ADMIN_PASSWORD} (Domain Admin)"
echo "  - testadmin / ${DEFAULT_PASSWORD} (Asset Admin)"
echo ""
echo "Manager Users:"
echo "  - testmanager / ${DEFAULT_PASSWORD}"
echo "  - manager1 / ${DEFAULT_PASSWORD}"
echo ""
echo "Regular Users:"
echo "  - testuser1 / ${DEFAULT_PASSWORD}"
echo "  - testuser2 / ${DEFAULT_PASSWORD}"
echo "  - testuser3 / ${DEFAULT_PASSWORD}"
echo "  - testuser4 / ${DEFAULT_PASSWORD}"
echo "  - testuser5 / ${DEFAULT_PASSWORD}"
echo ""
echo "Groups:"
echo "  - AssetAdmins (testadmin)"
echo "  - AssetManagers (testmanager, manager1)"
echo "  - AssetUsers (testuser1-5)"
echo "==================================="
