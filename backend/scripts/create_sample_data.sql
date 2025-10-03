-- Sample data creation script for Asset Management System
-- This script creates test users, departments, and assets

-- Create additional users (password: admin123 for all)
-- Password hash for 'admin123': generated using bcrypt
INSERT INTO users (username, email, password_hash, role, created_at) VALUES
('manager1', 'manager1@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYzpLY4qy3y', 'MANAGER', NOW()),
('manager2', 'manager2@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYzpLY4qy3y', 'MANAGER', NOW())
ON CONFLICT (username) DO NOTHING;

-- Assign managers to departments (many-to-many)
INSERT INTO user_departments (user_id, department_id, assigned_at)
SELECT u.id, d.id, NOW()
FROM users u, departments d
WHERE u.username = 'manager1' AND d.name = 'IT Department'
ON CONFLICT DO NOTHING;

INSERT INTO user_departments (user_id, department_id, assigned_at)
SELECT u.id, d.id, NOW()
FROM users u, departments d
WHERE u.username = 'manager2' AND d.name IN ('HR Department', 'Finance Department')
ON CONFLICT DO NOTHING;

-- Create sample assets
INSERT INTO assets (code, name, description, category, purchase_value, purchase_date, department_id, status, created_at)
SELECT
    'LAPTOP-' || LPAD(s::text, 4, '0'),
    'Laptop Dell ' || s,
    'Dell Latitude ' || s || ' business laptop',
    'Computer',
    25000000,
    CURRENT_DATE - (s * 30 || ' days')::interval,
    (SELECT id FROM departments WHERE name = 'IT Department'),
    'ACTIVE',
    NOW()
FROM generate_series(1, 5) AS s
ON CONFLICT (code) DO NOTHING;

INSERT INTO assets (code, name, description, category, purchase_value, purchase_date, department_id, status, created_at)
SELECT
    'DESK-' || LPAD(s::text, 4, '0'),
    'Office Desk ' || s,
    'Ergonomic office desk',
    'Furniture',
    5000000,
    CURRENT_DATE - (s * 60 || ' days')::interval,
    (SELECT id FROM departments WHERE name = 'HR Department'),
    'ACTIVE',
    NOW()
FROM generate_series(1, 3) AS s
ON CONFLICT (code) DO NOTHING;

INSERT INTO assets (code, name, description, category, purchase_value, purchase_date, department_id, status, created_at)
SELECT
    'PRINTER-' || LPAD(s::text, 4, '0'),
    'Printer HP ' || s,
    'HP LaserJet printer',
    'Equipment',
    8000000,
    CURRENT_DATE - (s * 45 || ' days')::interval,
    (SELECT id FROM departments WHERE name = 'Finance Department'),
    CASE WHEN s % 3 = 0 THEN 'DAMAGED'::assetstatus ELSE 'ACTIVE'::assetstatus END,
    NOW()
FROM generate_series(1, 4) AS s
ON CONFLICT (code) DO NOTHING;

INSERT INTO assets (code, name, description, category, purchase_value, purchase_date, department_id, status, created_at)
SELECT
    'PROJ-' || LPAD(s::text, 4, '0'),
    'Projector ' || s,
    'Digital projector for presentations',
    'Equipment',
    15000000,
    CURRENT_DATE - (s * 90 || ' days')::interval,
    (SELECT id FROM departments WHERE name = 'Marketing Department'),
    'ACTIVE',
    NOW()
FROM generate_series(1, 2) AS s
ON CONFLICT (code) DO NOTHING;

-- Update department statistics
UPDATE departments SET
    asset_count = (SELECT COUNT(*) FROM assets WHERE department_id = departments.id),
    user_count = (SELECT COUNT(*) FROM user_departments WHERE department_id = departments.id),
    total_value = (SELECT COALESCE(SUM(purchase_value), 0) FROM assets WHERE department_id = departments.id);

-- Display summary
SELECT 'Users created:' as info, COUNT(*) as count FROM users;
SELECT 'Departments:' as info, COUNT(*) as count FROM departments;
SELECT 'Assets created:' as info, COUNT(*) as count FROM assets;
SELECT 'Asset value by department:' as info;
SELECT d.name, COUNT(a.id) as asset_count, COALESCE(SUM(a.purchase_value), 0) as total_value
FROM departments d
LEFT JOIN assets a ON d.id = a.department_id
GROUP BY d.id, d.name
ORDER BY d.name;
