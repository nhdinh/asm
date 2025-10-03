# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Application Overview

This is an Asset Management System (AMS) built with a Flask-based microservices architecture:

- **Backend**: Flask REST API with SQLAlchemy ORM, JWT authentication, and PostgreSQL database
- **Frontend**: Flask web application serving HTML templates with session-based authentication
- **Database**: PostgreSQL with Redis for caching
- **Reverse Proxy**: Nginx for load balancing and SSL termination
- **Testing**: Selenium-based automated testing suite with pytest

## Architecture

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
export JWT_SECRET_KEY=your-secret-key
python src/backend.py

# Frontend setup
cd frontend
pip install -r requirements.txt
export API_BASE_URL=http://localhost:5000/api
export SECRET_KEY=your-frontend-secret
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

**Backend** ([backend/.env](backend/.env)):
- `POSTGRES_DB`: Database name (default: asset_man)
- `POSTGRES_HOST`: Database host (default: postgres)
- `POSTGRES_USER_FILE`: Path to file containing database username
- `POSTGRES_PASSWORD_FILE`: Path to file containing database password
- `JWT_SECRET_KEY`: Secret key for JWT token generation
- `LIMITED_LOGIN_LIMIT`: Max failed login attempts before lockout (default: 5)
- `LOGIN_BLOCKED_TIME`: Account lockout duration in minutes (default: 1)
- `FLASK_ENV`: Environment (production/development)

**Frontend**:
- `API_BASE_URL`: Backend API URL (default: http://backend:5000/api)
- `SECRET_KEY`: Session encryption key
- `TEMPLATE_PATH`: Path to templates directory (default: /app/templates)
- `FLASK_ENV`: Environment (production/development)

**Docker Compose** (.env in root):
- `BACKEND_JWT_SECRET_KEY`: JWT secret for backend
- `FRONTEND_APP_SECRET`: Session secret for frontend
- `POSTGRES_DB`: Database name
- `POSTGRES_DB_LOCATION`: Host path for database volume
- `REDIS_PASSWORD`: Redis authentication password

### Secrets Management
- All sensitive credentials stored in `.secrets/` directory (gitignored)
- Required secret files:
  - `.secrets/postgres_user.txt` - Database username
  - `.secrets/postgres_password.txt` - Database password
  - `.secrets/redis_password.txt` - Redis password
- Secrets mounted as Docker secrets in containers at `/run/secrets/`

### Docker Services
- **backend** (`ams-backend`): Flask API on port 5000
- **frontend** (`ams-frontend`): Web UI on port 3000
- **postgres** (`ams-postgres`): PostgreSQL database on port 5432
- **redis** (`ams-redis`): Redis cache on port 6379
- **nginx** (`ams-nginx`): Reverse proxy on ports 8080 (HTTP) and 443 (HTTPS)

### Health Checks
- Backend: `GET /api/health` (30s interval, 10s timeout, 3 retries, 40s start period)
- Frontend: `GET /health` (30s interval, 10s timeout, 3 retries, 40s start period)

### Nginx Configuration
- Configuration: [nginx/nginx.conf](nginx/nginx.conf)
- SSL certificates: [nginx/ssl/](nginx/ssl/)
- Logs: [nginx/logs/](nginx/logs/)

## Common Development Tasks

### Database Operations
- Models are auto-created via `db.create_all()` in [backend/src/app.py](backend/src/app.py) application factory
- Flask-Migrate integrated for schema migrations
- **Schema fixes**: If database schema is out of sync with models, run the migration script:
  ```bash
  # Apply schema fixes (adds missing columns)
  docker-compose exec postgres psql -U $(cat .secrets/postgres_user.txt) -d asset_man -f /app/scripts/fix_database_schema.sql

  # Or manually add missing columns:
  docker-compose exec postgres psql -U $(cat .secrets/postgres_user.txt) -d asset_man
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

### API Authentication Flow
1. Client sends credentials to `POST /api/auth/login`
2. Backend validates and returns JWT access token (24h expiration)
3. Client stores token and includes in subsequent requests via `Authorization: Bearer <token>` header
4. JWT verification via `@jwt_required()` decorator on protected endpoints
5. Failed login attempts tracked in UserActivity table
6. Account locked after configurable failed attempts for configurable duration

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
│   ├── nginx.conf              # Nginx configuration
│   ├── ssl/                    # SSL certificates
│   └── logs/                   # Nginx logs
├── postgres/
│   └── Dockerfile              # Custom PostgreSQL image
├── .secrets/                   # Secret files (gitignored)
├── docker-compose.yml          # Base Docker Compose
├── docker-compose.reload.yml   # Hot reload overlay
├── docker-compose.debug.yml    # Debug overlay
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
- Role-based access control (ADMIN, MANAGER)
- Failed login attempt tracking with temporary account lockout
- Session-based authentication in frontend with secure cookies

### Data Protection
- Database credentials stored in separate secret files
- Secrets mounted as Docker secrets (not environment variables)
- CORS enabled for API access control
- SQL injection protection via SQLAlchemy ORM
- Input validation on all API endpoints

### Network Security
- Nginx reverse proxy for SSL termination
- Internal Docker network for service communication
- Only necessary ports exposed to host
- Health check endpoints for monitoring

# Workflow
- The application is dockerized and running on http://localhost:8080/. Need to use `curl` to access the application.
- Default admin user and password is "admin" and "admin123". Default manager user and password is "manager" and "manager123". Use those user/password to work with the application.
- In frontend module, be sure to use ApiClient to make request to backend module, never use bare requests module to make request.
- Both the backend docker instance and frontend docker instance will be reloaded and restarted when python code changed, so no need to issue a command to reload docker upon every code changing. But when template file is changed, the frontend will not restarted and reloaded, so that the command to restart frontend docker instance need to be issued.
- When the backend docker instance is restarted, the log message "INFO in app: Asset Management API startup" is issued and following withs 2 lines of log contains debugger information
- When the frontend docker instance is restarted, the log message "INFO in app: Asset Management Frontend startup" is issued.
- In order to get correct log message from docker, be sure to clear log before make request, both with frontend and backend containers.