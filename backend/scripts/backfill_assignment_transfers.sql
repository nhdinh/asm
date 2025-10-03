-- Backfill transfer records for existing asset assignments
-- This creates historical transfer records for assets that were already assigned to users

-- Create transfer records for all currently assigned assets that don't have transfer records yet
INSERT INTO asset_transfers (asset_id, to_department_id, assigned_to_id, transferred_by, transfer_date, notes)
SELECT
    a.id as asset_id,
    a.department_id as to_department_id,
    a.assigned_to_id,
    1 as transferred_by,  -- Default to admin user
    a.created_at as transfer_date,
    'Bàn giao tài sản (dữ liệu cũ)' as notes
FROM assets a
WHERE a.assigned_to_id IS NOT NULL
AND NOT EXISTS (
    SELECT 1 FROM asset_transfers at
    WHERE at.asset_id = a.id
    AND at.assigned_to_id = a.assigned_to_id
);

-- Show results
SELECT
    at.id,
    a.code as asset_code,
    u.fullname as assigned_to,
    at.notes,
    at.transfer_date
FROM asset_transfers at
JOIN assets a ON at.asset_id = a.id
LEFT JOIN users u ON at.assigned_to_id = u.id
WHERE at.assigned_to_id IS NOT NULL
ORDER BY at.transfer_date DESC;
