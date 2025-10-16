-- Migration script to rename Asset columns
-- Renames department_id to assigned_to_department and assigned_to_id to assigned_to_user

-- Start transaction
BEGIN;

-- Rename department_id to assigned_to_department
ALTER TABLE assets RENAME COLUMN department_id TO assigned_to_department;

-- Rename assigned_to_id to assigned_to_user
ALTER TABLE assets RENAME COLUMN assigned_to_id TO assigned_to_user;

-- Commit transaction
COMMIT;

-- Verify the changes
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'assets'
  AND column_name IN ('assigned_to_department', 'assigned_to_user')
ORDER BY column_name;
