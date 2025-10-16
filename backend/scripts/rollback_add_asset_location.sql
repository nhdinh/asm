-- Rollback script for add_asset_location.sql
-- This script removes the location column from the assets table

-- Drop index first
DROP INDEX IF EXISTS idx_assets_location;

-- Drop location column
ALTER TABLE assets DROP COLUMN IF EXISTS location;
