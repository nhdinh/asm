CREATE USER asmdbuser WITH PASSWORD 'password';
 CREATE DATABASE asset_management;
 GRANT ALL PRIVILEGES ON DATABASE asset_management TO asmdbuser;
 
--  \connect vbvdb;
 
--  CREATE TABLE employees (
--      id SERIAL PRIMARY KEY,
--      name VARCHAR(100),
--      position VARCHAR(50),
--      salary DECIMAL(10, 2)
--  );
 
--  INSERT INTO employees (name, position, salary) VALUES
--  ('Bhuvi', 'Manager', 675000.00),
--  ('Vibhu', 'Developer', 555000.00),
--  ('Rudra', 'Analyst', 460000.00);
 
 GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO asmdbuser;