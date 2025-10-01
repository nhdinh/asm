# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Application Overview

This is an Asset Management System (AMS) built with a Flask-based microservices architecture:

- **Backend**: Flask REST API with SQLAlchemy ORM, JWT authentication, and PostgreSQL database
- **Frontend**: Flask web application serving HTML templates with AJAX API calls
- **Database**: PostgreSQL with Redis for session caching
- **Reverse Proxy**: Nginx for load balancing and SSL termination
- **Testing**: Selenium-based automated testing suite

## Architecture

### Backend (Port 5000)
- **Entry Point**: `backend/src/backend.py`
- **Application Factory**: `backend/src/app.py` - main Flask app configuration
- **Models**: `backend/src/models.py` - SQLAlchemy models (User, Department, Asset, UserActivity)
- **Routes**: `backend/src/routes/` - API endpoints organized by feature:
  - `auth.py` - Authentication endpoints
  - `users.py` - User management
  - `departments.py` - Department management
  - `assets.py` - Asset management
  - `reports.py` - Reporting functionality

### Frontend (Port 3000)
- **Entry Point**: `frontend/src/frontend.py` - Flask web application
- **API Client**: `frontend/src/api_client.py` - HTTP client for backend communication
- **Templates**: `frontend/templates/` - Jinja2 HTML templates

### Database Models
- **User**: Username/email authentication with admin/manager roles
- **Department**: Organizational units with managers
- **Asset**: Equipment/items with categories, status, and department assignment
- **UserActivity**: Audit log for user actions

## Development Commands

### Docker Development (Recommended)

```bash
# Start all services in production mode
docker-compose up

# Development mode with hot reload
docker-compose -f docker-compose.yml -f docker-compose.reload.yml up

# Debug mode with debugpy on ports 5678 (backend) and 5679 (frontend)
docker-compose -f docker-compose.yml -f docker-compose.debug.yml up

# Database admin interface available at http://localhost:8081 (Adminer)
```

### Local Development

```bash
# Backend setup
cd backend
pip install -r requirements.txt
export FLASK_APP=src/backend.py
export FLASK_ENV=development
python src/backend.py

# Frontend setup
cd frontend
pip install -r requirements.txt
export FLASK_APP=frontend.py
export API_BASE_URL=http://localhost:5000
python -m gunicorn --bind 0.0.0.0:3000 --reload --workers 2 frontend:app
```

### Testing

```bash
# Run automated tests
cd automated_tests
pip install -r requirements.txt
pytest tests/
```

## Key Configuration

### Environment Variables
- **Backend**: `POSTGRES_*` for database connection, `JWT_SECRET_KEY` for authentication
- **Frontend**: `API_BASE_URL` for backend communication, `SECRET_KEY` for sessions
- **Database credentials**: Stored in `.secrets/` directory (not in repo)

### Docker Services
- **Backend**: `ams-backend` container
- **Frontend**: `ams-frontend` container
- **Database**: `ams-postgres` container
- **Cache**: `ams-redis` container
- **Proxy**: `ams-nginx` container

### Health Checks
- Backend: `GET /api/health`
- Frontend: `GET /health`

## Common Development Tasks

### Database Operations
- Models are auto-created via `db.create_all()` in app factory
- Use Flask-Migrate for schema changes: `flask db migrate` and `flask db upgrade`

### API Authentication
- JWT tokens required for most endpoints
- Admin role required for user/department management
- Session-based authentication in frontend with token storage

### Hot Reload Development
Use `docker-compose.reload.yml` overlay for automatic code reloading during development.