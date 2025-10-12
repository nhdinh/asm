# User Authentication Types

The Asset Management System now supports multiple authentication types for users.

## User Types

### 1. **LOCAL** - Local Database Authentication
- Default authentication type
- Users authenticate with username and password stored in the database
- Password is hashed using bcrypt
- Suitable for internal users without Active Directory accounts

### 2. **AD (Active Directory)** - LDAP/Active Directory Authentication
- Users authenticate against Active Directory
- No password is stored in the local database
- User information (email, fullname) is synchronized from AD on each login
- New AD users are automatically provisioned on first login

### 3. **SSO (Single Sign-On)** - Future Support
- Reserved for future SSO integration (OAuth2, SAML, etc.)
- Not currently implemented

## Database Schema

### Users Table Fields

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255),  -- NULL for AD/SSO users
    email VARCHAR(100) UNIQUE NOT NULL,
    fullname VARCHAR(100),
    role VARCHAR(20) NOT NULL,
    user_type VARCHAR(20) NOT NULL DEFAULT 'local',  -- 'local', 'ad', or 'sso'
    is_ad_user BOOLEAN DEFAULT FALSE,  -- Deprecated, kept for backward compatibility
    deleted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_user_type ON users(user_type);
```

## API Changes

### Login Endpoint

**Endpoint**: `POST /api/auth/login`

**Request Body**:
```json
{
  "username": "john.doe",
  "password": "password123",
  "auth_type": "local"  // Optional: "local" (default) or "ad"
}
```

**Response** (Success):
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "expires_in": 3600,
  "user": {
    "id": 1,
    "username": "john.doe",
    "email": "john.doe@company.com",
    "fullname": "John Doe",
    "role": "USER",
    "user_type": "local",  // NEW: Shows authentication type
    "is_ad_user": false    // Backward compatibility
  }
}
```

### User Details Response

When querying user information, the `user_type` field is now included:

```json
{
  "id": 1,
  "username": "john.doe",
  "email": "john.doe@company.com",
  "fullname": "John Doe",
  "role": "USER",
  "user_type": "ad",  // NEW: Authentication type
  "is_ad_user": true,  // Backward compatibility
  "departments": [...]
}
```

## Active Directory Configuration

Enable AD authentication by setting the following environment variables in `auth/.env`:

```env
# Enable Active Directory
AD_ENABLED=true

# AD Server Configuration
AD_SERVER=dc.company.local
AD_PORT=389
AD_USE_SSL=false

# AD Base DN
AD_BASE_DN=DC=company,DC=local

# User DN Template
AD_USER_DN=CN={username},CN=Users,DC=company,DC=local

# Service Account for User Search (optional)
AD_BIND_USER=CN=service-account,CN=Users,DC=company,DC=local
AD_BIND_PASSWORD=service-password

# User Search Filter
AD_USER_SEARCH_FILTER=(sAMAccountName={username})
```

## Migration Script

To add the `user_type` column to an existing database, run:

```bash
docker-compose exec -T postgres psql -U asmdbu -d asset_man < auth/scripts/add_user_type_column.sql
docker-compose exec -T postgres psql -U asmdbu -d auth_db < auth/scripts/add_user_type_column.sql
```

Or manually:

```sql
-- Add user_type column
ALTER TABLE users ADD COLUMN IF NOT EXISTS user_type VARCHAR(20) NOT NULL DEFAULT 'local';

-- Migrate existing AD users
UPDATE users SET user_type = 'ad' WHERE is_ad_user = true;

-- Create index
CREATE INDEX IF NOT EXISTS idx_users_user_type ON users(user_type);
```

## Usage Examples

### 1. Login with Local Account

```bash
curl -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin123"
  }'
```

### 2. Login with Active Directory Account

```bash
curl -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john.doe",
    "password": "ad_password",
    "auth_type": "ad"
  }'
```

### 3. Create Local User (Admin Only)

Local users must have `user_type` set to `"local"`:

```bash
curl -X POST http://localhost:8080/api/users \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newuser",
    "email": "newuser@company.com",
    "fullname": "New User",
    "password": "password123",
    "role": "USER",
    "user_type": "local"
  }'
```

## Authentication Flow

### Local User Authentication Flow

1. Client sends username/password with `auth_type: "local"` (or omitted)
2. Auth service queries database for user with matching username
3. Verifies user has `user_type == "local"`
4. Checks password hash using bcrypt
5. Issues JWT access and refresh tokens

### Active Directory Authentication Flow

1. Client sends username/password with `auth_type: "ad"`
2. Auth service connects to AD server via LDAP
3. Attempts to bind with user credentials
4. If successful, retrieves user info (email, fullname, groups) from AD
5. Creates or updates user in local database with `user_type == "ad"`
6. Issues JWT access and refresh tokens

## Security Considerations

### Password Requirements

- **Local users**: MUST have a password hash in the database
- **AD users**: MUST NOT have a password hash (always null)
- **SSO users**: MUST NOT have a password hash (always null)

### Preventing Type Mixing

The system enforces that:
- Local users cannot authenticate via AD
- AD users cannot authenticate with local password
- Attempting to authenticate with wrong type returns: `"User must authenticate via AD"`

### Account Lockout

Both local and AD authentication respect the account lockout policy:
- Max failed attempts: `MAX_FAILED_LOGIN_ATTEMPTS` (default: 5)
- Lockout duration: `ACCOUNT_LOCKOUT_MINUTES` (default: 15)

## Backward Compatibility

The `is_ad_user` boolean field is maintained for backward compatibility:
- `user_type == "ad"` implies `is_ad_user == true`
- `user_type == "local"` implies `is_ad_user == false`

Both fields are included in API responses to support legacy clients.

## Future Enhancements

1. **SSO Integration**: OAuth2/SAML support with `user_type == "sso"`
2. **Multi-Factor Authentication**: Support for MFA across all user types
3. **AD Group Mapping**: Automatic role assignment based on AD groups
4. **Password Sync**: Option to sync AD passwords to local database (hybrid mode)
5. **Account Linking**: Allow linking AD and local accounts

## Troubleshooting

### AD Users Cannot Login

1. Check AD configuration in `auth/.env`:
   ```bash
   docker-compose exec auth printenv | grep AD_
   ```

2. Test AD connectivity:
   ```bash
   docker-compose exec auth ldapsearch -H ldap://AD_SERVER:389 \
     -x -D "BIND_USER" -w "BIND_PASSWORD" -b "BASE_DN"
   ```

3. Check auth service logs:
   ```bash
   docker-compose logs -f auth
   ```

### User Type Not Showing Correctly

Verify database migration was applied:

```sql
SELECT username, user_type, is_ad_user FROM users;
```

Expected output:
```
 username  | user_type | is_ad_user
-----------+-----------+------------
 admin     | local     | f
 john.doe  | ad        | t
```

## Related Files

- **Auth Service**: `auth/src/routes.py`, `auth/src/models.py`
- **AD Authenticator**: `auth/src/ad_authenticator.py`
- **Backend Models**: `backend/src/models.py`
- **Migration Script**: `auth/scripts/add_user_type_column.sql`
- **Configuration**: `auth/.env`, `CLAUDE.md`
