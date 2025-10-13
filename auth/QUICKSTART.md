# Authentication Service - Quick Start Guide

## Cài đặt và khởi động

### 1. Chuẩn bị Database

Tạo các bảng cần thiết cho auth service:

```bash
# Từ thư mục gốc của project
cat auth/scripts/create_auth_tables.sql | docker-compose exec -T postgres psql -U $(cat .secrets/postgres_user.txt) -d asset_management
```

### 2. Khởi động Auth Service

```bash
# Build và start auth service
docker-compose up -d auth

# Kiểm tra logs
docker-compose logs -f auth

# Kiểm tra health
curl http://localhost:8080/api/auth/health
```

Expected response:

```json
{
  "status": "healthy",
  "service": "authentication"
}
```

## Sử dụng cơ bản

### 1. Đăng nhập (Local Authentication)

```bash
curl -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin123",
    "auth_type": "local"
  }'
```

Response:

```json
{
  "access_token": "eyJhbGci...",
  "refresh_token": "eyJhbGci...",
  "expires_in": 3600,
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com",
    "role": "ADMIN",
    "is_ad_user": false
  }
}
```

### 2. Sử dụng Access Token

```bash
# Lưu token vào biến
ACCESS_TOKEN="eyJhbGci..."

# Gọi API với token
curl http://localhost:8080/api/auth/verify \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### 3. Làm mới Access Token

```bash
REFRESH_TOKEN="eyJhbGci..."

curl -X POST http://localhost:8080/api/auth/refresh \
  -H "Authorization: Bearer $REFRESH_TOKEN"
```

Response:

```json
{
  "access_token": "eyJhbGci...",
  "expires_in": 3600
}
```

### 4. Đăng xuất

```bash
# Đăng xuất phiên hiện tại
curl -X POST http://localhost:8080/api/auth/logout \
  -H "Authorization: Bearer $ACCESS_TOKEN"

# Đăng xuất tất cả phiên
curl -X POST http://localhost:8080/api/auth/logout \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"revoke_all": true}'
```

### 5. Xem các phiên đang hoạt động

```bash
curl http://localhost:8080/api/auth/sessions \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

## Cấu hình Active Directory

### 1. Cập nhật .env

```bash
# Chỉnh sửa file .env ở thư mục gốc
vim .env
```

Thêm/cập nhật các dòng sau:

```bash
AD_ENABLED=true
AD_SERVER=ad.company.local
AD_PORT=389
AD_USE_SSL=false
AD_BASE_DN=DC=company,DC=local
AD_USER_DN=CN={username},CN=Users,DC=company,DC=local
AD_BIND_USER=CN=ServiceAccount,CN=Users,DC=company,DC=local
AD_BIND_PASSWORD=YourSecurePassword
```

### 2. Restart Auth Service

```bash
docker-compose restart auth
```

### 3. Đăng nhập với AD

```bash
curl -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john.doe",
    "password": "ADPassword123",
    "auth_type": "ad"
  }'
```

Người dùng AD sẽ được tự động tạo trong database với thông tin từ AD.

## Kiểm tra và Debug

### 1. Kiểm tra kết nối Redis

```bash
docker-compose exec auth python -c "
import redis
from src.config import Config
r = redis.Redis(
    host=Config.REDIS_HOST,
    port=Config.REDIS_PORT,
    password=Config.REDIS_PASSWORD,
    decode_responses=True
)
print('Redis ping:', r.ping())
"
```

### 2. Kiểm tra kết nối Database

```bash
docker-compose exec auth python -c "
from src.auth_service import app
with app.app_context():
    from src.models import db, User
    print('Users count:', User.query.count())
"
```

### 3. Kiểm tra AD Connection

```bash
docker-compose exec auth python -c "
from src.config import Config
from src.ad_authenticator import ActiveDirectoryAuthenticator
ad = ActiveDirectoryAuthenticator(Config)
print('AD Enabled:', ad.enabled)
print('AD Server:', Config.AD_SERVER)
"
```

### 4. Xem Logs

```bash
# Container logs
docker-compose logs -f auth

# File logs
tail -f auth/logs/auth_service.log
```

## Troubleshooting

### Lỗi: "Failed to connect to Redis"

**Nguyên nhân**: Redis chưa chạy hoặc sai password

**Giải pháp**:

```bash
# Kiểm tra Redis
docker-compose ps redis

# Test kết nối
docker-compose exec redis redis-cli -a $(cat .secrets/redis_password.txt) ping
```

### Lỗi: "Database connection failed"

**Nguyên nhân**: PostgreSQL chưa sẵn sàng hoặc sai credentials

**Giải pháp**:

```bash
# Kiểm tra PostgreSQL
docker-compose ps postgres

# Test kết nối
docker-compose exec postgres psql -U $(cat .secrets/postgres_user.txt) -d asset_management -c "SELECT 1;"
```

### Lỗi: "AD authentication failed"

**Nguyên nhân**: Cấu hình AD sai hoặc không kết nối được

**Giải pháp**:

```bash
# Test kết nối AD server
telnet <AD_SERVER> 389

# Kiểm tra cấu hình AD
docker-compose exec auth env | grep AD_
```

### Token không hợp lệ

**Nguyên nhân**: Token hết hạn hoặc bị revoke

**Giải pháp**:

```bash
# Verify token
curl http://localhost:8080/api/auth/verify \
  -H "Authorization: Bearer $ACCESS_TOKEN"

# Refresh token nếu access token hết hạn
curl -X POST http://localhost:8080/api/auth/refresh \
  -H "Authorization: Bearer $REFRESH_TOKEN"
```

## Tích hợp với Frontend/Backend

### Frontend Integration

```javascript
// Login
const response = await fetch("http://localhost:8080/api/auth/login", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    username: "admin",
    password: "admin123",
  }),
});

const data = await response.json();
localStorage.setItem("access_token", data.access_token);
localStorage.setItem("refresh_token", data.refresh_token);

// Use token in API requests
const apiResponse = await fetch("http://localhost:8080/api/some-endpoint", {
  headers: {
    Authorization: `Bearer ${localStorage.getItem("access_token")}`,
  },
});

// Refresh token when expired
async function refreshToken() {
  const response = await fetch("http://localhost:8080/api/auth/refresh", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${localStorage.getItem("refresh_token")}`,
    },
  });

  const data = await response.json();
  localStorage.setItem("access_token", data.access_token);
}
```

### Backend Integration

```python
from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity

@app.route('/api/protected')
@jwt_required()
def protected_route():
    current_profile_username = get_jwt_identity()
    # Use current_profile_id to fetch user details
    return {'user_id': current_profile_id}
```

## Performance Tips

1. **Token caching**: Access token được cache trong Redis, không cần query database mỗi request
2. **Connection pooling**: SQLAlchemy pool size = 10, recycle mỗi 1h
3. **Redis persistence**: Append-only mode enabled cho durability
4. **Nginx caching**: Static responses được cache tại reverse proxy

## Security Checklist

- [ ] Đổi `JWT_SECRET_KEY` trong production
- [ ] Đổi `AUTH_SECRET_KEY` trong production
- [ ] Sử dụng HTTPS trong production (enable nginx SSL config)
- [ ] Cấu hình rate limiting phù hợp
- [ ] Định kỳ rotate AD service account password
- [ ] Monitor failed login attempts
- [ ] Backup Redis data (AOF persistence)
- [ ] Sử dụng strong password policy
- [ ] Review và revoke unused refresh tokens định kỳ

## Monitoring

```bash
# Check active sessions count
docker-compose exec redis redis-cli -a $(cat .secrets/redis_password.txt) \
  KEYS "user_tokens:*" | wc -l

# Check failed login attempts (last 24h)
docker-compose exec postgres psql -U $(cat .secrets/postgres_user.txt) -d asset_management -c \
  "SELECT COUNT(*) FROM login_attempts WHERE success = false AND attempt_time > NOW() - INTERVAL '24 hours';"

# Check token refresh rate
docker-compose exec redis redis-cli -a $(cat .secrets/redis_password.txt) \
  KEYS "refresh_token:*" | wc -l
```
