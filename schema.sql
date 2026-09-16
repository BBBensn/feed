-- feed.bensn.me — journal_entries schema
-- Lives in the shared `bensnos` Postgres DB (same instance feed-api already connects to
-- for the `shares` table). Native replacement for Obsidian-authored journal notes — see
-- CLAUDE.md for the phased rollout (mood first, other 8 types + historical backfill later).

CREATE TABLE journal_entries (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entry_type      VARCHAR(20) NOT NULL CHECK (entry_type IN
                        ('diary','mood','reflexion','symptome','therapie',
                         'fits','arbeit','ideas','project_log')),
    entry_date      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    title           TEXT,
    body            TEXT,
    tags            TEXT[] DEFAULT '{}',
    fields          JSONB DEFAULT '{}',       -- type-specific structured data, see CLAUDE.md
    images          TEXT[] DEFAULT '{}',
    deleted         BOOLEAN DEFAULT FALSE,
    migrated_from   VARCHAR(30),               -- 'obsidian' | 'apple_journal' | NULL (native)
    source          VARCHAR(20) DEFAULT 'web',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_journal_entries_date ON journal_entries(entry_date DESC);
CREATE INDEX idx_journal_entries_type ON journal_entries(entry_type);
CREATE INDEX idx_journal_entries_tags ON journal_entries USING GIN(tags);
CREATE INDEX idx_journal_entries_fields ON journal_entries USING GIN(fields);
