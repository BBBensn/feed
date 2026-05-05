-- Feed v1.7.0 — Share-Links System
-- Ausführen: docker cp /root/add_shares_table.sql bensn-postgres:/tmp/ && docker exec bensn-postgres psql -U bensn -d bensnos -f /tmp/add_shares_table.sql

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS shares (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  token             TEXT UNIQUE NOT NULL DEFAULT encode(gen_random_bytes(24), 'base64'),
  label             TEXT NOT NULL,
  allowed_types     TEXT[],
  blocked_types     TEXT[],
  blocked_wikilinks TEXT[],
  date_from         DATE,
  date_to           DATE,
  include_work      BOOLEAN NOT NULL DEFAULT true,
  active            BOOLEAN NOT NULL DEFAULT true,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
