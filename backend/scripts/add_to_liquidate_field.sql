-- Migration script to add to_liquidate field to assets table
-- Purpose: Allow marking bad assets for liquidation process

-- Add to_liquidate column to assets table
ALTER TABLE assets ADD COLUMN IF NOT EXISTS to_liquidate BOOLEAN NOT NULL DEFAULT FALSE;

-- Create an index for faster queries on to_liquidate field
CREATE INDEX IF NOT EXISTS idx_assets_to_liquidate ON assets(to_liquidate);

-- Optional: Add comment to document the field
COMMENT ON COLUMN assets.to_liquidate IS 'Flag indicating if the asset is marked for liquidation';

-- Display confirmation
SELECT 'Migration completed: to_liquidate field added to assets table' AS status;
