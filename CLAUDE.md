# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Application Overview

This is an Asset Management System (AMS) built with a Flask-based microservices architecture:

- **Authentication Service**: Dedicated JWT authentication service with Active Directory support (Port 5001)
- **Backend**: Flask REST API with SQLAlchemy ORM and PostgreSQL database (Port 5000)
- **Frontend**: Flask web application serving HTML templates with session-based authentication (Port 3000)
- **Database**: PostgreSQL with Redis for token storage and caching
- **Reverse Proxy**: Nginx for load balancing and SSL termination
- **Testing**: Selenium-based automated testing suite with pytest

## Architecture

### Authentication Service (Port 5001)

- **Entry Point**: [auth/src/auth_service.py](auth/src/auth_service.py) - Dedicated authentication microservice
- **Configuration**: [auth/src/config.py](auth/src/config.py) - Service configuration with AD settings
- **Models**: [auth/src/models.py](auth/src/models.py) - Authentication-specific models:
  - `User` - Minimal user model for authentication (shared with backend database)
  - `RefreshToken` - Refresh token storage with revocation support
  - `LoginAttempt` - Failed login tracking for account lockout
- **Components**:
  - [token_manager.py](auth/src/token_manager.py) - JWT access/refresh token management with Redis
  - [ad_authenticator.py](auth/src/ad_authenticator.py) - Active Directory/LDAP authentication
  - [routes.py](auth/src/routes.py) - Authentication API endpoints
- **Features**:
  - Dual authentication: Local database and Active Directory
  - Access tokens (1 hour) and refresh tokens (30 days)
  - Token revocation and session management
  - Account lockout after failed attempts
  - AD user auto-provisioning

### Backend (Port 5000)

- **Entry Point**: [backend/src/backend.py](backend/src/backend.py)
- **Application Factory**: [backend/src/app.py](backend/src/app.py) - Flask app configuration with extensions
- **Common Utilities**: [backend/src/common.py](backend/src/common.py) - Shared utilities and helpers
- **Models**: [backend/src/models.py](backend/src/models.py) - SQLAlchemy ORM models:
  - `User` - Authentication with bcrypt password hashing, admin/manager roles, many-to-many relationship with departments
  - `Department` - Organizational units with asset_count, user_count, and total_value tracking
  - `Asset` - Equipment/items with unique code, category, status (ACTIVE/DAMAGED/DISPOSED), department assignment, and optional user assignment
  - `AssetTransfer` - Transfer history tracking asset movements between departments
  - `UserActivity` - Audit log with action tracking, success/failed status, and failed login attempt counting
- **Routes**: [backend/src/routes/](backend/src/routes/) - API blueprints:
  - [auth.py](backend/src/routes/auth.py) - Login/logout with failed attempt tracking and temporary account lockout (configurable limits)
  - [users.py](backend/src/routes/users.py) - User CRUD operations (admin only)
  - [departments.py](backend/src/routes/departments.py) - Department CRUD operations (admin only)
  - [assets.py](backend/src/routes/assets.py) - Asset CRUD, transfer operations, and status updates
  - [reports.py](backend/src/routes/reports.py) - Analytics, reporting, and data export

### Frontend (Port 3000)

- **Entry Point**: [frontend/src/frontend.py](frontend/src/frontend.py) - Main Flask application with route handlers
- **Application Factory**: [frontend/src/app.py](frontend/src/app.py) - Flask app factory with configurable template path
- **API Client**: [frontend/src/api_client.py](frontend/src/api_client.py) - HTTP client wrapper for backend API communication with token management
- **Templates**: [frontend/templates/](frontend/templates/) - Jinja2 templates organized by feature:
  - [base.html](frontend/templates/base.html) - Base layout template with navigation
  - [dashboard.html](frontend/templates/dashboard.html) - Main dashboard with statistics
  - [users/](frontend/templates/users/) - User management views (list, create, edit)
  - [departments/](frontend/templates/departments/) - Department views (list, create, edit)
  - [assets/](frontend/templates/assets/) - Asset management views (list, create, edit, view)
  - [transfers/](frontend/templates/transfers/) - Asset transfer views
  - [reports/](frontend/templates/reports/) - Report generation and analytics views
  - [components/](frontend/templates/components/) - Reusable UI components

### Database Models Details

- **Enums**:
  - `UserRole`: ADMIN, MANAGER
  - `AssetStatus`: ACTIVE, DAMAGED, DISPOSED
  - `ActivityStatus`: FAILED, SUCCESS
- **Relationships**:
  - `user_departments`: Association table for many-to-many User-Department relationship with assigned_at timestamp
  - Users can belong to multiple departments
  - Assets belong to one department and can be assigned to one user
  - All models include created_at timestamps; Asset and UserActivity track additional temporal data

## Development Commands

### Docker Development (Recommended)

```bash
# Start all services in production mode
docker-compose up

# Start with detached mode
docker-compose up -d

# Stop all services
docker-compose down

# Development mode with hot reload (code changes auto-reload)
docker-compose -f docker-compose.yml -f docker-compose.reload.yml up

# Debug mode with debugpy on ports 5678 (backend) and 5679 (frontend)
docker-compose -f docker-compose.yml -f docker-compose.debug.yml up

# View logs
docker-compose logs -f [service_name]

# Rebuild containers
docker-compose build [service_name]
```

### Local Development

```bash
# Backend setup
cd backend
pip install -r requirements.txt
export FLASK_APP=src/backend.py
export FLASK_ENV=development
export POSTGRES_USER_FILE=path/to/.secrets/postgres_user.txt
export POSTGRES_PASSWORD_FILE=path/to/.secrets/postgres_password.txt
export BACKEND_JWT_SECRET=your-secret-key
python src/backend.py

# Frontend setup
cd frontend
pip install -r requirements.txt
export API_BASE_URL=http://localhost:5000/api
export FRONTEND_APP_SECRET=your-frontend-secret
python -m gunicorn --bind 0.0.0.0:3000 --reload --workers 2 src.frontend:app
```

### Testing

```bash
# Run automated tests with Selenium
cd automated_tests
pip install -r requirements.txt
pytest tests/

# Run specific test file
pytest tests/departments_test.py

# Run with verbose output
pytest -v tests/
```

## Key Configuration

### Environment Variables

**Root Environment File** (.env in project root):

Core application secrets and database configuration:

- `AUTH_DB`: Database name for Auth service (default: auth_db)
- `AUTH_JWT_SECRET`: JWT secret key for authentication service
- `AUTH_APP_SECRET`: Flask secret key for authentication service
- `BACKEND_DB`: Database name for Backend service (default: asset_management)
- `BACKEND_JWT_SECRET`: JWT secret key for backend service
- `FRONTEND_APP_SECRET`: Session secret key for frontend
- `REDIS_PASSWORD`: Redis authentication password
- `DB_LOCATION`: Host path for PostgreSQL database volume (default: ../asset_db/)

Active Directory configuration (optional):

- `AD_DOMAIN`: Active Directory domain name (default: ASSETMAN)
- `AD_REALM`: Active Directory realm (default: ASSETMAN.LOCAL)
- `AD_ADMIN_PASSWORD`: AD administrator password (default: Admin@123456)
- `AD_DEFAULT_PASSWORD`: AD default user password (default: User@123456)
- `AD_DNS_FORWARDER`: DNS forwarder for AD (default: 8.8.8.8)
- `AD_HOST_IP`: Static IP for AD container (default: 172.18.0.100)
- `AD_ENABLED`: Enable AD authentication in auth service (default: false)
- `AD_SERVER`: AD server hostname
- `AD_PORT`: AD server port (default: 389)
- `AD_USE_SSL`: Use SSL for AD connection (default: false)
- `AD_BASE_DN`: AD base Distinguished Name
- `AD_USER_DN`: AD user DN template
- `AD_BIND_USER`: AD bind user for service account
- `AD_BIND_PASSWORD`: AD bind password

**Authentication Service** (environment configured in docker-compose.yml):

- `FLASK_ENV`: Flask environment mode (default: production)
- `AUTH_APP_SECRET`: Flask secret key (from root .env)
- `AUTH_JWT_SECRET`: JWT secret key (from root .env)
- `AUTH_DB`: Database name (from root .env)
- `POSTGRES_HOST`: Database host (default: postgres)
- `POSTGRES_PORT`: Database port (default: 5432)
- `POSTGRES_USER_FILE`: Docker secret file path (default: /run/secrets/postgres_user)
- `POSTGRES_PASSWORD_FILE`: Docker secret file path (default: /run/secrets/postgres_password)
- `REDIS_HOST`: Redis server host (default: redis)
- `REDIS_PORT`: Redis server port (default: 6379)
- `REDIS_PASSWORD_FILE`: Docker secret file path (default: /run/secrets/redis_password)
- `JWT_ACCESS_TOKEN_MINS`: Access token expiration in minutes (default: 1440)
- `JWT_REFRESH_TOKEN_DAYS`: Refresh token expiration in days (default: 30)
- `AD_ENABLED`: Enable Active Directory authentication (default: false)
- `AD_SERVER`: Active Directory server hostname
- `AD_PORT`: AD port (default: 389)
- `AD_USE_SSL`: Use SSL for AD connection (default: false)
- `AD_BASE_DN`: Base Distinguished Name for AD searches
- `AD_USER_DN`: User DN template (e.g., CN={username},CN=Users,DC=domain,DC=local)
- `AD_BIND_USER`: Service account for AD binding
- `AD_BIND_PASSWORD`: Service account password
- `AD_USER_SEARCH_FILTER`: LDAP filter for user search (default: (sAMAccountName={username}))
- `AD_GROUP_SEARCH_FILTER`: LDAP filter for group search (default: (member={user_dn}))
- `MAX_FAILED_LOGIN_ATTEMPTS`: Max failed login attempts (default: 5)
- `ACCOUNT_LOCKOUT_MINUTES`: Account lockout duration in minutes (default: 15)
- `CORS_ORIGINS`: Allowed CORS origins, comma-separated (default: \*)

**Backend Service** (environment configured in docker-compose.yml):

- `FLASK_ENV`: Flask environment mode (default: production)
- `BACKEND_JWT_SECRET`: JWT secret key (from root .env)
- `BACKEND_DB`: Database name (from root .env)
- `POSTGRES_HOST`: Database host (default: postgres)
- `POSTGRES_USER_FILE`: Docker secret file path (default: /run/secrets/postgres_user)
- `POSTGRES_PASSWORD_FILE`: Docker secret file path (default: /run/secrets/postgres_password)
- `REDIS_HOST`: Redis server host (default: redis)
- `REDIS_PORT`: Redis server port (default: 6379)
- `REDIS_PASSWORD_FILE`: Docker secret file path (default: /run/secrets/redis_password)
- `USE_AUTH_SERVICE`: Enable authentication service integration (default: true)
- `AUTH_SERVICE_URL`: Authentication service URL (default: http://auth:5001/api/auth)

**Frontend Service** (environment configured in docker-compose.yml):

- `FLASK_ENV`: Flask environment mode (default: production)
- `API_BASE_URL`: Backend API URL (default: http://backend:5000/api)
- `FRONTEND_APP_SECRET`: Session encryption key (from root .env)
- `TEMPLATE_PATH`: Path to templates directory (default: /app/templates)

**Email Worker Service** (environment configured in docker-compose.yml):

- `FLASK_ENV`: Flask environment mode (default: production)
- `BACKEND_JWT_SECRET`: JWT secret (from root .env)
- `BACKEND_DB`: Database name (from root .env)
- `POSTGRES_USER_FILE`: Docker secret file path (default: /run/secrets/postgres_user)
- `POSTGRES_PASSWORD_FILE`: Docker secret file path (default: /run/secrets/postgres_password)
- `REDIS_HOST`: Redis server host (default: redis)
- `REDIS_PORT`: Redis server port (default: 6379)
- `REDIS_PASSWORD_FILE`: Docker secret file path (default: /run/secrets/redis_password)
- `EMAIL_WORKER_POLL_INTERVAL`: Seconds between queue polls (default: 5)
- `EMAIL_WORKER_BATCH_SIZE`: Max tasks to process per iteration (default: 10)
- `EMAIL_WORKER_ONE_SHOT`: Run once and exit, for testing (default: false)

**Samba AD Service** (environment configured in docker-compose.yml):

- `DOMAIN`: Active Directory domain name (from root .env, default: ASSETMAN)
- `REALM`: Active Directory realm (from root .env, default: ASSETMAN.LOCAL)
- `ADMIN_PASSWORD`: Administrator password (from root .env, default: Admin@123456)
- `DEFAULT_PASSWORD`: Default user password (from root .env, default: User@123456)
- `DNS_FORWARDER`: DNS forwarder address (from root .env, default: 8.8.8.8)
- `HOST_IP`: Static IP address for container (from root .env, default: 172.18.0.100)

**Automated Tests** (automated_tests/.env):

- `user`: Regular user username for testing (default: admin)
- `user_password`: Regular user password for testing (default: admin123)
- `admin`: Admin username for testing (default: admin)
- `admin_password`: Admin password for testing (default: admin123)

### Secrets Management

- All sensitive credentials stored in `.secrets/` directory (gitignored)
- Required secret files:
  - `.secrets/postgres_user.txt` - Database username
  - `.secrets/postgres_password.txt` - Database password
  - `.secrets/redis_password.txt` - Redis password
  - `.secrets/smtp_password.txt` - SMTP server password (for email functionality)
- Secrets mounted as Docker secrets in containers at `/run/secrets/`
- Docker secrets are referenced in docker-compose.yml and mounted at runtime

### Docker Services

- **auth** (`ams-auth`): Authentication service on port 5001
- **backend** (`ams-backend`): Flask API on port 5000
- **frontend** (`ams-frontend`): Web UI on port 3000
- **postgres** (`ams-postgres`): PostgreSQL database on port 5432
- **redis** (`ams-redis`): Redis cache and token storage on port 6379
- **nginx** (`ams-nginx`): Reverse proxy on ports 8080 (HTTP) and 443 (HTTPS)
- **email_worker** (`ams-email-worker`): Background email service for processing email queue
- **mailhog** (`ams-mailhog`): Email testing tool on ports 1025 (SMTP) and 8025 (Web UI)
- **samba-ad** (`ams-samba-ad`): Active Directory testing environment on ports 10053 (DNS), 10088 (Kerberos), 10389 (LDAP), 10445 (SMB), 10464 (Kerberos Password), 10636 (LDAPS), 13268 (Global Catalog), 13269 (Global Catalog SSL)

### Health Checks

- Auth: `GET /api/auth/health` (30s interval, 10s timeout, 3 retries, 40s start period)
- Backend: `GET /api/health` (30s interval, 10s timeout, 3 retries, 40s start period)
- Frontend: `GET /health` (30s interval, 10s timeout, 3 retries, 40s start period)

### Nginx Configuration

- Configuration: [nginx/nginx.conf](nginx/nginx.conf)
- SSL certificates: [nginx/ssl/](nginx/ssl/)
- Logs: [nginx/logs/](nginx/logs/)

## Common Development Tasks

### Database Operations

- Models are auto-created via `db.create_all()` in [backend/src/app.py](backend/src/app.py) and [auth/src/auth_service.py](auth/src/auth_service.py)
- Flask-Migrate integrated for schema migrations
- **Auth Service Setup**: First time setup requires creating auth tables:

  ```bash
  # Create auth service tables (refresh_tokens, login_attempts)
  cat auth/scripts/create_auth_tables.sql | docker-compose exec -T postgres psql -U $(cat .secrets/postgres_user.txt) -d asset_management

  # Or interactively:
  docker-compose exec postgres psql -U $(cat .secrets/postgres_user.txt) -d asset_management
  # Then paste SQL from auth/scripts/create_auth_tables.sql
  ```

- **Schema fixes**: If database schema is out of sync with models, run the migration script:

  ```bash
  # Apply schema fixes (adds missing columns)
  docker-compose exec postgres psql -U $(cat .secrets/postgres_user.txt) -d asset_management -f /app/scripts/fix_database_schema.sql

  # Or manually add missing columns:
  docker-compose exec postgres psql -U $(cat .secrets/postgres_user.txt) -d asset_management
  # Then run SQL commands from backend/scripts/fix_database_schema.sql
  ```

- Database migrations:
  ```bash
  cd backend
  flask db init          # Initialize migrations (first time only)
  flask db migrate -m "description"  # Generate migration
  flask db upgrade       # Apply migration
  flask db downgrade     # Rollback migration
  ```
- **Default admin user**: username: `admin`, password: `admin123`
- **Default manager user**: username: `manager`, password: `manager123`

### API Authentication Flow (New - Auth Service)

1. Client sends credentials to `POST /api/auth/login` (routed to auth service via nginx)
2. Auth service validates credentials (local DB or Active Directory)
3. Returns JWT access token (1h) and refresh token (30d)
4. Client stores tokens and includes access token in requests via `Authorization: Bearer <token>` header
5. JWT verification via `@jwt_required()` decorator on protected endpoints
6. Token validation checked against Redis (revocation support)
7. Failed login attempts tracked in `login_attempts` table
8. Account locked after configurable failed attempts for configurable duration
9. Access token refresh using `POST /api/auth/refresh` with refresh token
10. Logout revokes tokens via `POST /api/auth/logout`

### Legacy Authentication Flow (Backend - Deprecated)

1. Client sends credentials to `POST /api/auth/login` (old endpoint in backend)
2. Backend validates and returns JWT access token (24h expiration)
3. Client stores token and includes in subsequent requests via `Authorization: Bearer <token>` header
4. JWT verification via `@jwt_required()` decorator on protected endpoints
5. Failed login attempts tracked in UserActivity table
6. Account locked after configurable failed attempts for configurable duration

**Note**: Migrate to new auth service for enhanced security and AD support

### Frontend Authentication Flow

1. User submits login form to `/login` route
2. Frontend calls backend API via ApiClient
3. JWT token stored in Flask session
4. ApiClient automatically includes token in API requests
5. Protected routes use `@login_required` and `@admin_required` decorators

### API Authorization

- **Public endpoints**: Login, health check
- **Authenticated endpoints**: Most read operations, asset operations
- **Admin-only endpoints**: User management, department management, system configuration
- Role checks performed via `get_jwt_identity()` and user role validation

### Hot Reload Development

- Use `docker-compose.reload.yml` overlay for automatic code reloading
- Backend and frontend source directories mounted as volumes
- Changes to Python files trigger automatic reload via Gunicorn `--reload` flag
- Template changes reflected immediately (no restart needed)

### Debugging

- Use `docker-compose.debug.yml` overlay to enable debugpy
- Backend debugger: Port 5678
- Frontend debugger: Port 5679
- Configure your IDE to attach to remote Python debugger on these ports

### Log Files

- Backend logs: [backend/logs/backend.log](backend/logs/) (rotating, 10MB max, 10 backups)
- Frontend logs: [frontend/logs/frontend.log](frontend/logs/) (rotating, 10MB max, 10 backups)
- Nginx logs: [nginx/logs/](nginx/logs/)
- Log level: INFO in production, DEBUG in development

## Project Structure

```
asset_man/
├── auth/                       # Authentication Service
│   ├── src/
│   │   ├── auth_service.py     # Entry point
│   │   ├── config.py           # Configuration
│   │   ├── models.py           # Auth models (User, RefreshToken, LoginAttempt)
│   │   ├── routes.py           # Auth API endpoints
│   │   ├── token_manager.py    # JWT token management with Redis
│   │   └── ad_authenticator.py # Active Directory integration
│   ├── scripts/
│   │   └── create_auth_tables.sql  # Database migration
│   ├── logs/                   # Log files
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env                    # Auth service config
│   └── README.md               # Auth service documentation
├── backend/
│   ├── src/
│   │   ├── app.py              # Application factory
│   │   ├── backend.py          # Entry point
│   │   ├── common.py           # Shared utilities
│   │   ├── models.py           # Database models
│   │   └── routes/             # API blueprints
│   ├── data/                   # Application data
│   ├── logs/                   # Log files
│   ├── scripts/                # Utility scripts
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app.py              # Application factory
│   │   ├── frontend.py         # Entry point with routes
│   │   └── api_client.py       # Backend API client
│   ├── templates/              # Jinja2 templates
│   ├── logs/                   # Log files
│   ├── Dockerfile
│   └── requirements.txt
├── automated_tests/
│   ├── tests/                  # Test files
│   ├── pages/                  # Page object models
│   ├── data/                   # Test data
│   ├── screenshots/            # Test screenshots
│   └── requirements.txt
├── nginx/
│   ├── nginx.conf              # Nginx configuration (with auth routing)
│   ├── ssl/                    # SSL certificates
│   └── logs/                   # Nginx logs
├── postgres/
│   └── Dockerfile              # Custom PostgreSQL image
├── .secrets/                   # Secret files (gitignored)
├── docker-compose.yml          # Base Docker Compose (includes auth service)
├── docker-compose.reload.yml   # Hot reload overlay
├── docker-compose.debug.yml    # Debug overlay
├── .env                        # Environment variables
└── CLAUDE.md                   # This file
```

## Testing Strategy

### Automated Tests

- Framework: Selenium WebDriver with pytest
- Base test class: [automated_tests/tests/base_test.py](automated_tests/tests/base_test.py)
- Test files:
  - [departments_test.py](automated_tests/tests/departments_test.py) - Department CRUD tests
- Page Object Model pattern for maintainability
- Screenshots captured on test failures in [automated_tests/screenshots/](automated_tests/screenshots/)
- Session persistence via cookie.pkl for authenticated tests

### Test Execution

```bash
cd automated_tests
pytest tests/                    # Run all tests
pytest tests/departments_test.py # Run specific test
pytest -v                        # Verbose output
pytest --tb=short               # Short traceback
```

## Security Considerations

### Authentication & Authorization

- Passwords hashed using bcrypt with automatic salt generation
- JWT tokens for API authentication (24h expiration)
- Role-based access control (ADMIN, USER)
- Failed login attempt tracking with temporary account lockout
- Session-based authentication in frontend with secure cookies

### Data Protection

- Database credentials stored in separate secret files
- Secrets mounted as Docker secrets (not environment variables)
- CORS enabled for API access control
- SQL injection protection via SQLAlchemy ORM
- Input validation on all API endpoints
- Endpoint with multiple SQL query must be place under Flask app context

### Network Security

- Nginx reverse proxy for SSL termination
- Internal Docker network for service communication
- Only necessary ports exposed to host
- Health check endpoints for monitoring

# Workflow

- Temporary token for admin, manager and user saved on /tmp/admin_tok.txt, /tmp/manager_tok.txt and /tmp/user_tok.txt expectively. Login with the saved token first. If the backend response that the token has expire, then make a request with `curl -s -X POST http://localhost:8080/api/auth/login -H "Content-Type: application/json" -d "{\"username\":\"$username\",\"password\":\"$password\"}"` to get the refresh token. Ensure that the token should be saved for further command.
- Ensure that the param `-f docker-compose.yml -f docker-compose.reload.yml` be used when operating containers with docker-compose
- The application is dockerized and running on http://localhost:8080/. Need to use `curl` to access the application.
- In frontend module, be sure to use ApiClient to make request to backend module, never use bare requests module to make request.
- Both the backend docker instance and frontend docker instance will be reloaded and restarted when python code changed, so no need to issue a command to reload docker upon every code changing. But when template file is changed, the frontend will not restarted and reloaded, so that the command to restart frontend docker instance need to be issued.
- When the backend docker instance is restarted, the docker log message "INFO in app: Asset Management Backend API startup" is issued and following withs 2 lines of log contains debugger information
- When the frontend docker instance is restarted, the docker log message "INFO in app: Asset Management Frontend startup" is issued.
- In order to get correct log message from docker, be sure to clear log before make request, both with frontend and backend containers.
- In anytime the template frontend\templates\*\*.html file is edited, ensure that the frontend container is restart to load changes.
- Don't insert more users and departments when working with application
