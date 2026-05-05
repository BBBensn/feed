-- Fix: Tokens auf URL-safe Base64 umstellen (kein +, /, =)
-- Alle bestehenden Tokens neu generieren
UPDATE shares SET token = encode(gen_random_bytes(24), 'base64');

-- Funktion für zukünftige Tokens: ersetze +, /, = durch url-safe Zeichen
-- Postgres hat kein base64url nativ, daher Trick mit translate()
ALTER TABLE shares ALTER COLUMN token SET DEFAULT 
  translate(encode(gen_random_bytes(24), 'base64'), '+/=', '-_');

-- Bestehende Tokens auch url-safe machen
UPDATE shares SET token = translate(token, '+/=', '-_');
