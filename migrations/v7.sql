-- Re-enable WAL mode for concurrent reads during writes.
-- This allows the admin panel to query logs while the server is running.
PRAGMA journal_mode = WAL;

-- Checkpoint the WAL periodically to prevent unbounded growth.
-- 1000 pages (~4MB with default 4KB pages) is a reasonable threshold.
PRAGMA wal_autocheckpoint = 1000;

-- Additional indexes for common admin panel query patterns
CREATE INDEX IF NOT EXISTS idx_area_events_event_time ON area_events(event_time);
CREATE INDEX IF NOT EXISTS idx_area_events_area_id ON area_events(hub_id, area_id);
CREATE INDEX IF NOT EXISTS idx_area_events_event_subtype ON area_events(event_subtype);
CREATE INDEX IF NOT EXISTS idx_area_events_ipid ON area_events(ipid);
CREATE INDEX IF NOT EXISTS idx_connect_events_event_time ON connect_events(event_time);
CREATE INDEX IF NOT EXISTS idx_misc_events_event_time ON misc_events(event_time);

-- Assign the user version
PRAGMA user_version = 7;
