-- Feed v1.7.0 — Share-Links System
-- Ausführen: docker exec bensn-postgres psql -U bensn -d bensnos -f /tmp/add_shares_table.sql

CREATE TABLE IF NOT EXISTS shares (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  token             TEXT UNIQUE NOT NULL DEFAULT encode(gen_random_bytes(24), 'base64url'),
  label             TEXT NOT NULL,
  allowed_types     TEXT[],       -- null = alle Typen erlaubt
  blocked_types     TEXT[],       -- null = nichts geblockt
  blocked_wikilinks TEXT[],       -- z.B. ARRAY['amelie','privat','Selbstverletzung']
  date_from         DATE,         -- null = kein Limit
  date_to           DATE,         -- null = kein Limit
  include_work      BOOLEAN NOT NULL DEFAULT true,
  active            BOOLEAN NOT NULL DEFAULT true,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
