-- Remove unused data from the table and try to make it smaller
VACUUM;

-- Allow concurrent reads while the server is running
PRAGMA journal_mode = WAL;

-- funky indexes for faster queries on area_events
CREATE INDEX idx_area_events_hub_id ON area_events(hub_id);
CREATE INDEX idx_area_events_composite ON area_events(hub_id, event_time);

-- Assign the user version to 4
PRAGMA user_version = 5;