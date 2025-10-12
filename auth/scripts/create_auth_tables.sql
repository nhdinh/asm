-- Create refresh_tokens table
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_jti VARCHAR(255) UNIQUE NOT NULL,
    access_token_jti VARCHAR(255) NOT NULL,
    ip_address VARCHAR(45),
    user_agent VARCHAR(512),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    is_revoked BOOLEAN DEFAULT FALSE NOT NULL,
    revoked_at TIMESTAMP
);

-- Create indexes for refresh_tokens
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token_jti ON refresh_tokens(token_jti);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_access_jti ON refresh_tokens(access_token_jti);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_is_revoked ON refresh_tokens(is_revoked);

-- Create login_attempts table
CREATE TABLE IF NOT EXISTS login_attempts (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    ip_address VARCHAR(45),
    success BOOLEAN DEFAULT FALSE,
    attempt_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    failure_reason VARCHAR(255)
);

-- Create indexes for login_attempts
CREATE INDEX IF NOT EXISTS idx_login_attempts_username ON login_attempts(username);
CREATE INDEX IF NOT EXISTS idx_login_attempts_time ON login_attempts(attempt_time);
CREATE INDEX IF NOT EXISTS idx_login_attempts_success ON login_attempts(success);

-- Add is_ad_user column to users table if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='users' AND column_name='is_ad_user') THEN
        ALTER TABLE users ADD COLUMN is_ad_user BOOLEAN DEFAULT FALSE;
    END IF;
END $$;

-- Allow null password_hash for AD users
DO $$
BEGIN
    ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL;
EXCEPTION
    WHEN others THEN NULL;
END $$;

-- Grant permissions (adjust as needed)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON refresh_tokens TO your_app_user;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON login_attempts TO your_app_user;
-- GRANT USAGE, SELECT ON SEQUENCE refresh_tokens_id_seq TO your_app_user;
-- GRANT USAGE, SELECT ON SEQUENCE login_attempts_id_seq TO your_app_user;
