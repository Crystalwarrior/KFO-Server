DROP INDEX IF EXISTS idx_area_events_hub_id;
DROP INDEX IF EXISTS idx_area_events_area_id;

CREATE INDEX IF NOT EXISTS idx_area_events_ipid_time     ON area_events(ipid, event_time DESC, ooc_name);
CREATE INDEX IF NOT EXISTS idx_area_events_hub_area      ON area_events(hub_id, area_id, area_name);
CREATE INDEX IF NOT EXISTS idx_area_events_hub_name      ON area_events(hub_id, hub_name);
CREATE INDEX IF NOT EXISTS idx_area_events_hub_area_time ON area_events(hub_id, area_id, event_time DESC);
CREATE INDEX IF NOT EXISTS idx_area_events_subtype_time  ON area_events(event_subtype, event_time DESC);

CREATE INDEX IF NOT EXISTS idx_connect_events_ipid_time  ON connect_events(ipid, event_time DESC);
CREATE INDEX IF NOT EXISTS idx_misc_events_ipid_time     ON misc_events(ipid, event_time DESC);

CREATE INDEX IF NOT EXISTS idx_bans_ban_date             ON bans(ban_date DESC);
CREATE INDEX IF NOT EXISTS idx_ip_bans_ban_id            ON ip_bans(ban_id);
CREATE INDEX IF NOT EXISTS idx_hdid_bans_ban_id          ON hdid_bans(ban_id);

ANALYZE;

PRAGMA user_version = 8;
