-- AgentMessage Database Initialization Script
-- This script creates the necessary tables and indexes for AgentMessage

-- Enable UUID extension for generating unique identifiers
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create identities table
CREATE TABLE IF NOT EXISTS identities (
    did TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    capabilities JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_identities_name 
ON identities(name);

CREATE INDEX IF NOT EXISTS idx_identities_created_at 
ON identities(created_at);

CREATE INDEX IF NOT EXISTS idx_identities_updated_at 
ON identities(updated_at);

CREATE INDEX IF NOT EXISTS idx_identities_capabilities 
ON identities USING GIN(capabilities);

-- Create a function to automatically update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to automatically update updated_at
DROP TRIGGER IF EXISTS update_identities_updated_at ON identities;
CREATE TRIGGER update_identities_updated_at
    BEFORE UPDATE ON identities
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Create messages table for future message functionality
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sender_did TEXT NOT NULL,
    receiver_did TEXT NOT NULL,
    content JSONB NOT NULL,
    message_type TEXT DEFAULT 'text',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    read_at TIMESTAMP NULL,
    FOREIGN KEY (sender_did) REFERENCES identities(did) ON DELETE CASCADE,
    FOREIGN KEY (receiver_did) REFERENCES identities(did) ON DELETE CASCADE
);

-- Create indexes for messages table
CREATE INDEX IF NOT EXISTS idx_messages_sender_did 
ON messages(sender_did);

CREATE INDEX IF NOT EXISTS idx_messages_receiver_did 
ON messages(receiver_did);

CREATE INDEX IF NOT EXISTS idx_messages_created_at 
ON messages(created_at);

CREATE INDEX IF NOT EXISTS idx_messages_read_at 
ON messages(read_at);

-- Create a view for unread messages
CREATE OR REPLACE VIEW unread_messages AS
SELECT 
    m.*,
    s.name as sender_name,
    r.name as receiver_name
FROM messages m
JOIN identities s ON m.sender_did = s.did
JOIN identities r ON m.receiver_did = r.did
WHERE m.read_at IS NULL;

-- Insert some sample data (optional, for testing)
-- Uncomment the following lines if you want sample data
/*
INSERT INTO identities (did, name, description, capabilities) VALUES 
('did:example:agent1', 'Sample Agent 1', 'A sample agent for testing', '["chat", "analysis"]'),
('did:example:agent2', 'Sample Agent 2', 'Another sample agent', '["translation", "summarization"]')
ON CONFLICT (did) DO NOTHING;
*/

-- Grant necessary permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO agentmessage_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO agentmessage_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO agentmessage_user;

-- Print completion message
DO $$
BEGIN
    RAISE NOTICE 'AgentMessage database initialization completed successfully!';
END
$$;