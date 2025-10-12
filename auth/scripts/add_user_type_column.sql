-- Add user_type column to users table
-- This migration adds support for different authentication types (local, AD, SSO)

-- Add user_type column with default value 'local'
ALTER TABLE users ADD COLUMN IF NOT EXISTS user_type VARCHAR(20) NOT NULL DEFAULT 'local';

-- Update existing AD users based on is_ad_user flag
UPDATE users SET user_type = 'ad' WHERE is_ad_user = true;

-- Create index for faster user_type queries
CREATE INDEX IF NOT EXISTS idx_users_user_type ON users(user_type);

-- Add comment to document the column
COMMENT ON COLUMN users.user_type IS 'Authentication type: local, ad (Active Directory), or sso (Single Sign-On)';

-- Verify the migration
SELECT
    user_type,
    COUNT(*) as user_count,
    COUNT(CASE WHEN is_ad_user THEN 1 END) as ad_flag_count
FROM users
GROUP BY user_type;
