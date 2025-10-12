# Auth Service - User Information Endpoints

This document describes the user information retrieval endpoints added to the authentication service.

## Overview

The auth service now provides endpoints to retrieve user information by username or user ID. These endpoints are useful for:
- Getting user details without accessing the main backend database
- Verifying user existence and authentication type
- Building user interfaces that need to display user information

## Endpoints

### 1. Get User by Username

Retrieve user information by username.

**Endpoint**: `GET /api/auth/users/<username>`

**Authentication**: Required (JWT Bearer token)

**URL Parameters**:
- `username` (string, required): The username to look up

**Response** (200 OK):
```json
{
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com",
    "fullname": "Administrator",
    "role": "ADMIN",
    "user_type": "local",
    "is_ad_user": false
  }
}
```

**Error Responses**:
- `401 Unauthorized`: Invalid or missing authentication token
- `404 Not Found`: User not found or has been deleted

**Example**:
```bash
curl -X GET "http://localhost:8080/api/auth/users/admin" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

### 2. Get User by ID

Retrieve user information by user ID.

**Endpoint**: `GET /api/auth/users/id/<user_id>`

**Authentication**: Required (JWT Bearer token)

**URL Parameters**:
- `user_id` (integer, required): The user ID to look up

**Response** (200 OK):
```json
{
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com",
    "fullname": "Administrator",
    "role": "ADMIN",
    "user_type": "local",
    "is_ad_user": false
  }
}
```

**Error Responses**:
- `401 Unauthorized`: Invalid or missing authentication token
- `404 Not Found`: User not found or has been deleted

**Example**:
```bash
curl -X GET "http://localhost:8080/api/auth/users/id/1" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

### 3. List All Users

List all users in the system (admin only).

**Endpoint**: `GET /api/auth/users`

**Authentication**: Required (JWT Bearer token with ADMIN role)

**Query Parameters**:
- `include_deleted` (boolean, optional): Include soft-deleted users (default: false)
- `user_type` (string, optional): Filter by user type (`local`, `ad`, `sso`)
- `search` (string, optional): Search in username, email, or fullname

**Response** (200 OK):
```json
{
  "users": [
    {
      "id": 1,
      "username": "admin",
      "email": "admin@example.com",
      "fullname": "Administrator",
      "role": "ADMIN",
      "user_type": "local",
      "is_ad_user": false
    },
    {
      "id": 2,
      "username": "john.doe",
      "email": "john.doe@company.com",
      "fullname": "John Doe",
      "role": "USER",
      "user_type": "ad",
      "is_ad_user": true
    }
  ],
  "total": 2
}
```

**Error Responses**:
- `401 Unauthorized`: Invalid or missing authentication token
- `403 Forbidden`: User does not have admin privileges

**Examples**:
```bash
# List all users
curl -X GET "http://localhost:8080/api/auth/users" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# List only AD users
curl -X GET "http://localhost:8080/api/auth/users?user_type=ad" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Search for users
curl -X GET "http://localhost:8080/api/auth/users?search=john" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Include deleted users (admin only)
curl -X GET "http://localhost:8080/api/auth/users?include_deleted=true" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

### 4. Create New User

Create a new user account (admin only).

**Endpoint**: `POST /api/auth/users`

**Authentication**: Required (JWT Bearer token with ADMIN role)

**Request Body**:
```json
{
  "username": "newuser",
  "email": "newuser@company.com",
  "password": "SecurePassword123!",
  "fullname": "New User",
  "role": "USER",
  "user_type": "local"
}
```

**Field Descriptions**:
- `username` (string, required): Unique username for login
- `email` (string, required): User's email address (must be unique)
- `password` (string, required for `user_type: "local"`): User's password
  - Not required for AD/SSO users
  - Should not be provided for AD/SSO users
- `fullname` (string, optional): User's full name
- `role` (string, optional): User role - `"ADMIN"` or `"USER"` (default: `"USER"`)
- `user_type` (string, optional): Authentication type - `"local"`, `"ad"`, or `"sso"` (default: `"local"`)

**Response** (201 Created):
```json
{
  "message": "User created successfully",
  "user": {
    "id": 12,
    "username": "newuser",
    "email": "newuser@company.com",
    "fullname": "New User",
    "role": "USER",
    "user_type": "local",
    "is_ad_user": false
  }
}
```

**Error Responses**:
- `400 Bad Request`: Invalid input data
  - Missing required fields (username, email)
  - Username already exists
  - Email already exists
  - Invalid role (must be ADMIN or USER)
  - Invalid user_type (must be local, ad, or sso)
  - Password required for local users
  - Password provided for AD/SSO users
- `401 Unauthorized`: Invalid or missing authentication token
- `403 Forbidden`: User does not have admin privileges
- `500 Internal Server Error`: Database or server error

**Examples**:

**Create Local User:**
```bash
curl -X POST "http://localhost:8080/api/auth/users" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john.local",
    "email": "john.local@company.com",
    "password": "SecurePass123!",
    "fullname": "John Local",
    "role": "USER",
    "user_type": "local"
  }'
```

**Create AD User (No Password):**
```bash
curl -X POST "http://localhost:8080/api/auth/users" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "jane.ad",
    "email": "jane.ad@company.com",
    "fullname": "Jane AD",
    "role": "USER",
    "user_type": "ad"
  }'
```

**Create Admin User:**
```bash
curl -X POST "http://localhost:8080/api/auth/users" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin2",
    "email": "admin2@company.com",
    "password": "AdminPass123!",
    "fullname": "Administrator 2",
    "role": "ADMIN",
    "user_type": "local"
  }'
```

---

## User Object Fields

All endpoints return user objects with the following fields:

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Unique user identifier |
| `username` | string | Username for login |
| `email` | string | User's email address |
| `fullname` | string | User's full name |
| `role` | string | User role (`ADMIN` or `USER`) |
| `user_type` | string | Authentication type (`local`, `ad`, or `sso`) |
| `is_ad_user` | boolean | Legacy field - true if user authenticates via AD |

## Authorization

### Token Requirements

All endpoints require a valid JWT access token in the Authorization header:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Role-Based Access Control

- **Get User by Username**: Available to all authenticated users
- **Get User by ID**: Available to all authenticated users
- **List All Users**: Restricted to users with `ADMIN` role
- **Create User**: Restricted to users with `ADMIN` role

## Use Cases

### 1. Profile Page
```javascript
// Fetch current user's profile
const response = await fetch(`/api/auth/users/${currentUsername}`, {
  headers: {
    'Authorization': `Bearer ${accessToken}`
  }
});
const { user } = await response.json();
console.log(`Welcome, ${user.fullname}!`);
```

### 2. User Directory (Admin)
```javascript
// List all users with search
const searchTerm = 'john';
const response = await fetch(`/api/auth/users?search=${searchTerm}`, {
  headers: {
    'Authorization': `Bearer ${adminToken}`
  }
});
const { users, total } = await response.json();
console.log(`Found ${total} users matching "${searchTerm}"`);
```

### 3. User Type Filter
```javascript
// Get all Active Directory users
const response = await fetch(`/api/auth/users?user_type=ad`, {
  headers: {
    'Authorization': `Bearer ${adminToken}`
  }
});
const { users } = await response.json();
console.log(`AD Users: ${users.map(u => u.username).join(', ')}`);
```

### 4. User Lookup by ID
```javascript
// Get user details for assignment
const userId = 5;
const response = await fetch(`/api/auth/users/id/${userId}`, {
  headers: {
    'Authorization': `Bearer ${accessToken}`
  }
});
const { user } = await response.json();
console.log(`Assigning task to ${user.fullname}`);
```

### 5. Create New User (Admin)
```javascript
// Create a new local user
const newUserData = {
  username: 'newuser',
  email: 'newuser@company.com',
  password: 'SecurePass123!',
  fullname: 'New User',
  role: 'USER',
  user_type: 'local'
};

const response = await fetch('/api/auth/users', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${adminToken}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(newUserData)
});

if (response.ok) {
  const { user, message } = await response.json();
  console.log(message); // "User created successfully"
  console.log(`Created user: ${user.username} (ID: ${user.id})`);
} else {
  const error = await response.json();
  console.error('Failed to create user:', error.message);
}
```

### 6. Create AD User Without Password (Admin)
```javascript
// Create an AD user (no password needed)
const adUserData = {
  username: 'jane.ad',
  email: 'jane.ad@company.com',
  fullname: 'Jane from AD',
  role: 'USER',
  user_type: 'ad'  // No password field for AD users
};

const response = await fetch('/api/auth/users', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${adminToken}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(adUserData)
});

const { user } = await response.json();
console.log(`Created AD user: ${user.username}`);
```

## Error Handling

### Common Errors

**401 Unauthorized - Invalid Token**:
```json
{
  "error": "invalid_token",
  "message": "Invalid token"
}
```

**401 Unauthorized - Expired Token**:
```json
{
  "message": "Token has expired",
  "error": "token_expired"
}
```

**403 Forbidden - Insufficient Permissions**:
```json
{
  "message": "Unauthorized - admin only"
}
```

**404 Not Found - User Not Found**:
```json
{
  "message": "User not found"
}
```

**500 Internal Server Error**:
```json
{
  "message": "Internal server error"
}
```

### Error Handling Example
```javascript
try {
  const response = await fetch(`/api/auth/users/${username}`, {
    headers: {
      'Authorization': `Bearer ${accessToken}`
    }
  });

  if (!response.ok) {
    if (response.status === 404) {
      console.error('User not found');
    } else if (response.status === 401) {
      console.error('Authentication required - please login');
      // Redirect to login page
    } else if (response.status === 403) {
      console.error('Insufficient permissions');
    }
    return;
  }

  const { user } = await response.json();
  // Use user data...
} catch (error) {
  console.error('Network error:', error);
}
```

## Performance Considerations

- **Caching**: User data is queried directly from the database. Consider implementing client-side caching for frequently accessed user information.
- **Pagination**: The list users endpoint returns all matching users. For large user bases, consider adding pagination parameters.
- **Rate Limiting**: These endpoints are subject to the API rate limit configured in nginx (10 requests/second by default).

## Security Notes

1. **Password Exclusion**: Password hashes are never included in API responses
2. **Soft Delete**: Deleted users are excluded by default unless `include_deleted=true` is specified
3. **Role Verification**: User roles are verified on every request
4. **Token Validation**: All requests validate JWT tokens against Redis for revocation status

## Integration with Backend

While these endpoints are part of the auth service, they can complement the backend's user management:

- **Auth Service**: Lightweight user information for authentication context
- **Backend `/api/users`**: Full user management with department relationships

Choose the appropriate endpoint based on your needs:
- Use auth service for quick user lookups during authentication flows
- Use backend for comprehensive user management with department associations

## Related Documentation

- [User Authentication Types](./README_USER_TYPES.md) - Details on local vs AD vs SSO users
- [Auth Service API](./README.md) - Complete auth service documentation
- [JWT Token Management](./README_TOKENS.md) - Token lifecycle and management

## Changelog

### Version 1.2.0 (2025-10-11)
- Added `POST /api/auth/users` endpoint for creating new users (admin only)
- Support for creating local, AD, and SSO user types
- Validation for username and email uniqueness
- Password requirement enforcement for local users
- Password exclusion enforcement for AD/SSO users

### Version 1.1.0 (2025-10-11)
- Added `GET /api/auth/users/<username>` endpoint
- Added `GET /api/auth/users/id/<user_id>` endpoint
- Added `GET /api/auth/users` endpoint with filtering
- Integrated with user_type support (local/ad/sso)
