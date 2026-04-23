-- WAL mode ended up growing exponentially which resulted in huge file sizes
PRAGMA journal_mode = DELETE;

-- Remove unused data from the table and try to make it smaller
VACUUM;

-- Assign the user version
PRAGMA user_version = 6;