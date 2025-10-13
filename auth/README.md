# Authentication Service

Dịch vụ xác thực tách biệt cho hệ thống Asset Management, hỗ trợ xác thực cục bộ (local) và Active Directory với cơ chế access token và refresh token.

## Tính năng

- **Xác thực đa nguồn**: Hỗ trợ cả xác thực local database và Active Directory
- **JWT Tokens**: Sử dụng access token (thời hạn ngắn) và refresh token (thời hạn dài)
- **Quản lý phiên**: Lưu trữ và quản lý session trong Redis
- **Bảo mật**: Khóa tài khoản sau nhiều lần đăng nhập sai, theo dõi login attempts
- **Revocation**: Hỗ trợ thu hồi token (logout), logout tất cả phiên
- **Active Directory**: Tích hợp LDAP/AD với tự động đồng bộ thông tin người dùng

## Kiến trúc

```
auth/
├── src/
│   ├── auth_service.py       # Flask application chính
│   ├── config.py             # Cấu hình service
│   ├── models.py             # Database models
│   ├── routes.py             # API endpoints
│   ├── token_manager.py      # Quản lý JWT tokens
│   └── ad_authenticator.py   # Xác thực Active Directory
├── scripts/
│   └── create_auth_tables.sql  # Database migration
├── Dockerfile
├── requirements.txt
└── .env
```

## API Endpoints

### POST /api/auth/login

Đăng nhập và nhận tokens

**Request:**

```json
{
  "username": "string",
  "password": "string",
  "auth_type": "local|ad" // optional, mặc định "local"
}
```

**Response:**

```json
{
  "access_token": "eyJhbGci...",
  "refresh_token": "eyJhbGci...",
  "expires_in": 3600,
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com",
    "fullname": "Administrator",
    "role": "ADMIN",
    "is_ad_user": false
  }
}
```

### POST /api/auth/refresh

Làm mới access token bằng refresh token

**Headers:**

```
Authorization: Bearer <refresh_token>
```

**Response:**

```json
{
  "access_token": "eyJhbGci...",
  "expires_in": 3600
}
```

### POST /api/auth/logout

Đăng xuất và thu hồi tokens

**Headers:**

```
Authorization: Bearer <access_token>
```

**Request (optional):**

```json
{
  "revoke_all": true // Thu hồi tất cả phiên
}
```

### POST /api/auth/verify

Xác minh token hợp lệ

**Headers:**

```
Authorization: Bearer <access_token>
```

**Response:**

```json
{
  "valid": true,
  "user": { ... }
}
```

### GET /api/auth/sessions

Lấy danh sách phiên đăng nhập đang hoạt động

**Headers:**

```
Authorization: Bearer <access_token>
```

**Response:**

```json
{
  "sessions": [
    {
      "jti": "uuid",
      "ip_address": "192.168.1.1",
      "user_agent": "Mozilla/5.0...",
      "created_at": "2025-01-01T00:00:00"
    }
  ]
}
```

### GET /api/auth/health

Health check endpoint

## Cấu hình

### Biến môi trường (.env)

```bash
# Flask
AUTH_SECRET_KEY=your-secret-key

# Database
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
BACKEND_DB=asset_management
POSTGRES_USER_FILE=/run/secrets/postgres_user
POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password

# JWT
JWT_SECRET_KEY=your-jwt-secret
JWT_ACCESS_TOKEN_HOURS=1
JWT_REFRESH_TOKEN_DAYS=30

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD_FILE=/run/secrets/redis_password

# Active Directory
AD_ENABLED=false
AD_SERVER=ad.domain.local
AD_PORT=389
AD_USE_SSL=false
AD_BASE_DN=DC=domain,DC=local
AD_USER_DN=CN={username},CN=Users,DC=domain,DC=local
AD_BIND_USER=CN=ServiceAccount,CN=Users,DC=domain,DC=local
AD_BIND_PASSWORD=

# Security
MAX_FAILED_LOGIN_ATTEMPTS=5
ACCOUNT_LOCKOUT_MINUTES=15
```

## Cài đặt

### 1. Tạo database tables

```bash
# Chạy migration script
docker-compose exec postgres psql -U <user> -d asset_management -f /path/to/create_auth_tables.sql

# Hoặc sử dụng script
cat auth/scripts/create_auth_tables.sql | docker-compose exec -T postgres psql -U <user> -d asset_management
```

### 2. Khởi động service

```bash
# Build và start auth service
docker-compose up -d auth

# Xem logs
docker-compose logs -f auth

# Kiểm tra health
curl http://localhost:8080/api/auth/health
```

## Tích hợp Active Directory

### Cấu hình AD

1. Bật AD trong `.env`:

```bash
AD_ENABLED=true
AD_SERVER=ad.company.local
AD_PORT=389
AD_BASE_DN=DC=company,DC=local
AD_USER_DN=CN={username},CN=Users,DC=company,DC=local
```

2. Tạo service account trong AD để bind:

```bash
AD_BIND_USER=CN=AppServiceAccount,CN=Users,DC=company,DC=local
AD_BIND_PASSWORD=SecurePassword123
```

### Luồng xác thực AD

1. User đăng nhập với `auth_type: "ad"`
2. Service kết nối AD server qua LDAP
3. Xác thực credentials với AD
4. Lấy thông tin user từ AD (email, fullname, groups)
5. Tự động tạo/cập nhật user trong database
6. Trả về tokens như bình thường

### Mapping AD Groups sang Roles

Người dùng từ AD mặc định có role `USER`. Admin cần thủ công cập nhật role trong database nếu cần.

## Token Flow

### Access Token

- Thời hạn: 1 giờ (cấu hình được)
- Lưu trong Redis với metadata
- Sử dụng cho mọi API request
- Tự động revoke khi refresh

### Refresh Token

- Thời hạn: 30 ngày (cấu hình được)
- Lưu trong cả Redis và PostgreSQL
- Chỉ dùng để làm mới access token
- Revoke khi logout

### Revocation Strategy

- Logout: Revoke cả access và refresh token của phiên
- Logout all: Revoke tất cả tokens của user
- Token được kiểm tra trong Redis trước khi cho phép truy cập

## Bảo mật

### Failed Login Protection

- Giới hạn số lần đăng nhập sai (mặc định: 5 lần)
- Khóa tài khoản tạm thời (mặc định: 15 phút)
- Theo dõi trong bảng `login_attempts`

### Password Policy

- Yêu cầu độ dài tối thiểu
- Bắt buộc chữ hoa, chữ thường, số, ký tự đặc biệt
- Hash bằng bcrypt

### Token Security

- JWT với signature verification
- JTI (JWT ID) duy nhất cho mỗi token
- Lưu trữ trong Redis với TTL
- Không lưu sensitive data trong token claims

## Monitoring

### Logs

- File: `auth/logs/auth_service.log`
- Rotating: 10MB max, 10 backups
- Level: INFO/ERROR

### Metrics

- Login attempts (success/failed)
- Active sessions per user
- Token refresh rate
- AD authentication latency

## Troubleshooting

### Service không khởi động

```bash
# Kiểm tra logs
docker-compose logs auth

# Kiểm tra kết nối Redis
docker-compose exec auth redis-cli -h redis -a <password> ping

# Kiểm tra kết nối database
docker-compose exec auth python -c "from src.models import db; print('DB OK')"
```

### AD authentication lỗi

```bash
# Test AD connection
docker-compose exec auth python -c "
from src.config import Config
from src.ad_authenticator import ActiveDirectoryAuthenticator
ad = ActiveDirectoryAuthenticator(Config)
print('AD Enabled:', ad.enabled)
"

# Kiểm tra AD server
telnet <AD_SERVER> 389
```

### Token không hợp lệ

- Kiểm tra JWT_SECRET_KEY khớp giữa auth service và các service khác
- Xác nhận token chưa hết hạn
- Kiểm tra token chưa bị revoke trong Redis

## Migration từ Backend cũ

Backend hiện tại vẫn có auth endpoints riêng. Để migrate:

1. **Dual mode**: Giữ cả 2 auth endpoints, chuyển dần sang auth service
2. **Update frontend**: Đổi API endpoint từ `/api/auth/login` sang `/api/auth/login`
3. **Token compatibility**: Đảm bảo JWT secret key đồng bộ
4. **Database**: Chia sẻ bảng `users`, thêm bảng `refresh_tokens` và `login_attempts`

## Development

### Local development

```bash
cd auth
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

pip install -r requirements.txt
python src/auth_service.py
```

### Testing

```bash
# Test login
curl -X POST http://localhost:5001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# Test verify
curl http://localhost:5001/api/auth/verify \
  -H "Authorization: Bearer <access_token>"

# Test refresh
curl -X POST http://localhost:5001/api/auth/refresh \
  -H "Authorization: Bearer <refresh_token>"
```

## License

Internal use only - Asset Management System
