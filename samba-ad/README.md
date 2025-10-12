# Samba Active Directory Domain Controller for Testing

This is a containerized Samba AD DC for testing Active Directory authentication with the Asset Management System.

## Overview

- **Domain**: ASSETMAN
- **Realm**: ASSETMAN.LOCAL
- **Forest Level**: 2012_R2
- **DNS**: Samba Internal DNS
- **LDAP Base DN**: DC=assetman,DC=local

## Network Configuration

The Samba AD container runs on a static IP within the Docker network:
- **IP Address**: 172.18.0.100
- **Subnet**: 172.18.0.0/16

### Exposed Ports

| Service | Internal Port | External Port | Protocol |
|---------|---------------|---------------|----------|
| DNS | 53 | 10053 | TCP/UDP |
| Kerberos | 88 | 10088 | TCP/UDP |
| LDAP | 389 | 10389 | TCP/UDP |
| SMB/CIFS | 445 | 10445 | TCP |
| Kerberos Password | 464 | 10464 | TCP/UDP |
| LDAPS | 636 | 10636 | TCP |
| Global Catalog | 3268 | 13268 | TCP |
| Global Catalog SSL | 3269 | 13269 | TCP |

**Note**: External ports are remapped to avoid conflicts with Windows services.

## Organizational Structure

```
DC=assetman,DC=local
└── OU=AssetManagement
    ├── OU=Users
    │   ├── CN=testadmin
    │   ├── CN=testmanager
    │   ├── CN=manager1
    │   ├── CN=testuser1
    │   ├── CN=testuser2
    │   ├── CN=testuser3
    │   ├── CN=testuser4
    │   └── CN=testuser5
    └── OU=Groups
        ├── CN=AssetAdmins
        ├── CN=AssetManagers
        └── CN=AssetUsers
```

## Test Users

### Administrator Accounts

| Username | Password | Groups | Description |
|----------|----------|--------|-------------|
| Administrator | Admin@123456 | Domain Admins | Built-in domain administrator |
| testadmin | User@123456 | Domain Admins, AssetAdmins | Test admin account |

### Manager Accounts

| Username | Password | Groups | Description |
|----------|----------|--------|-------------|
| testmanager | User@123456 | AssetManagers | Test manager account |
| manager1 | User@123456 | AssetManagers | Test manager account |

### Regular User Accounts

| Username | Password | Groups | Description |
|----------|----------|--------|-------------|
| testuser1 | User@123456 | AssetUsers | Test user account 1 |
| testuser2 | User@123456 | AssetUsers | Test user account 2 |
| testuser3 | User@123456 | AssetUsers | Test user account 3 |
| testuser4 | User@123456 | AssetUsers | Test user account 4 |
| testuser5 | User@123456 | AssetUsers | Test user account 5 |

## Usage

### Starting the Samba AD Service

```bash
# Start only Samba AD
docker-compose up -d samba-ad

# Start all services including Samba AD
docker-compose up -d
```

### Stopping the Samba AD Service

```bash
docker-compose stop samba-ad
```

### Viewing Logs

```bash
# View container logs
docker-compose logs samba-ad

# Follow logs in real-time
docker-compose logs -f samba-ad

# View Samba service logs
docker-compose exec samba-ad tail -f /var/log/samba/samba.log
```

### Accessing the Container

```bash
# Execute a bash shell in the container
docker-compose exec samba-ad bash

# Run Samba AD commands
docker-compose exec samba-ad samba-tool user list
docker-compose exec samba-ad samba-tool group list
docker-compose exec samba-ad samba-tool domain info dc1
```

## Integration with Auth Service

To enable AD authentication in the Asset Management System, update the `.env` file:

```bash
# Active Directory Settings
AD_ENABLED=true
AD_SERVER=samba-ad
AD_PORT=389
AD_USE_SSL=false
AD_BASE_DN=DC=assetman,DC=local
AD_USER_DN=CN={username},OU=Users,OU=AssetManagement,DC=assetman,DC=local
AD_BIND_USER=Administrator
AD_BIND_PASSWORD=Admin@123456
```

Then restart the auth service:

```bash
docker-compose restart auth
```

## Testing LDAP Connection

### From Host Machine (External Port)

```bash
# Test LDAP connection (requires ldapsearch)
ldapsearch -H ldap://localhost:10389 -D "Administrator@assetman.local" -w "Admin@123456" -b "DC=assetman,DC=local"

# Search for users
ldapsearch -H ldap://localhost:10389 -D "Administrator@assetman.local" -w "Admin@123456" -b "OU=Users,OU=AssetManagement,DC=assetman,DC=local" "(objectClass=user)"

# Search for groups
ldapsearch -H ldap://localhost:10389 -D "Administrator@assetman.local" -w "Admin@123456" -b "OU=Groups,OU=AssetManagement,DC=assetman,DC=local" "(objectClass=group)"
```

### From Another Container (Internal Network)

```bash
# Test from auth container
docker-compose exec auth bash -c "apt-get update && apt-get install -y ldap-utils"
docker-compose exec auth ldapsearch -H ldap://samba-ad:389 -D "Administrator@assetman.local" -w "Admin@123456" -b "DC=assetman,DC=local"
```

### Using Python

```python
import ldap3
from ldap3 import Server, Connection, ALL

server = Server('samba-ad', port=389, get_info=ALL)
conn = Connection(server,
                  user='Administrator@assetman.local',
                  password='Admin@123456',
                  auto_bind=True)

conn.search('DC=assetman,DC=local',
            '(objectClass=user)',
            attributes=['cn', 'sAMAccountName', 'mail'])

for entry in conn.entries:
    print(entry)

conn.unbind()
```

## Samba AD Management Commands

### User Management

```bash
# List all users
docker-compose exec samba-ad samba-tool user list

# Create new user
docker-compose exec samba-ad samba-tool user create newuser "Password123!" \
  --userou="OU=Users,OU=AssetManagement"

# Delete user
docker-compose exec samba-ad samba-tool user delete username

# Set user password
docker-compose exec samba-ad samba-tool user setpassword username

# Enable/disable user
docker-compose exec samba-ad samba-tool user enable username
docker-compose exec samba-ad samba-tool user disable username
```

### Group Management

```bash
# List all groups
docker-compose exec samba-ad samba-tool group list

# Create new group
docker-compose exec samba-ad samba-tool group add GroupName \
  --groupou="OU=Groups,OU=AssetManagement"

# Add members to group
docker-compose exec samba-ad samba-tool group addmembers GroupName user1,user2

# Remove members from group
docker-compose exec samba-ad samba-tool group removemembers GroupName user1

# List group members
docker-compose exec samba-ad samba-tool group listmembers GroupName
```

### Domain Information

```bash
# Show domain information
docker-compose exec samba-ad samba-tool domain info dc1

# Show domain level
docker-compose exec samba-ad samba-tool domain level show

# Check DNS zones
docker-compose exec samba-ad samba-tool dns zonelist localhost
```

## Troubleshooting

### Check Service Status

```bash
# Check if Samba is running
docker-compose exec samba-ad ps aux | grep samba

# Test LDAP connectivity
docker-compose exec samba-ad smbclient -L localhost -U%
```

### View Configuration

```bash
# View Samba configuration
docker-compose exec samba-ad cat /etc/samba/smb.conf

# View Kerberos configuration
docker-compose exec samba-ad cat /etc/krb5.conf
```

### Reset Domain Controller

If you need to reprovision the AD:

```bash
# Stop and remove container
docker-compose down samba-ad

# Remove volumes
docker volume rm asset_man_samba_data asset_man_samba_config

# Start fresh
docker-compose up -d samba-ad
```

### Common Issues

1. **Port Conflicts**: If you see port binding errors, check which process is using the port:
   ```bash
   netstat -ano | findstr :10389
   ```

2. **DNS Resolution**: The Samba AD uses its own internal DNS. For external clients, you may need to configure DNS forwarding.

3. **Time Synchronization**: Kerberos requires time synchronization. Ensure Docker host time is accurate.

## Security Notes

**⚠️ This is a TEST environment only! Do NOT use in production!**

- Default passwords are simple and well-known
- SSL/TLS is not configured
- No password complexity policies enforced
- No account lockout policies configured
- All services are exposed without firewall rules

For production use, you should:
- Use strong, unique passwords
- Enable LDAPS (LDAP over SSL)
- Configure password policies
- Implement proper network security
- Enable audit logging
- Use proper DNS infrastructure
- Configure backup and disaster recovery

## Files

- `Dockerfile` - Container image definition
- `scripts/init-samba-ad.sh` - Domain controller provisioning script
- `scripts/create-test-users.sh` - Test user creation script
- `scripts/supervisord.conf` - Process supervisor configuration
- `logs/` - Samba service logs

## References

- [Samba Wiki - Setting up Samba as an AD DC](https://wiki.samba.org/index.php/Setting_up_Samba_as_an_Active_Directory_Domain_Controller)
- [Samba-tool Command Reference](https://wiki.samba.org/index.php/Samba-tool)
- [LDAP Protocol](https://ldap.com/)
- [Active Directory Schema](https://docs.microsoft.com/en-us/windows/win32/ad/active-directory-schema)
