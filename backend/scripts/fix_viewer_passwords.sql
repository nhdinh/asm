-- Fix viewer passwords with proper bcrypt hashes
-- Password for both viewers: admin123

UPDATE users
SET password_hash = '$2b$12$8qglaRpqcUqQ5kynYxoZh.N0lp607GdsTpYpOrYUOraqj5hH.YvYe'
WHERE username IN ('viewer1', 'viewer2');

-- Verify
SELECT id, username, length(password_hash) as hash_length
FROM users
WHERE username IN ('viewer1', 'viewer2');
