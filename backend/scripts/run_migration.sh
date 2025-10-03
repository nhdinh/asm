#!/bin/bash
# Database migration script runner
# This script applies database schema fixes to ensure compatibility with SQLAlchemy models

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "🔧 Running database migration..."
echo "Project root: $PROJECT_ROOT"

# Read database credentials
DB_USER=$(cat "$PROJECT_ROOT/.secrets/postgres_user.txt")
DB_NAME=${POSTGRES_DB:-asset_man}

# Run migration script
docker-compose exec postgres psql -U "$DB_USER" -d "$DB_NAME" -f /docker-entrypoint-initdb.d/fix_database_schema.sql

echo "✅ Migration completed successfully!"
