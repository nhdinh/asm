-- Add location field to assets table
-- This script adds a location column to track the physical location of assets

-- Add location column
ALTER TABLE assets ADD COLUMN IF NOT EXISTS location VARCHAR(255);

-- Add comment to the column
COMMENT ON COLUMN assets.location IS 'Physical location of the asset (e.g., "Building A, Room 101", "Warehouse Shelf B3")';

-- Create index on location for faster searches (optional, but recommended)
CREATE INDEX IF NOT EXISTS idx_assets_location ON assets(location);

-- Example: Update some test data (optional)
-- UPDATE assets SET location = 'Main Office' WHERE assigned_to_department = 1;
