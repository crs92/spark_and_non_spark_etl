-- Initialize Iceberg catalog database
CREATE DATABASE IF NOT EXISTS iceberg_catalog;
CREATE USER IF NOT EXISTS iceberg WITH PASSWORD 'iceberg123';
GRANT ALL PRIVILEGES ON DATABASE iceberg_catalog TO iceberg;

-- Create schema for Iceberg tables
\c iceberg_catalog;
CREATE SCHEMA IF NOT EXISTS iceberg;
GRANT ALL ON SCHEMA iceberg TO iceberg;
