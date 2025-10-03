-- Database schema migration script
-- This script adds missing columns to tables to match the SQLAlchemy models

-- Add missing columns to user_activities table
ALTER TABLE user_activities ADD COLUMN IF NOT EXISTS username VARCHAR(50) NOT NULL DEFAULT '';
ALTER TABLE user_activities ADD COLUMN IF NOT EXISTS status activitystatus;
ALTER TABLE user_activities ADD COLUMN IF NOT EXISTS failed_count INTEGER DEFAULT 0;

-- Add missing columns to departments table
ALTER TABLE departments ADD COLUMN IF NOT EXISTS asset_count INTEGER DEFAULT 0;
ALTER TABLE departments ADD COLUMN IF NOT EXISTS user_count INTEGER DEFAULT 0;
ALTER TABLE departments ADD COLUMN IF NOT EXISTS total_value FLOAT DEFAULT 0.0;

-- Add missing columns to assets table
ALTER TABLE assets ADD COLUMN IF NOT EXISTS assigned_to_id INTEGER REFERENCES users(id);
ALTER TABLE assets ADD COLUMN IF NOT EXISTS condition_notes TEXT;

-- Verify changes
SELECT 'user_activities columns:' as info;
SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'user_activities' ORDER BY ordinal_position;

SELECT 'departments columns:' as info;
SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'departments' ORDER BY ordinal_position;

SELECT 'assets columns:' as info;
SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'assets' ORDER BY ordinal_position;
