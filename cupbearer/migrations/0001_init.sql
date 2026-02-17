CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    direction TEXT NOT NULL,
    source TEXT NOT NULL,
    type TEXT NOT NULL,
    payload TEXT NOT NULL,
    idempotency_key TEXT,
    thread_id TEXT,
    contact_id TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_events_idempotency_key
    ON events(idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE TRIGGER IF NOT EXISTS trg_events_no_update
BEFORE UPDATE ON events
BEGIN
    SELECT RAISE(ABORT, 'events are immutable');
END;

CREATE TRIGGER IF NOT EXISTS trg_events_no_delete
BEFORE DELETE ON events
BEGIN
    SELECT RAISE(ABORT, 'events are immutable');
END;

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 5,
    available_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_error TEXT,
    idempotency_key TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_idempotency_key
    ON jobs(idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE TABLE IF NOT EXISTS contacts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    channel TEXT NOT NULL,
    address TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_contacts_channel_address
    ON contacts(channel, address);

CREATE TABLE IF NOT EXISTS threads (
    id TEXT PRIMARY KEY,
    topic TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    contact_id TEXT,
    direction TEXT NOT NULL,
    content TEXT NOT NULL,
    event_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(thread_id) REFERENCES threads(id),
    FOREIGN KEY(contact_id) REFERENCES contacts(id),
    FOREIGN KEY(event_id) REFERENCES events(id)
);

CREATE TABLE IF NOT EXISTS skills (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_skills_name ON skills(name);

CREATE TABLE IF NOT EXISTS skill_versions (
    id TEXT PRIMARY KEY,
    skill_id TEXT NOT NULL,
    version TEXT NOT NULL,
    entrypoint TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(skill_id) REFERENCES skills(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_skill_versions_skill_version
    ON skill_versions(skill_id, version);

CREATE TABLE IF NOT EXISTS skill_runs (
    id TEXT PRIMARY KEY,
    skill_version_id TEXT NOT NULL,
    event_id TEXT,
    status TEXT NOT NULL,
    input_json TEXT NOT NULL,
    output_json TEXT,
    stdout TEXT,
    stderr TEXT,
    error TEXT,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    FOREIGN KEY(skill_version_id) REFERENCES skill_versions(id),
    FOREIGN KEY(event_id) REFERENCES events(id)
);

CREATE TABLE IF NOT EXISTS auth_accounts (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    provider_account_id TEXT NOT NULL,
    email TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_auth_accounts_provider_account
    ON auth_accounts(provider, provider_account_id);

CREATE TABLE IF NOT EXISTS oauth_tokens (
    id TEXT PRIMARY KEY,
    auth_account_id TEXT NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    expires_at TEXT,
    scope TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(auth_account_id) REFERENCES auth_accounts(id)
);

CREATE TABLE IF NOT EXISTS memory_references (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    memory_id TEXT NOT NULL,
    snippet TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(event_id) REFERENCES events(id)
);

CREATE INDEX IF NOT EXISTS idx_memory_references_event_id
    ON memory_references(event_id);
