-- Initialize databases for AI Finance Platform

-- Create test database
CREATE DATABASE ai_finance_platform_test;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE ai_finance_platform TO postgres;
GRANT ALL PRIVILEGES ON DATABASE ai_finance_platform_test TO postgres;

-- Connect to main database and set up extensions
\c ai_finance_platform;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Connect to test database and set up extensions
\c ai_finance_platform_test;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
