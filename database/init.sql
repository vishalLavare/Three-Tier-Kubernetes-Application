-- PostgreSQL Database Initialization Script
-- Creates the users table and inserts sample data for testing the three-tier application

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    role VARCHAR(50) DEFAULT 'user',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Clean up any existing data (if re-run)
TRUNCATE TABLE users RESTART IDENTITY CASCADE;

-- Insert sample records
INSERT INTO users (name, email, role) VALUES
('Alice Smith', 'alice.smith@example.com', 'Administrator'),
('Bob Jones', 'bob.jones@example.com', 'Developer'),
('Charlie Brown', 'charlie.brown@example.com', 'User'),
('Diana Prince', 'diana.prince@example.com', 'Manager'),
('Evan Wright', 'evan.wright@example.com', 'User');
