-- Alle Share-Links löschen (DB cleanen)
-- Ausführen: docker exec bensn-postgres psql -U bensn -d bensnos -c "DELETE FROM shares;"
DELETE FROM shares;
