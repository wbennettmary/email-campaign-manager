-- Initialize the Campaign Manager Database
-- This script sets up the initial database schema with optimizations

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- Set optimal database configuration
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET work_mem = '4MB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET effective_io_concurrency = 200;

-- Reload configuration
SELECT pg_reload_conf();

-- Create optimized sequences
CREATE SEQUENCE IF NOT EXISTS email_log_id_seq;

-- Grant necessary permissions
GRANT ALL PRIVILEGES ON DATABASE campaign_db TO campaign_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO campaign_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO campaign_user;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO campaign_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO campaign_user;

-- Optimize for email log partitioning (will be created by SQLAlchemy)
-- This is just a preparation script