-- Fix SQLAlchemy enum cache issue by recreating the userrole enum type
-- This resolves the issue where SQLAlchemy doesn't recognize dynamically added enum values

-- 1. Backup existing users (safety measure)
CREATE TABLE IF NOT EXISTS users_backup AS SELECT * FROM users;

-- 2. Convert role column to VARCHAR temporarily
ALTER TABLE users ALTER COLUMN role TYPE VARCHAR(20);

-- 3. Drop and recreate enum with all values
DROP TYPE IF EXISTS userrole;
CREATE TYPE userrole AS ENUM ('admin', 'manager', 'viewer');

-- 4. Restore enum column type with proper casting
ALTER TABLE users ALTER COLUMN role TYPE userrole USING role::userrole;

-- 5. Verify viewer users exist
SELECT id, username, email, role FROM users WHERE role = 'viewer';

-- 6. Show all users
SELECT id, username, email, role FROM users ORDER BY role, username;
