-- Initialize Iceberg catalog database

-- Create schema for Iceberg catalog
CREATE SCHEMA IF NOT EXISTS iceberg;

-- Grant permissions
GRANT ALL PRIVILEGES ON SCHEMA iceberg TO iceberg;
GRANT ALL PRIVILEGES ON DATABASE iceberg_catalog TO iceberg;

-- Create tables for Iceberg catalog metadata (if needed)
-- Iceberg will create its own tables, but we can prepare the schema
