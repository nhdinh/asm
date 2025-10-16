-- Rollback script to revert Asset column renaming
-- Reverts assigned_to_department to department_id and assigned_to_user to assigned_to_id

-- Start transaction
BEGIN;

-- Revert assigned_to_department to department_id
ALTER TABLE assets RENAME COLUMN assigned_to_department TO department_id;

-- Revert assigned_to_user to assigned_to_id
ALTER TABLE assets RENAME COLUMN assigned_to_user TO assigned_to_id;

-- Commit transaction
COMMIT;

-- Verify the changes
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'assets'
  AND column_name IN ('department_id', 'assigned_to_id')
ORDER BY column_name;
